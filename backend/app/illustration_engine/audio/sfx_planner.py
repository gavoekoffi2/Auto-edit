"""SFXPlanner — one sound per visual event, chosen for what the event means.

The rule from the mission: a sound is tied to a visual, never used to fill a
gap. A card landing pops, a hand-drawn stroke scratches, a transition whooshes,
a key figure lands on a soft hit.
"""
from __future__ import annotations

from typing import Dict, List, Sequence

from .. import config
from ..schemas.scene import IllustrationScene, SFXCue
from ..schemas.visual import (
    R_CAPTION, R_CONNECTOR, R_ICON, R_ITEM, R_LABEL, R_NUMBER, R_SIDE_A,
    R_SIDE_B, R_TITLE, R_UNDERLINE, WHITEBOARD,
)
from . import sfx_library as lib

# Animation action -> sound. The action already encodes the intent.
ACTION_SFX: Dict[str, str] = {
    "pop": lib.POP,
    "appear": lib.CLICK,
    "draw": lib.PENCIL,
    "wipe": lib.MARKER,
    "slide": lib.WHOOSH,
    "connect": lib.WHOOSH,
    "count": lib.SUBTLE_HIT,
}

# Role overrides, applied when the role is more telling than the action.
ROLE_SFX: Dict[str, str] = {
    R_NUMBER: lib.SUBTLE_HIT,
    R_CONNECTOR: lib.WHOOSH,
    R_UNDERLINE: lib.MARKER,
    R_CAPTION: lib.CLICK,
}

# How long before the scene the anticipation riser starts.
RISER_LEAD = 0.45


class SFXPlanner:
    def __init__(self, enabled: bool = True, gain: float = None):
        self.enabled = bool(enabled and config.SFX_ENABLED)
        self.gain = config.SFX_GAIN if gain is None else float(gain)

    # ------------------------------------------------------------------ #
    def plan(self, scene: IllustrationScene) -> List[SFXCue]:
        """Cues for one scene, timed relative to the scene start.

        A negative time is intentional: the riser starts before the picture
        arrives, which is what makes a takeover feel deliberate.
        """
        if not self.enabled:
            return []
        whiteboard = scene.visual_type == WHITEBOARD
        cues: List[SFXCue] = [
            SFXCue(lib.RISER, -RISER_LEAD, lib.GAINS[lib.RISER] * self.gain,
                   "illustration"),
            SFXCue(lib.TRANSITION if not whiteboard else lib.WHOOSH, 0.0,
                   lib.GAINS[lib.TRANSITION] * self.gain, "illustration"),
        ]

        used_at: List[float] = []
        for instruction in scene.animation_sequence:
            element = scene.element(instruction.element_id)
            if element is None:
                continue
            if element.role == R_TITLE and instruction.start <= 0.2:
                continue          # the entrance sound already covers the title
            sound = self._sound_for(element.role, instruction.action, whiteboard)
            if sound is None:
                continue
            t = instruction.start
            # Never stack two cues on the same instant: that reads as a click.
            if any(abs(t - other) < 0.09 for other in used_at):
                continue
            used_at.append(t)
            cues.append(SFXCue(sound, t, lib.GAINS.get(sound, 0.5) * self.gain,
                               "illustration"))

        # A statistic resolves on its figure: mark the landing.
        if any(e.role == R_NUMBER for e in scene.elements):
            landing = max((i.start + i.duration for i in scene.animation_sequence
                           if scene.element(i.element_id)
                           and scene.element(i.element_id).role == R_NUMBER),
                          default=None)
            if landing is not None and landing < scene.duration - 0.3:
                cues.append(SFXCue(lib.SUCCESS, landing,
                                   lib.GAINS[lib.SUCCESS] * self.gain,
                                   "illustration"))

        exit_at = max(0.0, scene.duration - 0.40)
        cues.append(SFXCue(lib.EXIT, exit_at, lib.GAINS[lib.EXIT] * self.gain,
                           "illustration"))
        return [c for c in cues if c.t < scene.duration]

    def _sound_for(self, role: str, action: str, whiteboard: bool):
        if whiteboard:
            # Everything on a whiteboard is drawn, so everything scratches —
            # except the arrows, which still sweep.
            if role == R_CONNECTOR:
                return lib.WHOOSH
            if role in (R_ITEM, R_SIDE_A, R_SIDE_B, R_ICON, R_UNDERLINE,
                        R_LABEL, R_TITLE):
                return lib.PENCIL
        if role in ROLE_SFX:
            return ROLE_SFX[role]
        return ACTION_SFX.get(action, lib.CLICK)

    # ------------------------------------------------------------------ #
    def plan_all(self, scenes: Sequence[IllustrationScene]) -> Dict[str, List[SFXCue]]:
        return {scene.scene_id: self.plan(scene) for scene in scenes}

    def sounds_used(self, scenes: Sequence[IllustrationScene]) -> List[str]:
        names = set()
        for scene in scenes:
            for cue in self.plan(scene):
                names.add(cue.sfx)
        return sorted(names)
