"""Planificateur de B-roll IA — orienté Afrique francophone.

À partir du `Transcript` et de l'`EditDecisionList`, choisit un sous-ensemble
de segments narratifs dignes d'être illustrés par un B-roll, et compose
pour chacun un *prompt image* contextualisé Afrique business premium.

Le module **ne génère pas** les images: il produit la liste de `BrollCue`.
La génération est faite par `ImageGenerationService` (provider abstrait).

Il porte aussi le `BrollTypeRouter` (ÉTAPE 7): pour chaque beat, il décide
AUTOMATIQUEMENT quelle famille de B-roll raconte le mieux l'idée — image
statique, stock vidéo, vidéo IA, motion design ou **Collage Premium**. Le
routeur est une fonction pure, partagée par le pipeline V2 modulaire ET par le
moteur Auto Edit: une seule règle de décision dans tout le produit.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

from app.processing.collage.collage_types import BrollType
from app.processing.types import BrollCue, EditDecisionList, Transcript, TranscriptSegment

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Style et catalogue de scènes africaines
# ---------------------------------------------------------------------------
STYLE_SUFFIXES: dict[str, str] = {
    "african_business_premium": (
        "Premium realistic editorial photography, modern African business context, "
        "soft natural light, shallow depth of field, photorealistic, 35mm lens, "
        "color graded, magazine quality, diverse young African professionals "
        "(Togo, Benin, Ivory Coast, Senegal, Cameroon, DRC), modern offices, "
        "clean streets, contemporary urban Africa, no stereotypes, no clichés."
    ),
    "tiktok_viral": (
        "Vibrant TikTok style, dynamic, energetic, bold colors, young African creator, "
        "natural light, smartphone-friendly, vertical 9:16, eye-catching."
    ),
    "publicite_locale": (
        "Local African advertisement style, friendly, warm tones, modern African shop "
        "or service, clear product visibility, customer-focused, realistic, premium "
        "production value, recognizable francophone West/Central Africa setting."
    ),
    "podcast_propre": (
        "Clean editorial portrait, neutral background, modern African podcast studio, "
        "natural light, professional but warm."
    ),
    "formation_educative": (
        "Educational illustration, modern African teacher or trainer, clean room, "
        "engaged learners, friendly atmosphere, realistic, photographic."
    ),
}


# Mots-clés → "concept de scène" qu'on traduit en prompt visuel.
# L'ordre matter: on prend le premier match.
TOPIC_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(e[- ]?commerce|boutique en ligne|vente en ligne|shopify)\b", re.I),
     "Young African entrepreneur managing an e-commerce shop on a laptop, modern home office in Lomé, smartphone with mobile money next to the keyboard."),
    (re.compile(r"\b(mobile money|momo|orange money|wave|moov money|airtel money)\b", re.I),
     "Close-up of an African customer paying with mobile money on a smartphone in a small modern shop in Cotonou, friendly cashier smiling."),
    (re.compile(r"\b(restaurant|cuisine|chef|gastronomie)\b", re.I),
     "Modern African restaurant in Abidjan, well-dressed clients enjoying a meal, smiling chef plating a premium dish, warm ambient light."),
    (re.compile(r"\b(immobili|maison|appartement|location|airbnb)\b", re.I),
     "Modern African residential interior in Dakar, clean architecture, natural light, young African real estate agent presenting a key, contemporary furniture."),
    (re.compile(r"\b(formation|cours|enseigne|école|étudiant|étudiante|coach)\b", re.I),
     "African coach in modern coworking space giving a class to young francophone professionals, laptops open, friendly engaged audience."),
    (re.compile(r"\b(beaut[ée]|coiffure|salon|cosm[ée]tique|peau|maquillage)\b", re.I),
     "Modern African beauty salon in Yaoundé, premium interior, stylish African hairdresser working on a smiling client, soft natural light."),
    (re.compile(r"\b(transport|moto|voiture|taxi|livraison)\b", re.I),
     "Young African delivery rider in a clean uniform on a modern motorbike in a clean West-African street, smartphone in handlebar mount."),
    (re.compile(r"\b(recrut|emploi|candidat|cv|entretien)\b", re.I),
     "Job interview in a modern African corporate office, African HR manager and a young candidate, warm professional atmosphere."),
    (re.compile(r"\b(client|service|sav|support)\b", re.I),
     "African customer service representative wearing a headset in a modern call center in Abidjan, smiling, modern equipment."),
    (re.compile(r"\b(produit|marque|branding|marketing|publicit[ée])\b", re.I),
     "Premium product photography of a locally made African product on a marble counter, soft studio light, brand storytelling."),
    (re.compile(r"\b(argent|finance|budget|investissement|épargne)\b", re.I),
     "Young African entrepreneur reviewing a financial dashboard on a laptop, sticky notes, smartphone with mobile banking app, natural light."),
    (re.compile(r"\b(famille|enfant|parent|maman|papa)\b", re.I),
     "Modern African family in a bright living room, laughing together, contemporary urban Africa, warm tones."),
    (re.compile(r"\b(tiktok|réseau|réseaux|instagram|facebook|whatsapp)\b", re.I),
     "Young African creator filming themselves with a smartphone on a tripod in a modern bedroom in Lomé, ring light, vertical phone setup."),
    (re.compile(r"\b(bureau|équipe|coll[èe]gue|startup|entreprise)\b", re.I),
     "Modern African startup team in a coworking space in Dakar, diverse young francophone professionals collaborating on a laptop."),
    (re.compile(r"\b(rue|march[ée]|ville|commerce)\b", re.I),
     "Clean modern African street in Cotonou or Abidjan with small businesses, well-lit, contemporary urban Africa, no stereotypes."),
]

# Fallback scene si aucun mot-clé ne matche
FALLBACK_SCENE = (
    "Confident young African francophone entrepreneur looking at a laptop in a modern "
    "office in West Africa, premium realistic photography."
)


# ---------------------------------------------------------------------------
# ÉTAPE 7 — Routage automatique du TYPE de B-roll
#
# Chaque famille a un signal qui la trahit dans le transcript:
#   * une énumération / un pourcentage  -> motion design (compteurs, étapes)
#   * une scène physique nommée         -> image (ou stock vidéo) réaliste
#   * un mouvement décrit               -> vidéo IA (si activée)
#   * une IDÉE abstraite, une comparaison, une causalité -> collage premium
#
# Le routeur ne connaît AUCUN moteur: il renvoie un `BrollType`, l'appelant
# décide quoi en faire. C'est ce qui permet d'ajouter une famille sans toucher
# aux pipelines.
# ---------------------------------------------------------------------------
_ABSTRACT_RE = re.compile(
    r"\b(id[ée]e|concept|principe|philosophie|mentalit[ée]|[ée]tat d'esprit|"
    r"libert[ée]|temps|choix|risque|confiance|peur|doute|r[êe]ve|ambition|"
    r"[ée]chec|succ[èe]s|diff[ée]rence|probl[èe]me|solution|raison|pourquoi|"
    r"secret|v[ée]rit[ée]|erreur|le[çc]on|valeur|sens|vision|avenir|"
    r"opportunit[ée]|patience|discipline|habitude|croyance|mindset|"
    r"belief|freedom|failure|purpose|meaning|mistake|lesson|habit)\b",
    re.IGNORECASE,
)
_COMPARISON_RE = re.compile(
    r"(c'est comme|comme si|imagine|imaginez|pense à|penses à|"
    r"la m[ée]taphore|c'est un peu comme|it's like|imagine that|think of)",
    re.IGNORECASE,
)
_CAUSALITY_RE = re.compile(
    r"\b(parce que|donc|c'est pourquoi|r[ée]sultat|cons[ée]quence|"
    r"si tu|si vous|alors tu|alors vous|because|therefore|so that)\b",
    re.IGNORECASE,
)
_ENUM_RE = re.compile(
    r"\b(premi[èe]rement|deuxi[èe]mement|troisi[èe]mement|d'abord|ensuite|"
    r"enfin|[ée]tape|first|second|third|then|finally|step)\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"\b\d[\d.,]*\s*%?")
_MOTION_RE = re.compile(
    r"\b(court|courir|roule|rouler|voyage|voyager|marche|marcher|vole|voler|"
    r"danse|danser|nage|conduit|conduire|traverse|monte|descend|tombe|"
    r"running|driving|flying|walking|dancing|travelling)\b",
    re.IGNORECASE,
)
_AMBIANCE_RE = re.compile(
    r"\b(ville|rue|march[ée]|bureau|plage|campagne|coucher de soleil|foule|"
    r"quartier|paysage|city|street|office|beach|crowd|skyline)\b",
    re.IGNORECASE,
)


@dataclass
class BrollRoutingDecision:
    """Décision motivée du routeur — traçable dans le rapport de job."""

    broll_type: BrollType
    score: float
    scores: dict[str, float] = field(default_factory=dict)
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "broll_type": self.broll_type.value,
            "score": round(self.score, 3),
            "scores": {k: round(v, 3) for k, v in self.scores.items()},
            "reason": self.reason,
        }


class BrollTypeRouter:
    """Choisit automatiquement la famille de B-roll d'un beat parlé.

    Pur et déterministe: mêmes entrées, même sortie — donc testable et
    reproductible d'un rendu à l'autre.
    """

    #: Familles activables. Par défaut on n'active que ce qui EXISTE réellement
    #: dans le produit aujourd'hui (stock vidéo et vidéo IA restent des points
    #: d'extension: les activer sans moteur derrière ne créerait aucun visuel).
    DEFAULT_ENABLED = (
        BrollType.STATIC_IMAGE,
        BrollType.MOTION_DESIGN,
        BrollType.COLLAGE_PREMIUM,
    )

    def __init__(self, enabled: Optional[Sequence[BrollType]] = None,
                 collage_share: float = 0.5):
        self.enabled = tuple(enabled) if enabled else self.DEFAULT_ENABLED
        # Part maximale de beats routés vers le collage (coût + variété visuelle:
        # un montage entièrement en collage devient monotone).
        self.collage_share = max(0.0, min(1.0, collage_share))

    # ------------------------------------------------------------------
    def score(self, text: str) -> dict[BrollType, float]:
        """Score brut de chaque famille pour ce texte."""
        text = text or ""
        scores: dict[BrollType, float] = {t: 0.0 for t in self.enabled}

        abstract_hits = len(_ABSTRACT_RE.findall(text))
        concrete_scene = any(p.search(text) for p, _ in TOPIC_RULES)

        if BrollType.COLLAGE_PREMIUM in scores:
            collage = 0.9 * min(3, abstract_hits)
            if _COMPARISON_RE.search(text):
                collage += 2.4          # une comparaison EST une métaphore
            if _CAUSALITY_RE.search(text):
                collage += 0.9
            if not concrete_scene:
                collage += 0.7          # rien de filmable: il faut symboliser
            if "?" in text:
                collage += 0.4
            scores[BrollType.COLLAGE_PREMIUM] = collage

        if BrollType.MOTION_DESIGN in scores:
            motion = 0.0
            if _ENUM_RE.search(text) or text.count(",") >= 3:
                motion += 2.6
            if _NUMBER_RE.search(text):
                motion += 2.0
            scores[BrollType.MOTION_DESIGN] = motion

        if BrollType.STATIC_IMAGE in scores:
            static = 1.0 if concrete_scene else 0.25   # défaut sûr du produit
            if _AMBIANCE_RE.search(text):
                static += 0.6
            scores[BrollType.STATIC_IMAGE] = static

        if BrollType.STOCK_VIDEO in scores:
            scores[BrollType.STOCK_VIDEO] = (
                1.6 if (_AMBIANCE_RE.search(text) and not abstract_hits) else 0.0)

        if BrollType.AI_VIDEO in scores:
            scores[BrollType.AI_VIDEO] = 2.0 if _MOTION_RE.search(text) else 0.0

        return scores

    # ------------------------------------------------------------------
    def choose(self, text: str) -> BrollRoutingDecision:
        scores = self.score(text)
        best = max(scores, key=lambda t: (scores[t], -_PRIORITY.index(t)))
        return BrollRoutingDecision(
            broll_type=best,
            score=scores[best],
            scores={t.value: v for t, v in scores.items()},
            reason=_REASONS.get(best, ""),
        )

    # ------------------------------------------------------------------
    def route_many(self, texts: Sequence[str]) -> list[BrollRoutingDecision]:
        """Route une vidéo entière en respectant le quota de collage.

        Le quota est appliqué APRÈS le scoring, sur les beats les mieux notés:
        on garde les métaphores les plus évidentes et on renvoie les autres
        vers l'image statique. C'est le garde-fou coût ET variété.
        """
        decisions = [self.choose(t) for t in texts]
        collage_idx = [i for i, d in enumerate(decisions)
                       if d.broll_type is BrollType.COLLAGE_PREMIUM]
        budget = int(len(decisions) * self.collage_share)
        if len(collage_idx) > max(1, budget):
            keep = set(sorted(collage_idx, key=lambda i: decisions[i].score,
                              reverse=True)[: max(1, budget)])
            for i in collage_idx:
                if i in keep:
                    continue
                fallback = BrollType.STATIC_IMAGE
                decisions[i] = BrollRoutingDecision(
                    broll_type=fallback,
                    score=decisions[i].scores.get(fallback.value, 0.0),
                    scores=decisions[i].scores,
                    reason="collage_budget_exhausted",
                )
        return decisions


#: Ordre de préférence en cas d'égalité parfaite (le plus sûr d'abord).
_PRIORITY = [
    BrollType.STATIC_IMAGE,
    BrollType.MOTION_DESIGN,
    BrollType.COLLAGE_PREMIUM,
    BrollType.STOCK_VIDEO,
    BrollType.AI_VIDEO,
]

_REASONS = {
    BrollType.COLLAGE_PREMIUM: "idée abstraite / comparaison → métaphore visuelle",
    BrollType.MOTION_DESIGN: "énumération ou chiffre → carte animée",
    BrollType.STATIC_IMAGE: "scène concrète → photo générée + Ken Burns",
    BrollType.STOCK_VIDEO: "ambiance filmable → rush de banque",
    BrollType.AI_VIDEO: "mouvement décrit → vidéo générative",
}


@dataclass
class BrollPlannerConfig:
    style: str = "african_business_premium"
    aspect_ratio: str = "9:16"
    min_segment_duration: float = 2.5
    max_segment_duration: float = 8.0
    max_cues: int = 12
    # Routage automatique du type de B-roll (ÉTAPE 7). Désactivable pour
    # retrouver à l'octet près le comportement historique du planificateur.
    auto_broll_type: bool = True
    enabled_broll_types: tuple[BrollType, ...] | None = None
    collage_share: float = 0.5


class BrollPlanner:
    def __init__(self, config: BrollPlannerConfig | None = None,
                 router: BrollTypeRouter | None = None):
        self.config = config or BrollPlannerConfig()
        self.router = router or BrollTypeRouter(
            enabled=self.config.enabled_broll_types,
            collage_share=self.config.collage_share,
        )

    # ------------------------------------------------------------------
    def plan(self, transcript: Transcript, edl: EditDecisionList) -> list[BrollCue]:
        cfg = self.config
        if not transcript.segments:
            return []

        # 1. Récupère les segments du transcript qui tombent dans des cuts gardés
        kept = edl.kept_cuts()

        def in_kept(start: float, end: float) -> bool:
            if not kept:
                return True
            for c in kept:
                if start >= c.source_start and end <= c.source_end:
                    return True
            return False

        # 2. Regroupe les segments en blocs narratifs adjacents (durée min/max)
        blocks: list[TranscriptSegment] = []
        buffer: list[TranscriptSegment] = []
        buf_start: float | None = None

        for seg in transcript.segments:
            if not in_kept(seg.start, seg.end):
                continue
            if buf_start is None:
                buf_start = seg.start
            buffer.append(seg)
            current_dur = seg.end - buf_start
            if current_dur >= cfg.min_segment_duration:
                blocks.append(_merge_segments(buffer))
                buffer = []
                buf_start = None

        if buffer:
            blocks.append(_merge_segments(buffer))

        # 3. Garde les blocs assez longs et limite à max_cues
        blocks = [b for b in blocks if (b.end - b.start) >= cfg.min_segment_duration]
        if len(blocks) > cfg.max_cues:
            # On garde les `max_cues` plus longs
            blocks = sorted(blocks, key=lambda s: (s.end - s.start), reverse=True)[: cfg.max_cues]
            blocks.sort(key=lambda s: s.start)

        # 4. Routage automatique du TYPE de B-roll (ÉTAPE 7)
        decisions = (
            self.router.route_many([b.text for b in blocks])
            if cfg.auto_broll_type else
            [BrollRoutingDecision(BrollType.STATIC_IMAGE, 0.0, {}, "auto_routing_off")
             for _ in blocks]
        )

        # 5. Pour chaque bloc → prompt
        cues: list[BrollCue] = []
        style_suffix = STYLE_SUFFIXES.get(cfg.style, STYLE_SUFFIXES["african_business_premium"])
        for b, decision in zip(blocks, decisions):
            duration = min(b.end - b.start, cfg.max_segment_duration)
            scene = _scene_from_text(b.text)
            excerpt = _safe_excerpt(b.text)
            prompt = (
                f"{scene} Must directly illustrate this exact spoken excerpt: \"{excerpt}\". "
                f"Avoid generic stock imagery; every person, object and action should match the narration. "
                f"{style_suffix}"
            ).strip()
            cues.append(
                BrollCue(
                    segment_start=b.start,
                    segment_end=b.start + duration,
                    prompt=prompt,
                    style=cfg.style,
                    aspect_ratio=cfg.aspect_ratio,
                    priority=3,
                    broll_type=decision.broll_type.value,
                    excerpt=excerpt,
                )
            )
        by_type: dict[str, int] = {}
        for c in cues:
            by_type[c.broll_type] = by_type.get(c.broll_type, 0) + 1
        logger.info("[broll_planner] planned %d cues %s", len(cues), by_type)
        return cues


# ---------------------------------------------------------------------------
def _merge_segments(segments: list[TranscriptSegment]) -> TranscriptSegment:
    start = segments[0].start
    end = segments[-1].end
    text = " ".join(s.text for s in segments).strip()
    return TranscriptSegment(start=start, end=end, text=text, words=[])


def _scene_from_text(text: str) -> str:
    for pattern, scene in TOPIC_RULES:
        if pattern.search(text):
            return scene
    return FALLBACK_SCENE


def _safe_excerpt(text: str, max_chars: int = 190) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "…"
