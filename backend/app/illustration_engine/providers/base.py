"""Provider contract for semantic analysis.

A provider *refines* the heuristic reading of the transcript. It never gets to
be the only source of truth: whatever it returns is validated, clamped to the
units it was given, and silently discarded when it does not hold up. That is
what lets `offline` be the default and `free`/`cloud` be genuine bonuses.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from ..analyzer.semantic_analyzer import SemanticUnit
from ..schemas.visual import PATTERNS, VISUAL_TYPES


@dataclass
class Refinement:
    """What a provider may say about one unit of speech."""
    index: int                      # which unit this refers to
    pattern: str = ""
    title: str = ""
    items: List[str] = field(default_factory=list)
    visual_type: str = ""
    visual_score: Optional[float] = None
    concept: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index, "pattern": self.pattern, "title": self.title,
            "items": list(self.items), "visual_type": self.visual_type,
            "visual_score": self.visual_score, "concept": self.concept,
        }


class SemanticProvider:
    """Base class. Subclasses implement `available()` and `_refine()`."""

    name = "base"
    #: True when the provider reaches the network.
    network = False

    def available(self) -> bool:
        return False

    # ------------------------------------------------------------------ #
    def refine(self, units: Sequence[SemanticUnit]) -> List[Refinement]:
        """Validated refinements. Returns [] on any problem — never raises."""
        if not units or not self.available():
            return []
        try:
            raw = self._refine(units)
        except Exception as exc:  # noqa: BLE001 - a provider is never fatal
            import sys
            print(f"[illustration_engine] provider {self.name} indisponible: "
                  f"{exc}", file=sys.stderr)
            return []
        return self._validate(raw or [], len(units))

    def _refine(self, units: Sequence[SemanticUnit]) -> List[dict]:
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    @staticmethod
    def _validate(raw: Sequence[dict], n_units: int) -> List[Refinement]:
        """Keep only well-formed entries that point at a real unit.

        A model that invents a nineteenth scene for an eight-unit transcript
        has its extra entries dropped rather than shifting everything else.
        """
        out: List[Refinement] = []
        seen: set = set()
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                index = int(entry.get("index", -1))
            except (TypeError, ValueError):
                continue
            if not (0 <= index < n_units) or index in seen:
                continue
            seen.add(index)

            pattern = str(entry.get("pattern", "") or "").strip().lower()
            if pattern not in PATTERNS:
                pattern = ""
            visual_type = str(entry.get("visual_type", "") or "").strip().lower()
            if visual_type not in VISUAL_TYPES:
                visual_type = ""

            score = entry.get("visual_score")
            try:
                score = max(0.0, min(1.0, float(score))) if score is not None else None
            except (TypeError, ValueError):
                score = None

            items = entry.get("items") or []
            if not isinstance(items, list):
                items = []
            items = [str(i).strip()[:28] for i in items if str(i).strip()][:5]

            out.append(Refinement(
                index=index, pattern=pattern,
                title=str(entry.get("title", "") or "").strip()[:34],
                items=items, visual_type=visual_type, visual_score=score,
                concept=str(entry.get("concept", "") or "").strip()[:60],
            ))
        return out
