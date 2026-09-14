"""BaseRenderer — the frame loop every visual renderer shares.

A renderer is given a planned scene and must produce a clip. Everything that
is identical across visual languages lives here: canvas setup, font handling,
easing, the per-element animation semantics, scene entrance/exit, SFX event
extraction, and streaming frames to ffmpeg as ProRes 4444 with alpha.

Subclasses normally only override `paint_background` and, where their visual
language differs, individual `paint_*` methods.
"""
from __future__ import annotations

import math
import os
import sys
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

from .. import config
from ..assets import procedural_assets as pa
from ..assets.asset_manager import AssetManager
from ..schemas.render_job import RenderedIllustration
from ..schemas.scene import IllustrationScene
from ..schemas.visual import (
    AnimationInstruction, R_CAPTION, R_CONNECTOR, R_ICON, R_ITEM, R_LABEL,
    R_NUMBER, R_SIDE_A, R_SIDE_B, R_TITLE, R_UNDERLINE, VisualElement,
)
from ..styles import Style, get_style

RGBA = Tuple[int, int, int, int]

ENTRANCE = 0.42     # seconds the scene takes to arrive
EXIT = 0.40         # seconds it takes to leave


# --------------------------------------------------------------------------- #
# easing
# --------------------------------------------------------------------------- #
def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def ease_out_cube(p: float) -> float:
    p = clamp(p)
    return 1.0 - (1.0 - p) ** 3


def ease_out_back(p: float, s: float = 1.70158) -> float:
    p = clamp(p)
    return 1.0 + (s + 1.0) * (p - 1.0) ** 3 + s * (p - 1.0) ** 2


def ease_in_out(p: float) -> float:
    p = clamp(p)
    return 3 * p * p - 2 * p * p * p


EASINGS = {
    "ease_out_cube": ease_out_cube,
    "ease_out_back": ease_out_back,
    "ease_in_out": ease_in_out,
    "linear": clamp,
}


