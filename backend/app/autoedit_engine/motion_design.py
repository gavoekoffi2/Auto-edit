"""
STEP 6bis — MOTION DESIGN ILLUSTRÉ (PIL -> ProRes 4444 RGBA).

Full-frame animated scenes that DRAW what the speaker is explaining — not just
text.  Each scene takes over the frame for ~4.5-5.5 s while the voice keeps
talking, exactly like a pro explainer insert:

  * dark premium stage (gradient + drifting dot grid + vignette)
  * the ILLUSTRATION of the spoken idea:
      - AI flat-design image when available (``scene["image"]``), presented in
        a glowing rounded panel with pop-in, float and slow Ken Burns;
      - otherwise a PROCEDURAL line-art drawing (icon library below) that is
        drawn on screen stroke by stroke, whiteboard style;
  * hand-drawn animated doodles: curved arrows that draw themselves toward the
    illustration, a sketch circle around the headline, sparkles popping;
  * the headline keyword + kicker chip, numbered step pills (kind="steps") or
    an animated counter (kind="number");
  * entrance light-sweep + flash, exit fade — the SFX cues (riser, whoosh,
    pops on each element) are planned from the ``events`` this module exports.

Usage:
    python -m app.autoedit_engine.motion_design scenes.json --outdir motion_clips
    python -m app.autoedit_engine.motion_design --from-vu transcripts/v_vu.json --outdir motion_clips
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFilter

# Pillow-version-robust LANCZOS (Resampling moved in 9.1; constants vary by version).
try:
    _RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:  # Pillow < 9.1
    _RESAMPLE = Image.LANCZOS  # noqa: PIL legacy fallback

from . import config
from . import content
from .fonts import load_font
from .render_utils import ProResPipe, alpha_fade, clamp, ease_in_out, ease_out_back, ease_out_cube

W, H = config.WIDTH, config.HEIGHT
ACCENT = config.MOTION_ACCENT
GOLD = config.MOTION_GOLD
INK = config.MOTION_INK
# Stage background (mutable: varied per video by select_palette()).
BG_TOP = config.MOTION_BG_TOP
BG_BOTTOM = config.MOTION_BG_BOTTOM


def select_palette(seed_text: str, preset: Optional[str] = None) -> str:
    """Pick a per-video colour palette (accent/gold/background).

    When *preset* names a motion-design family it is used directly (the
    credit-saver edit drives this so the look varies per video in a
    reproducible way). Otherwise a stable seed of the spoken content chooses a
    family, so two different videos never share the same look — even when every
    scene falls back to the procedural drawings. Returns the chosen family name.
    """
    global ACCENT, GOLD, BG_TOP, BG_BOTTOM
    try:
        from . import motion_presets
        chosen = (motion_presets.preset_for(preset) if preset
                  else motion_presets.choose_preset(seed_text))
        BG_TOP, BG_BOTTOM, ACCENT, GOLD = chosen.palette()
        return chosen.name
    except Exception:
        # Fallback to the legacy palette table if presets are unavailable.
        palettes = getattr(config, "MOTION_PALETTES", None)
        if not palettes:
            return "default"
        import hashlib
        h = int(hashlib.md5((seed_text or "x").encode("utf-8")).hexdigest(), 16)
        bg_top, bg_bot, accent, gold = palettes[h % len(palettes)]
        BG_TOP, BG_BOTTOM = bg_top, bg_bot
        ACCENT, GOLD = accent, gold
        return "legacy"
STROKE_W = 14                      # doodle ink width (px)

# --------------------------------------------------------------------------- #
# scene LAYOUTS — distinct compositions, not just recoloured copies of the
# same template. A preset (motion_presets.py) only changes the colour/shape
# density; a layout changes WHERE things sit and HOW the background moves, so
# two scenes genuinely look like a different piece of design:
#
#   stage_center     signature look — centered panel, chip kicker, dot grid
#   split_panel      illustration as a wide letterboxed strip, single
#                     diagonal connector arrow, vertical drifting lines
#   badge_top        big illustration low on the frame, kicker+headline fused
#                     into a full-width ribbon banner across the top, rays
#   fullbleed_frame  illustration bleeds edge-to-edge, headline lives in a
#                     lower-third caption bar instead of floating mid-screen
#   corner_stack     small illustration tucked top-right, big vertical
#                     stacked kicker+headline chip pinned to the left edge,
#                     drifting diagonal corner wedges in the background
#   ticker_strip     illustration centered high, headline rides a bold
#                     horizontal marquee/ticker bar near the bottom, faint
#                     scrolling dash lines
#   frame_card       illustration sits inside a bracketed "card" with corner
#                     ticks (polaroid feel), headline centered just under the
#                     card, thin scanline shimmer in the background
#   diagonal_split   the frame is cut by a diagonal: illustration on one
#                     side, headline running along the cut on the other,
#                     a single bright diagonal seam sweeping slowly
#
# Eight structurally different compositions means a video with several
# motion-design beats can genuinely ALTERNATE between them instead of
# settling on one template for its whole length — and across videos the
# sequence is reshuffled (seeded by the spoken content) so two edits rarely
# walk through the layouts in the same order either.
# --------------------------------------------------------------------------- #
LAYOUTS = [
    "stage_center", "split_panel", "badge_top", "fullbleed_frame",
    "corner_stack", "ticker_strip", "frame_card", "diagonal_split",
]


def _layout_sequence(seed_text: str, n: int) -> List[str]:
    """A per-video shuffled rotation through every layout, never repeating
    the same one twice in a row, so a single video alternates between many
    designs instead of looping a short cycle.
    """
    import random
    rng = random.Random(seed_text or "x")
    seq: List[str] = []
    last: Optional[str] = None
    while len(seq) < n:
        pool = list(LAYOUTS)
        rng.shuffle(pool)
        if last is not None and pool[0] == last and len(pool) > 1:
            pool[0], pool[1] = pool[1], pool[0]
        seq.extend(pool)
        last = seq[-1]
    return seq[:n]

# Scene animation timeline (seconds from scene start).  These are the moments
# plan_overlays converts into per-element SFX cues.
T_ILLU = 0.12        # illustration pop / draw-on starts
T_KICKER = 0.05
T_HEADLINE = 0.42
T_UNDERLINE = 0.75
T_CIRCLE = 0.85
T_ARROWS = 0.95
T_ELEMENTS = 1.05    # first step pill / counter start
STEP_STAGGER = 0.50
EXIT_FADE = 0.22


# --------------------------------------------------------------------------- #
# procedural icon library — every stroke is a polyline in normalized [0,1]²
# coordinates; the renderer reveals them progressively (draw-on / whiteboard).
# --------------------------------------------------------------------------- #
Stroke = List[Tuple[float, float]]


def _arc(cx: float, cy: float, r: float, a0: float, a1: float, n: int = 28,
         ry: Optional[float] = None) -> Stroke:
    ry = r if ry is None else ry
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n),
             cy + ry * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def _icon_money() -> List[Stroke]:
    rect = [(0.08, 0.28), (0.92, 0.28), (0.92, 0.72), (0.08, 0.72), (0.08, 0.28)]
    return [rect, _arc(0.5, 0.5, 0.13, 0, 2 * math.pi),
            [(0.18, 0.44), (0.18, 0.56)], [(0.82, 0.44), (0.82, 0.56)]]


def _icon_growth() -> List[Stroke]:
    return [[(0.10, 0.12), (0.10, 0.88), (0.92, 0.88)],
            [(0.16, 0.74), (0.36, 0.56), (0.52, 0.64), (0.86, 0.24)],
            [(0.70, 0.24), (0.86, 0.24), (0.86, 0.40)]]


def _icon_phone() -> List[Stroke]:
    rect = [(0.30, 0.06), (0.70, 0.06), (0.70, 0.94), (0.30, 0.94), (0.30, 0.06)]
    return [rect, [(0.42, 0.14), (0.58, 0.14)], _arc(0.5, 0.84, 0.035, 0, 2 * math.pi)]


def _icon_people() -> List[Stroke]:
    return [_arc(0.36, 0.30, 0.13, 0, 2 * math.pi),
            _arc(0.36, 0.80, 0.24, math.pi, 2 * math.pi),
            _arc(0.72, 0.36, 0.10, 0, 2 * math.pi),
            _arc(0.72, 0.76, 0.18, math.pi, 2 * math.pi)]


def _icon_cart() -> List[Stroke]:
    return [[(0.06, 0.18), (0.20, 0.18), (0.32, 0.62), (0.82, 0.62), (0.92, 0.30), (0.28, 0.30)],
            _arc(0.40, 0.78, 0.06, 0, 2 * math.pi), _arc(0.74, 0.78, 0.06, 0, 2 * math.pi)]


def _icon_idea() -> List[Stroke]:
    return [_arc(0.5, 0.40, 0.22, -0.25 * math.pi, 1.25 * math.pi),
            [(0.40, 0.62), (0.40, 0.74), (0.60, 0.74), (0.60, 0.62)],
            [(0.43, 0.82), (0.57, 0.82)],
            [(0.5, 0.06), (0.5, 0.13)], [(0.18, 0.18), (0.26, 0.24)],
            [(0.82, 0.18), (0.74, 0.24)], [(0.10, 0.44), (0.19, 0.44)],
            [(0.90, 0.44), (0.81, 0.44)]]


def _icon_target() -> List[Stroke]:
    return [_arc(0.5, 0.55, 0.34, 0, 2 * math.pi), _arc(0.5, 0.55, 0.18, 0, 2 * math.pi),
            [(0.86, 0.10), (0.56, 0.50)],
            [(0.74, 0.10), (0.86, 0.10), (0.86, 0.22)]]


def _icon_gear() -> List[Stroke]:
    strokes = [_arc(0.5, 0.5, 0.26, 0, 2 * math.pi), _arc(0.5, 0.5, 0.10, 0, 2 * math.pi)]
    for k in range(8):
        a = k * math.pi / 4
        strokes.append([(0.5 + 0.28 * math.cos(a), 0.5 + 0.28 * math.sin(a)),
                        (0.5 + 0.40 * math.cos(a), 0.5 + 0.40 * math.sin(a))])
    return strokes


def _icon_book() -> List[Stroke]:
    return [[(0.5, 0.22), (0.5, 0.82)],
            [(0.5, 0.22), (0.30, 0.14), (0.08, 0.18), (0.08, 0.78), (0.30, 0.74), (0.5, 0.82)],
            [(0.5, 0.22), (0.70, 0.14), (0.92, 0.18), (0.92, 0.78), (0.70, 0.74), (0.5, 0.82)],
            [(0.18, 0.34), (0.40, 0.28)], [(0.60, 0.28), (0.82, 0.34)]]


def _icon_megaphone() -> List[Stroke]:
    return [[(0.10, 0.40), (0.10, 0.62), (0.30, 0.62), (0.66, 0.84), (0.66, 0.18), (0.30, 0.40), (0.10, 0.40)],
            [(0.30, 0.62), (0.34, 0.86), (0.46, 0.86)],
            _arc(0.74, 0.51, 0.10, -0.4 * math.pi, 0.4 * math.pi),
            _arc(0.74, 0.51, 0.20, -0.4 * math.pi, 0.4 * math.pi)]


def _icon_shield() -> List[Stroke]:
    return [[(0.5, 0.06), (0.88, 0.20), (0.88, 0.52), (0.5, 0.94), (0.12, 0.52), (0.12, 0.20), (0.5, 0.06)],
            [(0.32, 0.46), (0.46, 0.62), (0.72, 0.30)]]


def _icon_clock() -> List[Stroke]:
    return [_arc(0.5, 0.5, 0.38, 0, 2 * math.pi),
            [(0.5, 0.26), (0.5, 0.5), (0.70, 0.62)]]


def _icon_rocket() -> List[Stroke]:
    return [[(0.5, 0.04), (0.68, 0.30), (0.68, 0.62), (0.32, 0.62), (0.32, 0.30), (0.5, 0.04)],
            _arc(0.5, 0.34, 0.08, 0, 2 * math.pi),
            [(0.32, 0.48), (0.14, 0.70), (0.32, 0.66)],
            [(0.68, 0.48), (0.86, 0.70), (0.68, 0.66)],
            [(0.44, 0.66), (0.40, 0.84)], [(0.5, 0.66), (0.5, 0.92)], [(0.56, 0.66), (0.60, 0.84)]]


def _icon_map() -> List[Stroke]:
    drop = _arc(0.5, 0.42, 0.26, math.pi * 0.13, math.pi * 0.87)
    drop = [(0.5, 0.92)] + drop[::-1] + [(0.5, 0.92)]
    return [drop, _arc(0.5, 0.40, 0.10, 0, 2 * math.pi)]


ICONS: Dict[str, List[Stroke]] = {
    "money": _icon_money(), "growth": _icon_growth(), "phone": _icon_phone(),
    "people": _icon_people(), "cart": _icon_cart(), "idea": _icon_idea(),
    "target": _icon_target(), "gear": _icon_gear(), "book": _icon_book(),
    "megaphone": _icon_megaphone(), "shield": _icon_shield(),
    "clock": _icon_clock(), "rocket": _icon_rocket(), "map": _icon_map(),
}


# --------------------------------------------------------------------------- #
# draw-on stroke helpers
# --------------------------------------------------------------------------- #
def _seg_len(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _strokes_total_len(strokes: Sequence[Stroke]) -> float:
    return sum(_seg_len(a, b) for s in strokes for a, b in zip(s, s[1:])) or 1e-6


def _partial_strokes(strokes: Sequence[Stroke], frac: float) -> List[Stroke]:
    """Reveal the strokes progressively along their cumulative length."""
    frac = clamp(frac)
    if frac >= 0.999:
        return list(strokes)
    budget = _strokes_total_len(strokes) * frac
    out: List[Stroke] = []
    for stroke in strokes:
        if budget <= 0:
            break
        partial: Stroke = [stroke[0]]
        for a, b in zip(stroke, stroke[1:]):
            d = _seg_len(a, b)
            if d <= budget:
                partial.append(b)
                budget -= d
            else:
                t = budget / d if d > 0 else 0.0
                partial.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
                budget = 0
                break
        if len(partial) > 1:
            out.append(partial)
    return out


def _draw_strokes(draw: ImageDraw.ImageDraw, strokes: Sequence[Stroke],
                  box: Tuple[float, float, float, float], color, width: int = STROKE_W):
    """Draw normalized strokes inside *box* with round caps/joints."""
    x0, y0, x1, y1 = box
    sw, sh = x1 - x0, y1 - y0
    r = width / 2
    for stroke in strokes:
        pts = [(x0 + px * sw, y0 + py * sh) for px, py in stroke]
        if len(pts) < 2:
            continue
        draw.line(pts, fill=color, width=width, joint="curve")
        for cap in (pts[0], pts[-1]):
            draw.ellipse((cap[0] - r, cap[1] - r, cap[0] + r, cap[1] + r), fill=color)


def _bezier(p0, p1, p2, n: int = 36) -> Stroke:
    pts: Stroke = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        pts.append((x, y))
    return pts


def _arrow_strokes(p0, p1, p2, head: float = 34.0) -> List[Stroke]:
    """A curved hand-drawn arrow (quadratic bezier) + its arrowhead."""
    body = _bezier(p0, p1, p2)
    (ax, ay), (bx, by) = body[-2], body[-1]
    ang = math.atan2(by - ay, bx - ax)
    head_l = [(bx - head * math.cos(ang - 0.5), by - head * math.sin(ang - 0.5)), (bx, by)]
    head_r = [(bx - head * math.cos(ang + 0.5), by - head * math.sin(ang + 0.5)), (bx, by)]
    return [body, head_l, head_r]


def _sketch_ellipse(cx: float, cy: float, rx: float, ry: float,
                    turns: float = 1.12, n: int = 64, wobble: float = 5.0) -> Stroke:
    """A hand-sketched ellipse (slight radius wobble, > 1 full turn)."""
    pts: Stroke = []
    total = 2 * math.pi * turns
    for i in range(n + 1):
        a = -0.5 * math.pi + total * i / n
        wob = wobble * math.sin(a * 3.1 + 0.7)
        pts.append((cx + (rx + wob) * math.cos(a), cy + (ry + wob * 0.6) * math.sin(a)))
    return pts


# --------------------------------------------------------------------------- #
# stage (background) + small ui helpers
# --------------------------------------------------------------------------- #
def _stage_base() -> Image.Image:
    """Opaque gradient stage + vignette, computed once per scene.

    The vignette is alpha_composite'd (NOT pasted) so the stage stays fully
    opaque — the scene is a real takeover, nothing may bleed through from the
    video underneath.
    """
    grad = Image.new("RGB", (1, H))
    top, bot = BG_TOP, BG_BOTTOM
    px = grad.load()
    for y in range(H):
        t = y / (H - 1)
        px[0, y] = tuple(int(top[c] + (bot[c] - top[c]) * t) for c in range(3))
    base = grad.resize((W, H)).convert("RGBA")

    vig = Image.new("L", (W, H), 0)
    dv = ImageDraw.Draw(vig)
    dv.ellipse((-W * 0.35, -H * 0.20, W * 1.35, H * 1.20), fill=255)
    shade_a = vig.filter(ImageFilter.GaussianBlur(160)).point(lambda v: (255 - v) * 110 // 255)
    zero = Image.new("L", (W, H), 0)
    shade = Image.merge("RGBA", (zero, zero, zero, shade_a))
    return Image.alpha_composite(base, shade)


def _dots_layer(t: float) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    drift = 10.0 * math.sin(t * 0.6)
    for gy in range(120, H - 60, 96):
        for gx in range(60, W, 96):
            x = gx + drift * (1 if (gy // 96) % 2 == 0 else -1)
            d.ellipse((x - 2, gy - 2, x + 2, gy + 2), fill=(255, 255, 255, 16))
    return layer


def _lines_layer(t: float) -> Image.Image:
    """split_panel motif: slow vertical drifting hairlines."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    drift = 18.0 * math.sin(t * 0.35)
    for gx in range(40, W, 84):
        x = gx + drift
        d.line([(x, 0), (x, H)], fill=(255, 255, 255, 10), width=2)
    return layer


