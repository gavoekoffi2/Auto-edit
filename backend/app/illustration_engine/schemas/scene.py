"""IllustrationScene — one planned takeover, fully specified before rendering."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .visual import AnimationInstruction, Box, VisualElement


@dataclass
class SFXCue:
    """One sound effect, timed relative to the scene start."""
    sfx: str
    t: float
    gain: float = 1.0
    src: str = "illustration"

    def to_dict(self) -> Dict[str, Any]:
        return {"sfx": self.sfx, "t": round(self.t, 3),
                "gain": round(self.gain, 3), "src": self.src}


@dataclass
class IllustrationScene:
    """A single illustrated scene: what to show, when, and how to animate it.

    Times are in SOURCE seconds (before the montage cut), matching the contract
    the legacy engine had with `plan_overlays`.
    """
    scene_id: str
    start: float
    end: float
    spoken_text: str
    concept: str
    importance: float
    visual_score: float
    visual_type: str
    pattern: str = ""
    style: str = "professional"
    title: str = ""
    subtitle: str = ""
    elements: List[VisualElement] = field(default_factory=list)
    animation_sequence: List[AnimationInstruction] = field(default_factory=list)
    sfx: List[SFXCue] = field(default_factory=list)
    concepts: List[str] = field(default_factory=list)
    renderer: str = ""          # filled in by the router at render time
    reason: str = ""            # why this moment was chosen (debug/UI)

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def element(self, element_id: str) -> Optional[VisualElement]:
        for el in self.elements:
            if el.element_id == element_id:
                return el
        return None

    def ordered_elements(self) -> List[VisualElement]:
        return sorted(self.elements, key=lambda e: e.reveal_order)

    def instruction_for(self, element_id: str) -> Optional[AnimationInstruction]:
        for ins in self.animation_sequence:
            if ins.element_id == element_id:
                return ins
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "duration": round(self.duration, 3),
            "spoken_text": self.spoken_text,
            "concept": self.concept,
            "importance": round(self.importance, 3),
            "visual_score": round(self.visual_score, 3),
            "visual_type": self.visual_type,
            "pattern": self.pattern,
            "style": self.style,
            "title": self.title,
            "subtitle": self.subtitle,
            "concepts": list(self.concepts),
            "renderer": self.renderer,
            "reason": self.reason,
            "elements": [e.to_dict() for e in self.ordered_elements()],
            "animation_sequence": [a.to_dict() for a in self.animation_sequence],
            "sfx": [c.to_dict() for c in self.sfx],
        }

    # ----------------------------------------------------------------- #
    # legacy bridge
    # ----------------------------------------------------------------- #
    def legacy_spans(self) -> tuple:
        """(source_start, source_end) — the span B-roll and popups must avoid."""
        return (self.start, self.end)
