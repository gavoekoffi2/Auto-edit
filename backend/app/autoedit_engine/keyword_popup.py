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
import os
import re
import sys
from typing import Dict, List, Optional

from PIL import Image, ImageDraw

# Pillow-version-robust LANCZOS (Resampling moved in 9.1; constants vary by version).
try:
    _RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:  # Pillow < 9.1
    _RESAMPLE = Image.LANCZOS  # noqa: PIL legacy fallback

from . import config
from . import content
from .fonts import load_font
from .render_utils import ProResPipe, alpha_fade, clamp, ease_out_back
from .timeline import s2o

GOLD = config.KEYWORD_CHIP_COLOR
BG = (12, 14, 22, 200)
_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ0-9']+")


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


def render_popup(text: str, out_path: str, fps: int = config.FPS,
                 dur: float = config.KEYWORD_POPUP_DUR) -> str:
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

            fade = alpha_fade(t, dur)
            if fade < 0.999:
                r, g, b, a = frame.split()
                a = a.point(lambda v: int(v * fade))
                frame = Image.merge("RGBA", (r, g, b, a))
            pipe.write(frame)
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


def _append_popup_sfx(times: List[float], sfx_cues_path: str) -> int:
    """Give every popup chip a tiny UI blip (they used to appear in silence)."""
    if not times or not os.path.exists(sfx_cues_path):
        return 0
    with open(sfx_cues_path, "r", encoding="utf-8") as fh:
        cues = json.load(fh)
    existing = sorted(float(c["t"]) for c in cues)

    added = 0
    for i, t in enumerate(times[:config.POPUP_SFX_MAX]):
        # Skip if another cue already hits within 0.3 s (no SFX pile-ups).
        if any(abs(t - e) < 0.3 for e in existing):
            continue
        cues.append({"sfx": config.POPUP_SFX_POOL[i % len(config.POPUP_SFX_POOL)],
                     "t": round(t, 3), "src": "popup"})
        existing.append(t)
        added += 1

    cues.sort(key=lambda c: c["t"])
    with open(sfx_cues_path, "w", encoding="utf-8") as fh:
        json.dump(cues, fh, ensure_ascii=False, indent=2)
    return added


def build_popups(edl_path: str, outdir: str,
                 sfx_cues_path: Optional[str] = None) -> dict:
    with open(edl_path, "r", encoding="utf-8") as fh:
        edl = json.load(fh)
    vu = json.load(open(edl["transcripts_vu"], encoding="utf-8"))
    ranges = edl["ranges"]
    os.makedirs(outdir, exist_ok=True)
    if sfx_cues_path is None:
        sfx_cues_path = os.path.join(os.path.dirname(os.path.abspath(edl_path)),
                                     "sfx_cues.json")

    keywords = content.top_keywords(vu, config.KEYWORD_TOP_N)

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

    movs: Dict[str, str] = {}
    overlays = edl.get("overlays", [])
    counters: Dict[str, int] = {}
    for ot, kw in kept:
        if kw not in movs:
            mov = os.path.join(outdir, f"popup_{_fname_safe(kw)}.mov")
            render_popup(kw, mov)
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

    sfx_added = _append_popup_sfx([ot for ot, _ in kept], sfx_cues_path)
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
