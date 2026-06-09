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

BROLL_DEMOGRAPHIC_SUFFIXES = {
    "african": (
        "modern African people and African environments, francophone West/Central Africa, "
        "premium realistic look, no stereotypes, no clichés"
    ),
    "caucasian": (
        "caucasian / white people in modern professional environments, premium realistic look"
    ),
    "global": (
        "diverse international people, inclusive casting, premium realistic modern environments"
    ),
}

# Spoken-text → visual scene mapping. This is intentionally closer to the
# transcript than the old keyword-only prompts: each generated image should show
# the exact idea being discussed during that timestamp, not a generic business
# stock photo.
BROLL_SCENE_RULES: list[tuple[re.Pattern[str], str]] = [
    # Put specific visual actions before broad words like “client” so a phrase
    # such as “client paie en mobile money” produces a payment image, not a
    # generic support/call-center image.
    (re.compile(r"\b(mobile money|momo|orange money|wave|moov money|airtel money|paiement|payer)\b", re.I),
     "a close-up of a mobile-money payment on a smartphone in a modern African shop"),
    (re.compile(r"\b(e[- ]?commerce|boutique en ligne|vente en ligne|shopify|woocommerce|commande|livraison)\b", re.I),
     "an African e-commerce seller checking online orders, parcels ready for delivery, laptop and smartphone visible"),
    (re.compile(r"\b(client|clients|prospect|prospects|service client|support|appel|call center|centre d'appel)\b", re.I),
     "an African customer-service agent wearing a headset, speaking with a customer while a CRM dashboard is open"),
    (re.compile(r"\b(argent|finance|budget|investissement|revenu|profit|chiffre d'affaires|co[uû]t|prix)\b", re.I),
     "an African entrepreneur reviewing a financial dashboard with revenue charts and budget notes"),
    (re.compile(r"\b(marketing|publicit[ée]|marque|branding|r[ée]seaux sociaux|instagram|tiktok|facebook|whatsapp)\b", re.I),
     "an African creator planning a social-media marketing campaign on a phone and laptop"),
    (re.compile(r"\b(formation|cours|apprendre|coach|strat[ée]gie|m[ée]thode|conseil|solution)\b", re.I),
     "an African coach explaining a business strategy on a clean whiteboard to attentive learners"),
    (re.compile(r"\b(restaur|cuisine|chef|menu|repas)\b", re.I),
     "a modern African restaurant team serving customers and preparing orders"),
    (re.compile(r"\b(immobili|maison|appartement|terrain|location|airbnb)\b", re.I),
     "an African real-estate agent presenting a modern apartment and handing over keys"),
    (re.compile(r"\b(salon|beaut[ée]|coiffure|cosm[ée]tique|maquillage|peau)\b", re.I),
     "a premium African beauty salon with a stylist serving a smiling customer"),
    (re.compile(r"\b(transport|moto|voiture|taxi|chauffeur)\b", re.I),
     "a clean African urban transport scene with a delivery rider checking a route on a smartphone"),
]


def _demographic_suffix(style: Optional[str]) -> str:
    return BROLL_DEMOGRAPHIC_SUFFIXES.get(style or "african", BROLL_DEMOGRAPHIC_SUFFIXES["african"])


def _overlaps(start: float, end: float, spans: list[tuple[float, float]]) -> bool:
    return any(start < span_end and end > span_start for span_start, span_end in spans)


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


def _broll_seconds_per(total_duration: float, has_motion_graphics: bool) -> float:
    """Return cadence for generated B-roll images.

    Shorts/Reels need more frequent visual changes. For longer videos, keep a
    slower cadence so cost and render time stay under control.
    """
    if total_duration <= config.SHORTS_MAX_DURATION_SECONDS:
        return (
            config.SHORTS_SECONDS_PER_BROLL_WITH_MOTION
            if has_motion_graphics
            else config.SHORTS_SECONDS_PER_BROLL
        )
    return config.SECONDS_PER_BROLL_WITH_MOTION if has_motion_graphics else config.SECONDS_PER_BROLL


