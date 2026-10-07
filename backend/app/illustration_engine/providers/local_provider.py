"""LocalSemanticProvider — the offline default.

It adds nothing on top of the heuristic analyzer, and that is the point: it
exists so the provider chain always terminates on something that works with no
network, no key and no model. `refine()` returning [] means "the heuristics
stand as they are".
"""
from __future__ import annotations

from typing import List, Sequence

from ..analyzer.semantic_analyzer import SemanticUnit
from .base import Refinement, SemanticProvider


class LocalSemanticProvider(SemanticProvider):
    name = "local"
    network = False

    def available(self) -> bool:
        return True

    def _refine(self, units: Sequence[SemanticUnit]) -> List[dict]:
        return []

    def refine(self, units: Sequence[SemanticUnit]) -> List[Refinement]:
        return []
