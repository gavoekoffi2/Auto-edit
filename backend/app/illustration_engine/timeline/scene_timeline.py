"""Assemble rendered scenes into a timeline the compositor can burn in."""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Sequence, Tuple

from ..schemas.render_job import (
    IllustrationTimeline, RenderedIllustration, TimelineItem)
from ..schemas.scene import IllustrationScene
from ..schemas.storyboard import Storyboard
from .synchronization import place_scene, resolve_overlaps


def build_timeline(storyboard: Storyboard,
                   rendered: Dict[str, RenderedIllustration],
                   fps: int = 30, width: int = 1920, height: int = 1080
                   ) -> IllustrationTimeline:
    """Pair each planned scene with its clip, in source-time order."""
    items: List[TimelineItem] = []
    for scene in storyboard.scenes:
        clip = rendered.get(scene.scene_id)
        if clip is None:
            continue
        items.append(TimelineItem(scene=scene, rendered=clip))
    items.sort(key=lambda item: item.scene.start)
    return IllustrationTimeline(items=items, fps=fps, width=width, height=height)


def to_output_overlays(timeline: IllustrationTimeline,
                       edl_ranges: Sequence[dict] = (),
                       total_output: float = 0.0) -> List[dict]:
    """Overlay records on the OUTPUT timeline, ready for the compositor.

    The shape matches what the montage's `plan_overlays` emits, so the same
    ffmpeg compositing stage handles both.
    """
    placements: List[Tuple[float, float, IllustrationScene]] = []
    lookup: Dict[str, TimelineItem] = {i.scene.scene_id: i for i in timeline}
    for item in timeline:
        span = place_scene(item.scene, edl_ranges, total_output)
        if span is None:
            continue
        placements.append((span[0], span[1], item.scene))

    overlays: List[dict] = []
    for start, end, scene in resolve_overlaps(placements):
        item = lookup[scene.scene_id]
        overlays.append({
            "kind": "illustration",
            "id": scene.scene_id,
            "mov": item.rendered.path,
            "start": round(start, 3),
            "end": round(min(end, start + item.rendered.duration), 3),
            "visual_type": scene.visual_type,
            "renderer": item.rendered.renderer,
        })
    return overlays


def write_manifest(timeline: IllustrationTimeline, path: str,
                   storyboard: Optional[Storyboard] = None) -> str:
    """Persist the timeline next to the clips, for debugging and for the UI."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    payload = {
        "timeline": timeline.to_dict(),
        "legacy_motion_clips": timeline.to_legacy_motion_clips(),
    }
    if storyboard is not None:
        payload["storyboard"] = storyboard.to_dict()
        payload["plan"] = storyboard.plan_summary()
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return path
