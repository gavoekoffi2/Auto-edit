"""MotionGraphicsRenderer — the general-purpose graphic language.

Cards, panels, arrows, dividers and typography on a flat graded ground. It is
the default for anything that is not hand-drawn, purely numeric or purely
typographic, and it is the fallback target of every other renderer.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from .base import BaseRenderer, ease_out_cube, tint
from ..assets import procedural_assets as pa
from ..schemas.scene import IllustrationScene
from ..schemas.visual import (
    COMPARISON, CONCEPT, FLOWCHART, MOTION_GRAPHICS, PROCESS, TIMELINE,
    UI_EXPLAINER,
)


class MotionGraphicsRenderer(BaseRenderer):
    name = "motion_graphics"
    handles = (MOTION_GRAPHICS, COMPARISON, CONCEPT, FLOWCHART, PROCESS,
               TIMELINE, UI_EXPLAINER)

    def paint_background(self, canvas: Image.Image, scene: IllustrationScene,
                         t: float) -> None:
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, 0, self.width, self.height), fill=self.style.bg)

        # A single diagonal plane separates the title zone from the content
        # zone — it gives the eye a reading order instead of decorating.
        top = int(self.height * 0.30)
        draw.polygon([(0, 0), (self.width, 0), (self.width, top),
                      (0, int(top * 0.72))], fill=self.style.bg_alt)

        pa.dotted_grid(canvas, tint(self.style.muted, 0.09),
                       step=self.unit(56), radius=max(1, self.unit(2)))

        # A thin accent rule that grows with the scene: progress, not glitter.
        grow = ease_out_cube(min(1.0, t / max(scene.duration * 0.55, 0.1)))
        bar_h = max(2, self.unit(6))
        draw.rectangle((0, self.height - bar_h,
                        int(self.width * grow), self.height),
                       fill=tint(self.style.accent, 0.85))
