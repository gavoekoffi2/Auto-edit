"""ÉTAPE 2 — `CollageConceptPlanner`: comprendre la phrase avant de dessiner.

À partir d'un segment de transcript, ce module produit un JSON structuré:

    {
      "meaning":  "ce que la phrase veut dire, en une ligne",
      "emotion":  "urgency | hope | warning | pride | curiosity | trust | ...",
      "metaphor": "la meilleure métaphore visuelle pour cette idée",
      "objects":  [{ "name": ..., "order": 1, "note": ... }, ...],   # 3 à 6
      "palette":  ["#E8452C", "#F7F1E3", "#1D1D1B"],
      "sequence": ["objet 1", "objet 2", ...]                        # ordre d'apparition
    }

Deux chemins, jamais bloquants:

  1. **LLM** (défaut quand une clé OpenRouter existe) — UN SEUL appel HTTP pour
     TOUS les beats de la vidéo. Le workflow de référence interroge le modèle
     ligne par ligne et demande une validation humaine; ici on batche et on
     valide par contrat (schéma + bornes), ce qui divise le coût par N et rend
     l'étape 100 % automatique.
  2. **Heuristique** — bibliothèque de métaphores indexée sur les concepts déjà
     détectés par le moteur (`autoedit_engine.content.icon_for_text`). Aucune
     duplication de règles: on réutilise les ICON_RULES existantes.

Le résultat de l'étape 1 est mis en cache par empreinte du texte: deux vidéos
qui disent la même chose ne repaient pas l'analyse.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import replace
from typing import Iterable, Optional, Sequence

import httpx

from . import collage_config as ccfg
from . import collage_lexicon, collage_profiles
from .collage_cache import JsonCache, make_key
from .collage_types import (
    CollageConcept,
    CollageObject,
    Emotion,
    layout_for,
)

logger = logging.getLogger(__name__)

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"

_MAX_EXCERPT = 220


# --------------------------------------------------------------------------- #
# Bibliothèques de métaphores et consignes LLM
#
# Elles vivent désormais dans `collage_profiles`: c'est ce qui différencie les
# moteurs (éditorial vs UGC produit) sans dupliquer une ligne de pipeline. Les
# alias ci-dessous gardent l'ancien vocabulaire d'import du module.
# --------------------------------------------------------------------------- #
METAPHOR_LIBRARY = collage_profiles.EDITORIAL_LIBRARY
DEFAULT_METAPHOR = collage_profiles.EDITORIAL_DEFAULT

#: Émotion déduite du texte quand le LLM n'est pas là. Ordre = priorité.
_EMOTION_RULES: list[tuple[re.Pattern[str], Emotion]] = [
    (re.compile(r"\b(attention|danger|erreur|pi[eè]ge|risque|arnaque|perdre|"
                r"warning|scam|mistake)\b", re.I), Emotion.WARNING),
    (re.compile(r"\b(vite|urgent|maintenant|imm[ée]diat|dernier|aujourd'hui|"
                r"tout de suite|now|hurry)\b", re.I), Emotion.URGENCY),
    (re.compile(r"\b(fier|r[ée]ussi|victoire|champion|meilleur|record|bravo|"
                r"success|proud)\b", re.I), Emotion.PRIDE),
    (re.compile(r"\b(confiance|s[ée]curit[ée]|garantie|fiable|prot[ée]g|"
                r"trust|secure|safe)\b", re.I), Emotion.TRUST),
    (re.compile(r"\b(gal[èe]re|difficile|bloqu|frustr|marre|compliqu|"
                r"stuck|hard)\b", re.I), Emotion.FRUSTRATION),
    (re.compile(r"\b(pourquoi|comment|imagine|secret|d[ée]couvr|savais|"
                r"why|how|discover)\b", re.I), Emotion.CURIOSITY),
    (re.compile(r"\b(peux|possible|opportunit|avenir|r[êe]ve|objectif|"
                r"can|future|dream|goal)\b", re.I), Emotion.HOPE),
]

#: Chaque émotion pousse vers une famille de papier coloré (identité cohérente).
_EMOTION_PALETTE_INDEX: dict[Emotion, int] = {
    Emotion.URGENCY: 0,       # rouge
    Emotion.WARNING: 5,       # noir profond
    Emotion.HOPE: 1,          # vert
    Emotion.PRIDE: 2,         # jaune
    Emotion.TRUST: 3,         # bleu
    Emotion.CURIOSITY: 4,     # rose
    Emotion.FRUSTRATION: 5,
    Emotion.NEUTRAL: 1,
}


# --------------------------------------------------------------------------- #
def chat_completion(prompt: str, *, model: str, api_key: str,
                    timeout_s: int = 60) -> str:
    """Appel texte OpenRouter minimal. Lève en cas d'échec (l'appelant retombe)."""
    with httpx.Client(timeout=timeout_s) as client:
        resp = client.post(
            OPENROUTER_CHAT_URL,
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}]},
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"planner LLM HTTP {resp.status_code}")
    data = resp.json() or {}
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("planner LLM: réponse sans choix")
    return (choices[0].get("message") or {}).get("content") or ""


class CollageConceptPlanner:
    """Transcript → concepts de collage structurés (JSON)."""

    def __init__(self, api_key: Optional[str] = None,
                 model: Optional[str] = None,
                 use_llm: Optional[bool] = None,
                 cache: Optional[JsonCache] = None,
                 profile: Optional[collage_profiles.CollageProfile] = None):
        self.api_key = api_key if api_key is not None else os.environ.get("OPENROUTER_API_KEY", "")
        self.model = model or ccfg.PLANNER_MODEL
        self.profile = profile or collage_profiles.get(ccfg.PROFILE)
        use_llm = ccfg.PLANNER_ENABLED if use_llm is None else bool(use_llm)
        self.use_llm = bool(use_llm and self.profile.allow_planner_llm)
        self.cache = cache if cache is not None else JsonCache("concepts")

    # ------------------------------------------------------------------ #
    def plan(self, beats: Sequence[dict]) -> list[CollageConcept]:
        """*beats*: [{id, source_start, source_end, text}] → concepts validés.

        Ne lève jamais: un beat qui échoue côté LLM repart en heuristique.
        """
        prepared = [b for b in (self._prepare(b, i) for i, b in enumerate(beats)) if b]
        if not prepared:
            return []

        # 1) Cache: on ne repaie jamais l'analyse d'un texte déjà vu.
        pending: list[dict] = []
        concepts: dict[str, CollageConcept] = {}
        for beat in prepared:
            cached = self.cache.get(beat["cache_key"])
            if cached:
                concept = self._concept_from_payload(cached, beat, planner="cache")
                if concept:
                    concepts[beat["id"]] = concept
                    continue
            pending.append(beat)

        # 2) Un SEUL appel LLM pour tout ce qui reste.
        if pending and self.use_llm and self.api_key:
            for beat, payload in zip(pending, self._llm_batch(pending)):
                if not payload:
                    continue
                concept = self._concept_from_payload(payload, beat, planner="llm")
                if concept:
                    concepts[beat["id"]] = concept
                    self.cache.set(beat["cache_key"], payload)

        # 3) Repli heuristique pour les beats non couverts.
        for beat in prepared:
            if beat["id"] not in concepts:
                concepts[beat["id"]] = self._heuristic_concept(beat)

        # 4) ANCRAGE: la scène doit montrer ce que la phrase nomme, pas ce que
        #    sa catégorie suggère. Cette passe s'applique aux TROIS chemins
        #    (cache, LLM, heuristique) — sinon la précision dépendrait de la
        #    présence d'une clé API.
        out = [self._anchor_to_speech(concepts[b["id"]], b["text"])
               for b in prepared if b["id"] in concepts]
        n_llm = sum(1 for c in out if c.planner == "llm")
        logger.info("[collage_planner] %d concept(s) — %d LLM, %d cache/heuristique",
                    len(out), n_llm, len(out) - n_llm)
        return out

    # ------------------------------------------------------------------ #
    def _anchor_to_speech(self, concept: CollageConcept,
                          text: str) -> CollageConcept:
        """Réécrit les objets du concept pour qu'ils collent au texte prononcé.

        Deux corrections, dans cet ordre:

        1. **Le sujet passe devant.** Les choses concrètes réellement nommées
           dans l'extrait ouvrent la scène. Une phrase sur une voiture commence
           par une voiture, quelle que soit l'intention détectée derrière.
        2. **Aucun objet indessinable ne survit** quand le profil illustre par
           découpes vectorielles (moteurs UGC). Avant, un objet inconnu du
           vocabulaire était rendu par une forme tirée au hasard du nom: stable
           d'un rendu à l'autre, mais sans rapport avec le propos. Il est
           désormais remplacé par une chose réellement dite, ou retiré.

        Le profil éditorial garde ses objets abstraits: c'est un modèle d'image
        qui les dessine, il n'est pas limité au vocabulaire des découpes.
        """
        if not ccfg.GROUNDING_ENABLED:
            return concept

        drawable_only = not self.profile.allow_ai_images
        anchors = max(0, ccfg.GROUNDED_OBJECTS_MAX)
        entities = collage_lexicon.ground(text, limit=ccfg.MAX_OBJECTS)

        names: list[str] = []
        covered: set[str] = set()

        def push(name: str, pictogram: Optional[str]) -> None:
            name = (name or "").strip()
            key = pictogram or name.lower()
            if not name or key in covered or len(names) >= ccfg.MAX_OBJECTS:
                return
            covered.add(key)
            names.append(name)

        for entity in entities[:anchors]:
            push(entity.noun, entity.pictogram)

        spare = list(entities[anchors:])
        for obj in concept.ordered_objects():
            pictogram = collage_lexicon.resolve(obj.name)
            if pictogram is None and drawable_only:
                if spare:
                    substitute = spare.pop(0)
                    push(substitute.noun, substitute.pictogram)
                continue
            push(obj.name, pictogram)

        # Plancher: une scène de collage a besoin d'un minimum de pièces pour
        # que l'assemblage raconte quelque chose.
        for substitute in spare:
            if len(names) >= ccfg.MIN_OBJECTS:
                break
            push(substitute.noun, substitute.pictogram)
        if len(names) < ccfg.MIN_OBJECTS:
            for name in self.profile.default_metaphor[1]:
                push(name, collage_lexicon.resolve(name))

        if names == [obj.name for obj in concept.ordered_objects()]:
            return concept
        return replace(concept,
                       objects=_build_objects(names, concept.palette, concept.id))

    # ------------------------------------------------------------------ #
    def _prepare(self, beat: dict, index: int) -> Optional[dict]:
        text = re.sub(r"\s+", " ", str(beat.get("text") or beat.get("excerpt") or "")).strip()
        if len(text) < 12:
            return None
        excerpt = text[: _MAX_EXCERPT - 1].rstrip() + "…" if len(text) > _MAX_EXCERPT else text
        return {
            "id": str(beat.get("id") or f"cg_{index:03d}"),
            "source_start": float(beat.get("source_start") or 0.0),
            "source_end": float(beat.get("source_end") or 0.0),
            "text": text,
            "excerpt": excerpt,
            # Le PROFIL entre dans la clé: la même phrase ne doit pas resservir
            # un concept éditorial abstrait à un montage UGC produit (et
            # inversement) sous prétexte qu'elle a déjà été analysée.
            "cache_key": make_key("concept", ccfg.STYLE_LOCK_VERSION,
                                  self.profile.id, excerpt.lower()),
        }

    # ------------------------------------------------------------------ #
    def _llm_batch(self, beats: Sequence[dict]) -> list[Optional[dict]]:
        """Un appel, N concepts. Renvoie une liste alignée sur *beats*."""
        items = "\n".join(f'{i + 1}. "{b["excerpt"]}"' for i, b in enumerate(beats))
        # Le vocabulaire dessinable est injecté dans la consigne: un modèle qui
        # ne le connaît pas propose « steering wheel » ou « supply chain », des
        # objets qui n'existent en découpe nulle part et finissent remplacés.
        prompt = (self.profile.llm_instruction
                  .replace("{n}", str(len(beats)))
                  .replace("{vocabulary}", collage_lexicon.vocabulary_hint(90))
                  .replace("{items}", items))
        try:
            text = chat_completion(prompt, model=self.model, api_key=self.api_key,
                                   timeout_s=ccfg.PLANNER_TIMEOUT_S)
            payloads = _extract_json_array(text)
            if len(payloads) != len(beats):
                raise RuntimeError(
                    f"planner: {len(payloads)} concepts pour {len(beats)} extraits")
            return [p if isinstance(p, dict) else None for p in payloads]
        except Exception as exc:  # noqa: BLE001 - l'heuristique prend le relais
            logger.warning("[collage_planner] LLM ignoré (%s: %s) — repli heuristique",
                           type(exc).__name__, str(exc)[:160])
            return [None] * len(beats)

    # ------------------------------------------------------------------ #
    def _concept_from_payload(self, payload: dict, beat: dict,
                              planner: str) -> Optional[CollageConcept]:
        """Valide + normalise la réponse du modèle. None si inexploitable."""
        raw_objects = payload.get("objects")
        if not isinstance(raw_objects, list):
            return None
        names: list[str] = []
        for item in raw_objects:
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
            else:
                name = str(item or "").strip()
            # Un « objet » qui contient un chiffre ou des guillemets sent le
            # texte déguisé — le style interdit toute typographie.
            if not name or len(name) > 48 or re.search(r"[0-9\"“”]", name):
                continue
            if name.lower() in {n.lower() for n in names}:
                continue
            names.append(name)
        if len(names) < ccfg.MIN_OBJECTS:
            return None
        names = names[: ccfg.MAX_OBJECTS]

        metaphor = str(payload.get("metaphor") or "").strip()
        if len(metaphor) < 8:
            return None

        emotion = Emotion.parse(payload.get("emotion"))
        palette, background = _resolve_palette(payload, emotion, beat["excerpt"])
        concept = CollageConcept(
            id=beat["id"],
            source_start=beat["source_start"],
            source_end=beat["source_end"],
            excerpt=beat["excerpt"],
            meaning=str(payload.get("meaning") or "").strip()[:240],
            emotion=emotion,
            metaphor=metaphor[:240],
            objects=_build_objects(names, palette, beat["id"]),
            background_color=background,
            palette=palette,
            label=_normalize_label(payload.get("label"), beat["text"]),
            planner=planner,
            confidence=0.9 if planner == "llm" else 0.75,
        )
        return concept

    # ------------------------------------------------------------------ #
    def _heuristic_concept(self, beat: dict) -> CollageConcept:
        """Concept déterministe: métaphore du PROFIL + palette seedée.

        Chemin critique des moteurs UGC: sans clé API, c'est lui qui décide de
        tout ce qui sera illustré. Il commence donc par chercher une intention
        PRODUIT dans le texte (prix, livraison, avis…), et ne retombe sur le
        vocabulaire d'icônes du moteur que si rien ne se déclenche.
        """
        profile = self.profile
        key = profile.intent_for(beat["text"])
        if key is None:
            icon = _icon_for(beat["text"])
            # Les profils UGC traduisent l'icône en intention produit; le profil
            # éditorial est indexé directement sur les icônes.
            key = (collage_profiles.UGC_ICON_FALLBACK.get(icon, "product")
                   if profile.intent_rules else icon)
        metaphor, names, default_emotion = profile.metaphor_for(key)
        emotion = _emotion_for(beat["text"]) or default_emotion
        palette, background = _resolve_palette({}, emotion, beat["excerpt"])
        return CollageConcept(
            id=beat["id"],
            source_start=beat["source_start"],
            source_end=beat["source_end"],
            excerpt=beat["excerpt"],
            meaning=beat["excerpt"][:240],
            emotion=emotion,
            metaphor=metaphor,
            objects=_build_objects(list(names)[: ccfg.MAX_OBJECTS], palette,
                                   beat["id"]),
            background_color=background,
            palette=palette,
            label=_normalize_label(None, beat["text"]),
            planner="heuristic",
            confidence=0.55,
        )


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _icon_for(text: str) -> str:
    """Concept dominant du texte — réutilise les règles du moteur Auto Edit."""
    try:
        from app.autoedit_engine.content import icon_for_text
        return icon_for_text(text)
    except Exception:  # noqa: BLE001 - moteur indisponible (tests isolés)
        return "idea"


def _emotion_for(text: str) -> Optional[Emotion]:
    for pattern, emotion in _EMOTION_RULES:
        if pattern.search(text):
            return emotion
    return None


def _resolve_palette(payload: dict, emotion: Emotion,
                     seed_text: str) -> tuple[list[str], str]:
    """Palette finale (fond + papiers). Le modèle propose, le style dispose."""
    from .collage_types import _normalize_hex

    raw = payload.get("palette") if isinstance(payload.get("palette"), list) else []
    papers = [_normalize_hex(c, "") for c in raw]
    papers = [c for c in papers if c]

    fallback = ccfg.FALLBACK_PALETTES[
        _EMOTION_PALETTE_INDEX.get(emotion, 0) % len(ccfg.FALLBACK_PALETTES)
    ]
    background = _normalize_hex(payload.get("background_color"), "") or fallback["background"]
    if not papers:
        papers = list(fallback["papers"])
    # Le crème de contour fait partie du verrou de style: il est toujours là.
    if "#F7F1E3" not in papers:
        papers.append("#F7F1E3")
    return papers[:5], background


def _build_objects(names: Sequence[str], palette: Sequence[str],
                   seed: object = None) -> list[CollageObject]:
    """Attribue layout, entrée et papier à chaque objet (ordre = narration).

    *seed* (l'id du beat) doit être le MÊME que celui utilisé par
    `CollageConcept.layout()`, sinon les ancrages écrits ici ne correspondraient
    plus aux zones réellement animées.
    """
    cells = layout_for(len(names), seed)
    entrances = ("drop", "slide_left", "scale_pop", "slide_right", "rise", "rotate_in")
    papers = [c for c in palette if c] or ["#F7F1E3"]
    objects: list[CollageObject] = []
    for i, name in enumerate(names[: len(cells)]):
        anchor = cells[i][0]
        objects.append(CollageObject(
            name=name,
            order=i + 1,
            anchor=anchor,
            entrance=entrances[i % len(entrances)],
            paper_color=papers[i % len(papers)],
        ))
    return objects


def _normalize_label(raw: object, fallback_text: str) -> str:
    """Mot-clé court en majuscules — jamais rendu DANS l'image, seulement en
    métadonnée (chip de la timeline / debug)."""
    label = re.sub(r"[^A-Za-zÀ-ÿ' -]", "", str(raw or "")).strip()
    if 2 <= len(label) <= 14:
        return label.upper()
    try:
        from app.autoedit_engine.content import _content_tokens
        tokens = _content_tokens(fallback_text)
    except Exception:  # noqa: BLE001
        tokens = [t for t in re.findall(r"[A-Za-zÀ-ÿ]{4,}", fallback_text)]
    return (tokens[0][:14].upper() if tokens else "IDÉE")


def _extract_json_array(text: str) -> list:
    """Extrait le premier tableau JSON d'une réponse de modèle (tolère le ```)."""
    if not text:
        return []
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        parsed = json.loads(text[start:end + 1])
    except ValueError:
        return []
    return parsed if isinstance(parsed, list) else []


def beats_from_ideas(ideas: Iterable[dict]) -> list[dict]:
    """Adapte les « ideas » du moteur Auto Edit au contrat d'entrée du planner.

    Évite toute duplication de la détection de beats: le moteur sait déjà
    découper le discours en fenêtres illustrables (`content.derive_broll_ideas`),
    on se contente d'en reprendre le texte et les bornes.
    """
    beats: list[dict] = []
    for i, idea in enumerate(ideas or []):
        text = idea.get("excerpt") or idea.get("text") or idea.get("prompt") or ""
        beats.append({
            "id": str(idea.get("id") or f"cg_{i:03d}"),
            "source_start": float(idea.get("source_start") or 0.0),
            "source_end": float(idea.get("source_end") or 0.0),
            "text": text,
        })
    return beats
