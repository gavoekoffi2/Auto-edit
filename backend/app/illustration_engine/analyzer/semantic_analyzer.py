"""SemanticAnalyzer — transcript -> discourse units with a recognised pattern.

This is the part that answers "what is the speaker *doing* right now?".
It works on the word-level transcript produced by the transcription step and
needs no network access: the offline mode depends entirely on it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import lexicon as lx
from ..schemas.visual import (
    P_ARCHITECTURE, P_CAUSE, P_COMPARISON, P_DEFINITION, P_KEYWORD, P_LIST,
    P_NUMBER, P_PROBLEM, P_PROCESS, P_STEPS,
)

_SENT_END = re.compile(r"[.!?…]+$")
# Units shorter than this cannot carry an idea; longer ones stop being one idea.
MIN_UNIT_DUR = 2.5
MAX_UNIT_DUR = 14.0
TARGET_UNIT_DUR = 7.0
# A pause this long is a natural idea boundary even without punctuation.
PAUSE_BOUNDARY = 0.55


@dataclass
class Sentence:
    start: float
    end: float
    text: str

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class SemanticUnit:
    """One coherent stretch of speech plus what the analyzer understood of it."""
    start: float
    end: float
    text: str
    pattern: str = P_KEYWORD
    confidence: float = 0.0
    items: List[str] = field(default_factory=list)
    numbers: List[Tuple[str, float]] = field(default_factory=list)
    sides: Tuple[str, str] = ("", "")
    markers: List[str] = field(default_factory=list)
    announced_count: int = 0
    definition: Tuple[str, str] = ("", "")

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    @property
    def folded(self) -> str:
        return lx.fold(self.text)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start": round(self.start, 3), "end": round(self.end, 3),
            "text": self.text, "pattern": self.pattern,
            "confidence": round(self.confidence, 3),
            "items": list(self.items),
            "numbers": [list(n) for n in self.numbers],
            "sides": list(self.sides), "markers": list(self.markers),
            "announced_count": self.announced_count,
        }


# --------------------------------------------------------------------------- #
# transcript -> sentences
# --------------------------------------------------------------------------- #
def sentences_from_vu(vu: dict) -> List[Sentence]:
    """Split the word stream into sentences on punctuation and long pauses."""
    out: List[Sentence] = []
    for seg in vu.get("segments", []) or []:
        words = seg.get("words") or []
        if not words:
            text = (seg.get("text") or "").strip()
            if text:
                out.append(Sentence(float(seg.get("start", 0.0)),
                                    float(seg.get("end", 0.0)), text))
            continue
        buf: List[str] = []
        start: Optional[float] = None
        prev_end: Optional[float] = None
        for word in words:
            token = str(word.get("word", "")).strip()
            if not token:
                continue
            w_start, w_end = float(word.get("start", 0.0)), float(word.get("end", 0.0))
            if start is None:
                start = w_start
            elif prev_end is not None and w_start - prev_end >= PAUSE_BOUNDARY and buf:
                out.append(Sentence(start, prev_end, " ".join(buf).strip()))
                buf, start = [], w_start
            buf.append(token)
            prev_end = w_end
            if _SENT_END.search(token) and buf:
                out.append(Sentence(start, w_end, " ".join(buf).strip()))
                buf, start = [], None
        if buf and start is not None and prev_end is not None:
            out.append(Sentence(start, prev_end, " ".join(buf).strip()))
    return [s for s in out if s.text]


def group_units(sentences: List[Sentence]) -> List[SemanticUnit]:
    """Merge sentences into units of roughly TARGET_UNIT_DUR seconds.

    A unit never splits a sentence: the illustration has to line up with a
    complete thought, not with a clock tick.
    """
    units: List[SemanticUnit] = []
    buf: List[Sentence] = []
    for sent in sentences:
        buf.append(sent)
        span = buf[-1].end - buf[0].start
        if span >= TARGET_UNIT_DUR:
            units.append(SemanticUnit(buf[0].start, buf[-1].end,
                                      " ".join(s.text for s in buf).strip()))
            buf = []
    if buf:
        span = buf[-1].end - buf[0].start
        if units and span < MIN_UNIT_DUR:
            units[-1].end = buf[-1].end
            units[-1].text = (units[-1].text + " " +
                              " ".join(s.text for s in buf)).strip()
        else:
            units.append(SemanticUnit(buf[0].start, buf[-1].end,
                                      " ".join(s.text for s in buf).strip()))
    for unit in units:
        if unit.duration > MAX_UNIT_DUR:
            unit.end = unit.start + MAX_UNIT_DUR
    return units


# --------------------------------------------------------------------------- #
# extraction helpers
# --------------------------------------------------------------------------- #
_SPLIT_ITEMS = re.compile(r",| et | ainsi que | puis | ou bien |;| and | then ",
                          re.IGNORECASE)
# Articles and coordinators never belong in a label.
_STOP_ITEM = re.compile(r"^(le|la|les|l|un|une|des|du|de|d|au|aux|the|a|an|of|"
                        r"to|et|and|ce|cette|ces|son|sa|ses|leur|leurs)$",
                        re.IGNORECASE)
# Leading subject + verb scaffolding: "vous devez trouver un bon produit"
# has to become "Bon Produit", not "Vous Devez Trouver".
_LEAD_NOISE = re.compile(
    r"^(?:(?:vous|tu|on|je|il|elle|nous|ils|elles|you|we|they|i)\s+)?"
    r"(?:(?:devez|dois|doit|devons|doivent|faut|allez|vas|va|allons|vont|"
    r"pouvez|peux|peut|must|should|need to|have to|will|can)\s+)?"
    r"(?:(?:bien|vraiment|absolument|surtout|really|also)\s+)?"
    r"(?:(?:trouver|trouvez|attirer|attirez|assurer|assurez|maitriser|"
    r"maîtriser|maitrisez|avoir|ayez|faire|faites|creer|créer|creez|créez|"
    r"choisir|choisissez|find|get|build|create|make|ensure|drive|master)\s+)?",
    re.IGNORECASE)


# Copula + relative pronoun scaffolding left over after a marker:
# "le problème, c'est que personne ne suit ses marges" -> "personne ne suit...".
_LEAD_COPULA = re.compile(
    r"^(?:[,:\-–—\s]+)?"
    r"(?:(?:c'est|c’est|ce sont|it's|it is)\s+)?"
    r"(?:(?:est|sont|etait|était|is|are|was|were)\s+)?"
    r"(?:(?:que|qu'|qu’|qui|that|which|de|d')\s*)?",
    re.IGNORECASE)


def _clean_item(raw: str) -> str:
    item = re.sub(r"^[\s\-–—:•]+|[\s\.\!\?…]+$", "", raw or "").strip()
    item = re.sub(r"\s+", " ", item)
    # A label never runs past the end of its own sentence: the slice handed in
    # often reaches to the end of the unit.
    item = re.split(r"[.!?…](?:\s|$)", item)[0].strip()
    decopulated = _LEAD_COPULA.sub("", item, count=1).strip()
    if len(decopulated) >= 3:
        item = decopulated
    stripped = _LEAD_NOISE.sub("", item, count=1).strip()
    # Only accept the stripped form if something meaningful survived.
    if len(stripped.split()) >= 1 and len(stripped) >= 3:
        item = stripped
    words = [w for w in item.split() if not _STOP_ITEM.match(w.strip("'’"))]
    # An item has to read as a label, not as a clause.
    return " ".join(words[:3]).strip(" ,;:'’").title() if words else ""


def extract_list_items(text: str, expected: int = 0) -> List[str]:
    """Pull the enumerated items out of a list announcement.

    Looks after the colon or the announcing verb, then splits on commas and
    coordinating conjunctions.
    """
    folded = lx.fold(text)
    tail = text
    for intro in (":", *lx.LIST_INTROS):
        idx = folded.find(lx.fold(intro))
        if idx >= 0:
            candidate = text[idx + len(intro):]
            if len(candidate) > 8:
                tail = candidate
                break
    parts = [_clean_item(p) for p in _SPLIT_ITEMS.split(tail)]
    items = [p for p in parts if p and 2 <= len(p) <= 28]
    # Drop duplicates while keeping order.
    seen, unique = set(), []
    for item in items:
        key = lx.fold(item)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    if expected and len(unique) > expected:
        unique = unique[:expected]
    return unique[:5]


def extract_steps(text: str) -> List[str]:
    """Ordered steps announced with ordinals or sequence markers."""
    folded = lx.fold(text)
    hits: List[Tuple[int, int, str]] = []
    for marker, rank in lx.ORDINALS.items():
        for match in re.finditer(rf"\b{re.escape(marker)}\b", folded):
            hits.append((match.start(), rank, marker))
    for marker in lx.SEQUENCE_MARKERS:
        for match in re.finditer(rf"\b{re.escape(marker)}\b", folded):
            hits.append((match.start(), 99, marker))
    if len(hits) < 2:
        return []
    hits.sort()
    steps: List[str] = []
    for index, (pos, _rank, marker) in enumerate(hits):
        start = pos + len(marker)
        end = hits[index + 1][0] if index + 1 < len(hits) else len(text)
        label = _clean_item(text[start:end])
        if label:
            steps.append(label)
    return steps[:5]


def extract_sides(text: str) -> Tuple[str, str]:
    """(before, after) for a comparison, as short labels."""
    folded = lx.fold(text)
    for left, right in lx.COMPARISON_PAIRS:
        li, ri = folded.find(left), folded.find(right)
        if li >= 0 and ri > li:
            a = _clean_item(text[li + len(left):ri])
            b = _clean_item(text[ri + len(right):])
            if a or b:
                return (a or left.title(), b or right.title())
    for marker in lx.COMPARISON_MARKERS:
        idx = folded.find(marker)
        if idx >= 0:
            a = _clean_item(text[:idx])
            b = _clean_item(text[idx + len(marker):])
            if a and b:
                return (a, b)
    return ("", "")


def extract_definition(text: str) -> Tuple[str, str]:
    match = lx.DEFINITION_COPULA.search(text or "")
    if not match:
        return ("", "")
    term = _clean_item(match.group(1))
    meaning = re.sub(r"\s+", " ", (match.group(2) or "").strip())[:70]
    if term and meaning:
        return (term, meaning)
    return ("", "")


# --------------------------------------------------------------------------- #
# pattern detection
# --------------------------------------------------------------------------- #
def _clause_sides(text: str, folded: str, left_marker: str,
                  right_marker: str) -> Tuple[str, str]:
    """Label each side of a problem/solution pair with its own clause.

    Falls back to the marker itself when the clause after it is unusable, so
    the scene always has two readable labels.
    """
    def _after(marker: str) -> str:
        if not marker:
            return ""
        idx = folded.find(marker)
        if idx < 0:
            return ""
        tail = text[idx + len(marker):]
        # Stop at the next sentence boundary — one clause, not a paragraph.
        tail = re.split(r"[.!?…]", tail)[0]
        return _clean_item(tail)

    left = _after(left_marker) or left_marker.title()
    right = _after(right_marker) or right_marker.title()
    return (left, right)


def detect_pattern(unit: SemanticUnit) -> SemanticUnit:
    """Classify one unit. Confidence reflects how much evidence was found.

    Ordered most-specific first: a sentence can carry several markers, and the
    most structurally informative reading wins, because that is the one that
    produces a visual which actually explains something.
    """
    folded = unit.folded
    markers: List[str] = []

    unit.numbers = lx.parse_numbers(unit.text)
    unit.announced_count = lx.count_announcement(folded)

    # 1. explicit steps — strongest structure
    steps = extract_steps(unit.text)
    if len(steps) >= 2:
        unit.pattern = P_STEPS
        unit.items = steps
        unit.confidence = min(1.0, 0.55 + 0.12 * len(steps))
        unit.markers = [m for m in lx.SEQUENCE_MARKERS if m in folded][:3]
        return unit

    # 2. announced list
    if unit.announced_count >= 2:
        items = extract_list_items(unit.text, expected=unit.announced_count)
        unit.pattern = P_LIST
        unit.items = items
        unit.confidence = 0.6 + (0.15 if len(items) >= unit.announced_count else 0.0)
        unit.markers = ["count:%d" % unit.announced_count]
        return unit

    # 3. comparison
    sides = extract_sides(unit.text)
    if sides[0] and sides[1]:
        unit.pattern = P_COMPARISON
        unit.sides = sides
        unit.confidence = 0.7
        unit.markers = [lx.first_hit(folded, lx.COMPARISON_MARKERS) or "pair"]
        return unit

    # 4. statistic
    strong_numbers = [n for n in unit.numbers if n[1] >= 10 or "%" in n[0]]
    if strong_numbers:
        unit.pattern = P_NUMBER
        unit.numbers = strong_numbers
        unit.confidence = 0.65 + (0.1 if "%" in strong_numbers[0][0] else 0.0)
        unit.markers = ["number"]
        return unit

    # 5. problem -> solution
    has_problem = lx.has_any(folded, lx.PROBLEM_MARKERS)
    has_solution = lx.has_any(folded, lx.SOLUTION_MARKERS)
    if has_problem and has_solution:
        unit.pattern = P_PROBLEM
        unit.sides = _clause_sides(
            unit.text, folded,
            lx.first_hit(folded, lx.PROBLEM_MARKERS),
            lx.first_hit(folded, lx.SOLUTION_MARKERS))
        unit.confidence = 0.72
        unit.markers = ["problem", "solution"]
        return unit

    # 6. cause -> effect
    if lx.has_any(folded, lx.CAUSE_MARKERS) and lx.has_any(folded, lx.EFFECT_MARKERS):
        unit.pattern = P_CAUSE
        unit.confidence = 0.62
        unit.markers = [lx.first_hit(folded, lx.CAUSE_MARKERS),
                        lx.first_hit(folded, lx.EFFECT_MARKERS)]
        return unit

    # 7. definition
    definition = extract_definition(unit.text)
    if definition[0] and (lx.has_any(folded, lx.DEFINITION_MARKERS) or len(definition[1]) > 12):
        unit.pattern = P_DEFINITION
        unit.definition = definition
        unit.confidence = 0.6 if lx.has_any(folded, lx.DEFINITION_MARKERS) else 0.48
        unit.markers = ["definition"]
        return unit

    # 8. architecture — named components
    arch_hits = [n for n in lx.ARCHITECTURE_NOUNS if re.search(rf"\b{re.escape(n)}\b", folded)]
    if len(arch_hits) >= 2:
        unit.pattern = P_ARCHITECTURE
        unit.items = [h.title() for h in arch_hits[:4]]
        unit.confidence = 0.58
        unit.markers = arch_hits[:3]
        return unit

    # 9. process — flow verbs in sequence
    flow_hits = [v for v in lx.FLOW_VERBS if re.search(rf"\b{re.escape(v)}\b", folded)]
    if len(flow_hits) >= 2 or (flow_hits and lx.has_any(folded, lx.SEQUENCE_MARKERS)):
        unit.pattern = P_PROCESS
        unit.items = [h.title() for h in flow_hits[:4]]
        unit.confidence = 0.55
        unit.markers = flow_hits[:3]
        return unit

    # 10. nothing structural — emphasis only
    unit.pattern = P_KEYWORD
    unit.confidence = 0.3 if lx.has_any(folded, lx.EMPHASIS_MARKERS) else 0.12
    unit.markers = [lx.first_hit(folded, lx.EMPHASIS_MARKERS)] if unit.confidence > 0.2 else []
    return unit


class SemanticAnalyzer:
    """Transcript in, understood units out. No network, no model, no state."""

    def analyze(self, vu: dict) -> List[SemanticUnit]:
        sentences = sentences_from_vu(vu or {})
        if not sentences:
            return []
        return [detect_pattern(u) for u in group_units(sentences)]

    def analyze_text(self, text: str, start: float = 0.0,
                     end: float = 0.0) -> SemanticUnit:
        """Classify a bare string — used by tests and by provider validation."""
        return detect_pattern(SemanticUnit(start, end or max(start + 1.0, 1.0), text))