def _broll_windows(vu: dict, target_seconds: float, max_windows: int) -> List[dict]:
    """Create timestamp-aligned transcript windows for B-roll.

    The old planner divided the whole video into abstract equal slots, which can
    cut across sentence boundaries and produce visuals that feel unrelated. This
    window builder starts from real word timings and carries the exact spoken
    text that the image must illustrate.
    """
    words = _all_words(vu)
    if not words:
        return []
    windows: List[dict] = []
    cur: List[dict] = []
    cur_start: Optional[float] = None
    for word in words:
        w_start = float(word["start"])
        w_end = float(word.get("end", w_start + 0.25))
        if cur_start is None:
            cur_start = w_start
        cur.append(word)
        reached_duration = (w_end - cur_start) >= target_seconds
        sentence_break = str(word.get("word", "")).rstrip().endswith(('.', '!', '?', ';', ':'))
        if reached_duration or (sentence_break and (w_end - cur_start) >= target_seconds * 0.65):
            text = " ".join(str(w.get("word", "")).strip() for w in cur).strip()
            if text:
                windows.append({"start": cur_start, "end": w_end, "text": text})
            cur, cur_start = [], None
            if len(windows) >= max_windows:
                break
    if cur and cur_start is not None and len(windows) < max_windows:
        end = float(cur[-1].get("end", cur_start + target_seconds))
        text = " ".join(str(w.get("word", "")).strip() for w in cur).strip()
        if text:
            windows.append({"start": cur_start, "end": end, "text": text})
    return windows


def _scene_for_broll_text(text: str, focus: List[str]) -> str:
    for pattern, scene in BROLL_SCENE_RULES:
        if pattern.search(text):
            return scene
    if focus:
        return f"a cinematic visual metaphor for: {', '.join(focus[:4])}, shown through realistic people and objects"
    return "a realistic premium business scene that directly illustrates the spoken idea"


def _safe_excerpt(text: str, max_chars: int = 190) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "…"


def derive_broll_ideas(
    vu: dict,
    n: Optional[int] = None,
    demographic: str = "african",
    graphic_specs: Optional[List[dict]] = None,
) -> List[dict]:
    """
    Build B-roll ideas that match the spoken segment at each timestamp.

    The engine mixes two visual systems:
      * motion-design illustrations/cards for many key points;
      * generated B-roll images for the strongest spoken beats.

    Shorts get a denser B-roll cadence. Each idea keeps the exact spoken excerpt
    in the prompt so the generated image corresponds to the narration where it
    appears.
    """
    words = _all_words(vu)
    if not words:
        return []
    total = float(vu.get("duration") or words[-1]["end"])
    graphic_spans = [
        (float(g.get("source_start", 0.0)), float(g.get("source_end", 0.0)))
        for g in (graphic_specs or [])
    ]
    is_short = total <= config.SHORTS_MAX_DURATION_SECONDS
    seconds_per = _broll_seconds_per(total, bool(graphic_spans))
    if n is None:
        n = max(1, round(total / seconds_per))

    counts = keyword_counts(vu)
    suffix = _demographic_suffix(demographic)
    ideas: List[dict] = []
    windows = _broll_windows(vu, seconds_per, max_windows=max(n * 2, n + 4))

    for idx, window in enumerate(windows):
        if len(ideas) >= n:
            break
        s, e, spoken_text = float(window["start"]), float(window["end"]), window["text"]
        if graphic_spans and not is_short and _overlaps(s, e, graphic_spans) and idx % 2 == 0:
            # For long videos, let some motion-design beats carry the narration.
            # For shorts, do NOT skip: Claude wants more frequent B-roll.
            continue
        toks = _content_tokens(spoken_text)
        if not toks:
            continue
        ranked = sorted(set(toks), key=lambda t: counts.get(t, 0), reverse=True)
        focus = ranked[:5]
        label = (ranked[0] if ranked else toks[0]).upper()
        scene = _scene_for_broll_text(spoken_text, focus)
        excerpt = _safe_excerpt(spoken_text)
        prompt = (
            f"{scene}. Must directly illustrate this exact spoken excerpt: \"{excerpt}\". "
            f"Key concepts to show: {', '.join(focus[:4])}. Visual direction: {suffix}. "
            "Avoid generic stock imagery; show concrete objects, people and actions mentioned in the excerpt."
        )
        ideas.append({
            "id": f"br_{len(ideas):03d}",
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
