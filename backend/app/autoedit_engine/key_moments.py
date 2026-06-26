"""
keyMomentPlanner — turn a word-level transcript into key-moment cues.

This module is the brain of the *credit-saver creator edit*: instead of relying
on generated B-roll images, it finds the moments that DESERVE a visual accent
(the hook, a number, an emotional word, a topic shift, the final CTA…) and
emits cues describing what to do there (camera flash, shutter SFX, punch zoom,
keyword pop, …).

It is intentionally pure-Python (no ffmpeg, no API, no I/O) so it is fast,
deterministic and trivially testable. Timings are in SOURCE time — the pipeline
maps them to output time via the EDL like every other visual decision.

Heuristics (RÈGLE produit):
  * first sentence / hook                         -> strong cue
  * numbers, amounts, dates, percentages          -> medium/strong cue
  * "attention / important / secret / erreur /
     gratuit / argent / résultat / opportunité /
     danger / solution / maintenant" …            -> cue
  * topic change between segments                  -> transition cue
  * CTA near the end of the video                  -> strong cue
  * a kept cut after a removed silence             -> low cue (punch)
  * never place two flashes < FLASH_MIN_GAP apart  (premium pacing, not hysteric)

Cadence target (premium, never an effect every second):
  *  < 30 s : 3-6 cues
  * 30-60 s : 5-10 cues
  * 1-3 min : 10-22 cues
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from . import config
from . import content

# Two flashes closer than this look hysterical — keep a premium rhythm.
FLASH_MIN_GAP = 2.5
# A kept cut that follows a removed silence of at least this long earns a punch.
PAUSE_CUT_MIN_GAP = 0.6

Intensity = str   # "low" | "medium" | "high"
Reason = str      # hook | keyword | number | cta | topic_shift | emotional_word | pause_cut
Effect = str      # flash | shutter_sfx | punch_zoom | light_streak | motion_card | underline | keyword_pop


# Emotional / attention words that justify a visual accent (FR + EN). These are
# the words a creator would punch-in on. Matched on de-accented, lowercased
# tokens so "résultat" and "resultat" both hit.
_EMOTIONAL_WORDS = {
    # FR
    "attention", "important", "importante", "essentiel", "essentielle",
    "secret", "secrets", "erreur", "erreurs", "gratuit", "gratuite", "argent",
    "resultat", "resultats", "opportunite", "opportunites", "danger", "dangers",
    "solution", "solutions", "maintenant", "jamais", "toujours", "incroyable",
    "enorme", "puissant", "rapidement", "urgent", "exclusif", "garanti",
    "preuve", "verite", "piege", "astuce", "secrete", "bonus", "cadeau",
    "explose", "exploser", "double", "doubler", "millionnaire", "succes",
    # EN
    "warning", "important", "secret", "mistake", "mistakes", "free", "money",
    "result", "results", "opportunity", "danger", "solution", "now", "never",
    "always", "incredible", "huge", "powerful", "urgent", "exclusive",
    "guaranteed", "proof", "truth", "hack", "bonus", "gift", "boom",
}

# Words that signal a call to action — strongest near the end of the video.
_CTA_WORDS = {
    # FR
    "abonne", "abonnez", "abonner", "abonnement", "partage", "partagez",
    "commente", "commentez", "clique", "cliquez", "lien", "bio", "inscris",
    "inscrivez", "inscription", "rejoins", "rejoignez", "decouvre", "decouvrez",
    "profite", "profitez", "contacte", "contactez", "telecharge", "telechargez",
    "reserve", "reservez", "achete", "achetez", "suis", "suivez", "swipe",
    # EN
    "subscribe", "follow", "share", "comment", "click", "link", "join",
    "discover", "download", "register", "buy", "grab", "dm", "swipe", "tap",
}

_ACCENTS = str.maketrans(
    "àáâäãåçèéêëìíîïñòóôöõùúûü", "aaaaaaceeeeiiiinooooouuuu"
)

_PERCENT_RE = re.compile(r"\d[\d.,]*\s*%|pour\s*cent|percent", re.IGNORECASE)
_MONEY_RE = re.compile(
    r"[€$]|\b(fcfa|cfa|francs?|euros?|dollars?|cedis?|nairas?|k|millions?|milliards?)\b",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"\b(20\d{2}|19\d{2}|janvier|fevrier|mars|avril|mai|juin|juillet|aout|"
    r"septembre|octobre|novembre|decembre|jour|jours|semaine|semaines|mois|"
    r"annee|annees|an|ans|heure|heures|minute|minutes)\b",
    re.IGNORECASE,
)
_NUM_RE = re.compile(r"\d")


def _norm(token: str) -> str:
    return token.lower().translate(_ACCENTS)


@dataclass
class KeyMomentCue:
    """A single key moment + the visual/audio accents it should trigger.

    Mirrors the documented `KeyMomentCue` shape (camelCase serialised via
    :meth:`to_dict`). Times are in SOURCE seconds.
    """

    start: float
    end: float
    intensity: Intensity
    reason: Reason
    text_excerpt: str
    effects: List[Effect] = field(default_factory=list)
    score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "intensity": self.intensity,
            "reason": self.reason,
            "textExcerpt": self.text_excerpt,
            "effects": list(self.effects),
        }


# --------------------------------------------------------------------------- #
# effect vocabulary per reason / intensity
# --------------------------------------------------------------------------- #
def _effects_for(reason: Reason, intensity: Intensity) -> List[Effect]:
    base: List[Effect] = []
    if reason == "hook":
        base = ["flash", "shutter_sfx", "punch_zoom", "light_streak"]
    elif reason == "cta":
        base = ["flash", "shutter_sfx", "punch_zoom", "keyword_pop"]
    elif reason == "number":
        base = ["flash", "shutter_sfx", "punch_zoom", "keyword_pop"]
    elif reason == "emotional_word":
        base = ["flash", "shutter_sfx", "punch_zoom"]
    elif reason == "keyword":
        base = ["punch_zoom", "keyword_pop", "underline"]
    elif reason == "topic_shift":
        base = ["flash", "light_streak", "motion_card"]
    else:  # pause_cut
        base = ["punch_zoom"]

    if intensity == "low":
        # Keep it subtle: drop the white flash, keep a punch (+ pop if present).
        return [e for e in base if e in ("punch_zoom", "keyword_pop", "underline")] or ["punch_zoom"]
    return base


_BASE_SCORE = {
    "hook": 100.0,
    "cta": 90.0,
    "number": 70.0,
    "emotional_word": 65.0,
    "topic_shift": 45.0,
    "keyword": 40.0,
    "pause_cut": 25.0,
}


def _cadence_bounds(duration: float) -> tuple[int, int]:
    if duration < 30.0:
        return 3, 6
    if duration <= 60.0:
        return 5, 10
    return 10, 22


def target_cue_count(duration: float) -> int:
    """How many cues a premium edit of *duration* seconds should carry."""
    lo, hi = _cadence_bounds(duration)
    # ~1 accent every 7 s, clamped into the premium cadence window.
    return max(lo, min(hi, round(duration / 7.0)))


def _excerpt_around(words: Sequence[dict], idx: int, span: int = 4) -> str:
    lo = max(0, idx - 1)
    hi = min(len(words), idx + span)
    return " ".join(str(w.get("word", "")).strip() for w in words[lo:hi]).strip()


def _classify_number(token: str) -> Optional[tuple[Intensity, float]]:
    """Return (intensity, score_bonus) if *token* is a number-ish accent."""
    if _PERCENT_RE.search(token) or _MONEY_RE.search(token):
        return "high", 15.0
    if _NUM_RE.search(token):
        return "medium", 5.0
    if _DATE_RE.search(token):
        return "medium", 0.0
    return None


def _candidate_cues(vu: dict) -> List[KeyMomentCue]:
    segments = vu.get("segments") or []
    words = content._all_words(vu)
    counts = content.keyword_counts(vu)
    top = set(content.top_keywords(vu, n=8))
    duration = float(vu.get("duration") or (segments[-1]["end"] if segments else 0.0))
    cues: List[KeyMomentCue] = []

    # 1) Hook — the very first spoken beat.
    if words:
        w0 = words[0]
        start = float(w0["start"])
        cues.append(KeyMomentCue(
            start=start, end=start + 1.1, intensity="high", reason="hook",
            text_excerpt=_excerpt_around(words, 0, span=6),
            effects=_effects_for("hook", "high"), score=_BASE_SCORE["hook"],
        ))

    # 2) Numbers / money / dates / percentages, emotional + keyword punches.
    for i, w in enumerate(words):
        raw = str(w.get("word", ""))
        tok = _norm(raw.strip(".,;:!?"))
        if not tok:
            continue
        start = float(w["start"])
        end = float(w.get("end", start + 0.3))

        num = _classify_number(raw)
        if num is not None:
            intensity, bonus = num
            cues.append(KeyMomentCue(
                start=start, end=max(end, start + 0.6), intensity=intensity,
                reason="number", text_excerpt=_excerpt_around(words, i),
                effects=_effects_for("number", intensity),
                score=_BASE_SCORE["number"] + bonus,
            ))
            continue

        if tok in _EMOTIONAL_WORDS:
            cues.append(KeyMomentCue(
                start=start, end=max(end, start + 0.6), intensity="medium",
                reason="emotional_word", text_excerpt=_excerpt_around(words, i),
                effects=_effects_for("emotional_word", "medium"),
                score=_BASE_SCORE["emotional_word"],
            ))
            continue

        if tok in top and counts.get(tok, 0) >= 2 and len(tok) > 3:
            cues.append(KeyMomentCue(
                start=start, end=max(end, start + 0.6), intensity="low",
                reason="keyword", text_excerpt=_excerpt_around(words, i),
                effects=_effects_for("keyword", "low"),
                score=_BASE_SCORE["keyword"] + min(8.0, counts[tok]),
            ))

    # 3) Topic shifts between consecutive segments (silence gap or low overlap).
    for prev, seg in zip(segments, segments[1:]):
        gap = float(seg["start"]) - float(prev["end"])
        prev_tok = set(content._content_tokens(prev.get("text", "")))
        cur_tok = set(content._content_tokens(seg.get("text", "")))
        overlap = (len(prev_tok & cur_tok) / len(prev_tok | cur_tok)) if (prev_tok | cur_tok) else 1.0
        if gap >= config.GAP_CUT or overlap < 0.12:
            start = float(seg["start"])
            cues.append(KeyMomentCue(
                start=start, end=start + 0.8, intensity="medium",
                reason="topic_shift", text_excerpt=content._headline(seg.get("text", "")),
                effects=_effects_for("topic_shift", "medium"),
                score=_BASE_SCORE["topic_shift"] + min(6.0, gap * 4.0),
            ))

    # 4) Pause cuts — a kept word resuming after a removed silence.
    for prev, w in zip(words, words[1:]):
        gap = float(w["start"]) - float(prev.get("end", prev["start"]))
        if gap >= PAUSE_CUT_MIN_GAP:
            start = float(w["start"])
            cues.append(KeyMomentCue(
                start=start, end=start + 0.5, intensity="low", reason="pause_cut",
                text_excerpt=str(w.get("word", "")).strip(),
                effects=_effects_for("pause_cut", "low"),
                score=_BASE_SCORE["pause_cut"] + min(5.0, gap * 3.0),
            ))

    # 5) Final CTA — a CTA word in the last third of the video is a strong cue.
    cutoff = duration * 0.66
    for i, w in enumerate(words):
        if float(w["start"]) < cutoff:
            continue
        tok = _norm(str(w.get("word", "")).strip(".,;:!?"))
        if tok in _CTA_WORDS:
            start = float(w["start"])
            cues.append(KeyMomentCue(
                start=start, end=start + 1.0, intensity="high", reason="cta",
                text_excerpt=_excerpt_around(words, i, span=6),
                effects=_effects_for("cta", "high"), score=_BASE_SCORE["cta"],
            ))
            break

    return cues


def _select(cues: List[KeyMomentCue], *, max_cues: int, min_gap: float) -> List[KeyMomentCue]:
    """Greedy: keep the highest-scoring cues that respect *min_gap* spacing."""
    chosen: List[KeyMomentCue] = []
    for cue in sorted(cues, key=lambda c: (-c.score, c.start)):
        if len(chosen) >= max_cues:
            break
        if all(abs(cue.start - c.start) >= min_gap for c in chosen):
            chosen.append(cue)
    chosen.sort(key=lambda c: c.start)
    return chosen


def plan_key_moments(
    vu: dict,
    *,
    min_gap: float = FLASH_MIN_GAP,
    max_cues: Optional[int] = None,
) -> List[KeyMomentCue]:
    """Plan the key-moment cues for a word-level transcript *vu*.

    Returns a chronological list of :class:`KeyMomentCue`, spaced by at least
    *min_gap* seconds (so no two flashes are hysterically close) and capped to a
    premium cadence derived from the video duration.
    """
    segments = vu.get("segments") or []
    if not segments:
        return []
    duration = float(vu.get("duration") or segments[-1]["end"])
    if max_cues is None:
        max_cues = target_cue_count(duration)
    candidates = _candidate_cues(vu)
    return _select(candidates, max_cues=max_cues, min_gap=min_gap)


def flash_times(cues: Sequence[KeyMomentCue]) -> List[float]:
    """Source-time instants of cues that carry a white camera flash."""
    return [round(c.start, 3) for c in cues if "flash" in c.effects]


def shutter_times(cues: Sequence[KeyMomentCue]) -> List[float]:
    """Source-time instants of cues that carry a shutter / camera SFX."""
    return [round(c.start, 3) for c in cues if "shutter_sfx" in c.effects]


def plan_light_overlays(
    vu: dict,
    *,
    pause_gap: float = config.LIGHT_OVERLAY_PAUSE_GAP,
    min_gap: float = config.LIGHT_OVERLAY_MIN_GAP,
) -> List[float]:
    """Source-time instants where the speaker takes a short breath/pause.

    Unlike :func:`plan_key_moments` (a scored, capped pool tuned for ~1 accent
    every 7s), this is deliberately DENSE: it fires at every meaningful pause
    between two parts of a sentence — not just full stops — so a "light leak"
    overlay + whoosh SFX can be dropped throughout the whole video to keep a
    plain talking-head edit visually dynamic. Only a tight *min_gap* keeps two
    overlays from stacking back-to-back.
    """
    words = content._all_words(vu)
    if len(words) < 2:
        return []
    chosen: List[float] = []
    for prev, w in zip(words, words[1:]):
        gap = float(w["start"]) - float(prev.get("end", prev["start"]))
        if gap < pause_gap:
            continue
        t = float(w["start"])
        if chosen and (t - chosen[-1]) < min_gap:
            continue
        chosen.append(round(t, 3))
    return chosen
