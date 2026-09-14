"""ImportanceDetector — how much rhetorical weight does this passage carry?

Importance is about the *speech*: emphasis wording, structural signalling,
delivery (speaking rate, pauses around it) and position in the video. It is
deliberately independent of whether the passage is drawable — that is the
visual detector's job.
"""
from __future__ import annotations

from typing import List, Sequence

from . import lexicon as lx
from .semantic_analyzer import SemanticUnit
from ..schemas.visual import (
    P_ARCHITECTURE, P_CAUSE, P_COMPARISON, P_DEFINITION, P_KEYWORD, P_LIST,
    P_NUMBER, P_PROBLEM, P_PROCESS, P_STEPS,
)

# How much structure alone says "this matters".
PATTERN_WEIGHT = {
    P_STEPS: 0.85, P_LIST: 0.80, P_COMPARISON: 0.75, P_NUMBER: 0.75,
    P_PROBLEM: 0.78, P_CAUSE: 0.62, P_DEFINITION: 0.66, P_PROCESS: 0.64,
    P_ARCHITECTURE: 0.60, P_KEYWORD: 0.28,
}


class ImportanceDetector:
    def __init__(self, total_duration: float = 0.0):
        self.total_duration = max(0.0, float(total_duration or 0.0))

    # ------------------------------------------------------------------ #
    def _emphasis(self, folded: str) -> float:
        hits = sum(1 for m in lx.EMPHASIS_MARKERS if m in folded)
        return min(1.0, hits / 2.0)

    def _low_value(self, folded: str) -> float:
        """Penalty for greetings, calls to action and pure filler."""
        hits = sum(1 for m in lx.LOW_VALUE_MARKERS if m in folded)
        return min(1.0, hits / 2.0)

    def _position(self, unit: SemanticUnit) -> float:
        """The hook and the payoff matter more than the middle."""
        if self.total_duration <= 0:
            return 0.5
        p = min(1.0, max(0.0, unit.start / self.total_duration))
        # U-shaped: high at the start, dips mid, rises again near the end.
        return round(1.0 - 2.6 * p * (1.0 - p), 3)

    def _delivery(self, unit: SemanticUnit) -> float:
        """Slower, deliberate speech reads as emphasis."""
        words = len((unit.text or "").split())
        if words < 3 or unit.duration <= 0:
            return 0.4
        wps = words / unit.duration
        # ~2.2 words/second is conversational French; slower = weightier.
        if wps <= 1.6:
            return 0.85
        if wps >= 3.4:
            return 0.25
        return round(1.0 - (wps - 1.6) / (3.4 - 1.6) * 0.6, 3)

    # ------------------------------------------------------------------ #
    def score(self, unit: SemanticUnit) -> float:
        folded = unit.folded
        structure = PATTERN_WEIGHT.get(unit.pattern, 0.3) * unit.confidence
        raw = (
            0.44 * structure
            + 0.24 * self._emphasis(folded)
            + 0.18 * self._delivery(unit)
            + 0.14 * self._position(unit)
        )
        raw -= 0.35 * self._low_value(folded)
        return round(max(0.0, min(1.0, raw)), 3)

    def score_all(self, units: Sequence[SemanticUnit]) -> List[float]:
        return [self.score(u) for u in units]