def _rays_layer(t: float) -> Image.Image:
    """badge_top motif: faint rays radiating from the top-center banner."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = W // 2, 140
    spin = t * 0.15
    for k in range(14):
        a = spin + k * (2 * math.pi / 14)
        x2, y2 = cx + math.cos(a) * 1400, cy + math.sin(a) * 1400
        d.line([(cx, cy), (x2, y2)], fill=(255, 255, 255, 9), width=3)
    return layer


def _grain_layer(t: float) -> Image.Image:
    """fullbleed_frame motif: sparse drifting dust specks over the bleed image."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    drift = 14.0 * math.sin(t * 0.5)
    for gy in range(80, H, 140):
        for gx in range(40, W, 140):
            x = gx + drift * (1 if (gy // 140) % 2 == 0 else -1)
            y = gy + drift * 0.4
            d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 255, 255, 12))
    return layer


def _wedges_layer(t: float) -> Image.Image:
    """corner_stack motif: drifting diagonal wedges from the top-left corner."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    drift = 12.0 * math.sin(t * 0.45)
    for k in range(6):
        off = k * 220 + drift
        d.line([(-200 + off, -200), (1400 + off, 1000)], fill=(255, 255, 255, 11), width=14)
    return layer


def _ticker_layer(t: float) -> Image.Image:
    """ticker_strip motif: faint horizontal dashes scrolling sideways."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    scroll = (t * 140) % 120
    for gy in range(160, H, 220):
        for gx in range(-120, W + 120, 120):
            x = gx - scroll
            d.line([(x, gy), (x + 60, gy)], fill=(255, 255, 255, 12), width=4)
    return layer


