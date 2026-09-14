"""Procedural drawing: vector icons and shapes rendered onto PIL canvases.

Two capabilities matter here:

* **partial strokes** — any icon can be drawn to a fraction of its total path
  length, which is what produces a hand-drawing reveal without any third-party
  dependency;
* **resolution independence** — icons are normalised polylines, so the same
  definition is crisp at 1920x1080 and at a 120 px thumbnail.
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw

from . import icon_library
from .icon_library import Icon, Point, Stroke

RGBA = Tuple[int, int, int, int]


# --------------------------------------------------------------------------- #
# stroke maths
# --------------------------------------------------------------------------- #
def stroke_length(stroke: Sequence[Point]) -> float:
    return sum(math.dist(stroke[i], stroke[i + 1]) for i in range(len(stroke) - 1))


def total_length(icon: Icon) -> float:
    return sum(stroke_length(s) for s in icon)


def partial(icon: Icon, fraction: float) -> Icon:
    """The first `fraction` of the icon's total path length.

    Strokes are consumed in order, and the stroke that straddles the cut is
    truncated at the exact point — so the line appears to be drawn, not
    revealed in chunks.
    """
    fraction = max(0.0, min(1.0, fraction))
    if fraction >= 1.0:
        return [list(s) for s in icon]
    if fraction <= 0.0:
        return []
    budget = total_length(icon) * fraction
    out: Icon = []
    for stroke in icon:
        if budget <= 0:
            break
        length = stroke_length(stroke)
        if length <= budget:
            out.append(list(stroke))
            budget -= length
            continue
        # Walk this stroke until the budget runs out.
        drawn: Stroke = [stroke[0]]
        for i in range(len(stroke) - 1):
            seg = math.dist(stroke[i], stroke[i + 1])
            if seg <= budget:
                drawn.append(stroke[i + 1])
                budget -= seg
            else:
                ratio = (budget / seg) if seg else 0.0
                x0, y0 = stroke[i]
                x1, y1 = stroke[i + 1]
                drawn.append((x0 + (x1 - x0) * ratio, y0 + (y1 - y0) * ratio))
                budget = 0.0
                break
        if len(drawn) > 1:
            out.append(drawn)
        break
    return out


def scale_icon(icon: Icon, box: Tuple[int, int, int, int]) -> Icon:
    """Map a 0..1 icon into a pixel box, preserving its aspect ratio."""
    x1, y1, x2, y2 = box
    width, height = max(1, x2 - x1), max(1, y2 - y1)
    side = min(width, height)
    ox = x1 + (width - side) / 2.0
    oy = y1 + (height - side) / 2.0
    return [[(ox + px * side, oy + py * side) for px, py in stroke]
            for stroke in icon]


# --------------------------------------------------------------------------- #
# drawing
# --------------------------------------------------------------------------- #
def draw_strokes(draw: ImageDraw.ImageDraw, icon: Icon, color: RGBA,
                 width: int = 6) -> None:
    for stroke in icon:
        if len(stroke) < 2:
            continue
        draw.line([(float(x), float(y)) for x, y in stroke],
                  fill=color, width=max(1, width), joint="curve")
        # Round the ends so thick strokes do not look chopped.
        radius = max(1, width // 2)
        for x, y in (stroke[0], stroke[-1]):
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)


def draw_icon(draw: ImageDraw.ImageDraw, name: str,
              box: Tuple[int, int, int, int], color: RGBA,
              width: int = 6, progress: float = 1.0) -> None:
    """Draw an icon into a pixel box, optionally only partially traced."""
    icon = scale_icon(icon_library.get(name), box)
    if progress < 1.0:
        icon = partial(icon, progress)
    draw_strokes(draw, icon, color, width)


def rounded_rect(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int],
                 radius: int, fill: Optional[RGBA] = None,
                 outline: Optional[RGBA] = None, width: int = 0) -> None:
    x1, y1, x2, y2 = box
    radius = max(0, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
    draw.rounded_rectangle((x1, y1, x2, y2), radius=radius, fill=fill,
                           outline=outline, width=width)


def rect_path(box: Tuple[int, int, int, int], radius: int = 0) -> Stroke:
    """A rounded rectangle as one continuous polyline.

    Returned as a path rather than drawn, so it can be traced progressively
    like any other stroke — that is what lets a card draw itself by hand.
    """
    x1, y1, x2, y2 = box
    radius = max(0, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
    if radius <= 1:
        return [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
    points: Stroke = []
    corners = (
        (x2 - radius, y1 + radius, -math.pi / 2, 0.0),
        (x2 - radius, y2 - radius, 0.0, math.pi / 2),
        (x1 + radius, y2 - radius, math.pi / 2, math.pi),
        (x1 + radius, y1 + radius, math.pi, 3 * math.pi / 2),
    )
    points.append((x1 + radius, y1))
    for cx, cy, a0, a1 in corners:
        steps = 8
        for i in range(steps + 1):
            angle = a0 + (a1 - a0) * i / steps
            points.append((cx + radius * math.cos(angle),
                           cy + radius * math.sin(angle)))
    points.append((x1 + radius, y1))
    return points


def arrow(draw: ImageDraw.ImageDraw, start: Point, end: Point, color: RGBA,
          width: int = 6, head: float = 0.0, progress: float = 1.0) -> None:
    """A straight arrow with a proportional head, drawable progressively."""
    length = math.dist(start, end)
    if length < 1:
        return
    head = head or max(12.0, min(length * 0.28, width * 4.5))
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    shaft_end = (end[0] - head * 0.55 * math.cos(angle),
                 end[1] - head * 0.55 * math.sin(angle))
    icon: Icon = [
        [start, shaft_end],
        [end, (end[0] - head * math.cos(angle - 0.42),
               end[1] - head * math.sin(angle - 0.42))],
        [end, (end[0] - head * math.cos(angle + 0.42),
               end[1] - head * math.sin(angle + 0.42))],
    ]
    if progress < 1.0:
        icon = partial(icon, progress)
    draw_strokes(draw, icon, color, width)


def curved_arrow(draw: ImageDraw.ImageDraw, start: Point, end: Point,
                 color: RGBA, width: int = 6, bend: float = 0.22,
                 progress: float = 1.0) -> None:
    """A hand-drawn looking arc — used by the whiteboard language."""
    mx, my = (start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0
    dx, dy = end[0] - start[0], end[1] - start[1]
    control = (mx - dy * bend, my + dx * bend)
    points: Stroke = []
    steps = 26
    for i in range(steps + 1):
        t = i / steps
        inv = 1.0 - t
        points.append((
            inv * inv * start[0] + 2 * inv * t * control[0] + t * t * end[0],
            inv * inv * start[1] + 2 * inv * t * control[1] + t * t * end[1],
        ))
    angle = math.atan2(points[-1][1] - points[-2][1], points[-1][0] - points[-2][0])
    head = max(12.0, width * 4.0)
    icon: Icon = [
        points,
        [end, (end[0] - head * math.cos(angle - 0.42),
               end[1] - head * math.sin(angle - 0.42))],
        [end, (end[0] - head * math.cos(angle + 0.42),
               end[1] - head * math.sin(angle + 0.42))],
    ]
    if progress < 1.0:
        icon = partial(icon, progress)
    draw_strokes(draw, icon, color, width)


def sketch_ellipse(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int],
                   color: RGBA, width: int = 6, progress: float = 1.0,
                   wobble: float = 0.03) -> None:
    """A marker-pen circle: slightly irregular and overshooting its start."""
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    rx, ry = (x2 - x1) / 2.0, (y2 - y1) / 2.0
    points: Stroke = []
    steps = 46
    for i in range(steps + 1):
        angle = -math.pi / 2 + 2.15 * math.pi * i / steps
        jitter = 1.0 + wobble * math.sin(angle * 3.0)
        points.append((cx + rx * jitter * math.cos(angle),
                       cy + ry * jitter * math.sin(angle)))
    icon: Icon = [points]
    if progress < 1.0:
        icon = partial(icon, progress)
    draw_strokes(draw, icon, color, width)


def underline(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int],
              color: RGBA, width: int = 8, progress: float = 1.0) -> None:
    x1, y1, x2, y2 = box
    span = (x2 - x1) * max(0.0, min(1.0, progress))
    cy = (y1 + y2) / 2.0
    if span < 1:
        return
    draw.line([(x1, cy), (x1 + span, cy)], fill=color,
              width=max(2, width), joint="curve")


def progress_bar(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int],
                 value: float, track: RGBA, fill: RGBA, radius: int = 0) -> None:
    x1, y1, x2, y2 = box
    radius = radius or max(2, (y2 - y1) // 2)
    rounded_rect(draw, (x1, y1, x2, y2), radius, fill=track)
    filled = int(round((x2 - x1) * max(0.0, min(1.0, value))))
    if filled > radius:
        rounded_rect(draw, (x1, y1, x1 + filled, y2), radius, fill=fill)


def dotted_grid(image: Image.Image, color: RGBA, step: int = 64,
                radius: int = 2) -> None:
    """A faint dot grid — structure for the eye, never a decoration on its own."""
    draw = ImageDraw.Draw(image)
    for y in range(step, image.height, step):
        for x in range(step, image.width, step):
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)


def paper_texture(size: Tuple[int, int], base: RGBA, seed: int = 7) -> Image.Image:
    """A very light noise plate so flat whites do not band on video."""
    import random
    rng = random.Random(seed)
    image = Image.new("RGBA", size, base)
    pixels = image.load()
    step = max(3, min(size) // 240)
    for y in range(0, size[1], step):
        for x in range(0, size[0], step):
            delta = rng.randint(-3, 3)
            r, g, b, a = pixels[x, y]
            pixels[x, y] = (max(0, min(255, r + delta)),
                            max(0, min(255, g + delta)),
                            max(0, min(255, b + delta)), a)
    return image
