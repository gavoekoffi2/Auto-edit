"""Synchronisation — keep the pictures on the words.

Two mappings matter:

* **source -> output**: the montage cuts silences and false starts out of the
  source, so a scene planned at source t=32.4 s does not land at output 32.4 s.
  The engine reuses the montage EDL for this rather than inventing a second
  mapping that could drift from it.
* **scene -> elements**: inside a scene, each element's reveal is weighted by
  the narration it illustrates, so the picture builds at the speed of the voice.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from ..schemas.scene import IllustrationScene

# A placed scene must keep enough of itself to still read as an explanation.
MIN_PLACED_DUR = 1.5
MIN_PLACED_FRACTION = 0.6


def source_to_output(t_src: float, edl_ranges: Sequence[dict]) -> Optional[float]:
    """Map a source timestamp onto the cut timeline.

    Delegates to the montage engine's mapping when available so the two can
    never disagree; the local implementation is an exact reimplementation used
    when the illustration engine runs standalone.
    """
    try:
        from ...autoedit_engine.timeline import s2o
        return s2o(t_src, edl_ranges)
    except Exception:  # noqa: BLE001 - standalone fallback
        offset = 0.0
        for entry in edl_ranges:
            start, end = float(entry["start"]), float(entry["end"])
            if t_src < start:
                return offset
            if start <= t_src <= end:
                return offset + (t_src - start)
            offset += end - start
        return None


def output_duration(edl_ranges: Sequence[dict]) -> float:
    return sum(float(r["end"]) - float(r["start"]) for r in edl_ranges)


def place_scene(scene: IllustrationScene, edl_ranges: Sequence[dict],
                total_output: float = 0.0) -> Optional[Tuple[float, float]]:
    """(start, end) of a scene on the OUTPUT timeline, or None if it was cut.

    A scene whose beat was removed by the smart cut is dropped rather than
    slid somewhere else: an illustration that no longer matches what is being
    said is worse than no illustration.
    """
    if not edl_ranges:
        start = scene.start
        end = scene.end
    else:
        mapped = source_to_output(scene.start, edl_ranges)
        if mapped is None:
            return None
        start = mapped
        end = start + scene.duration
    limit = total_output or output_duration(edl_ranges) or end
    if limit and start >= limit - 0.2:
        return None
    if limit:
        end = min(end, limit)

    # A truncated scene never finishes revealing what it was built to show, so
    # a half-drawn flash at the end of the video is dropped rather than shown.
    kept = end - start
    if kept < MIN_PLACED_DUR or kept < scene.duration * MIN_PLACED_FRACTION:
        return None
    return (round(start, 3), round(end, 3))


def resolve_overlaps(placements: List[Tuple[float, float, IllustrationScene]],
                     min_gap: float = 0.35
                     ) -> List[Tuple[float, float, IllustrationScene]]:
    """Drop any scene that would overlap the one before it.

    Two illustrations on screen at once is never what the plan intended; it
    means the cut moved two beats next to each other.
    """
    kept: List[Tuple[float, float, IllustrationScene]] = []
    for start, end, scene in sorted(placements, key=lambda item: item[0]):
        if kept and start < kept[-1][1] + min_gap:
            continue
        kept.append((start, end, scene))
    return kept


def narration_weights(scene: IllustrationScene) -> List[float]:
    """Per-element weight blending its narration length and its area.

    Same blend the MIT whiteboard-animator uses for narration-weighted plans:
    characters spoken dominate, area breaks the ties.
    """
    elements = scene.ordered_elements()
    if not elements:
        return []
    char_counts = [len((e.annotation or e.text or "").strip()) for e in elements]
    areas = [max(e.box.area, 1e-4) for e in elements]
    total_chars = float(sum(char_counts))
    total_area = float(sum(areas))
    weights: List[float] = []
    for chars, area in zip(char_counts, areas):
        area_share = area / total_area
        if total_chars:
            weights.append(0.7 * (chars / total_chars) + 0.3 * area_share)
        else:
            weights.append(area_share)
    return weights