# --------------------------------------------------------------------------- #
# fonts
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=512)
def load_font(family: str, size: int):
    """Resolve a font, reusing the montage engine's bundled OFL families."""
    try:
        from ...autoedit_engine import fonts as engine_fonts
        return engine_fonts.load_font(family, size)
    except Exception:  # noqa: BLE001 - standalone use must still work
        for candidate in (f"{family}.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
        return ImageFont.load_default()


def fit_font(family: str, text: str, max_w: int, max_h: int,
             start: int, minimum: int = 16):
    """Largest size of *family* at which *text* fits the box on one line."""
    size = max(minimum, start)
    while size > minimum:
        font = load_font(family, size)
        box = font.getbbox(text or " ")
        if (box[2] - box[0]) <= max_w and (box[3] - box[1]) <= max_h:
            return font
        size -= max(1, size // 14)
    return load_font(family, minimum)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_w: int,
              max_lines: int = 3) -> List[str]:
    words = (text or "").split()
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_w or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
            if len(lines) == max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and words:
        joined = " ".join(lines)
        if len(joined.split()) < len(words):
            lines[-1] = lines[-1].rstrip(" ,;:") + "…"
    return lines


def alpha(image: Image.Image, factor: float) -> Image.Image:
    factor = clamp(factor)
    if factor >= 1.0:
        return image
    if factor <= 0.0:
        return Image.new("RGBA", image.size, (0, 0, 0, 0))
    channels = list(image.split())
    channels[3] = channels[3].point(lambda v: int(v * factor))
    return Image.merge("RGBA", channels)


def tint(color: RGBA, factor: float) -> RGBA:
    """Same colour at a different opacity."""
    return (color[0], color[1], color[2],
            max(0, min(255, int((color[3] if len(color) > 3 else 255) * clamp(factor)))))


# --------------------------------------------------------------------------- #
# renderer
# --------------------------------------------------------------------------- #
class BaseRenderer:
    """Shared machinery. Subclasses set `name` and override paint hooks."""

    name = "base"
    #: Visual types this renderer claims. Empty means "anything".
    handles: Tuple[str, ...] = ()

    def __init__(self, style: str | Style = "professional",
                 width: int = 1920, height: int = 1080,
                 fps: int = 30, assets: Optional[AssetManager] = None,
                 preview: bool = False):
        self.style: Style = style if isinstance(style, Style) else get_style(style)
        self.width, self.height = int(width), int(height)
        self.fps = max(1, int(fps))
        self.assets = assets or AssetManager()
        self.preview = preview

    # ------------------------------------------------------------------ #
    def supports(self, scene: IllustrationScene) -> bool:
        return not self.handles or scene.visual_type in self.handles

    # -- geometry helpers ---------------------------------------------- #
    def px(self, element: VisualElement) -> Tuple[int, int, int, int]:
        return element.box.pixels(self.width, self.height)

    def unit(self, value: float) -> int:
        """A size in canvas-relative units, so layouts scale with resolution."""
        return max(1, int(round(value * min(self.width, self.height) / 1000.0)))

    @property
    def line_width(self) -> int:
        return self.unit(self.style.line_width * 1.15)

    @property
    def radius(self) -> int:
        return self.unit(self.style.corner_radius * 1.4)

    # -- animation ------------------------------------------------------ #
    def progress(self, instruction: Optional[AnimationInstruction],
                 t: float) -> float:
        if instruction is None:
            return 1.0
        if instruction.duration <= 0:
            return 1.0 if t >= instruction.start else 0.0
        raw = (t - instruction.start) / instruction.duration
        easing = EASINGS.get(instruction.easing, ease_out_cube)
        return easing(clamp(raw))

    def scene_alpha(self, scene: IllustrationScene, t: float) -> float:
        duration = scene.duration
        if t < ENTRANCE:
            return clamp(t / ENTRANCE)
        if t > duration - EXIT:
            return clamp((duration - t) / EXIT)
        return 1.0

    # ------------------------------------------------------------------ #
    # painting — subclasses override these
    # ------------------------------------------------------------------ #
    def paint_background(self, canvas: Image.Image, scene: IllustrationScene,
                         t: float) -> None:
        """Flat ground plus a faint structural grid. No decoration."""
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, 0, self.width, self.height), fill=self.style.bg)
        band = int(self.height * 0.34)
        draw.rectangle((0, 0, self.width, band), fill=self.style.bg_alt)
        pa.dotted_grid(canvas, tint(self.style.muted, 0.10),
                       step=self.unit(52), radius=max(1, self.unit(2)))

    def paint_element(self, canvas: Image.Image, draw: ImageDraw.ImageDraw,
                      scene: IllustrationScene, element: VisualElement,
                      t: float) -> None:
        instruction = scene.instruction_for(element.element_id)
        if instruction is not None and t < instruction.start:
            return
        p = self.progress(instruction, t)
        if p <= 0.0:
            return
        action = instruction.action if instruction else "appear"
        painter = {
            R_TITLE: self.paint_title,
            R_UNDERLINE: self.paint_underline,
            R_ITEM: self.paint_item,
            R_SIDE_A: self.paint_panel,
            R_SIDE_B: self.paint_panel,
            R_NUMBER: self.paint_number,
            R_LABEL: self.paint_label,
            R_CONNECTOR: self.paint_connector,
            R_ICON: self.paint_icon,
            R_CAPTION: self.paint_caption,
        }.get(element.role, self.paint_caption)
        painter(canvas, draw, scene, element, p, action)

    # -- individual roles ---------------------------------------------- #
    def paint_title(self, canvas, draw, scene, element, p, action):
        if not element.text:
            return
        x1, y1, x2, y2 = self.px(element)
        font = fit_font(self.style.font_title, element.text,
                        x2 - x1, y2 - y1, self.unit(74), self.unit(26))
        text = element.text
        if action == "draw":
            # Typewriter reveal: the title writes itself with the voice.
            keep = max(1, int(round(len(text) * p)))
            text = text[:keep]
        offset = int((1.0 - p) * self.unit(26)) if action in ("appear", "slide") else 0
        color = tint(self.style.ink, 1.0 if action == "draw" else p)
        draw.text((x1, y1 + offset), text, font=font, fill=color)

    def paint_underline(self, canvas, draw, scene, element, p, action):
        x1, y1, x2, y2 = self.px(element)
        pa.underline(draw, (x1, y1, x2, y2), self.style.accent,
                     width=self.unit(9), progress=p)

    def paint_item(self, canvas, draw, scene, element, p, action):
        x1, y1, x2, y2 = self.px(element)
        scale = ease_out_back(p) if action == "pop" else p
        if scale <= 0:
            return
        # Grow from the centre so cards land rather than slide in.
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        half_w, half_h = (x2 - x1) / 2.0 * scale, (y2 - y1) / 2.0 * scale
        box = (int(cx - half_w), int(cy - half_h), int(cx + half_w), int(cy + half_h))
        if box[2] - box[0] < 4 or box[3] - box[1] < 4:
            return
        self._paint_card(canvas, draw, element, box, p)

    def paint_panel(self, canvas, draw, scene, element, p, action):
        x1, y1, x2, y2 = self.px(element)
        shift = int((1.0 - p) * self.unit(90))
        if action == "slide":
            direction = -1 if element.role == R_SIDE_A else 1
            x1 += direction * shift
            x2 += direction * shift
        self._paint_card(canvas, draw, element, (x1, y1, x2, y2), p,
                         accent=self.style.accent if element.role == R_SIDE_A
                         else self.style.accent_alt)

    def _paint_card(self, canvas, draw, element, box, p,
                    accent: Optional[RGBA] = None) -> None:
        accent = accent or self.style.accent
        x1, y1, x2, y2 = box
        width, height = x2 - x1, y2 - y1
        if element.shape in ("card", "node", "panel", "hub", "frame", "row",
                             "milestone"):
            pa.rounded_rect(draw, box, self.radius,
                            fill=tint(self.style.surface, p),
                            outline=tint(accent, p * 0.9),
                            width=max(2, self.unit(3)))
        # Numbered badge for ordered content.
        if element.value and element.shape in ("card", "node", "milestone"):
            badge = self.unit(46)
            bx, by = x1 + self.unit(18), y1 + self.unit(18)
            draw.ellipse((bx, by, bx + badge, by + badge), fill=tint(accent, p))
            font = load_font(self.style.font_number, int(badge * 0.62))
            label = str(int(element.value))
            tw = draw.textlength(label, font=font)
            draw.text((bx + (badge - tw) / 2, by + badge * 0.16), label,
                      font=font, fill=tint(self.style.bg, p))
        # A short card cannot stack an icon over a label without the two
        # colliding, so below this ratio the icon moves beside the text.
        stacked = bool(element.text) and height >= width * 0.85
        has_badge = bool(element.value) and element.shape in ("card", "node",
                                                              "milestone")

        # Measure the label first: icon and text are centred together as one
        # block, otherwise a tall card shows a void between them.
        lines: List[str] = []
        font = None
        line_h = 0
        text_w = width - self.unit(28)
        text_x1 = x1 + self.unit(14)
        if element.text:
            if element.icon and not stacked:
                side_guess = max(self.unit(34), min(int(height * 0.52), self.unit(120)))
                text_x1 = x1 + self.unit(26) + side_guess + self.unit(22)
                text_w = max(self.unit(60), x2 - self.unit(20) - text_x1)
            font = fit_font(self.style.font_body, element.text, text_w,
                            self.unit(56), self.unit(38), self.unit(18))
            lines = wrap_text(draw, element.text, font, text_w, 2)
            line_h = font.getbbox("Ag")[3] + self.unit(6)
        text_h = line_h * len(lines)

        icon_box = None
        if element.icon:
            if not element.text:
                side = max(self.unit(40), min(int(min(width, height) * 0.62),
                                              self.unit(190)))
                icon_box = (x1 + (width - side) // 2,
                            y1 + (height - side) // 2, side)
            elif stacked:
                side = max(self.unit(40),
                           min(int(min(width, height * 0.55) * 0.62), self.unit(170)))
                gap = self.unit(24)
                block = side + gap + text_h
                # Leave room for the number badge in the top-left corner.
                top = y1 + max((height - block) / 2.0,
                               self.unit(70) if has_badge else self.unit(18))
                icon_box = (x1 + (width - side) // 2, int(top), side)
            else:
                side = max(self.unit(34), min(int(height * 0.52), self.unit(120)))
                icon_box = (x1 + self.unit(26), y1 + (height - side) // 2, side)
        if icon_box:
            ix, iy, side = icon_box
            pa.draw_icon(draw, element.icon, (ix, iy, ix + side, iy + side),
                         tint(accent, p), width=max(2, self.line_width // 2),
                         progress=min(1.0, p * 1.4))

        if lines and font is not None:
            if icon_box and stacked:
                ty = icon_box[1] + icon_box[2] + self.unit(24)
            elif icon_box:
                ty = y1 + (height - text_h) / 2.0
            else:
                ty = y1 + (height - text_h) / 2.0 + (self.unit(20) if has_badge else 0)
            for line in lines:
                tw = draw.textlength(line, font=font)
                tx = (text_x1 + (text_w - tw) / 2
                      if (stacked or not element.icon) else text_x1)
                draw.text((tx, ty), line, font=font, fill=tint(self.style.ink, p))
                ty += line_h

    def paint_number(self, canvas, draw, scene, element, p, action):
        x1, y1, x2, y2 = self.px(element)
        raw = element.text or ""
        if action == "count" and element.value:
            # Count up to the figure: the viewer watches it land.
            current = element.value * ease_out_cube(p)
            digits = 0 if float(element.value).is_integer() else 1
            shown = f"{current:.{digits}f}".replace(".", ",") + (element.unit or "")
        else:
            shown = raw
        font = fit_font(self.style.font_number, shown or raw,
                        x2 - x1, y2 - y1, self.unit(300), self.unit(60))
        tw = draw.textlength(shown, font=font)
        bbox = font.getbbox(shown or "0")
        # Centre the glyph box inside the element box rather than guessing an
        # offset — a 300 px figure otherwise spills onto whatever is below.
        ty = y1 + ((y2 - y1) - (bbox[3] - bbox[1])) / 2.0 - bbox[1]
        draw.text(((x1 + x2 - tw) / 2, ty), shown, font=font,
                  fill=tint(self.style.accent_alt, p))

    def paint_label(self, canvas, draw, scene, element, p, action):
        x1, y1, x2, y2 = self.px(element)
        if element.shape == "bar":
            pa.progress_bar(draw, (x1, y1, x2, y2),
                            (element.value or 0.0) * p,
                            tint(self.style.muted, 0.28 * p),
                            tint(self.style.accent, p))
        else:
            pa.underline(draw, (x1, y1, x2, y2), tint(self.style.accent, p),
                         width=self.unit(7), progress=p)

    def paint_connector(self, canvas, draw, scene, element, p, action):
        x1, y1, x2, y2 = self.px(element)
        color = tint(self.style.accent, 0.92 * p)
        width = max(2, self.line_width // 2)
        if element.shape == "divider":
            if x2 - x1 > y2 - y1:
                pa.underline(draw, (x1, y1, x2, y2), color, width=max(2, self.unit(5)),
                             progress=p)
            else:
                cy = y1 + (y2 - y1) * p
                draw.line([(x1, y1), (x1, cy)], fill=color, width=max(2, self.unit(5)))
        elif element.shape == "axis":
            pa.underline(draw, (x1, y1, x2, y2), color, width=max(2, self.unit(6)),
                         progress=p)
        elif element.shape == "link":
            a = scene.element(element.connects[0])
            b = scene.element(element.connects[1])
            if a and b:
                # Stop on the box borders: a line that runs under the cards
                # reads as a mistake, not as a relationship.
                start = self._edge_point(a, b)
                end = self._edge_point(b, a)
                pa.arrow(draw, start, end, color, width=width, progress=p)
        else:   # arrow
            if element.shape in ("arrow_h", "arrow_v"):
                horizontal = element.shape == "arrow_h"
            else:
                horizontal = (x2 - x1) >= (y2 - y1)
            if horizontal:
                start = (x1 + self.unit(8), (y1 + y2) / 2.0)
                end = (x2 - self.unit(8), (y1 + y2) / 2.0)
            else:
                start = ((x1 + x2) / 2.0, y1 + self.unit(8))
                end = ((x1 + x2) / 2.0, y2 - self.unit(8))
            pa.arrow(draw, start, end, color, width=width, progress=p)

    def _edge_point(self, element: VisualElement, toward: VisualElement
                    ) -> Tuple[float, float]:
        """Where the segment element->toward crosses element's border."""
        cx, cy = element.box.center(self.width, self.height)
        tx, ty = toward.box.center(self.width, self.height)
        dx, dy = tx - cx, ty - cy
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            return (cx, cy)
        x1, y1, x2, y2 = self.px(element)
        half_w = max(1.0, (x2 - x1) / 2.0) + self.unit(6)
        half_h = max(1.0, (y2 - y1) / 2.0) + self.unit(6)
        scale = min(half_w / abs(dx) if dx else float("inf"),
                    half_h / abs(dy) if dy else float("inf"))
        return (cx + dx * scale, cy + dy * scale)

    def paint_icon(self, canvas, draw, scene, element, p, action):
        x1, y1, x2, y2 = self.px(element)
        pa.draw_icon(draw, element.icon, (x1, y1, x2, y2),
                     tint(self.style.accent, p), width=max(2, self.line_width // 2),
                     progress=p)

    def paint_caption(self, canvas, draw, scene, element, p, action):
        if not element.text:
            return
        x1, y1, x2, y2 = self.px(element)
        font = fit_font(self.style.font_body, element.text, x2 - x1,
                        self.unit(44), self.unit(34), self.unit(16))
        lines = wrap_text(draw, element.text, font, x2 - x1, 3)
        line_h = font.getbbox("Ag")[3] + self.unit(8)
        ty = y1 + int((1.0 - p) * self.unit(14))
        for line in lines:
            tw = draw.textlength(line, font=font)
            draw.text(((x1 + x2 - tw) / 2, ty), line, font=font,
                      fill=tint(self.style.muted, p))
            ty += line_h

    # ------------------------------------------------------------------ #
    def compose_frame(self, scene: IllustrationScene, t: float) -> Image.Image:
        canvas = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        self.paint_background(canvas, scene, t)
        draw = ImageDraw.Draw(canvas)
        for element in scene.ordered_elements():
            self.paint_element(canvas, draw, scene, element, t)
        return self.apply_transition(canvas, scene, t)

    def apply_transition(self, canvas: Image.Image, scene: IllustrationScene,
                         t: float) -> Image.Image:
        """Scene-level entrance and exit, then the global opacity envelope."""
        duration = scene.duration
        transition = self.style.transition
        offset = 0
        if t < ENTRANCE and transition in ("slide_up", "slide_left", "pop", "draw"):
            p = ease_out_cube(t / ENTRANCE)
            offset = int((1.0 - p) * self.height * 0.10)
        elif t > duration - EXIT and transition in ("slide_up", "slide_left", "pop", "draw"):
            p = ease_in_out(clamp((duration - t) / EXIT))
            offset = -int((1.0 - p) * self.height * 0.08)
        if offset:
            shifted = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            if transition == "slide_left":
                shifted.paste(canvas, (offset, 0))
            else:
                shifted.paste(canvas, (0, offset))
            canvas = shifted
        return alpha(canvas, self.scene_alpha(scene, t))

    # ------------------------------------------------------------------ #
    def events(self, scene: IllustrationScene) -> Dict[str, Any]:
        """Element timings for the SFX planner, relative to the scene start."""
        elements = [round(i.start, 3) for i in scene.animation_sequence
                    if i.start < scene.duration - EXIT - 0.1]
        return {
            "entrance": 0.0,
            "elements": sorted(set(elements))[:12],
            "exit": round(max(0.0, scene.duration - EXIT), 3),
        }

    # ------------------------------------------------------------------ #
    def render(self, scene: IllustrationScene, out_path: str) -> RenderedIllustration:
        """Stream the scene to a ProRes 4444 clip with alpha."""
        from ..timeline.encoder import ClipWriter   # local: avoids a cycle

        duration = max(0.4, scene.duration)
        n_frames = max(1, int(round(duration * self.fps)))
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with ClipWriter(out_path, self.width, self.height, self.fps) as writer:
            for index in range(n_frames):
                writer.write(self.compose_frame(scene, index / self.fps))
        return RenderedIllustration(
            scene_id=scene.scene_id, path=out_path, duration=round(duration, 3),
            renderer=self.name, events=self.events(scene), has_alpha=True,
            width=self.width, height=self.height,
        )
