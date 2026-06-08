"""
STEP 5 — Graphic overlays (PIL -> ProRes 4444 RGBA).

Renders animated graphics (counters, progress bars, lists, stat cards,
lower-thirds) frame-by-frame and pipes them to ffmpeg as ProRes 4444 with a
real alpha channel.

Anti-collision safe zone (px):
  * face   : y < 850 stays free
  * graphics: y in [800, 1340]
  * subs   : y ~ 1425  (TikTok-safe, distinct from overlays)

Persistence: the intro animation plays once, then the overlay HOLDS its final
state (counters/bars stay maxed) until the 0.20 s fade-out.  The clip length is
the topic duration (5-17 s), not the animation length.

Usage:
    python -m engine.overlays specs.json --outdir animations
    # or, from a transcript:
    python -m engine.overlays --from-vu transcripts/v_vu.json --outdir animations
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from PIL import Image, ImageDraw

from . import config
from . import content
from .fonts import load_font
from .render_utils import ProResPipe, alpha_fade, clamp, ease_out_back, ease_out_cube

# Palette
WHITE = (255, 255, 255, 255)
GOLD = (212, 175, 55, 255)
PANEL = (12, 14, 22, 205)
PANEL_BORDER = (212, 175, 55, 230)
ACCENT = (0, 220, 255, 255)

# Horizontal panel bounds (centred, inside the safe zone).
PANEL_X0, PANEL_X1 = 80, 1000


# --------------------------------------------------------------------------- #
# drawing helpers
# --------------------------------------------------------------------------- #
def _frame() -> Image.Image:
    return Image.new("RGBA", (config.WIDTH, config.HEIGHT), (0, 0, 0, 0))


def _panel(draw: ImageDraw.ImageDraw, box, radius=36, fill=PANEL, border=PANEL_BORDER, bw=3):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=border, width=bw)


def _text(draw, xy, text, font, fill=WHITE, anchor="la", stroke=4, stroke_fill=(0, 0, 0, 230)):
    draw.text(xy, text, font=font, fill=fill, anchor=anchor,
              stroke_width=stroke, stroke_fill=stroke_fill)


def _measure(draw, text, font) -> tuple[int, int]:
    l, t, r, b = draw.textbbox((0, 0), text, font=font, stroke_width=4)
    return r - l, b - t


def _fit_font(family: str, size: int, text: str, max_w: int, min_size: int = 28):
    """Largest font (<= size) of *family* whose *text* fits within *max_w*."""
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    s = size
    while s > min_size:
        font = load_font(family, s)
        if _measure(probe, text, font)[0] <= max_w:
            return font
        s -= 4
    return load_font(family, min_size)


def _apply_alpha(img: Image.Image, factor: float) -> Image.Image:
    if factor >= 0.999:
        return img
    r, g, b, a = img.split()
    a = a.point(lambda v: int(v * factor))
    return Image.merge("RGBA", (r, g, b, a))


def _fmt_number(value: float) -> str:
    if value is None:
        return ""
    if abs(value - round(value)) < 1e-6:
        return f"{int(round(value)):,}".replace(",", " ")
    return f"{value:,.1f}".replace(",", " ")


# --------------------------------------------------------------------------- #
# per-type renderers (draw the current animation state at local time t)
# --------------------------------------------------------------------------- #
def _intro(dur: float) -> float:
    return min(1.0, dur * 0.35)


def _count_time(dur: float) -> float:
    return min(1.6, dur * 0.45)


def _draw_lower_third(img, draw, t, dur, spec):
    p = ease_out_back(clamp(t / _intro(dur)))
    slide = int((1 - p) * 420)                       # slide in from the left
    y0 = 1100
    box = (PANEL_X0 - slide, y0, PANEL_X1 - slide, y0 + 190)
    _panel(draw, box, radius=28)
    # gold accent bar
    draw.rounded_rectangle((box[0] + 22, y0 + 28, box[0] + 34, y0 + 162), radius=6, fill=GOLD)
    max_w = (box[2] - box[0]) - 86
    title = spec.get("title", "")
    f_title = _fit_font("Montserrat", 60, title, max_w)
    f_sub = _fit_font("Montserrat", 34, spec.get("subtitle", ""), max_w)
    _text(draw, (box[0] + 56, y0 + 46), title, f_title, fill=WHITE, anchor="la")
    if spec.get("subtitle"):
        _text(draw, (box[0] + 58, y0 + 120), spec["subtitle"], f_sub, fill=GOLD, anchor="la", stroke=3)


def _draw_stat(img, draw, t, dur, spec):
    p = ease_out_cube(clamp(t / _intro(dur)))
    cy = 1075
    box = (PANEL_X0, cy - 170, PANEL_X1, cy + 170)
    _panel(draw, box)
    value = spec.get("value")
    if value is not None:
        shown = value * ease_out_cube(clamp(t / _count_time(dur)))
        big = _fmt_number(shown)
        suffix = "%" if "%" in str(spec.get("raw", "")) else ""
        big = big + suffix
    else:
        big = str(spec.get("raw", spec.get("title", "")))
    max_w = (box[2] - box[0]) - 80
    f_big = _fit_font("Anton", 150 if len(big) <= 5 else 110, big, max_w, min_size=60)
    f_lbl = _fit_font("Montserrat", 40, spec.get("label", ""), max_w)
    # pop-in scale via font already chosen; fade handled globally. Center text.
    _text(draw, (config.WIDTH // 2, cy - 30), big, f_big, fill=GOLD, anchor="mm", stroke=6)
    _text(draw, (config.WIDTH // 2, cy + 110), spec.get("label", ""), f_lbl, fill=WHITE, anchor="mm")
    _ = p  # intro reserved for future scale tween


def _draw_progress(img, draw, t, dur, spec):
    cy = 1075
    box = (PANEL_X0, cy - 130, PANEL_X1, cy + 130)
    _panel(draw, box)
    target = float(spec.get("percent", 0))
    shown = target * ease_out_cube(clamp(t / _count_time(dur)))
    f_pct = load_font("Anton", 64)
    pct_w = _measure(draw, "100%", f_pct)[0]
    lbl_max = (box[2] - box[0]) - 80 - pct_w - 30   # reserve room for the % on the right
    f_lbl = _fit_font("Montserrat", 42, spec.get("label", ""), lbl_max)
    _text(draw, (box[0] + 40, cy - 96), spec.get("label", ""), f_lbl, anchor="la")
    # bar track
    bx0, bx1 = box[0] + 40, box[1] + 0
    track = (box[0] + 40, cy + 10, box[2] - 40, cy + 56)
    draw.rounded_rectangle(track, radius=23, fill=(255, 255, 255, 40))
    fill_w = int((track[2] - track[0]) * shown / 100.0)
    if fill_w > 8:
        draw.rounded_rectangle((track[0], track[1], track[0] + fill_w, track[3]),
                               radius=23, fill=GOLD)
    _text(draw, (box[2] - 40, cy - 96), f"{shown:.0f}%", f_pct, fill=GOLD, anchor="ra")
    _ = (bx0, bx1)


def _draw_list(img, draw, t, dur, spec):
    items = spec.get("items", [])[:4]
    n = max(1, len(items))
    box = (PANEL_X0, 820, PANEL_X1, 820 + 90 + n * 110)
    box = (box[0], box[1], box[2], min(box[3], config.ZONE_OVERLAY_BOTTOM))
    _panel(draw, box)
    hdr_max = (box[2] - box[0]) - 80
    item_max = (box[2] - box[0]) - 132
    f_h = _fit_font("Montserrat", 44, spec.get("label", ""), hdr_max)
    _text(draw, (box[0] + 40, box[1] + 28), spec.get("label", ""), f_h, fill=GOLD, anchor="la")
    step = _count_time(dur) / n
    iy = box[1] + 110
    for i, item in enumerate(items):
        appear = clamp((t - i * step) / max(step, 0.2))
        if appear <= 0:
            continue
        slide = int((1 - ease_out_cube(appear)) * 120)
        # bullet
        draw.ellipse((box[0] + 44 - slide, iy + 16, box[0] + 70 - slide, iy + 42), fill=ACCENT)
        f_i = _fit_font("Montserrat", 40, item, item_max)
        _text(draw, (box[0] + 92 - slide, iy + 6), item, f_i, anchor="la", stroke=3)
        iy += 110


_RENDERERS = {
    "lower_third": _draw_lower_third,
    "stat": _draw_stat,
    "progress": _draw_progress,
    "list": _draw_list,
}


# --------------------------------------------------------------------------- #
# clip rendering
# --------------------------------------------------------------------------- #
def render_overlay(spec: dict, out_path: str, fps: int = config.FPS) -> str:
    dur = float(spec["duration"])
    n_frames = max(1, int(round(dur * fps)))
    renderer = _RENDERERS.get(spec.get("type"), _draw_stat)

    with ProResPipe(out_path, fps=fps) as pipe:
        for fi in range(n_frames):
            t = fi / fps
            img = _frame()
            draw = ImageDraw.Draw(img)
            renderer(img, draw, t, dur, spec)
            img = _apply_alpha(img, alpha_fade(t, dur))
            pipe.write(img)
    return out_path


def render_all(specs: List[dict], outdir: str) -> List[dict]:
    os.makedirs(outdir, exist_ok=True)
    out: List[dict] = []
    for spec in specs:
        path = os.path.join(outdir, f"{spec['id']}.mov")
        render_overlay(spec, path)
        out.append({**spec, "mov": path})
        print(f"[overlays] {spec['type']:12s} {spec['id']} ({spec['duration']:.1f}s) -> {path}")
    return out


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Render graphic overlays -> ProRes 4444 .mov")
    ap.add_argument("specs", nargs="?", help="JSON list of overlay specs")
    ap.add_argument("--from-vu", help="derive specs from a transcript _vu.json")
    ap.add_argument("--outdir", default="animations")
    ap.add_argument("--dump-specs", help="write derived specs to this path and exit")
    args = ap.parse_args(argv)

    if args.from_vu:
        vu = json.load(open(args.from_vu, encoding="utf-8"))
        specs = content.derive_overlay_specs(vu)
    elif args.specs:
        specs = json.load(open(args.specs, encoding="utf-8"))
    else:
        ap.error("provide specs.json or --from-vu")

    if args.dump_specs:
        json.dump(specs, open(args.dump_specs, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"[overlays] {len(specs)} specs -> {args.dump_specs}")
        return 0

    rendered = render_all(specs, args.outdir)
    json.dump(rendered, open(os.path.join(args.outdir, "_overlays.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
