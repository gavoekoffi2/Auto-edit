"""
STEP 6 (b) — B-roll animation (PIL -> ProRes 4444 RGBA).

Each AI image becomes a full-frame cinematic clip that sits ABOVE the graphics
during the "ballotage" (speaker -> B-roll full frame ~3 s -> speaker).

Entrances cycle in this exact order:
    punch / slide_r / slide_l / rise / glitch / flash / transition / swoosh_up

Common to every clip:
  * blurred, dimmed background plate (GaussianBlur r=40, brightness 0.45x)
  * continuous Ken Burns (kb=0.10) for the whole clip
  * CYAN corner brackets + a gold chip label (y ~ 250)
  * alpha fade 0.13 s in / 0.20 s out
  * 3.0 s standard (3.2 s for wide images)

Usage:
    python -m engine.broll_anim broll/_broll_images.json --outdir broll_clips
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

# Pillow-version-robust LANCZOS (Resampling moved in 9.1; constants vary by version).
try:
    _RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:  # Pillow < 9.1
    _RESAMPLE = Image.LANCZOS  # noqa: PIL legacy fallback

from . import config
from .fonts import load_font
from .render_utils import ProResPipe, alpha_fade, clamp, ease_in_out, ease_out_cube

CYAN = config.BROLL_BRACKET_COLOR
GOLD = config.BROLL_CHIP_COLOR
W, H = config.WIDTH, config.HEIGHT
ENTRANCE_DUR = 0.5                    # seconds of intro motion
MARGIN = 70                          # frame inset for brackets / main image


# --------------------------------------------------------------------------- #
# image helpers
# --------------------------------------------------------------------------- #
def _cover(img: Image.Image, w: int, h: int) -> Image.Image:
    src_ratio = img.width / img.height
    dst_ratio = w / h
    if src_ratio > dst_ratio:
        nh = h
        nw = int(h * src_ratio)
    else:
        nw = w
        nh = int(w / src_ratio)
    img = img.resize((nw, nh), _RESAMPLE)
    left = (nw - w) // 2
    top = (nh - h) // 2
    return img.crop((left, top, left + w, top + h))


def _fit(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    ratio = min(max_w / img.width, max_h / img.height)
    return img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))), _RESAMPLE)


def _background_plate(img: Image.Image) -> Image.Image:
    plate = _cover(img.convert("RGB"), W, H).filter(ImageFilter.GaussianBlur(config.BROLL_BLUR_RADIUS))
    plate = ImageEnhance.Brightness(plate).enhance(config.BROLL_BLUR_BRIGHTNESS)
    return plate.convert("RGBA")


def _rgb_shift(img: Image.Image, dx: int) -> Image.Image:
    if dx <= 0:
        return img
    r, g, b, a = img.split()
    r = r.transform(img.size, Image.AFFINE, (1, 0, -dx, 0, 1, 0))
    b = b.transform(img.size, Image.AFFINE, (1, 0, dx, 0, 1, 0))
    return Image.merge("RGBA", (r, g, b, a))


def _brackets(draw: ImageDraw.ImageDraw, inset: int = MARGIN, length: int = 90, wd: int = 7):
    c = CYAN
    x0, y0, x1, y1 = inset, inset, W - inset, H - inset
    # TL, TR, BL, BR
    draw.line([(x0, y0), (x0 + length, y0)], fill=c, width=wd)
    draw.line([(x0, y0), (x0, y0 + length)], fill=c, width=wd)
    draw.line([(x1, y0), (x1 - length, y0)], fill=c, width=wd)
    draw.line([(x1, y0), (x1, y0 + length)], fill=c, width=wd)
    draw.line([(x0, y1), (x0 + length, y1)], fill=c, width=wd)
    draw.line([(x0, y1), (x0, y1 - length)], fill=c, width=wd)
    draw.line([(x1, y1), (x1 - length, y1)], fill=c, width=wd)
    draw.line([(x1, y1), (x1, y1 - length)], fill=c, width=wd)


def _chip(canvas: Image.Image, label: str):
    if not label:
        return
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    font = load_font("Montserrat", 44)
    l, t, r, b = d.textbbox((0, 0), label, font=font)
    tw, th = r - l, b - t
    pad_x, pad_y = 34, 18
    cw, ch = tw + 2 * pad_x, th + 2 * pad_y
    x0 = (W - cw) // 2
    y0 = config.BROLL_CHIP_Y
    d.rounded_rectangle((x0, y0, x0 + cw, y0 + ch), radius=ch // 2, fill=GOLD)
    d.text((x0 + pad_x - l, y0 + pad_y - t), label, font=font, fill=(20, 16, 6, 255))
    canvas.alpha_composite(layer)


def _light_sweep(progress: float, strength: float = 140.0) -> Image.Image:
    """A diagonal white sweep crossing the frame as *progress* goes 0->1."""
    xs = np.arange(W)
    ys = np.arange(H)
    gx, gy = np.meshgrid(xs, ys)
    # diagonal line position sweeps from off-left to off-right
    pos = (progress * 1.6 - 0.3) * (W + H)
    d = (gx + gy) - pos
    band = np.exp(-(d / 160.0) ** 2) * strength
    alpha = np.clip(band, 0, 255).astype(np.uint8)
    layer = np.zeros((H, W, 4), dtype=np.uint8)
    layer[..., 0:3] = 255
    layer[..., 3] = alpha
    return Image.fromarray(layer, "RGBA")


def _white_flash(intensity: float) -> Image.Image:
    a = int(clamp(intensity) * 200)
    return Image.new("RGBA", (W, H), (255, 255, 255, a))


# --------------------------------------------------------------------------- #
# per-frame composition
# --------------------------------------------------------------------------- #
def _compose_frame(main: Image.Image, plate: Image.Image, label: str,
                   entrance: str, t: float, dur: float) -> Image.Image:
    ep = clamp(t / ENTRANCE_DUR)
    e = ease_out_cube(ep)
    kb = 1.0 + config.BROLL_KB * ease_in_out(clamp(t / dur))   # continuous Ken Burns

    scale = kb
    off_x = off_y = 0
    shift = 0
    flash = 0.0
    sweep = False

    if entrance == "punch":
        scale = (1.6 - 0.6 * e) * kb
        flash = (1.0 - ep) * 0.8
        sweep = ep < 1.0
    elif entrance == "flash":
        scale = (0.7 + 0.3 * e) * kb
        flash = (1.0 - ep) * 0.8
        sweep = ep < 1.0
    elif entrance == "slide_r":
        off_x = int((1 - e) * 0.7 * W)
    elif entrance == "slide_l":
        off_x = int(-(1 - e) * 0.7 * W)
    elif entrance == "rise":
        off_y = int((1 - e) * 0.5 * H)
        scale = (0.95 + 0.05 * e) * kb
    elif entrance == "swoosh_up":
        off_y = int((1 - e) * 0.6 * H)
        scale = (0.9 + 0.1 * e) * kb
        sweep = ep < 1.0
    elif entrance == "glitch":
        shift = int((1 - e) * 28)
    elif entrance == "transition":
        off_x = int((1 - e) * 0.4 * W)
        scale = (0.9 + 0.1 * e) * kb

    # Exit motion — the clip LEAVES with energy (paired with its entrance),
    # layered on top of the 0.20 s alpha fade-out.
    xq = 1.0 - clamp((dur - t) / config.BROLL_EXIT_DUR)
    if xq > 0:
        x2 = xq * xq                              # accelerating ease-in
        exit_name = config.BROLL_EXITS.get(entrance, "punch_out")
        if exit_name == "slide_out_l":
            off_x -= int(x2 * 0.9 * W)
        elif exit_name == "slide_out_r":
            off_x += int(x2 * 0.9 * W)
        elif exit_name == "drop":
            off_y += int(x2 * 0.8 * H)
        elif exit_name == "swoosh_out_up":
            off_y -= int(x2 * 0.8 * H)
        elif exit_name == "glitch_out":
            shift = max(shift, int(x2 * 30))
        elif exit_name == "scale_out":           # léger zoom + fondu, sobre
            scale *= 1.0 + 0.22 * x2
        else:                                     # punch_out
            scale *= 1.0 + 0.45 * x2
            flash = max(flash, x2 * 0.35)

    canvas = plate.copy()

    # scale the (pre-fit) main image
    sw = max(1, int(main.width * scale))
    sh = max(1, int(main.height * scale))
    frame_main = main.resize((sw, sh), _RESAMPLE)
    if shift > 0:
        frame_main = _rgb_shift(frame_main, shift)

    px = (W - sw) // 2 + off_x
    py = (H - sh) // 2 + off_y
    canvas.alpha_composite(frame_main, (px, py))

    draw = ImageDraw.Draw(canvas)
    _brackets(draw)
    _chip(canvas, label)

    if sweep:
        canvas.alpha_composite(_light_sweep(ep))
    if flash > 0.01:
        canvas.alpha_composite(_white_flash(flash))

    # global fade -> alpha
    fade = alpha_fade(t, dur)
    if fade < 0.999:
        r, g, b, a = canvas.split()
        a = a.point(lambda v: int(v * fade))
        canvas = Image.merge("RGBA", (r, g, b, a))
    return canvas


def render_broll(image_path: str, out_path: str, label: str = "",
                 entrance: str = "punch", fps: int = config.FPS) -> float:
    """Render the clip; returns its duration in seconds."""
    src = Image.open(image_path).convert("RGBA")
    is_wide = src.width >= src.height
    dur = config.BROLL_DURATION_WIDE if is_wide else config.BROLL_DURATION

    plate = _background_plate(src)
    main = _fit(src, W - 2 * MARGIN - 40, H - 2 * MARGIN - 360)  # leave room for chip/brackets

    n_frames = max(1, int(round(dur * fps)))
    with ProResPipe(out_path, fps=fps) as pipe:
        for fi in range(n_frames):
            frame = _compose_frame(main, plate, label, entrance, fi / fps, dur)
            pipe.write(frame)
    return dur


def render_all(images: List[dict], outdir: str) -> List[dict]:
    os.makedirs(outdir, exist_ok=True)
    out: List[dict] = []
    for i, item in enumerate(images):
        entrance = item.get("entrance") or config.BROLL_ENTRANCES[i % len(config.BROLL_ENTRANCES)]
        path = os.path.join(outdir, f"br_{item.get('id', f'{i:03d}')}.mov")
        dur = render_broll(item["image"], path, label=item.get("label", ""), entrance=entrance)
        out.append({**item, "entrance": entrance, "mov": path, "duration": round(dur, 3)})
        print(f"[broll_anim] {item.get('id')} {entrance:10s} ({dur:.1f}s) -> {path}")
    return out


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Animate B-roll images -> ProRes 4444 .mov")
    ap.add_argument("images", help="JSON list of {id,image,label} (e.g. _broll_images.json)")
    ap.add_argument("--outdir", default="broll_clips")
    args = ap.parse_args(argv)
    images = json.load(open(args.images, encoding="utf-8"))
    rendered = render_all(images, args.outdir)
    json.dump(rendered, open(os.path.join(args.outdir, "_broll_clips.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
