"""VisualOpportunityDetector — should this moment be illustrated at all?

The `visual_score` answers the mission's core question: "would a picture here
make the viewer understand better?". It is NOT importance. A passage can be
rhetorically important and still have nothing to draw ("croyez-moi, c'est
vrai"), and a modest passage can be highly illustratable ("le colis part de
l'entrepôt, passe au tri, puis arrive chez le client").

Bands (from the mission):
    0.00-0.39  no animation
    0.40-0.59  optional
    0.60-0.79  recommended
    0.80-1.00  strongly recommended
"""
from __future__ import annotations

from typing import List, Sequence

from .. import config
from . import lexicon as lx
from .concept_detector import ConceptDetector
from .importance_detector import ImportanceDetector
from .semantic_analyzer import SemanticAnalyzer, SemanticUnit
from ..schemas.visual import (
    P_ARCHITECTURE, P_CAUSE, P_COMPARISON, P_DEFINITION, P_KEYWORD, P_LIST,
    P_NUMBER, P_PROBLEM, P_PROCESS, P_STEPS, VisualOpportunity,
)

# How well each discourse pattern maps onto an explanatory picture.
ILLUSTRATABILITY = {
    P_STEPS: 0.95, P_LIST: 0.92, P_COMPARISON: 0.90, P_NUMBER: 0.88,
    P_PROCESS: 0.86, P_ARCHITECTURE: 0.84, P_PROBLEM: 0.82, P_CAUSE: 0.74,
    P_DEFINITION: 0.70, P_KEYWORD: 0.30,
}

BAND_NONE = "none"
BAND_OPTIONAL = "optional"
BAND_RECOMMENDED = "recommended"
BAND_STRONG = "strongly_recommended"


def band(score: float) -> str:
    if score < config.SCORE_NONE:
        return BAND_NONE
    if score < config.SCORE_OPTIONAL:
        return BAND_OPTIONAL
    if score < config.SCORE_RECOMMENDED:
        return BAND_RECOMMENDED
    return BAND_STRONG


class VisualOpportunityDetector:
    """Turns understood units into scored, populated opportunities."""

    def __init__(self, total_duration: float = 0.0,
                 concepts: ConceptDetector | None = None):
        self.total_duration = float(total_duration or 0.0)
        self.concepts = concepts or ConceptDetector()
        self.importance = ImportanceDetector(total_duration)

    # ------------------------------------------------------------------ #
    def _material(self, unit: SemanticUnit) -> float:
        """Is there enough concrete material to actually build the scene?

        A "list" with no extractable items would render as an empty card —
        exactly the decorative animation the mission forbids.
        """
        if unit.pattern in (P_LIST, P_STEPS, P_PROCESS, P_ARCHITECTURE):
            n = len(unit.items)
            if n == 0:
                return 0.15
            return min(1.0, 0.45 + 0.22 * n)
        if unit.pattern == P_NUMBER:
            return 1.0 if unit.numbers else 0.2
        if unit.pattern in (P_COMPARISON, P_PROBLEM):
            return 1.0 if (unit.sides[0] and unit.sides[1]) else 0.35
        if unit.pattern == P_DEFINITION:
            return 0.9 if unit.definition[0] else 0.4
        return 0.35

    def _duration_fit(self, unit: SemanticUnit) -> float:
        """A scene needs room to breathe but must not hold the screen too long."""
        d = unit.duration
        if d < config.MIN_SCENE_DUR:
            return max(0.0, d / max(config.MIN_SCENE_DUR, 0.1))
        if d > config.MAX_SCENE_DUR * 1.6:
            return 0.55
        return 1.0

    # ------------------------------------------------------------------ #
    def score(self, unit: SemanticUnit) -> float:
        illustratability = ILLUSTRATABILITY.get(unit.pattern, 0.3) * (
            0.55 + 0.45 * unit.confidence)
        material = self._material(unit)
        concreteness = self.concepts.concreteness(unit.text)
        importance = self.importance.score(unit)

        raw = (
            0.38 * illustratability
            + 0.24 * material
            + 0.22 * importance
            + 0.16 * concreteness
        ) * self._duration_fit(unit)

        # Hard veto: filler and calls to action never get a picture.
        if lx.has_any(unit.folded, lx.LOW_VALUE_MARKERS) and unit.pattern == P_KEYWORD:
            raw *= 0.35
        return round(max(0.0, min(1.0, raw)), 3)

    def detect(self, units: Sequence[SemanticUnit]) -> List[VisualOpportunity]:
        out: List[VisualOpportunity] = []
        for unit in units:
            score = self.score(unit)
            out.append(VisualOpportunity(
                start=unit.start, end=unit.end, text=unit.text,
                pattern=unit.pattern, visual_score=score,
                importance=self.importance.score(unit),
                concepts=self.concepts.concepts(unit.text, limit=4),
                items=list(unit.items), numbers=list(unit.numbers),
                sides=unit.sides,
                reason=self._reason(unit, score),
            ))
        return out

    def _reason(self, unit: SemanticUnit, score: float) -> str:
        label = band(score)
        if unit.pattern == P_KEYWORD:
            return f"{label}: aucune structure de discours détectée"
        detail = {
            P_LIST: f"liste de {len(unit.items) or unit.announced_count} éléments",
            P_STEPS: f"séquence de {len(unit.items)} étapes",
            P_COMPARISON: f"comparaison {unit.sides[0]} / {unit.sides[1]}",
            P_NUMBER: f"chiffre clé {unit.numbers[0][0] if unit.numbers else ''}",
            P_PROBLEM: "problème puis solution",
            P_CAUSE: "cause puis conséquence",
            P_DEFINITION: f"définition de « {unit.definition[0]} »",
            P_PROCESS: "processus séquentiel",
            P_ARCHITECTURE: "architecture en composants",
        }.get(unit.pattern, unit.pattern)
        return f"{label}: {detail}"


def analyze_transcript(vu: dict) -> List[VisualOpportunity]:
    """One-call convenience path: transcript -> scored opportunities."""
    analyzer = SemanticAnalyzer()
    units = analyzer.analyze(vu)
    if not units:
        return []
    total = float(vu.get("duration") or (units[-1].end if units else 0.0))
    concepts = ConceptDetector().fit([u.text for u in units])
    return VisualOpportunityDetector(total, concepts).detect(units)
