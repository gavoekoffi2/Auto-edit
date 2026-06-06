"""
Content analysis — turns a transcript into montage decisions.

Everything here is DYNAMIC, never fixed (per spec):
  * keyword frequency (stopword-filtered, FR + EN)
  * topic grouping (5-17 s spans of speech)
  * overlay graphic specs (counters / progress / lists / stats / lower-thirds),
    chosen from what the speaker actually says (numbers, enumerations, ...)
  * B-roll ideas (~1 per 5 s, one strong idea each)

Timings here are in SOURCE time; plan_overlays maps them to output time.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import List, Optional

from . import config

_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ0-9'%€$]+")
_NUM_RE = re.compile(r"\b\d[\d.,]*\s*%?")
_PERCENT_RE = re.compile(r"(\d[\d.,]*)\s*%")
_ENUM_HINTS = re.compile(
    r"\b(premi[èe]rement|deuxi[èe]mement|troisi[èe]mement|d'abord|ensuite|"
    r"enfin|first|second|third|then|finally|num[ée]ro)\b",
    re.IGNORECASE,
)


def tokenize(text: str) -> List[str]:
    return [w.lower() for w in _WORD_RE.findall(text)]


def keyword_counts(vu: dict) -> Counter:
    """Frequency of meaningful tokens across the whole transcript."""
    counts: Counter = Counter()
    for seg in vu.get("segments", []):
        for tok in tokenize(seg.get("text", "")):
            if (len(tok) < 3 or tok.isdigit()
                    or tok in config.STOPWORDS or tok in config.FILLERS):
                continue
            counts[tok] += 1
    return counts


def top_keywords(vu: dict, n: int = config.KEYWORD_TOP_N) -> List[str]:
    return [w for w, _ in keyword_counts(vu).most_common(n)]


def _all_words(vu: dict) -> List[dict]:
    words: List[dict] = []
    for seg in vu.get("segments", []):
        words.extend(seg.get("words", []))
    words.sort(key=lambda w: float(w["start"]))
    return words


def topic_segments(vu: dict) -> List[dict]:
    """
    Group transcript segments into topics of roughly OVERLAY_MIN_DUR..MAX_DUR.

    A topic accumulates consecutive segments until it reaches >= MIN_DUR, then
    closes (without exceeding MAX_DUR).  Returns {start, end, text}.
    """
    topics: List[dict] = []
    cur_text: List[str] = []
    cur_start: Optional[float] = None
    cur_end = 0.0

    for seg in vu.get("segments", []):
        if cur_start is None:
            cur_start = float(seg["start"])
        cur_text.append(seg.get("text", "").strip())
        cur_end = float(seg["end"])
        dur = cur_end - cur_start
        if dur >= config.OVERLAY_MIN_DUR:
            topics.append({"start": cur_start, "end": cur_end, "text": " ".join(cur_text).strip()})
            cur_text, cur_start = [], None

    if cur_text and cur_start is not None:
        # Fold a tiny trailing remainder into the previous topic.
        if topics and (cur_end - cur_start) < config.OVERLAY_MIN_DUR / 2:
            topics[-1]["end"] = cur_end
            topics[-1]["text"] = (topics[-1]["text"] + " " + " ".join(cur_text)).strip()
        else:
            topics.append({"start": cur_start, "end": cur_end, "text": " ".join(cur_text).strip()})

    # Clamp each topic length to the overlay window.
    for tp in topics:
        tp["end"] = min(tp["end"], tp["start"] + config.OVERLAY_MAX_DUR)
    return topics


def _content_tokens(text: str) -> List[str]:
    """Meaningful tokens (no stopwords/fillers/short/numeric)."""
    return [t for t in tokenize(text)
            if t not in config.STOPWORDS and t not in config.FILLERS
            and len(t) > 2 and not t.isdigit()]


def _headline(text: str, max_words: int = 4) -> str:
    """A short, punchy label from a chunk of text (drop stopwords first)."""
    toks = _content_tokens(text) or tokenize(text)
    return " ".join(toks[:max_words]).upper()


def derive_overlay_specs(vu: dict) -> List[dict]:
    """
    Decide which graphic overlays to render and over which topic span.

    Heuristics (content-driven, never a fixed set):
      * numbers / percentages  -> stat or progress
      * enumerations           -> list
      * the opening topic       -> lower_third title card
      * otherwise              -> a keyword stat card now and then
    """
    topics = topic_segments(vu)
    specs: List[dict] = []
    kw = top_keywords(vu, 6)

    for idx, tp in enumerate(topics):
        text = tp["text"]
        dur = max(config.OVERLAY_MIN_DUR, min(config.OVERLAY_MAX_DUR, tp["end"] - tp["start"]))
        base = {
            "id": f"gfx_{idx:03d}",
            "source_start": tp["start"],
            "source_end": tp["start"] + dur,
            "duration": round(dur, 3),
            "title": _headline(text),
        }

        pct = _PERCENT_RE.search(text)
        nums = _NUM_RE.findall(text)

        if idx == 0:
            toks = _content_tokens(text)
            specs.append({**base, "type": "lower_third",
                          "title": " ".join(toks[:3]).upper() or "AUTO EDIT",
                          "subtitle": " ".join(toks[3:7]).upper()})
        elif pct:
            specs.append({**base, "type": "progress",
                          "percent": _clamp_pct(pct.group(1)),
                          "label": base["title"] or "PROGRESSION"})
        elif nums:
            value = _parse_number(nums[0])
            specs.append({**base, "type": "stat",
                          "value": value, "raw": nums[0].strip(),
                          "label": base["title"] or "CHIFFRE CLÉ"})
        elif _ENUM_HINTS.search(text) or text.count(",") >= 2:
            specs.append({**base, "type": "list",
                          "items": _list_items(text),
                          "label": base["title"] or "POINTS CLÉS"})
        elif idx % 3 == 1 and kw:
            specs.append({**base, "type": "stat",
                          "value": None, "raw": kw[idx % len(kw)].upper(),
                          "label": "À RETENIR"})
        # else: this topic carries B-roll instead of a graphic.

    return specs


def derive_broll_ideas(vu: dict, n: Optional[int] = None) -> List[dict]:
    """
    Build ~1 B-roll idea per SECONDS_PER_BROLL of speech.

    Each idea: {prompt, label, source_start, source_end}.  One strong idea per
    slot, derived from the densest keywords spoken in that slot.
    """
    words = _all_words(vu)
    if not words:
        return []
    total = float(vu.get("duration") or words[-1]["end"])
    if n is None:
        n = max(1, round(total / config.SECONDS_PER_BROLL))

    counts = keyword_counts(vu)
    ideas: List[dict] = []
    slot = total / n
    for i in range(n):
        s, e = i * slot, (i + 1) * slot
        in_slot = " ".join(w["word"] for w in words if s <= float(w["start"]) < e)
        toks = _content_tokens(in_slot)
        if not toks:
            continue
        # Strongest idea = highest-frequency tokens spoken in this slot.
        ranked = sorted(set(toks), key=lambda t: counts.get(t, 0), reverse=True)
        focus = ranked[:4]
        label = (ranked[0] if ranked else "").upper()
        prompt = ", ".join(focus) if focus else " ".join(toks[:4])
        ideas.append({
            "id": f"br_{i:03d}",
            "prompt": prompt,
            "label": label,
            "source_start": round(s, 3),
            "source_end": round(e, 3),
        })
    return ideas


# --------------------------------------------------------------------------- #
# small parsers
# --------------------------------------------------------------------------- #
def _parse_number(raw: str) -> Optional[float]:
    cleaned = raw.replace("%", "").replace(" ", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _clamp_pct(raw: str) -> float:
    val = _parse_number(raw) or 0.0
    return max(0.0, min(100.0, val))


def _list_items(text: str, max_items: int = 4) -> List[str]:
    parts = re.split(r"[,.;:]| et | and ", text)
    items = []
    for part in parts:
        cleaned = _headline(part, 3)
        if cleaned and cleaned not in items:
            items.append(cleaned)
        if len(items) >= max_items:
            break
    return items or [_headline(text, 3)]
