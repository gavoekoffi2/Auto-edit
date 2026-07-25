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
from typing import Iterable, Optional, Sequence

import httpx

from . import collage_config as ccfg
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
# Bibliothèque de métaphores — repli déterministe (aucun appel réseau)
#
# Clé = identifiant d'icône produit par `content.icon_for_text` (déjà utilisé
# par le motion design). Valeur = (métaphore, objets, émotion par défaut).
# --------------------------------------------------------------------------- #
METAPHOR_LIBRARY: dict[str, tuple[str, list[str], Emotion]] = {
    "money": ("value flowing from one hand to another",
              ["open hand", "folded banknote", "coin stack", "arrow"], Emotion.TRUST),
    "growth": ("a small seed becoming a rising staircase",
               ["seed", "sprout", "rising bar", "upward arrow"], Emotion.HOPE),
    "transfer": ("a bridge carrying a parcel across a gap",
                 ["hand with phone", "bridge", "parcel", "receiving hand"], Emotion.TRUST),
    "crypto": ("a locked block joining an endless chain",
               ["chain link", "padlock", "coin", "network node"], Emotion.CURIOSITY),
    "bank": ("two currencies balancing on a scale",
             ["balance scale", "banknote", "coin", "arrow"], Emotion.TRUST),
    "card": ("a card unlocking a closed shutter",
             ["bank card", "shutter", "key", "open door"], Emotion.TRUST),
    "check": ("a key finally matching its lock",
              ["key", "padlock", "check mark", "shield"], Emotion.TRUST),
    "warning": ("a crack spreading across a smooth surface",
                ["cracked plate", "warning triangle", "falling piece"], Emotion.WARNING),
    "phone": ("a hand holding a window onto the world",
              ["hand", "phone screen", "signal waves", "small globe"], Emotion.CURIOSITY),
    "people": ("separate silhouettes converging into one circle",
               ["silhouette", "second silhouette", "circle", "handshake"], Emotion.PRIDE),
    "cart": ("a shelf emptying into a customer's basket",
             ["shelf", "product box", "basket", "arrow"], Emotion.HOPE),
    "idea": ("a struck match lighting a dark room",
             ["match", "flame", "light beam", "open book"], Emotion.CURIOSITY),
    "target": ("an arrow finding the exact centre",
               ["bow", "arrow", "target rings", "flag"], Emotion.PRIDE),
    "gear": ("loose gears clicking into one mechanism",
             ["gear", "second gear", "belt", "lever"], Emotion.NEUTRAL),
    "book": ("a closed book opening into a staircase",
             ["closed book", "open book", "staircase", "graduation cap"], Emotion.HOPE),
    "megaphone": ("one voice multiplying into many ears",
                  ["megaphone", "sound waves", "ear", "crowd silhouette"], Emotion.URGENCY),
    "shield": ("a shield absorbing an incoming arrow",
               ["shield", "incoming arrow", "padlock", "safe hands"], Emotion.TRUST),
    "clock": ("sand running out of an hourglass",
              ["hourglass", "falling sand", "clock face", "hand"], Emotion.URGENCY),
    "rocket": ("a rocket leaving its launch pad",
               ["rocket", "launch pad", "smoke plume", "star"], Emotion.HOPE),
    "map": ("a pin dropping onto a folded map",
            ["folded map", "location pin", "route line", "parcel"], Emotion.NEUTRAL),
    "chart": ("scattered dots aligning into a rising line",
              ["scattered dots", "rising line", "axis", "magnifier"], Emotion.CURIOSITY),
    "star": ("one shape lifted above a row of identical shapes",
             ["row of squares", "lifted star", "pedestal", "sparkle"], Emotion.PRIDE),
    "heart": ("two hands protecting a small flame",
              ["hand", "second hand", "flame", "heart"], Emotion.HOPE),
    "globe": ("threads stitching distant points together",
              ["globe", "thread", "pin", "envelope"], Emotion.CURIOSITY),
    "chat": ("two speech bubbles overlapping into one",
             ["speech bubble", "second bubble", "overlap shape", "pen"], Emotion.NEUTRAL),
    "lock": ("a padlock closing over a folder",
             ["folder", "padlock", "key", "shield"], Emotion.TRUST),
    "handshake": ("two hands meeting over a signed sheet",
                  ["hand", "second hand", "signed sheet", "seal"], Emotion.TRUST),
    "calendar": ("a single date circled on a wall of days",
                 ["calendar grid", "circled date", "pen", "clock"], Emotion.URGENCY),
}