def _scanlines_layer(t: float) -> Image.Image:
    """frame_card motif: thin shimmering scanlines drifting downward."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    shift = (t * 60) % 48
    for y in range(int(-48 + shift), H, 48):
        d.line([(0, y), (W, y)], fill=(255, 255, 255, 7), width=2)
    return layer


def _diagonal_seam_layer(t: float) -> Image.Image:
    """diagonal_split motif: a single bright seam sweeping slowly across."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    drift = 30.0 * math.sin(t * 0.3)
    cx = W * 0.42 + drift
    d.line([(cx - H * 0.5, 0), (cx + H * 0.5, H)], fill=(255, 255, 255, 26), width=6)
    return layer


def _bg_motif(layout: str, t: float) -> Image.Image:
    if layout == "split_panel":
        return _lines_layer(t)
    if layout == "badge_top":
        return _rays_layer(t)
    if layout == "fullbleed_frame":
        return _grain_layer(t)
    if layout == "corner_stack":
        return _wedges_layer(t)
    if layout == "ticker_strip":
        return _ticker_layer(t)
    if layout == "frame_card":
        return _scanlines_layer(t)
    if layout == "diagonal_split":
        return _diagonal_seam_layer(t)
    return _dots_layer(t)


def _light_sweep(progress: float) -> Image.Image:
    """Diagonal white sweep crossing the frame (entrance transition)."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    pos = (progress * 1.6 - 0.3) * (W + H)
    band = 180
    for off in range(-band, band, 8):
        a = int(120 * math.exp(-((off / 110.0) ** 2)))
        if a <= 2:
            continue
        d.line([(pos + off - H, H), (pos + off, 0)], fill=(255, 255, 255, a), width=8)
    return layer


def _fit_font(family: str, size: int, text: str, max_w: int, min_size: int = 30):
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    s = size
    while s > min_size:
        font = load_font(family, s)
        l, t, r, b = probe.textbbox((0, 0), text, font=font, stroke_width=3)
        if r - l <= max_w:
            return font
        s -= 4
    return load_font(family, min_size)


def _apply_alpha(img: Image.Image, factor: float) -> Image.Image:
    if factor >= 0.999:
        return img
    r, g, b, a = img.split()
    a = a.point(lambda v: int(v * factor))
    return Image.merge("RGBA", (r, g, b, a))


def _rounded_image(img: Image.Image, radius: int = 44) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width, img.height), radius=radius, fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def _fmt_value(value: float, raw: str) -> str:
    suffix = "%" if "%" in (raw or "") else ""
    if abs(value - round(value)) < 1e-6:
        return f"{int(round(value)):,}".replace(",", " ") + suffix
    return f"{value:,.1f}".replace(",", " ") + suffix


# --------------------------------------------------------------------------- #
# scene rendering
# --------------------------------------------------------------------------- #
def _illu_box(kind: str, layout: str = "stage_center") -> Tuple[int, int, int, int]:
    """Bounds of the illustration zone — varies by *layout* (see LAYOUTS),
    not just by *kind* (steps/number scenes always keep extra room for text).
    """
    if kind == "steps":
        return (210, 330, W - 210, 950)
    if kind == "number":
        return (170, 330, W - 170, 1000)
    if layout == "split_panel":
        return (70, 470, W - 70, 1240)        # wide letterboxed strip, lower
    if layout == "badge_top":
        return (130, 600, W - 130, 1430)      # big panel, room for top ribbon
    if layout == "fullbleed_frame":
        return (0, 210, W, 1540)              # edge-to-edge bleed
    if layout == "corner_stack":
        return (430, 300, W - 60, 1080)       # tucked top-right, room left for the stack
    if layout == "ticker_strip":
        return (140, 260, W - 140, 1280)      # centered high, room low for the ticker bar
    if layout == "frame_card":
        return (160, 300, W - 160, 1220)      # bracketed card, room below for headline
    if layout == "diagonal_split":
        return (340, 360, W - 60, 1300)       # right-of-seam, headline runs along the cut
    return (120, 330, W - 120, 1130)          # stage_center (signature look)


def _pop(t: float, start: float, dur: float = 0.45) -> float:
    return ease_out_back(clamp((t - start) / dur))


def _linear(t: float, start: float, dur: float) -> float:
    return clamp((t - start) / dur)


def _draw_kicker(draw: ImageDraw.ImageDraw, target: Image.Image, text: str, t: float):
    p = _pop(t, T_KICKER, 0.35)
    if p <= 0:
        return
    font = load_font("Montserrat", 40)
    l, tt, r, b = draw.textbbox((0, 0), text, font=font)
    tw, th = r - l, b - tt
    pad_x, pad_y = 36, 16
    cw, ch = int((tw + 2 * pad_x) * (0.6 + 0.4 * p)), int((th + 2 * pad_y) * (0.6 + 0.4 * p))
    x0, y0 = (W - cw) // 2, 196 - ch // 2 + 40
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dl = ImageDraw.Draw(layer)
    dl.rounded_rectangle((x0, y0, x0 + cw, y0 + ch), radius=ch // 2,
                         fill=(12, 14, 22, 215), outline=GOLD, width=4)
    if p > 0.55:
        f2 = load_font("Montserrat", int(40 * min(1.0, p)))
        dl.text((W // 2, y0 + ch // 2), text, font=f2, fill=GOLD, anchor="mm")
    target.alpha_composite(layer)


def _draw_headline(draw: ImageDraw.ImageDraw, headline: str, t: float, y: int):
    p = _pop(t, T_HEADLINE, 0.4)
    if p <= 0:
        return
    font = _fit_font("Anton", 132, headline, 940, min_size=64)
    # pop via font size approximation: draw at full size, fade quickly
    a = int(255 * clamp(p * 1.6))
    draw.text((W // 2, y), headline, font=font, anchor="mm",
              fill=(255, 255, 255, a), stroke_width=6, stroke_fill=(0, 0, 0, min(a, 230)))
    # underline draw-on
    up = ease_out_cube(_linear(t, T_UNDERLINE, 0.35))
    if up > 0:
        l, tt, r, b = draw.textbbox((W // 2, y), headline, font=font, anchor="mm")
        width = (r - l) * 0.92 * up
        draw.line([(W // 2 - width / 2, b + 26), (W // 2 + width / 2, b + 26)],
                  fill=GOLD, width=10)


def _draw_headline_circle(draw: ImageDraw.ImageDraw, headline: str, t: float, y: int):
    p = _linear(t, T_CIRCLE, 0.45)
    if p <= 0 or len(headline) > 14:
        return
    font = _fit_font("Anton", 132, headline, 940, min_size=64)
    l, tt, r, b = draw.textbbox((W // 2, y), headline, font=font, anchor="mm")
    rx, ry = (r - l) / 2 + 70, (b - tt) / 2 + 44
    sketch = _sketch_ellipse(W // 2, y, rx, ry)
    _draw_strokes(draw, _partial_strokes([sketch], ease_in_out(p)),
                  (0, 0, 1, 1), ACCENT, width=8)


def _draw_arrows(draw: ImageDraw.ImageDraw, t: float, box: Tuple[int, int, int, int]):
    x0, y0, x1, y1 = box
    cy = (y0 + y1) // 2
    left = _arrow_strokes((70, y1 + 130), (40, cy + 120), (x0 + 30, cy + 60))
    right = _arrow_strokes((W - 70, y0 - 90), (W - 30, y0 + 60), (x1 - 26, y0 + 130))
    pl = ease_in_out(_linear(t, T_ARROWS, 0.5))
    pr = ease_in_out(_linear(t, T_ARROWS + 0.20, 0.5))
    if pl > 0:
        _draw_strokes(draw, _partial_strokes(left, pl), (0, 0, 1, 1), ACCENT, width=11)
    if pr > 0:
        _draw_strokes(draw, _partial_strokes(right, pr), (0, 0, 1, 1), GOLD, width=11)


def _draw_arrow_diagonal(draw: ImageDraw.ImageDraw, t: float, box: Tuple[int, int, int, int]):
    """split_panel layout: a single bold diagonal connector, headline -> panel."""
    x0, y0, x1, y1 = box
    arrow = _arrow_strokes((W - 140, 300), (W // 2 + 40, 360), (x1 - 40, y0 + 70))
    p = ease_in_out(_linear(t, T_ARROWS, 0.55))
    if p > 0:
        _draw_strokes(draw, _partial_strokes(arrow, p), (0, 0, 1, 1), GOLD, width=13)


def _draw_ribbon_banner(draw: ImageDraw.ImageDraw, target: Image.Image,
                        kicker: str, headline: str, t: float):
    """badge_top layout: kicker + headline fused into a full-width top ribbon."""
    p = _pop(t, T_KICKER, 0.4)
    if p <= 0:
        return
    h = int(300 * (0.5 + 0.5 * p))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dl = ImageDraw.Draw(layer)
    dl.rectangle((0, 0, W, h), fill=(10, 10, 14, 230))
    dl.line([(0, h), (W, h)], fill=GOLD, width=6)
    if p > 0.4:
        fk = load_font("Montserrat", 38)
        dl.text((W // 2, max(40, h - 200)), kicker, font=fk, fill=GOLD, anchor="mm")
    if p > 0.6:
        fh = _fit_font("Anton", 108, headline, 980, min_size=56)
        a = int(255 * clamp((p - 0.6) / 0.4))
        dl.text((W // 2, max(120, h - 100)), headline, font=fh, anchor="mm",
                fill=(255, 255, 255, a), stroke_width=5, stroke_fill=(0, 0, 0, min(a, 230)))
    target.alpha_composite(layer)


def _draw_caption_bar(draw: ImageDraw.ImageDraw, target: Image.Image,
                      kicker: str, headline: str, t: float):
    """fullbleed_frame layout: headline lives in a lower-third caption bar."""
    p = _pop(t, T_HEADLINE, 0.4)
    if p <= 0:
        return
    y0 = H - int(360 * (0.5 + 0.5 * p))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dl = ImageDraw.Draw(layer)
    dl.rectangle((0, y0, W, H), fill=(8, 8, 12, 215))
    dl.line([(0, y0), (W, y0)], fill=ACCENT, width=6)
    fk = load_font("Montserrat", 36)
    dl.text((90, y0 + 60), kicker.upper(), font=fk, fill=GOLD, anchor="lm")
    fh = _fit_font("Anton", 104, headline, W - 180, min_size=54)
    a = int(255 * clamp(p * 1.6))
    dl.text((90, y0 + 170), headline, font=fh, anchor="lm",
            fill=(255, 255, 255, a), stroke_width=5, stroke_fill=(0, 0, 0, min(a, 230)))
    target.alpha_composite(layer)


def _draw_corner_stack(draw: ImageDraw.ImageDraw, target: Image.Image,
                       kicker: str, headline: str, t: float):
    """corner_stack layout: kicker + headline stacked vertically, pinned left."""
    p = _pop(t, T_KICKER, 0.4)
    if p <= 0:
        return
    w = int(360 * (0.5 + 0.5 * p))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dl = ImageDraw.Draw(layer)
    dl.rounded_rectangle((40, 280, 40 + w, 1080), radius=36,
                         fill=(10, 10, 14, 225), outline=GOLD, width=4)
    if p > 0.35:
        fk = load_font("Montserrat", 36)
        dl.text((40 + w // 2, 360), kicker.upper(), font=fk, fill=GOLD, anchor="mm")
    if p > 0.55:
        fh = _fit_font("Anton", 92, headline, w - 70, min_size=46)
        a = int(255 * clamp((p - 0.55) / 0.45))
        # wrap onto a few lines so a long headline fits the narrow stack
        words = headline.split()
        lines: List[str] = []
        cur = ""
        for word in words:
            probe = (cur + " " + word).strip()
            if draw.textbbox((0, 0), probe, font=fh)[2] <= w - 70 or not cur:
                cur = probe
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        ly = 520
        for line in lines[:4]:
            dl.text((40 + w // 2, ly), line, font=fh, anchor="mm",
                    fill=(255, 255, 255, a), stroke_width=5, stroke_fill=(0, 0, 0, min(a, 230)))
            ly += 130
    target.alpha_composite(layer)


def _draw_ticker_bar(draw: ImageDraw.ImageDraw, target: Image.Image,
                     kicker: str, headline: str, t: float):
    """ticker_strip layout: headline rides a bold marquee bar near the bottom."""
    p = _pop(t, T_HEADLINE, 0.4)
    if p <= 0:
        return
    h = int(220 * (0.5 + 0.5 * p))
    y0 = 1370
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dl = ImageDraw.Draw(layer)
    dl.rectangle((0, y0, W, y0 + h), fill=GOLD)
    fh = _fit_font("Anton", 96, headline, W - 140, min_size=48)
    a = int(255 * clamp(p * 1.6))
    dl.text((W // 2, y0 + h // 2 + 10), headline, font=fh, anchor="mm",
            fill=(10, 10, 14, a))
    fk = load_font("Montserrat", 34)
    dl.text((W // 2, y0 - 36), kicker.upper(), font=fk, fill=ACCENT, anchor="mm")
    target.alpha_composite(layer)


def _draw_card_caption(draw: ImageDraw.ImageDraw, target: Image.Image,
                       kicker: str, headline: str, t: float,
                       box: Tuple[int, int, int, int]):
    """frame_card layout: bracketed corner ticks around the card + caption below."""
    x0, y0, x1, y1 = box
    p = _pop(t, T_ILLU, 0.4)
    if p > 0:
        tick = 56
        col = GOLD
        for cx, cy, dx, dy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
            draw.line([(cx, cy), (cx + dx * tick, cy)], fill=col, width=8)
            draw.line([(cx, cy), (cx, cy + dy * tick)], fill=col, width=8)
    hp = _pop(t, T_HEADLINE, 0.4)
    if hp <= 0:
        return
    fk = load_font("Montserrat", 36)
    draw.text((W // 2, y1 + 70), kicker.upper(), font=fk, fill=GOLD, anchor="mm")
    fh = _fit_font("Anton", 110, headline, W - 200, min_size=56)
    a = int(255 * clamp(hp * 1.6))
    draw.text((W // 2, y1 + 180), headline, font=fh, anchor="mm",
              fill=(255, 255, 255, a), stroke_width=5, stroke_fill=(0, 0, 0, min(a, 230)))


def _draw_diagonal_caption(draw: ImageDraw.ImageDraw, target: Image.Image,
                           kicker: str, headline: str, t: float):
    """diagonal_split layout: headline runs vertically down the left seam."""
    p = _pop(t, T_HEADLINE, 0.4)
    if p <= 0:
        return
    fk = load_font("Montserrat", 36)
    draw.text((150, 420), kicker.upper(), font=fk, fill=GOLD, anchor="lm")
    fh = _fit_font("Anton", 100, headline, 360, min_size=48)
    a = int(255 * clamp(p * 1.6))
    words = headline.split()
    lines: List[str] = []
    cur = ""
    for word in words:
        probe = (cur + " " + word).strip()
        if draw.textbbox((0, 0), probe, font=fh)[2] <= 360 or not cur:
            cur = probe
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    ly = 540
    for line in lines[:4]:
        draw.text((150, ly), line, font=fh, anchor="lm",
                  fill=(255, 255, 255, a), stroke_width=5, stroke_fill=(0, 0, 0, min(a, 230)))
        ly += 130


def _draw_sparkles(draw: ImageDraw.ImageDraw, t: float, box: Tuple[int, int, int, int]):
    x0, y0, x1, y1 = box
    spots = [(x0 + 30, y0 - 40, 1.30), (x1 - 40, y1 - 20, 1.55), (x0 + 80, y1 + 40, 1.80)]
    for cx, cy, t0 in spots:
        p = _pop(t, t0, 0.3)
        if p <= 0:
            continue
        s = 16 + 14 * p
        a = int(235 * clamp(2.2 - abs(p * 2 - 1)))
        col = (255, 255, 255, max(0, min(255, a)))
        draw.line([(cx - s, cy), (cx + s, cy)], fill=col, width=7)
        draw.line([(cx, cy - s), (cx, cy + s)], fill=col, width=7)


def _paste_illustration(canvas: Image.Image, illu: Image.Image, t: float, dur: float,
                        box: Tuple[int, int, int, int]):
    """AI illustration: rounded panel + glow border, pop + float + Ken Burns."""
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    p = _pop(t, T_ILLU, 0.5)
    if p <= 0:
        return
    kb = 1.0 + 0.06 * ease_in_out(clamp(t / dur))
    scale = (0.55 + 0.45 * min(p, 1.06)) * kb
    # cover-fit the source into the panel
    ratio = max(bw / illu.width, bh / illu.height)
    iw, ih = int(illu.width * ratio * scale), int(illu.height * ratio * scale)
    img = illu.resize((max(1, iw), max(1, ih)), _RESAMPLE)
    left, top = (img.width - bw) // 2, (img.height - bh) // 2
    img = img.crop((left, top, left + bw, top + bh))
    img = _rounded_image(img)

    float_y = int(8 * math.sin(2 * math.pi * 0.4 * t))
    px, py = x0, y0 + float_y
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dg = ImageDraw.Draw(glow)
    for grow, alpha in ((26, 28), (14, 55)):
        dg.rounded_rectangle((px - grow, py - grow, px + bw + grow, py + bh + grow),
                             radius=44 + grow, outline=(ACCENT[0], ACCENT[1], ACCENT[2], alpha),
                             width=grow)
    canvas.alpha_composite(glow)
    canvas.alpha_composite(img, (px, py))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((px, py, px + bw, py + bh), radius=44, outline=ACCENT, width=5)


def _draw_icon_drawing(target: Image.Image, icon: str, t: float, dur: float,
                       box: Tuple[int, int, int, int]):
    """Procedural fallback: the line-art icon draws itself, whiteboard style."""
    strokes = ICONS.get(icon, ICONS[content.DEFAULT_ICON])
    p = ease_in_out(_linear(t, T_ILLU, 1.1))
    if p <= 0:
        return
    x0, y0, x1, y1 = box
    side = min(x1 - x0, y1 - y0) - 120
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2 + int(8 * math.sin(2 * math.pi * 0.4 * t))
    d = ImageDraw.Draw(target)
    # soft panel behind the drawing
    d.rounded_rectangle((x0, cy - (y1 - y0) // 2, x1, cy + (y1 - y0) // 2), radius=44,
                        fill=(16, 20, 34, 235), outline=(255, 255, 255, 36), width=3)
    ibox = (cx - side / 2, cy - side / 2, cx + side / 2, cy + side / 2)
    _draw_strokes(d, _partial_strokes(strokes, p), ibox, INK, width=STROKE_W)
    # accent re-draw: a second colored pass chases the white ink
    p2 = ease_in_out(_linear(t, T_ILLU + 0.35, 1.1))
    if p2 > 0:
        _draw_strokes(d, _partial_strokes(strokes, p2 * 0.999), ibox, ACCENT, width=6)


def _draw_steps(draw: ImageDraw.ImageDraw, steps: List[str], t: float) -> List[float]:
    """Numbered step pills, staggered pop + connector arrows. Returns event times."""
    events: List[float] = []
    n = min(4, len(steps))
    top = 1000
    row_h = 92
    gap = 18
    for i in range(n):
        t0 = T_ELEMENTS + i * STEP_STAGGER
        events.append(t0)
        p = _pop(t, t0, 0.4)
        if p <= 0:
            continue
        slide = int((1 - ease_out_cube(clamp(p))) * 160)
        y0 = top + i * (row_h + gap)
        x0 = 120 - slide if i % 2 == 0 else 120 + slide
        x1 = x0 + W - 240
        draw.rounded_rectangle((x0, y0, x1, y0 + row_h), radius=row_h // 2,
                               fill=(16, 20, 34, 225), outline=ACCENT, width=3)
        badge_r = 30
        bx, by = x0 + 52, y0 + row_h // 2
        draw.ellipse((bx - badge_r, by - badge_r, bx + badge_r, by + badge_r), fill=GOLD)
        f_n = load_font("Anton", 40)
        draw.text((bx, by - 2), str(i + 1), font=f_n, fill=(20, 16, 6, 255), anchor="mm")
        f_s = _fit_font("Montserrat", 42, steps[i], x1 - x0 - 160)
        draw.text((bx + 56, by), steps[i], font=f_s, fill=(255, 255, 255, 255), anchor="lm")
    return events


def _draw_counter(draw: ImageDraw.ImageDraw, value: float, raw: str, t: float) -> List[float]:
    t0 = T_ELEMENTS
    p = ease_out_cube(_linear(t, t0, 1.3))
    if p <= 0:
        return [t0]
    shown = _fmt_value(value * p, raw)
    font = _fit_font("Anton", 200, _fmt_value(value, raw), 880, min_size=90)
    draw.text((W // 2, 1110), shown, font=font, fill=GOLD, anchor="mm",
              stroke_width=8, stroke_fill=(0, 0, 0, 235))
    return [t0]


# --------------------------------------------------------------------------- #
# scene entrance / exit transitions (variants cycled per scene)
# --------------------------------------------------------------------------- #
ENTRANCE_DUR = 0.5
EXIT_MOTION_DUR = 0.38


def _iris(canvas: Image.Image, p: float, closing: bool = False) -> Image.Image:
    """Circular reveal (or close) of the whole scene, with an accent ring."""
    p = clamp(p)
    radius = (1.0 - p if closing else p) * math.hypot(W, H) * 0.62
    mask = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(mask)
    cx, cy = W // 2, H // 2 - 140
    dm.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=255)
    r, g, b, a = canvas.split()
    out = Image.merge("RGBA", (r, g, b, ImageChops.multiply(a, mask)))
    if 0.02 < p < 0.98 and radius > 4:
        do = ImageDraw.Draw(out)
        do.ellipse((cx - radius, cy - radius, cx + radius, cy + radius),
                   outline=ACCENT, width=10)
    return out


def _translate(canvas: Image.Image, dx: int, dy: int) -> Image.Image:
    if dx == 0 and dy == 0:
        return canvas
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(canvas, (dx, dy))
    return out


def _scale_center(canvas: Image.Image, s: float) -> Image.Image:
    if abs(s - 1.0) < 1e-3:
        return canvas
    nw, nh = max(1, int(W * s)), max(1, int(H * s))
    img = canvas.resize((nw, nh), _RESAMPLE)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(img, ((W - nw) // 2, (H - nh) // 2))
    return out


def _apply_scene_transitions(canvas: Image.Image, scene: dict,
                             t: float, dur: float) -> Image.Image:
    variant_in = scene.get("variant_in", "sweep")
    variant_out = scene.get("variant_out", "scale_fade")

    ep = clamp(t / ENTRANCE_DUR)
    if ep < 1.0:
        if variant_in == "iris":
            canvas = _iris(canvas, ease_out_cube(ep))
            flash = Image.new("RGBA", (W, H), (255, 255, 255, int((1 - ep) * 70)))
            canvas.alpha_composite(flash)
        elif variant_in == "slide_up":
            off = int((1.0 - ease_out_back(ep)) * H)
            canvas = _translate(canvas, 0, off)
        else:  # "sweep" — signature diagonal light sweep + flash
            canvas.alpha_composite(_light_sweep(ep))
            flash = Image.new("RGBA", (W, H), (255, 255, 255, int((1 - ep) * 130)))
            canvas.alpha_composite(flash)

    xq = 1.0 - clamp((dur - t) / EXIT_MOTION_DUR)
    if xq > 0:
        x2 = xq * xq
        if variant_out == "slide_down":
            canvas = _translate(canvas, 0, int(x2 * H))
        elif variant_out == "iris_close":
            canvas = _iris(canvas, x2, closing=True)
        else:  # "scale_fade"
            canvas = _scale_center(canvas, 1.0 - 0.10 * x2)
    return canvas


def _compose_frame(scene: dict, illu: Optional[Image.Image], stage: Image.Image,
                   t: float, dur: float) -> Image.Image:
    kind = scene.get("kind", "idea")
    # The 4 distinct layouts (see LAYOUTS) only apply to plain "idea" beats —
    # steps/number scenes keep their own bespoke composition (pills/counter)
    # so those stay legible regardless of the layout rotation.
    layout = scene.get("layout", "stage_center") if kind == "idea" else "stage_center"

    canvas = stage.copy()
    canvas.alpha_composite(_bg_motif(layout, t))

    box = _illu_box(kind, layout)
    if illu is not None:
        _paste_illustration(canvas, illu, t, dur, box)

    # All ink (panels, doodles, text) goes on its own layer composited once:
    # ImageDraw REPLACES pixels (alpha included), so drawing semi-transparent
    # fills straight on the canvas would punch see-through holes in the scene.
    fg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(fg)

    if illu is None:
        _draw_icon_drawing(fg, scene.get("icon", content.DEFAULT_ICON), t, dur, box)
        draw = ImageDraw.Draw(fg)

    kicker = scene.get("kicker", "À RETENIR")
    headline_y = 1245 if kind != "steps" else 0
    if kind == "steps":
        _draw_kicker(draw, fg, kicker, t)
        draw = ImageDraw.Draw(fg)
        _draw_steps(draw, scene.get("steps", []), t)
    else:
        if kind == "number" and scene.get("value") is not None:
            _draw_kicker(draw, fg, kicker, t)
            draw = ImageDraw.Draw(fg)
            _draw_counter(draw, float(scene["value"]), scene.get("raw", ""), t)
            headline_y = 1290
            _draw_headline(draw, scene.get("headline", ""), t, headline_y)
            _draw_headline_circle(draw, scene.get("headline", ""), t, headline_y)
            _draw_arrows(draw, t, box)
        elif layout == "badge_top":
            _draw_ribbon_banner(draw, fg, kicker, scene.get("headline", ""), t)
            draw = ImageDraw.Draw(fg)
        elif layout == "fullbleed_frame":
            _draw_caption_bar(draw, fg, kicker, scene.get("headline", ""), t)
            draw = ImageDraw.Draw(fg)
        elif layout == "split_panel":
            _draw_kicker(draw, fg, kicker, t)
            draw = ImageDraw.Draw(fg)
            _draw_headline(draw, scene.get("headline", ""), t, 1340)
            _draw_arrow_diagonal(draw, t, box)
        elif layout == "corner_stack":
            _draw_corner_stack(draw, fg, kicker, scene.get("headline", ""), t)
            draw = ImageDraw.Draw(fg)
        elif layout == "ticker_strip":
            _draw_ticker_bar(draw, fg, kicker, scene.get("headline", ""), t)
            draw = ImageDraw.Draw(fg)
        elif layout == "frame_card":
            _draw_card_caption(draw, fg, kicker, scene.get("headline", ""), t, box)
        elif layout == "diagonal_split":
            _draw_diagonal_caption(draw, fg, kicker, scene.get("headline", ""), t)
        else:  # stage_center — signature look
            _draw_kicker(draw, fg, kicker, t)
            draw = ImageDraw.Draw(fg)
            _draw_headline(draw, scene.get("headline", ""), t, headline_y)
            _draw_headline_circle(draw, scene.get("headline", ""), t, headline_y)
            _draw_arrows(draw, t, box)

    _draw_sparkles(draw, t, box)
    canvas.alpha_composite(fg)

    canvas = _apply_scene_transitions(canvas, scene, t, dur)
    return _apply_alpha(canvas, alpha_fade(t, dur, fin=0.18, fout=EXIT_FADE))


def scene_events(scene: dict) -> dict:
    """Element timings (relative to scene start) used for SFX planning."""
    dur = float(scene.get("duration", config.MOTION_SCENE_DUR))
    elements = [T_HEADLINE, T_ARROWS]
    kind = scene.get("kind", "idea")
    if kind == "steps":
        n = min(4, len(scene.get("steps", []))) or 2
        elements = [T_ELEMENTS + i * STEP_STAGGER for i in range(n)]
    elif kind == "number":
        elements = [T_HEADLINE, T_ELEMENTS]
    elements = sorted(et for et in elements if et < dur - EXIT_FADE - 0.2)
    return {
        "entrance": 0.0,
        "elements": [round(et, 3) for et in elements],
        "exit": round(dur - EXIT_FADE, 3),
    }


def render_scene(scene: dict, out_path: str, fps: int = config.FPS) -> dict:
    """Render one motion-design scene to ProRes 4444; returns the enriched spec."""
    dur = float(scene.get("duration", config.MOTION_SCENE_DUR))
    illu: Optional[Image.Image] = None
    image_path = scene.get("image")
    if image_path and os.path.exists(image_path):
        try:
            illu = Image.open(image_path).convert("RGBA")
        except OSError as exc:
            print(f"[motion_design] WARN cannot read {image_path}: {exc} "
                  f"-> procedural drawing", file=sys.stderr)

    stage = _stage_base()
    n_frames = max(1, int(round(dur * fps)))
    with ProResPipe(out_path, fps=fps) as pipe:
        for fi in range(n_frames):
            pipe.write(_compose_frame(scene, illu, stage, fi / fps, dur))

    events = scene_events(scene)
    if illu is None:
        events["draw"] = T_ILLU       # the drawing draws itself -> pencil SFX
    return {**scene, "mov": out_path, "duration": round(dur, 3),
            "illustrated": illu is not None, "events": events}


def render_all(scenes: List[dict], outdir: str, *, preset: Optional[str] = None,
               seed_text: Optional[str] = None) -> List[dict]:
    os.makedirs(outdir, exist_ok=True)
    # Per-video colour palette (variety across videos). A stable seed (job/video
    # id or the transcript) keeps a given job reproducible; *preset* forces a
    # named motion-design family.
    seed = seed_text or "|".join(
        s.get("headline", "") + s.get("excerpt", "") for s in scenes)
    select_palette(seed, preset=preset)
    layouts = _layout_sequence(seed, len(scenes))
    out: List[dict] = []
    for i, scene in enumerate(scenes):
        # Cycle the entrance/exit transition variants so two consecutive
        # takeovers never use the same move (belles transitions variées), AND
        # rotate the scene LAYOUT itself (composition, not just colour) so the
        # motion-design beats of a single video alternate between many
        # designs instead of repeating one template — the rotation is
        # reshuffled per video so different edits don't even share the same
        # layout order.
        scene = {
            **scene,
            "variant_in": config.MOTION_ENTRANCES[i % len(config.MOTION_ENTRANCES)],
            "variant_out": config.MOTION_EXITS[i % len(config.MOTION_EXITS)],
            "layout": layouts[i],
        }
        path = os.path.join(outdir, f"{scene['id']}.mov")
        try:
            rendered = render_scene(scene, path)
        except Exception as exc:  # noqa: BLE001 - one bad scene must not kill the montage
            print(f"[motion_design] WARN scene {scene.get('id')} failed: {exc}",
                  file=sys.stderr)
            continue
        out.append(rendered)
        src = "AI illustration" if rendered["illustrated"] else f"drawing '{scene.get('icon')}'"
        print(f"[motion_design] {scene['id']} {scene.get('kind', 'idea'):7s} "
              f"({rendered['duration']:.1f}s, {src}) -> {path}")
    return out


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Render illustrated motion-design scenes -> ProRes 4444 .mov")
    ap.add_argument("scenes", nargs="?", help="JSON list of scene specs")
    ap.add_argument("--from-vu", help="derive scenes from a transcript _vu.json")
    ap.add_argument("--outdir", default="motion_clips")
    ap.add_argument("--dump-scenes", help="write derived scenes to this path and exit")
    args = ap.parse_args(argv)

    if args.from_vu:
        vu = json.load(open(args.from_vu, encoding="utf-8"))
        scenes = content.derive_motion_scenes(vu)
    elif args.scenes:
        scenes = json.load(open(args.scenes, encoding="utf-8"))
    else:
        ap.error("provide scenes.json or --from-vu")

    if args.dump_scenes:
        json.dump(scenes, open(args.dump_scenes, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print(f"[motion_design] {len(scenes)} scenes -> {args.dump_scenes}")
        return 0

    rendered = render_all(scenes, args.outdir)
    json.dump(rendered, open(os.path.join(args.outdir, "_motion_clips.json"), "w",
                             encoding="utf-8"), ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
