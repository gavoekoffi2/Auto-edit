"""
Source <-> output timeline mapping.

The EDL keeps a list of source ``ranges`` that survive the cut.  Concatenating
them produces the output timeline, so a source timestamp maps to an output
timestamp by summing the durations of all earlier kept ranges.

``s2o`` (source->output) is used by plan_overlays / keyword_popup to place a
graphic at the output instant where the speaker starts a topic.
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

Range = Tuple[float, float]


def _ranges(edl_ranges: Sequence[dict]) -> List[Range]:
    return [(float(r["start"]), float(r["end"])) for r in edl_ranges]


def s2o(t_src: float, edl_ranges: Sequence[dict]) -> Optional[float]:
    """
    Map a *source* timestamp to its *output* timestamp.

    Returns None if ``t_src`` falls inside a cut-out gap (no output frame
    corresponds to it).  If it lands before the first kept frame it clamps to 0.
    """
    offset = 0.0
    for start, end in _ranges(edl_ranges):
        if t_src < start:
            # Inside a removed gap -> snap to the start of this kept range.
            return offset
        if start <= t_src <= end:
            return offset + (t_src - start)
        offset += end - start
    return None


def s2o_clamped(t_src: float, edl_ranges: Sequence[dict]) -> float:
    """Like :func:`s2o` but always returns a valid output time (clamped)."""
    out = s2o(t_src, edl_ranges)
    if out is not None:
        return out
    return output_duration(edl_ranges)


def output_duration(edl_ranges: Sequence[dict]) -> float:
    """Total output duration = sum of kept range lengths."""
    return sum(end - start for start, end in _ranges(edl_ranges))
