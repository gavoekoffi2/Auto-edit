"""TimingPlanner — snap scenes onto the voice.

An illustration that starts mid-word looks like a glitch. Every scene boundary
is moved to the nearest word boundary of the transcript, then clamped to the
engine's duration rules, then checked against its neighbours.
"""
from __future__ import annotations

from bisect import bisect_left
from typing import Dict, List, Optional, Sequence, Tuple

from .. import config


def all_words(vu: dict) -> List[dict]:
    words: List[dict] = []
    for seg in (vu or {}).get("segments", []) or []:
        for word in seg.get("words") or []:
            if word.get("word"):
                words.append(word)
    words.sort(key=lambda w: float(w.get("start", 0.0)))
    return words


class TimingPlanner:
    """Aligns scene spans to word boundaries and enforces pacing rules."""

    def __init__(self, vu: dict | None = None, total_duration: float = 0.0):
        self.words = all_words(vu or {})
        self.starts = [float(w.get("start", 0.0)) for w in self.words]
        self.ends = [float(w.get("end", 0.0)) for w in self.words]
        self.total = float(total_duration or (self.ends[-1] if self.ends else 0.0))

    # ------------------------------------------------------------------ #
    def _nearest(self, values: Sequence[float], t: float) -> float:
        if not values:
            return t
        idx = bisect_left(values, t)
        options = []
        if idx < len(values):
            options.append(values[idx])
        if idx > 0:
            options.append(values[idx - 1])
        return min(options, key=lambda v: abs(v - t)) if options else t

    def snap_start(self, t: float) -> float:
        """Move to the nearest word onset, but only if it is genuinely near."""
        snapped = self._nearest(self.starts, t)
        return snapped if abs(snapped - t) <= 0.45 else t

    def snap_end(self, t: float) -> float:
        snapped = self._nearest(self.ends, t)
        return snapped if abs(snapped - t) <= 0.45 else t

    def spoken_between(self, start: float, end: float) -> str:
        """The words actually spoken inside a span — the scene's annotation."""
        out = [str(w.get("word", "")) for w in self.words
               if float(w.get("start", 0.0)) >= start - 0.01
               and float(w.get("end", 0.0)) <= end + 0.01]
        return " ".join(out).strip()

    # ------------------------------------------------------------------ #
    def plan(self, start: float, end: float,
             previous_end: Optional[float] = None,
             target_duration: Optional[float] = None) -> Optional[Tuple[float, float]]:
        """Final (start, end) for a scene, or None if it cannot be placed.

        Rules applied in order: lead-in, word snapping, duration sizing, guards
        against the opening and the tail, and the minimum gap after the
        previous scene.

        `target_duration` is how long the scene *needs* to reveal its content.
        A scene never holds the screen longer than it has something to show —
        the talking head comes back as soon as the picture is complete.
        """
        start = max(0.0, float(start) - config.LEAD)
        end = float(end)
        if end <= start:
            return None

        start = self.snap_start(start)
        end = self.snap_end(end)

        if target_duration:
            wanted = max(config.MIN_SCENE_DUR,
                         min(config.MAX_SCENE_DUR, float(target_duration)))
            # Never stretch past what the speaker actually says here.
            wanted = min(wanted, max(end - start, config.MIN_SCENE_DUR))
            end = self.snap_end(start + wanted)
            if abs((end - start) - wanted) > 0.6:
                end = start + wanted

        duration = end - start
        if duration < config.MIN_SCENE_DUR:
            end = start + config.MIN_SCENE_DUR
        elif duration > config.MAX_SCENE_DUR:
            end = self.snap_end(start + config.MAX_SCENE_DUR)
            if end - start > config.MAX_SCENE_DUR * 1.15:
                end = start + config.MAX_SCENE_DUR

        if start < config.MIN_START:
            shift = config.MIN_START - start
            start += shift
            end += shift

        if self.total > 0:
            limit = self.total - config.TAIL_GUARD
            if start >= limit:
                return None
            if end > limit:
                end = limit

        if previous_end is not None and start - previous_end < config.MIN_GAP:
            return None
        if end - start < config.MIN_SCENE_DUR:
            return None
        return (round(start, 3), round(end, 3))

    # ------------------------------------------------------------------ #
    def element_windows(self, start: float, end: float,
                        weights: Sequence[float],
                        draw_budget: float = 0.75) -> List[Tuple[float, float]]:
        """Split the scene into per-element reveal windows, relative to start.

        Windows are proportional to `weights` (narration length, area, or a
        blend) and together span `draw_budget` of the scene, leaving the tail
        to hold the finished picture — the same pacing idea the MIT
        whiteboard-animator uses for its narration-weighted plans.
        """
        duration = max(0.0, end - start)
        n = len(weights)
        if n == 0 or duration <= 0:
            return []
        total = float(sum(max(w, 0.0) for w in weights)) or float(n)
        budget = duration * draw_budget
        windows: List[Tuple[float, float]] = []
        cursor = 0.0
        for weight in weights:
            slot = budget * (max(weight, 0.0) / total)
            windows.append((round(cursor, 3), round(cursor + slot, 3)))
            cursor += slot
        return windows
