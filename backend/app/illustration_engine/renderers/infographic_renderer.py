"""InfographicRenderer — lists and statistics, where the data is the picture.

Differs from the general graphic language in two ways: the figure (or the item
count) is given the most contrast on screen, and the ground stays quiet so
nothing competes with it.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from .base import BaseRenderer, ease_out_cube, load_font, tint
from ..assets import procedural_assets as pa
from ..schemas.scene import IllustrationScene
from ..schemas.visual import INFOGRAPHIC, STATISTICS


class InfographicRenderer(BaseRenderer):
    name = "infographic"
    handles = (INFOGRAPHIC, STATISTICS)

    def paint_background(self, canvas: Image.Image, scene: IllustrationScene,
                         t: float) -> None:
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, 0, self.width, self.height), fill=self.style.bg)

        if scene.visual_type == STATISTICS:
            # A concentric ring behind the figure: it reads as a gauge, and it
            # is the only ornament allowed because it frames the number.
            cx, cy = self.width // 2, int(self.height * 0.44)
            for index, radius_unit in enumerate((330, 250, 180)):
                radius = self.unit(radius_unit)
                grow = ease_out_cube(min(1.0, (t - index * 0.12) /
                                         max(scene.duration * 0.5, 0.1)))
                if grow <= 0:
                    continue
                draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius),
                             outline=tint(self.style.accent, 0.16 + 0.06 * index),
                             width=max(1, self.unit(3)))
        else:
            band = int(self.height * 0.28)
            draw.rectangle((0, 0, self.width, band), fill=self.style.bg_alt)

        pa.dotted_grid(canvas, tint(self.style.muted, 0.08),
                       step=self.unit(60), radius=max(1, self.unit(2)))
