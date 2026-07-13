"""
STEP 7 — Keyword popups (RÈGLE PRO #2 — hiérarchie visuelle).

Takes the 8 most frequent keywords (stopword/filler filtered) and, for each
occurrence on the timeline (>= 8 s between two hits of the same word), shows a
gold animated chip:
  * ProRes 4444 RGBA, 1.5 s
  * y ~ 450 (above the face, TikTok style)
  * rounded semi-transparent bg + gold border + white text
  * pop-in scale 60% -> 100% + fade

One .mov is rendered per keyword (reused at every occurrence); the occurrences
are appended to edl.json AFTER the graphics and B-roll overlays.

Usage:
    python -m engine.keyword_popup edl.json --outdir broll_clips
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
from typing import Dict, List, Optional

from PIL import Image, ImageDraw, ImageFilter

# Pillow-version-robust LANCZOS (Resampling moved in 9.1; constants vary by version).
try:
    _RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:  # Pillow < 9.1
    _RESAMPLE = Image.LANCZOS  # noqa: PIL legacy fallback

from . import config
from . import content
from .fonts import load_font
from .render_utils import ProResPipe, alpha_fade, clamp, ease_out_back, ease_out_cube
from .timeline import s2o

GOLD = config.KEYWORD_CHIP_COLOR
BG = (12, 14, 22, 200)
_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ0-9']+")

_POPUP_BLOCKLIST = {
    "dire", "dit", "dis", "parler", "tellement", "probablement", "voir", "vu",
    "passer", "passe", "vient", "venir", "semaine", "derriere", "derrière",
    "created", "create", "make", "thing", "things",
}


def _display_keyword(kw: str) -> str:
    """Clean spoken token for a premium on-screen chip."""
    cleaned = kw.strip().lower().strip("'’\".,;:!?()[]{}")
    cleaned = re.sub(r"^(?:l|d|j|m|t|s|c|n|qu)['’]", "", cleaned)
    return cleaned


def _is_strong_keyword(kw: str) -> bool:
    display = _display_keyword(kw)
    if len(display) < 5 or display.isdigit():
        return False
    if display in _POPUP_BLOCKLIST or display in config.STOPWORDS or display in config.FILLERS:
        return False
    # Avoid weak French adverbs that often appear frequently but do not help the
    # viewer understand the point.
    if display.endswith("ment") and display not in {"paiement", "investissement"}:
        return False
    return True


# --------------------------------------------------------------------------- #
# chip rendering
# --------------------------------------------------------------------------- #
def _chip_tile(text: str) -> Image.Image:
    """Render the chip at full size on its own tile (transparent margins)."""
    font = load_font("Montserrat", 64)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    l, t, r, b = tmp.textbbox((0, 0), text, font=font, stroke_width=3)
    tw, th = r - l, b - t
    pad_x, pad_y = 46, 26
    cw, ch = tw + 2 * pad_x, th + 2 * pad_y
    margin = 24                                  # room for the scaled-up glow
    tile = Image.new("RGBA", (cw + 2 * margin, ch + 2 * margin), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    box = (margin, margin, margin + cw, margin + ch)
    d.rounded_rectangle(box, radius=ch // 2, fill=BG, outline=GOLD, width=5)
    d.text((margin + pad_x - l, margin + pad_y - t), text, font=font,
           fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 230))
    return tile


def _apply_fade(frame: Image.Image, fade: float) -> Image.Image:
    if fade < 0.999:
        r, g, b, a = frame.split()
        a = a.point(lambda v: int(v * fade))
        frame = Image.merge("RGBA", (r, g, b, a))
    return frame


# ---- theme: editorial_collage (réf. vidéo 1 — bandeau papier déchiré) ------ #
_PAPER_BLUE = (43, 98, 226, 255)
_PAPER_BLUE_DARK = (28, 70, 178, 255)


def _torn_banner_tile(text: str) -> Image.Image:
    """Blue crumpled-paper strip with a torn bottom edge + rotated black bar."""
    rng = random.Random(text)
    font = load_font("Anton", 76)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    l, t, r, b = tmp.textbbox((0, 0), text, font=font)
    tw, th = r - l, b - t

    bw = min(config.WIDTH, max(tw + 260, 640))
    bh = th + 210
    tile = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)

    # Paper strip with irregular torn bottom edge (white deckle under blue).
    tear_pts = [(0, 0), (bw, 0)]
    x = bw
    base_y = bh - 46
    while x > 0:
        tear_pts.append((x, base_y + rng.randint(-18, 18)))
        x -= rng.randint(28, 64)
    tear_pts.append((0, base_y + rng.randint(-18, 18)))
    white_tear = [(px, min(bh - 2, py + 10)) for px, py in tear_pts]
    d.polygon(white_tear, fill=(245, 242, 234, 255))          # torn white backing
    d.polygon(tear_pts, fill=_PAPER_BLUE)
    # Crumple speckle: light/dark creases on the blue paper.
    for _ in range(int(bw * base_y / 900)):
        px, py = rng.randint(0, bw - 1), rng.randint(0, base_y - 1)
        shade = _PAPER_BLUE_DARK if rng.random() < 0.5 else (86, 140, 255, 255)
        d.line([(px, py), (px + rng.randint(4, 18), py + rng.randint(-4, 4))],
               fill=shade, width=1)

    # Rotated black bar carrying the keyword.
    bar_pad_x, bar_pad_y = 56, 26
    bar = Image.new("RGBA", (tw + 2 * bar_pad_x, th + 2 * bar_pad_y), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bar)
    bd.rectangle((0, 0, bar.width, bar.height), fill=(14, 14, 14, 255))
    bd.text((bar_pad_x - l, bar_pad_y - t), text, font=font, fill=(250, 248, 240, 255))
    bar = bar.rotate(rng.uniform(-2.5, 2.5), expand=True, resample=Image.BICUBIC)
    tile.alpha_composite(bar, ((bw - bar.width) // 2, (base_y - bar.height) // 2))
    return tile


def _render_editorial_collage(text: str, out_path: str, fps: int, dur: float) -> str:
    """Banner slides down from the top edge (torn-paper collage, réf. vidéo 1)."""
    tile = _torn_banner_tile(text)
    n_frames = max(1, int(round(dur * fps)))
    slide = 0.32
    final_y = 150                                  # top of frame, above the face
    with ProResPipe(out_path, fps=fps) as pipe:
        for fi in range(n_frames):
            t = fi / fps
            p = ease_out_cube(clamp(t / slide))
            y = int(-tile.height + (final_y + tile.height) * p)
            frame = Image.new("RGBA", (config.WIDTH, config.HEIGHT), (0, 0, 0, 0))
            frame.alpha_composite(tile, ((config.WIDTH - tile.width) // 2, y))
            pipe.write(_apply_fade(frame, alpha_fade(t, dur, fin=0.0)))
    return out_path


# ---- theme: neon_glitch (réf. vidéo 2 — mot MAJUSCULE glow cyan) ----------- #
_NEON_CYAN = (0, 229, 255)


def _neon_tile(text: str) -> Image.Image:
    font = load_font("Anton", 118)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    l, t, r, b = tmp.textbbox((0, 0), text, font=font)
    tw, th = r - l, b - t
    margin = 60
    tile = Image.new("RGBA", (tw + 2 * margin, th + 2 * margin), (0, 0, 0, 0))
    # Cyan glow underlay (blurred), then crisp white text on top.
    glow = Image.new("RGBA", tile.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.text((margin - l, margin - t), text, font=font, fill=(*_NEON_CYAN, 235))
    glow = glow.filter(ImageFilter.GaussianBlur(14))
    tile.alpha_composite(glow)
    tile.alpha_composite(glow)                     # double pass = stronger halo
    d = ImageDraw.Draw(tile)
    d.text((margin - l, margin - t), text, font=font, fill=(255, 255, 255, 255),
           stroke_width=2, stroke_fill=(10, 20, 24, 255))
    return tile


def _render_neon_glitch(text: str, out_path: str, fps: int, dur: float) -> str:
    """Glowing word with a brief chromatic-aberration jitter on entry."""
    rng = random.Random(text)
    tile = _neon_tile(text.upper())
    n_frames = max(1, int(round(dur * fps)))
    cx, cy = config.WIDTH // 2, config.KEYWORD_POPUP_Y
    popin, glitch_span = 0.22, 0.30
    r_ch, g_ch, b_ch, a_ch = tile.split()
    zero = a_ch.point(lambda _: 0)
    red_copy = Image.merge("RGBA", (r_ch, zero, zero, a_ch.point(lambda v: int(v * 0.55))))
    cyan_copy = Image.merge("RGBA", (zero, g_ch, b_ch, a_ch.point(lambda v: int(v * 0.55))))
    with ProResPipe(out_path, fps=fps) as pipe:
        for fi in range(n_frames):
            t = fi / fps
            scale = 0.72 + 0.28 * ease_out_back(clamp(t / popin))
            sw, sh = max(1, int(tile.width * scale)), max(1, int(tile.height * scale))
            frame = Image.new("RGBA", (config.WIDTH, config.HEIGHT), (0, 0, 0, 0))
            x, y = cx - sw // 2, cy - sh // 2
            if t < glitch_span:                    # RGB split jitter, then locks
                amp = int(10 * (1.0 - t / glitch_span)) + 1
                dx = rng.randint(-amp, amp)
                frame.alpha_composite(red_copy.resize((sw, sh), _RESAMPLE), (x - dx, y))
                frame.alpha_composite(cyan_copy.resize((sw, sh), _RESAMPLE), (x + dx, y))
            frame.alpha_composite(tile.resize((sw, sh), _RESAMPLE), (x, y))
            pipe.write(_apply_fade(frame, alpha_fade(t, dur)))
    return out_path


# ---- theme: sketch (réf. vidéo 3 — mot manuscrit + cercle dessiné) --------- #
def _sketch_tile(text: str) -> Image.Image:
    font = load_font("Caveat", 128)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    l, t, r, b = tmp.textbbox((0, 0), text, font=font, stroke_width=2)
    tw, th = r - l, b - t
    margin = 90                                    # room for the drawn ellipse
    tile = Image.new("RGBA", (tw + 2 * margin, th + 2 * margin), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    d.text((margin - l + 5, margin - t + 7), text, font=font,
           fill=(0, 0, 0, 200))                    # marked shadow -> readable on any video
    d.text((margin - l, margin - t), text, font=font, fill=(255, 255, 255, 255),
           stroke_width=2, stroke_fill=(255, 255, 255, 90))
    return tile


def _render_sketch(text: str, out_path: str, fps: int, dur: float) -> str:
    """Handwritten word; a wobbly hand-drawn ellipse strokes itself around it."""
    rng = random.Random(text)
    tile = _sketch_tile(text)
    n_frames = max(1, int(round(dur * fps)))
    cx, cy = config.WIDTH // 2, config.KEYWORD_POPUP_Y
    draw_span = 0.55                               # seconds to stroke the ellipse
    rx, ry = tile.width // 2 - 8, tile.height // 2 - 8
    wobble = [rng.uniform(-5.0, 5.0) for _ in range(72)]
    with ProResPipe(out_path, fps=fps) as pipe:
        for fi in range(n_frames):
            t = fi / fps
            frame = Image.new("RGBA", (config.WIDTH, config.HEIGHT), (0, 0, 0, 0))
            frame.alpha_composite(tile, (cx - tile.width // 2, cy - tile.height // 2))
            progress = clamp(t / draw_span)
            if progress > 0.02:
                d = ImageDraw.Draw(frame)
                steps = int(72 * ease_in_out_sine(progress))
                pts = []
                for k in range(steps + 1):
                    ang = math.radians(-90 + 360 * k / 72)
                    w = wobble[k % len(wobble)]
                    pts.append((cx + (rx + w) * math.cos(ang),
                                cy + (ry + w * 0.6) * math.sin(ang)))
                if len(pts) >= 2:
                    shadow_pts = [(px + 4, py + 5) for px, py in pts]
                    d.line(shadow_pts, fill=(0, 0, 0, 150), width=6, joint="curve")
                    d.line(pts, fill=(255, 255, 255, 235), width=6, joint="curve")
            pipe.write(_apply_fade(frame, alpha_fade(t, dur, fin=0.08)))
    return out_path


def ease_in_out_sine(p: float) -> float:
    p = clamp(p)
    return 0.5 * (1.0 - math.cos(math.pi * p))


_THEME_RENDERERS = {
    "editorial_collage": _render_editorial_collage,
    "neon_glitch": _render_neon_glitch,
    "sketch": _render_sketch,
}


def render_popup(text: str, out_path: str, fps: int = config.FPS,
                 dur: float = config.KEYWORD_POPUP_DUR,
                 theme: str = config.DEFAULT_POPUP_THEME) -> str:
    renderer = _THEME_RENDERERS.get(theme)
    if renderer is not None:
        return renderer(text if theme == "sketch" else text.upper(), out_path, fps, dur)

    tile = _chip_tile(text.upper())
    n_frames = max(1, int(round(dur * fps)))
    cx, cy = config.WIDTH // 2, config.KEYWORD_POPUP_Y
    popin = 0.30                                  # seconds for the 60->100 pop

    with ProResPipe(out_path, fps=fps) as pipe:
        for fi in range(n_frames):
            t = fi / fps
            scale = 0.6 + 0.4 * ease_out_back(clamp(t / popin))
            sw, sh = max(1, int(tile.width * scale)), max(1, int(tile.height * scale))
            scaled = tile.resize((sw, sh), _RESAMPLE)

            frame = Image.new("RGBA", (config.WIDTH, config.HEIGHT), (0, 0, 0, 0))
            frame.alpha_composite(scaled, (cx - sw // 2, cy - sh // 2))

            pipe.write(_apply_fade(frame, alpha_fade(t, dur)))
    return out_path


# --------------------------------------------------------------------------- #
# occurrence finding + edl patch
# --------------------------------------------------------------------------- #
def _all_words(vu: dict) -> List[dict]:
    words: List[dict] = []
    for seg in vu.get("segments", []):
        words.extend(seg.get("words", []))
    words.sort(key=lambda w: float(w["start"]))
    return words


def find_occurrences(vu: dict, keyword: str, ranges: List[dict]) -> List[float]:
    """Output-time occurrences of *keyword* (>= KEYWORD_MIN_GAP apart, surviving cuts)."""
    out_times: List[float] = []
    last = -1e9
    for w in _all_words(vu):
        toks = _WORD_RE.findall(w["word"].lower())
        if keyword not in toks:
            continue
        src_t = float(w["start"])
        ot = s2o(src_t, ranges)
        if ot is None:                            # inside a removed gap -> skip
            continue
        if ot - last >= config.KEYWORD_MIN_GAP:
            out_times.append(round(ot, 3))
            last = ot
    return out_times


def _fname_safe(kw: str) -> str:
    return re.sub(r"[^A-Za-z0-9À-ÿ_-]+", "_", kw) or "kw"


def _append_popup_sfx(times: List[float], sfx_cues_path: str,
                      theme: str = config.DEFAULT_POPUP_THEME) -> int:
    """Give every popup a sound that MATCHES its visual theme.

    paper_rip pour les bandeaux papier déchiré, glitch pour le néon, crayon
    pour le sketch — le blip UI générique reste le défaut historique.
    """
    if not times or not os.path.exists(sfx_cues_path):
        return 0
    with open(sfx_cues_path, "r", encoding="utf-8") as fh:
        cues = json.load(fh)
    existing = sorted(float(c["t"]) for c in cues)
    pool = config.POPUP_SFX_THEME_POOLS.get(theme, config.POPUP_SFX_POOL)

    added = 0
    for i, t in enumerate(times[:config.POPUP_SFX_MAX]):
        # Skip if another cue already hits within 0.3 s (no SFX pile-ups).
        if any(abs(t - e) < 0.3 for e in existing):
            continue
        cues.append({"sfx": pool[i % len(pool)],
                     "t": round(t, 3), "src": "popup"})
        existing.append(t)
        added += 1

    cues.sort(key=lambda c: c["t"])
    with open(sfx_cues_path, "w", encoding="utf-8") as fh:
        json.dump(cues, fh, ensure_ascii=False, indent=2)
    return added


def build_popups(edl_path: str, outdir: str,
                 sfx_cues_path: Optional[str] = None,
                 theme: str = config.DEFAULT_POPUP_THEME) -> dict:
    with open(edl_path, "r", encoding="utf-8") as fh:
        edl = json.load(fh)
    vu = json.load(open(edl["transcripts_vu"], encoding="utf-8"))
    ranges = edl["ranges"]
    os.makedirs(outdir, exist_ok=True)
    if sfx_cues_path is None:
        sfx_cues_path = os.path.join(os.path.dirname(os.path.abspath(edl_path)),
                                     "sfx_cues.json")

    keywords = [kw for kw in content.top_keywords(vu, config.KEYWORD_TOP_N * 2)
                if _is_strong_keyword(kw)][:config.KEYWORD_TOP_N]

    # Full-frame takeovers (motion-design scenes) own their span: a popup chip
    # must never blink on top of an illustrated scene.
    takeover_spans = [
        (float(o["start"]) - 0.2, float(o["end"]) + 0.2)
        for o in edl.get("overlays", [])
        if o.get("kind") == "motion"
    ]

    def _in_takeover(t: float) -> bool:
        end_t = t + config.KEYWORD_POPUP_DUR
        return any(t < b and end_t > a for a, b in takeover_spans)

    # Gather every candidate occurrence, then de-collide globally so two chips
    # never share the screen (>= popup duration + small gap apart).
    candidates: List[tuple] = []
    for kw in keywords:
        for ot in find_occurrences(vu, kw, ranges):
            candidates.append((ot, kw))
    candidates.sort(key=lambda c: c[0])

    min_spacing = config.KEYWORD_POPUP_DUR + 0.4
    kept: List[tuple] = []
    last = -1e9
    for ot, kw in candidates:
        if ot - last >= min_spacing and not _in_takeover(ot):
            kept.append((ot, kw))
            last = ot

    kept = kept[:config.KEYWORD_POPUP_MAX_PER_VIDEO]

    movs: Dict[str, str] = {}
    overlays = edl.get("overlays", [])
    counters: Dict[str, int] = {}
    for ot, kw in kept:
        label = _display_keyword(kw)
        if kw not in movs:
            mov = os.path.join(outdir, f"popup_{_fname_safe(kw)}.mov")
            render_popup(label, mov, theme=theme)
            movs[kw] = mov
        k = counters.get(kw, 0)
        counters[kw] = k + 1
        overlays.append({
            "id": f"pop_{kw}_{k}",
            "mov": movs[kw],
            "start": ot,
            "end": round(ot + config.KEYWORD_POPUP_DUR, 3),
            "kind": "popup",
        })
    added = len(kept)
    for kw, c in counters.items():
        print(f"[keyword_popup] '{kw}': {c} popup(s)")

    edl["overlays"] = overlays
    with open(edl_path, "w", encoding="utf-8") as fh:
        json.dump(edl, fh, ensure_ascii=False, indent=2)

    sfx_added = _append_popup_sfx([ot for ot, _ in kept], sfx_cues_path, theme=theme)
    print(f"[keyword_popup] +{added} popups for {len(movs)} keywords "
          f"(+{sfx_added} SFX) -> {edl_path}")
    return {"keywords": list(movs), "added": added, "sfx_added": sfx_added}


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Keyword popups -> ProRes chips + edl patch")
    ap.add_argument("edl", help="edl.json")
    ap.add_argument("--outdir", default="broll_clips")
    args = ap.parse_args(argv)
    build_popups(args.edl, args.outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
