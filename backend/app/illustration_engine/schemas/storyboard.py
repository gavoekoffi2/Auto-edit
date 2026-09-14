"""Storyboard — the ordered set of scenes chosen for one video."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .scene import IllustrationScene


@dataclass
class Storyboard:
    scenes: List[IllustrationScene] = field(default_factory=list)
    source_duration: float = 0.0
    style: str = "professional"
    intensity: str = "medium"
    ai_mode: str = "offline"
    provider: str = "heuristic"
    notes: List[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.scenes)

    def __iter__(self):
        return iter(self.scenes)

    @property
    def coverage(self) -> float:
        """Fraction of the source occupied by illustrations.

        The product rule is that the talking head stays the backbone, so this
        is the number the planner keeps low on purpose.
        """
        if self.source_duration <= 0:
            return 0.0
        return sum(s.duration for s in self.scenes) / self.source_duration

    def spans(self) -> List[tuple]:
        return [s.legacy_spans() for s in self.scenes]

    def type_histogram(self) -> Dict[str, int]:
        hist: Dict[str, int] = {}
        for s in self.scenes:
            hist[s.visual_type] = hist.get(s.visual_type, 0) + 1
        return hist

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_duration": round(self.source_duration, 3),
            "style": self.style,
            "intensity": self.intensity,
            "ai_mode": self.ai_mode,
            "provider": self.provider,
            "coverage": round(self.coverage, 4),
            "type_histogram": self.type_histogram(),
            "notes": list(self.notes),
            "scenes": [s.to_dict() for s in self.scenes],
        }

    def plan_summary(self) -> List[Dict[str, Any]]:
        """Compact plan for the frontend "ILLUSTRATION PLAN" panel."""
        out = []
        for s in self.scenes:
            mm, ss = divmod(int(s.start), 60)
            out.append({
                "scene_id": s.scene_id,
                "at": f"{mm:02d}:{ss:02d}",
                "start": round(s.start, 2),
                "duration": round(s.duration, 2),
                "visual_type": s.visual_type,
                "concept": s.concept or s.title,
                "visual_score": round(s.visual_score, 2),
            })
        return out
