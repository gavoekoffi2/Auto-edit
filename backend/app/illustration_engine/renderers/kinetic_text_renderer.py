"""KineticTextRenderer — typography only.

Used when the passage has no structure to diagram but a word worth landing.
Each word arrives on its own beat, scaled and tracked so it fills the frame.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from .base import BaseRenderer, ease_out_back, fit_font, tint
from ..schemas.scene import IllustrationScene
from ..schemas.visual import KINETIC_TYPOGRAPHY, R_TITLE, VisualElement


class KineticTextRenderer(BaseRenderer):
    name = "kinetic_typography"
    handles = (KINETIC_TYPOGRAPHY,)

    def paint_background(self, canvas: Image.Image, scene: IllustrationScene,
                         t: float) -> None:
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, 0, self.width, self.height), fill=self.style.bg)

    def paint_title(self, canvas, draw, scene, element: VisualElement, p, action):
        """Every kinetic word is a title: big, centred, punched in."""
        if not element.text:
            return
        x1, y1, x2, y2 = self.px(element)
        width, height = x2 - x1, y2 - y1
        font = fit_font(self.style.font_title, element.text, width,
                        int(height * 0.92), self.unit(220), self.unit(40))
        scale = ease_out_back(p)
        text_w = draw.textlength(element.text, font=font)
        bbox = font.getbbox(element.text)
        text_h = bbox[3] - bbox[1]

        # Draw to a tile, then scale it: PIL cannot scale a font mid-frame.
        tile = Image.new("RGBA", (max(1, int(text_w) + 8), max(1, int(text_h) + 16)),
                         (0, 0, 0, 0))
        tile_draw = ImageDraw.Draw(tile)
        colour = self.style.ink if element.emphasis >= 0.9 else self.style.accent
        tile_draw.text((4, -bbox[1] + 8), element.text, font=font,
                       fill=tint(colour, p))
        if scale <= 0.02:
            return
        scaled = tile.resize((max(1, int(tile.width * scale)),
                              max(1, int(tile.height * scale))), Image.LANCZOS)
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        canvas.alpha_composite(scaled, (cx - scaled.width // 2,
                                        cy - scaled.height // 2))
