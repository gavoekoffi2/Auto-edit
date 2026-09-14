"""DiagramRenderer — architecture and flows, where the links carry the meaning.

Connectors are drawn *under* the nodes and are given more presence than in the
general graphic language, because in a diagram the relationship between the
boxes is the information.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from .base import BaseRenderer, tint
from ..assets import procedural_assets as pa
from ..schemas.scene import IllustrationScene
from ..schemas.visual import DIAGRAM, R_CONNECTOR


class DiagramRenderer(BaseRenderer):
    name = "diagram"
    handles = (DIAGRAM,)

    def paint_background(self, canvas: Image.Image, scene: IllustrationScene,
                         t: float) -> None:
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, 0, self.width, self.height), fill=self.style.bg)
        band = int(self.height * 0.26)
        draw.rectangle((0, 0, self.width, band), fill=self.style.bg_alt)
        pa.dotted_grid(canvas, tint(self.style.muted, 0.12),
                       step=self.unit(48), radius=max(1, self.unit(2)))

    def compose_frame(self, scene: IllustrationScene, t: float) -> Image.Image:
        """Two passes: links first, then nodes on top of them."""
        canvas = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        self.paint_background(canvas, scene, t)
        draw = ImageDraw.Draw(canvas)
        elements = scene.ordered_elements()
        for element in (e for e in elements if e.role == R_CONNECTOR):
            self.paint_element(canvas, draw, scene, element, t)
        for element in (e for e in elements if e.role != R_CONNECTOR):
            self.paint_element(canvas, draw, scene, element, t)
        return self.apply_transition(canvas, scene, t)
