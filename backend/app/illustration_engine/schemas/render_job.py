"""Rendered artefacts and the timeline that places them in the montage."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .scene import IllustrationScene


@dataclass
class RenderedIllustration:
    """The output of a renderer for one scene."""
    scene_id: str
    path: str                       # .mov (ProRes 4444, alpha) or .mp4
    duration: float
    renderer: str
    events: Dict[str, Any] = field(default_factory=dict)
    has_alpha: bool = True
    used_ai_image: bool = False
    fallback_from: str = ""         # renderer that failed before this one
    width: int = 0
    height: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "path": self.path,
            "duration": round(self.duration, 3),
            "renderer": self.renderer,
            "events": self.events,
            "has_alpha": self.has_alpha,
            "used_ai_image": self.used_ai_image,
            "fallback_from": self.fallback_from,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class IllustrationTimeline:
    """Rendered scenes paired with their specs, ready for compositing."""
    items: List["TimelineItem"] = field(default_factory=list)
    fps: int = 30
    width: int = 1080
    height: int = 1920

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def to_legacy_motion_clips(self) -> List[Dict[str, Any]]:
        """Emit the exact dict shape `plan_overlays` expects from the old engine.

        This is what keeps every downstream stage (overlay planning, SFX cue
        generation, ffmpeg compositing) working unchanged.
        """
        return [item.to_legacy_clip() for item in self.items]

    def spans(self) -> List[tuple]:
        return [(i.scene.start, i.scene.end) for i in self.items]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fps": self.fps, "width": self.width, "height": self.height,
            "items": [i.to_dict() for i in self.items],
        }


@dataclass
class TimelineItem:
    scene: IllustrationScene
    rendered: RenderedIllustration

    def to_legacy_clip(self) -> Dict[str, Any]:
        """Legacy `_motion_clips.json` record.

        `plan_overlays._place_motion` reads `source_start` / `duration` / `mov`,
        and `_motion_cues` reads `events`. Everything else is carried for
        debugging and for the frontend plan panel.
        """
        s, r = self.scene, self.rendered
        return {
            "id": s.scene_id,
            "kind": s.visual_type,
            "priority": round(s.importance, 3),
            "source_start": round(s.start, 3),
            "source_end": round(s.end, 3),
            "duration": round(r.duration, 3),
            "headline": s.title,
            "kicker": s.subtitle,
            "concepts": list(s.concepts),
            "excerpt": s.spoken_text,
            "spoken_line": s.spoken_text[:112],
            "mov": r.path,
            "illustrated": r.used_ai_image,
            "silhouette": None,
            "events": r.events,
            # new-engine extras (ignored by legacy consumers)
            "visual_type": s.visual_type,
            "visual_score": round(s.visual_score, 3),
            "pattern": s.pattern,
            "renderer": r.renderer,
            "style": s.style,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {"scene": self.scene.to_dict(), "rendered": self.rendered.to_dict()}