DEFAULT_METAPHOR = ("a closed door opening onto a bright path",
                    ["closed door", "turning key", "open path", "silhouette"],
                    Emotion.CURIOSITY)

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


_LLM_INSTRUCTION = (
    "Tu es directeur artistique d'un studio de motion design éditorial. "
    "Pour CHAQUE extrait parlé ci-dessous, conçois UNE scène de collage papier "
    "qui raconte visuellement l'idée (jamais une illustration littérale de mots).\n"
    "Contraintes strictes:\n"
    "- 3 à 6 objets MAXIMUM, tous concrets et découpables en papier;\n"
    "- aucun objet ne doit être du texte, un logo, un chiffre ou une lettre;\n"
    "- la métaphore doit être compréhensible en 2 secondes, sans légende;\n"
    "- l'ordre des objets = ordre d'apparition qui construit le sens "
    "(le sujet d'abord, la conséquence en dernier);\n"
    "- couleurs = aplats de papier saturés, une couleur de fond + 2 ou 3 accents.\n"
    "Réponds UNIQUEMENT par un tableau JSON de {n} objets, dans le MÊME ORDRE, "
    "chaque objet ayant exactement ces clés:\n"
    '{"meaning": str, "emotion": "urgency|hope|warning|pride|curiosity|trust|'
    'frustration|neutral", "metaphor": str, "objects": [{"name": str, '
    '"order": int, "note": str}], "background_color": "#RRGGBB", '
    '"palette": ["#RRGGBB", ...], "label": str}\n'
    "`label` = UN mot-clé en majuscules (max 12 caractères).\n\n"
    "Extraits:\n{items}"
)


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
                 cache: Optional[JsonCache] = None):
        self.api_key = api_key if api_key is not None else os.environ.get("OPENROUTER_API_KEY", "")
        self.model = model or ccfg.PLANNER_MODEL
        self.use_llm = ccfg.PLANNER_ENABLED if use_llm is None else bool(use_llm)
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

        out = [concepts[b["id"]] for b in prepared if b["id"] in concepts]
        n_llm = sum(1 for c in out if c.planner == "llm")
        logger.info("[collage_planner] %d concept(s) — %d LLM, %d cache/heuristique",
                    len(out), n_llm, len(out) - n_llm)
        return out

    # ------------------------------------------------------------------ #
    @staticmethod
    def _prepare(beat: dict, index: int) -> Optional[dict]:
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
            "cache_key": make_key("concept", ccfg.STYLE_LOCK_VERSION, excerpt.lower()),
        }

    # ------------------------------------------------------------------ #
    def _llm_batch(self, beats: Sequence[dict]) -> list[Optional[dict]]:
        """Un appel, N concepts. Renvoie une liste alignée sur *beats*."""
        items = "\n".join(f'{i + 1}. "{b["excerpt"]}"' for i, b in enumerate(beats))
        prompt = _LLM_INSTRUCTION.replace("{n}", str(len(beats))).replace("{items}", items)
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
            objects=_build_objects(names, palette),
            background_color=background,
            palette=palette,
            label=_normalize_label(payload.get("label"), beat["text"]),
            planner=planner,
            confidence=0.9 if planner == "llm" else 0.75,
        )
        return concept

    # ------------------------------------------------------------------ #
    def _heuristic_concept(self, beat: dict) -> CollageConcept:
        """Concept déterministe: métaphore de bibliothèque + palette seedée."""
        icon = _icon_for(beat["text"])
        metaphor, names, default_emotion = METAPHOR_LIBRARY.get(icon, DEFAULT_METAPHOR)
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
            objects=_build_objects(list(names)[: ccfg.MAX_OBJECTS], palette),
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


def _build_objects(names: Sequence[str], palette: Sequence[str]) -> list[CollageObject]:
    """Attribue layout, entrée et papier à chaque objet (ordre = narration)."""
    cells = layout_for(len(names))
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
