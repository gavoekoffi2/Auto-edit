"""Planificateur de B-roll IA — orienté Afrique francophone.

À partir du `Transcript` et de l'`EditDecisionList`, choisit un sous-ensemble
de segments narratifs dignes d'être illustrés par un B-roll, et compose
pour chacun un *prompt image* contextualisé Afrique business premium.

Le module **ne génère pas** les images: il produit la liste de `BrollCue`.
La génération est faite par `ImageGenerationService` (provider abstrait).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable

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


@dataclass
class BrollPlannerConfig:
    style: str = "african_business_premium"
    aspect_ratio: str = "9:16"
    min_segment_duration: float = 2.5
    max_segment_duration: float = 8.0
    max_cues: int = 12


class BrollPlanner:
    def __init__(self, config: BrollPlannerConfig | None = None):
        self.config = config or BrollPlannerConfig()

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

        # 4. Pour chaque bloc → prompt
        cues: list[BrollCue] = []
        style_suffix = STYLE_SUFFIXES.get(cfg.style, STYLE_SUFFIXES["african_business_premium"])
        for b in blocks:
            duration = min(b.end - b.start, cfg.max_segment_duration)
            scene = _scene_from_text(b.text)
            prompt = f"{scene} {style_suffix}".strip()
            cues.append(
                BrollCue(
                    segment_start=b.start,
                    segment_end=b.start + duration,
                    prompt=prompt,
                    style=cfg.style,
                    aspect_ratio=cfg.aspect_ratio,
                    priority=3,
                )
            )
        logger.info("[broll_planner] planned %d cues", len(cues))
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
