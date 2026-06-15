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

# Phrases that mark an IMPORTANT explanatory beat — these are the moments the
# motion-design scenes must illustrate (RÈGLE: illustrer ce que la personne dit).
_EMPHASIS_RE = re.compile(
    r"\b(important|essentiel|cl[ée]|secret|astuce|conseil|strat[ée]gie|"
    r"m[ée]thode|syst[èe]me|erreur|probl[èe]me|solution|r[ée]sultat|retenez|"
    r"retiens|attention|jamais|toujours|v[ée]rit[ée]|r[èe]gle|principe|"
    r"[ée]tape|exemple|preuve|garantie|objectif|but|raison|pourquoi|comment|"
    r"important|key|secret|tip|mistake|strategy|method|rule|step|because|"
    r"reason|never|always|truth|goal|result)\b",
    re.IGNORECASE,
)

BROLL_DEMOGRAPHIC_SUFFIXES = {
    # Default product promise: African imagery ONLY, unless the user explicitly
    # switches the setting before launching the job.
    "african": (
        "EVERY person in the image MUST be Black African with dark skin — no "
        "white or non-African people. Modern francophone West/Central African "
        "setting (Abidjan, Dakar, Lomé, Cotonou, Douala), contemporary "
        "clothing and clean modern environments, premium realistic look, "
        "no stereotypes, no clichés"
    ),
    "caucasian": (
        "every person in the image must be caucasian / white, in modern "
        "professional environments, premium realistic look"
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


# Concept -> procedural icon id (motion_design fallback drawings + prompt hints).
# First match wins, so put the most specific concepts first.
ICON_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(mobile money|momo|paiement|payer|argent|cash|prix|euro|franc|fcfa|revenu|salaire|money|pay)\b", re.I), "money"),
    (re.compile(r"\b(croissance|augmenter|progresser|doubler|exploser|grandir|growth|scale|profit|chiffre)\b", re.I), "growth"),
    (re.compile(r"\b(t[ée]l[ée]phone|whatsapp|smartphone|appel|application|appli|phone|app|tiktok|instagram)\b", re.I), "phone"),
    (re.compile(r"\b(client|clients|prospect|audience|communaut[ée]|[ée]quipe|gens|personnes|people|team)\b", re.I), "people"),
    (re.compile(r"\b(vendre|vente|boutique|commande|produit|e[- ]?commerce|panier|achat|magasin|sell|shop)\b", re.I), "cart"),
    (re.compile(r"\b(id[ée]e|secret|astuce|penser|cr[ée]atif|inspiration|idea|tip|think)\b", re.I), "idea"),
    (re.compile(r"\b(objectif|but|cible|viser|atteindre|goal|target|focus)\b", re.I), "target"),
    (re.compile(r"\b(m[ée]thode|syst[èe]me|processus|outil|automatis|machine|process|tool|system)\b", re.I), "gear"),
    (re.compile(r"\b(formation|apprendre|cours|[ée]tudier|livre|le[çc]on|learn|course|book|teach)\b", re.I), "book"),
    (re.compile(r"\b(publicit[ée]|annonce|promo|marketing|communiquer|message|parler|announce|ad)\b", re.I), "megaphone"),
    (re.compile(r"\b(s[ée]curit[ée]|confiance|garantie|prot[ée]ger|fiable|secure|trust|safe)\b", re.I), "shield"),
    (re.compile(r"\b(temps|heure|minute|jour|semaine|mois|ann[ée]e|rapide|vite|time|fast|deadline)\b", re.I), "clock"),
    (re.compile(r"\b(lancer|d[ée]marrer|commencer|d[ée]but|launch|start|fus[ée]e|rocket)\b", re.I), "rocket"),
    (re.compile(r"\b(lieu|localis|adresse|ville|pays|carte|livraison|transport|map|location)\b", re.I), "map"),
]
DEFAULT_ICON = "idea"


def icon_for_text(text: str) -> str:
    """Best procedural icon id for a chunk of spoken text."""
    for pattern, icon in ICON_RULES:
        if pattern.search(text):
            return icon
    return DEFAULT_ICON


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
    Group transcript segments into TOPICS (semantic beats) of roughly
    TOPIC_MIN_DUR..TOPIC_MAX_DUR. A topic carries a coherent idea — that's what
    a motion-design scene illustrates — independent of how long an overlay is
    actually displayed on screen.
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
        if dur >= config.TOPIC_MIN_DUR:
            topics.append({"start": cur_start, "end": cur_end, "text": " ".join(cur_text).strip()})
            cur_text, cur_start = [], None

    if cur_text and cur_start is not None:
        # Fold a tiny trailing remainder into the previous topic.
        if topics and (cur_end - cur_start) < config.TOPIC_MIN_DUR / 2:
            topics[-1]["end"] = cur_end
            topics[-1]["text"] = (topics[-1]["text"] + " " + " ".join(cur_text)).strip()
        else:
            topics.append({"start": cur_start, "end": cur_end, "text": " ".join(cur_text).strip()})

    # Clamp each topic length to the semantic window.
    for tp in topics:
        tp["end"] = min(tp["end"], tp["start"] + config.TOPIC_MAX_DUR)
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


def _clean_display_token(token: str) -> str:
    """Normalize a spoken token for on-screen labels (l'intelligence -> intelligence)."""
    cleaned = token.strip().lower().strip("'’\".,;:!?()[]{}")
    cleaned = re.sub(r"^(?:l|d|j|m|t|s|c|n|qu)['’]", "", cleaned)
    return cleaned


def _display_label_from_focus(focus: List[str], fallback_text: str, max_words: int = 2) -> str:
    """Professional short label from meaningful concepts, not generic filler words."""
    labels: List[str] = []
    for tok in focus:
        clean = _clean_display_token(tok)
        if (len(clean) < 4 or clean in config.STOPWORDS or clean in config.FILLERS
                or clean in labels):
            continue
        labels.append(clean)
        if len(labels) >= max_words:
            break
    if labels:
        return " ".join(labels).upper()
    return _headline(fallback_text, max_words)


def derive_overlay_specs(vu: dict) -> List[dict]:
    """
    Decide which graphic overlays to render and over which topic span.

    RÈGLE PRODUIT: ces overlays graphiques sont LÉGERS, BREFS et OCCASIONNELS —
    ils ne couvrent jamais le visage (zone basse) et n'apparaissent que sur un
    signal FORT (un chiffre, un pourcentage). On a retiré les cartes "à retenir"
    génériques et les listes envahissantes: l'illustration du propos passe par
    les scènes motion_design, pas par des cartons de texte permanents.
    """
    topics = topic_segments(vu)
    specs: List[dict] = []

    def _short(tp: dict) -> float:
        return round(max(config.OVERLAY_MIN_DUR,
                         min(config.OVERLAY_MAX_DUR, tp["end"] - tp["start"])), 3)

    last_start = -1e9
    for idx, tp in enumerate(topics):
        if len(specs) >= config.OVERLAY_MAX_PER_VIDEO:
            break
        if float(tp["start"]) - last_start < config.OVERLAY_MIN_GAP:
            continue                              # espacer: pas deux overlays collés
        text = tp["text"]
        dur = _short(tp)
        base = {
            "id": f"gfx_{idx:03d}",
            "source_start": tp["start"],
            "source_end": tp["start"] + dur,
            "duration": dur,
            "title": _headline(text),
        }

        pct = _PERCENT_RE.search(text)
        nums = _NUM_RE.findall(text)

        spec = None
        if pct:
            spec = {**base, "type": "progress", "percent": _clamp_pct(pct.group(1)),
                    "label": base["title"] or "PROGRESSION"}
        elif nums:
            value = _parse_number(nums[0])
            if value is not None and 0 < value < 10_000_000:
                spec = {**base, "type": "stat", "value": value,
                        "raw": nums[0].strip(), "label": base["title"] or "CHIFFRE CLÉ"}
        # Plus de cartes "liste"/"à retenir" génériques: elles encombraient le
        # cadre. Les énumérations sont désormais illustrées par les scènes
        # motion_design (kind="steps").

        if spec is not None:
            specs.append(spec)
            last_start = float(tp["start"])

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
    avoid_spans: Optional[List[tuple]] = None,
) -> List[dict]:
    """
    Build B-roll ideas that match the spoken segment at each timestamp.

    The engine mixes two visual systems:
      * motion-design illustrated scenes for the key explanatory beats
        (``avoid_spans`` — B-roll never competes with them);
      * generated B-roll images for the strongest remaining spoken beats.

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
    motion_spans = [(float(a), float(b)) for a, b in (avoid_spans or [])]
    is_short = total <= config.SHORTS_MAX_DURATION_SECONDS
    seconds_per = _broll_seconds_per(total, bool(graphic_spans))
    if n is None:
        n = max(1, round(total / seconds_per))
    n = max(1, min(n, config.MAX_BROLL_IMAGES))

    counts = keyword_counts(vu)
    suffix = _demographic_suffix(demographic)
    ideas: List[dict] = []
    # With denser motion design, many windows can be reserved for free
    # procedural illustrations. Scan farther ahead so we still keep the B-roll
    # image budget when enough non-overlapping speech exists.
    windows = _broll_windows(
        vu,
        seconds_per,
        max_windows=max(n * 5, n + len(motion_spans) * 2 + 8),
    )

    for idx, window in enumerate(windows):
        if len(ideas) >= n:
            break
        s, e, spoken_text = float(window["start"]), float(window["end"]), window["text"]
        if motion_spans and _overlaps(s, e, motion_spans):
            # A motion-design scene already illustrates this beat.
            continue
        if graphic_spans and not is_short and _overlaps(s, e, graphic_spans) and idx % 2 == 0:
            # For long videos, let some motion-design beats carry the narration.
            # For shorts, do NOT skip: Claude wants more frequent B-roll.
            continue
        toks = _content_tokens(spoken_text)
        if not toks:
            continue
        ranked = sorted(set(toks), key=lambda t: counts.get(t, 0), reverse=True)
        focus = ranked[:5]
        label = _display_label_from_focus(focus, spoken_text, max_words=2)
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
# MOTION DESIGN scenes — illustrate what the speaker explains
# --------------------------------------------------------------------------- #
def _beat_score(text: str, counts: Counter) -> float:
    """How much a beat deserves a motion-design illustration."""
    score = 0.0
    if _ENUM_HINTS.search(text) or text.count(",") >= 3:
        score += 3.0
    if _PERCENT_RE.search(text):
        score += 3.0
    elif _NUM_RE.search(text):
        score += 1.5
    score += min(3.0, 1.2 * len(_EMPHASIS_RE.findall(text)))
    if "?" in text:
        score += 0.8
    toks = _content_tokens(text)
    if toks:
        top = sorted((counts.get(t, 0) for t in set(toks)), reverse=True)[:3]
        # Frequency is only a tie-breaker. It must not promote weak repeated
        # words into full-screen motion scenes by itself.
        score += min(1.0, 0.12 * sum(top))
    return score


def _steps_from_text(text: str, max_steps: int = 4) -> List[str]:
    """Short uppercase step labels from an enumeration-style sentence."""
    parts = re.split(r"[,.;:]|\bpuis\b|\bensuite\b|\bensuite,\b|\bet puis\b|\bthen\b|\bd'abord\b|\benfin\b",
                     text, flags=re.IGNORECASE)
    steps: List[str] = []
    for part in parts:
        label = _headline(part, 3)
        if label and label not in steps and len(label) >= 3:
            steps.append(label)
        if len(steps) >= max_steps:
            break
    return steps


def derive_motion_scenes(vu: dict, demographic: str = "african") -> List[dict]:
    """
    Pick the most important explanatory beats and turn each into a
    motion-design scene spec (full-frame illustrated animation).

    Selection is DYNAMIC, driven by what the speaker actually says: scored on
    enumerations, numbers, emphasis phrases and keyword density; spaced by
    MOTION_MIN_SPACING; capped at ~1 scene / 18-30 s (MOTION_MAX_SCENES max).
    Each spec carries the exact spoken excerpt + an illustration prompt + a
    procedural icon fallback, so the scene ALWAYS renders, with or without an
    image-generation API key.
    """
    topics = topic_segments(vu)
    if not topics:
        return []
    words = _all_words(vu)
    total = float(vu.get("duration") or (words[-1]["end"] if words else 0.0))
    if total < 10.0:
        return []

    every = (config.MOTION_EVERY_SHORT if total <= config.SHORTS_MAX_DURATION_SECONDS
             else config.MOTION_EVERY_LONG)
    budget = max(1, min(config.MOTION_MAX_SCENES, round(total / every)))

    counts = keyword_counts(vu)
    ranked = sorted(
        (tp for tp in topics if float(tp["start"]) >= config.MOTION_MIN_START),
        key=lambda tp: _beat_score(tp["text"], counts),
        reverse=True,
    )

    picked: List[dict] = []
    for tp in ranked:
        if len(picked) >= budget:
            break
        start = float(tp["start"])
        if any(abs(start - float(p["start"])) < config.MOTION_MIN_SPACING for p in picked):
            continue
        if _beat_score(tp["text"], counts) <= 1.2:
            continue
        picked.append(tp)

    # GARANTIE PRODUIT: une vidéo assez longue doit TOUJOURS avoir au moins une
    # scène motion design — même si le scoring ne trouve aucun beat "fort",
    # on force les meilleurs sujets disponibles.
    if not picked and total >= 25.0 and ranked:
        for tp in ranked[:2]:
            if not any(abs(float(tp["start"]) - float(p["start"])) < config.MOTION_MIN_SPACING
                       for p in picked):
                picked.append(tp)

    picked.sort(key=lambda tp: float(tp["start"]))

    suffix = _demographic_suffix(demographic)
    scenes: List[dict] = []
    used_headlines: set = set()      # VARIÉTÉ: jamais deux scènes avec le même mot-clé
    used_icons: List[str] = []       # ni la même icône deux fois de suite
    for idx, tp in enumerate(picked):
        text = tp["text"]
        toks = _content_tokens(text)
        ranked_toks = sorted(set(toks), key=lambda t: counts.get(t, 0), reverse=True)
        focus = ranked_toks[:4]
        # Choisir un titre DIFFÉRENT des scènes précédentes (évite
        # "confiance / confiance / confiance"). On prend le 1er mot-clé non
        # encore utilisé; sinon on retombe sur le meilleur disponible.
        headline = next((_display_label_from_focus([t], text) for t in ranked_toks
                         if _display_label_from_focus([t], text) not in used_headlines), "")
        if not headline:
            headline = _display_label_from_focus(focus, text)
        used_headlines.add(headline)
        excerpt = _safe_excerpt(text, 170)
        pct = _PERCENT_RE.search(text)
        nums = _NUM_RE.findall(text)
        enum = bool(_ENUM_HINTS.search(text)) or text.count(",") >= 3

        kind = "idea"
        steps: List[str] = []
        value: Optional[float] = None
        raw = ""
        if enum:
            steps = _steps_from_text(text)
            if len(steps) >= 2:
                kind = "steps"
        if kind == "idea" and pct:
            kind, value, raw = "number", _clamp_pct(pct.group(1)), pct.group(0).strip()
        elif kind == "idea" and nums:
            parsed = _parse_number(nums[0])
            if parsed is not None and 0 < parsed < 10_000_000:
                kind, value, raw = "number", parsed, nums[0].strip()

        # Icône VARIÉE: si le texte mappe sur la même icône que la scène
        # précédente, on tente une icône liée à un autre mot-clé du focus.
        icon = icon_for_text(text)
        if used_icons and icon == used_icons[-1]:
            for alt_tok in focus[1:]:
                alt = icon_for_text(alt_tok)
                if alt != icon:
                    icon = alt
                    break
        used_icons.append(icon)

        scene_desc = _scene_for_broll_text(text, focus)
        prompt = (
            f"{scene_desc}, drawn as a simple symbolic illustration of: \"{excerpt}\". "
            f"Key concepts: {', '.join(focus[:4]) or headline.lower()}. "
            f"Characters (if any): {suffix}."
        )
        # La scène dure le TEMPS DU PROPOS qu'elle illustre (glisse à l'entrée
        # du point, repart quand la personne a fini), borné par MIN/MAX pour
        # rester pro. Les "steps" ont un plancher un peu plus haut (cascade).
        span = float(tp["end"]) - float(tp["start"])
        floor = config.MOTION_SCENE_DUR_STEPS if kind == "steps" else config.MOTION_SCENE_MIN_DUR
        dur = round(max(floor, min(config.MOTION_SCENE_MAX_DUR, span)), 3)
        scenes.append({
            "id": f"md_{idx:03d}",
            "kind": kind,
            "priority": round(_beat_score(text, counts), 3),
            "source_start": round(float(tp["start"]), 3),
            "source_end": round(float(tp["start"]) + dur, 3),
            "duration": dur,
            "headline": headline,
            "kicker": "ÉTAPES" if kind == "steps" else ("CHIFFRE CLÉ" if kind == "number" else "À RETENIR"),
            "steps": steps,
            "value": value,
            "raw": raw,
            "concepts": focus,
            "excerpt": excerpt,
            "icon": icon,
            "prompt": prompt,
        })
    return scenes


def motion_scene_spans(scenes: List[dict]) -> List[tuple]:
    """(start, end) source-time spans claimed by motion scenes (for B-roll)."""
    return [
        (float(s["source_start"]), float(s["source_start"]) + float(s["duration"]))
        for s in scenes
    ]


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
