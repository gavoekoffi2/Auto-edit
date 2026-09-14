"""SVG export of the procedural library.

SVG is the engine's interchange format: the same normalised polylines that PIL
draws can be written out as vectors for a web preview, for the frontend plan
panel, or to feed an external renderer.
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple

from . import icon_library
from .icon_library import Icon

RGBA = Tuple[int, int, int, int]


def _hex(color: Sequence[int]) -> str:
    r, g, b = (int(c) for c in color[:3])
    return f"#{r:02x}{g:02x}{b:02x}"


def _opacity(color: Sequence[int]) -> float:
    return round((color[3] if len(color) > 3 else 255) / 255.0, 3)


def icon_to_svg(name: str, size: int = 200, color: RGBA = (0, 0, 0, 255),
                width: float = 6.0, background: Optional[RGBA] = None) -> str:
    """One icon as a standalone SVG document."""
    icon = icon_library.get(name)
    return strokes_to_svg(icon, size, size, color, width, background)


def strokes_to_svg(icon: Icon, width_px: int, height_px: int,
                   color: RGBA = (0, 0, 0, 255), stroke_width: float = 6.0,
                   background: Optional[RGBA] = None) -> str:
    """Normalised polylines -> an SVG document of the requested pixel size."""
    side = min(width_px, height_px)
    ox = (width_px - side) / 2.0
    oy = (height_px - side) / 2.0
    parts: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_px}" '
        f'height="{height_px}" viewBox="0 0 {width_px} {height_px}">'
    ]
    if background is not None:
        parts.append(f'<rect width="{width_px}" height="{height_px}" '
                     f'fill="{_hex(background)}" fill-opacity="{_opacity(background)}"/>')
    parts.append(f'<g fill="none" stroke="{_hex(color)}" '
                 f'stroke-opacity="{_opacity(color)}" '
                 f'stroke-width="{stroke_width}" stroke-linecap="round" '
                 f'stroke-linejoin="round">')
    for stroke in icon:
        if len(stroke) < 2:
            continue
        points = " ".join(f"{ox + x * side:.2f},{oy + y * side:.2f}"
                          for x, y in stroke)
        parts.append(f'<polyline points="{points}"/>')
    parts.append("</g></svg>")
    return "".join(parts)


def export_library(outdir: str, size: int = 200,
                   color: RGBA = (17, 19, 24, 255)) -> List[str]:
    """Write every icon to `outdir` as an SVG. Returns the written paths."""
    import os
    os.makedirs(outdir, exist_ok=True)
    written: List[str] = []
    for name in icon_library.names():
        path = os.path.join(outdir, f"{name}.svg")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(icon_to_svg(name, size, color))
        written.append(path)
    return written


def scene_to_svg(scene, width: int = 1920, height: int = 1080,
                 style=None) -> str:
    """A flat SVG preview of a planned scene — boxes, labels and icons.

    Used by the preview endpoint and by tests that need to assert on layout
    without running a full video render.
    """
    from ..styles import get_style
    st = style or get_style(getattr(scene, "style", None))
    parts: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="{_hex(st.bg)}"/>',
    ]
    for element in scene.ordered_elements():
        x1, y1, x2, y2 = element.box.pixels(width, height)
        if element.shape in ("card", "node", "panel", "hub", "frame", "row"):
            parts.append(
                f'<rect x="{x1}" y="{y1}" width="{x2 - x1}" height="{y2 - y1}" '
                f'rx="{st.corner_radius}" fill="{_hex(st.surface)}" '
                f'stroke="{_hex(st.accent)}" stroke-width="3"/>')
        if element.icon:
            side = min(x2 - x1, y2 - y1) * 0.4
            icon_svg = strokes_to_svg(
                icon_library.get(element.icon), int(side), int(side),
                st.accent, max(2.0, st.line_width * 0.5))
            inner = icon_svg.split(">", 1)[1].rsplit("</svg>", 1)[0]
            parts.append(f'<g transform="translate({x1 + 24},{y1 + 24})">{inner}</g>')
        if element.text:
            size = max(18, int((y2 - y1) * (0.34 if element.role == "title" else 0.22)))
            parts.append(
                f'<text x="{(x1 + x2) // 2}" y="{(y1 + y2) // 2 + size // 3}" '
                f'text-anchor="middle" font-size="{size}" '
                f'font-family="{st.font_title}, sans-serif" '
                f'fill="{_hex(st.ink)}">'
                f'{_escape(element.text)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _escape(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))
