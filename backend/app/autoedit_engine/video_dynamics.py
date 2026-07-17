"""
STEP 4 — Dynamic zoom (Ken Burns + gaussian micro-punches).

Operates on the concatenated ``base_only.mp4`` and produces ``base_dyn.mp4``.

zoompan is fed a PRE-SCALED (x2) input to kill jitter (mandatory).  A single
piecewise ``z`` expression drives the whole timeline:

  Ken Burns alternates per output segment (i = kept-range index):
    i%4==0  zoom IN  slow        (1.0 -> 1.11, ease-out cube)
    i%4==2  zoom OUT slow        (1.11 -> 1.0, ease-out cube)
    i%4==1  zoom IN  progressive (1.0 -> 1.11, linear)
    i%4==3  zoom OUT progressive (1.11 -> 1.0, linear)

  Micro-punches (RÈGLE PRO #3): every 3.5 s inside a segment a gaussian
  impulse  AMP * exp(-((t - tp)/sigma)^2)  is ADDED to the base curve
  (AMP=0.10, sigma=0.30/2.5=0.12).

Usage:
    python -m engine.video_dynamics base_only.mp4 edl.json -o base_dyn.mp4
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from . import config
from . import ffmpeg_utils
from .timeline import output_duration


def _seg_curve(i: int, o_start: float, dur: float, t: str) -> str:
    """Base Ken Burns z-curve for segment *i* as a function of time token *t*."""
    # p = clamped local progress in [0, 1]
    p = f"(clip(({t}-{o_start:.3f})/{max(dur, 0.001):.3f},0,1))"
    rng = f"{config.KB_ZOOM_MAX - config.KB_ZOOM_MIN:.3f}"  # 0.110
    lo = f"{config.KB_ZOOM_MIN:.3f}"
    hi = f"{config.KB_ZOOM_MAX:.3f}"
    mode = i % 4
    if mode == 0:        # IN slow (ease-out cube)
        return f"({lo}+{rng}*(1-pow(1-{p},3)))"
    if mode == 1:        # IN progressive (linear)
        return f"({lo}+{rng}*{p})"
    if mode == 2:        # OUT slow (ease-out cube)
        return f"({hi}-{rng}*(1-pow(1-{p},3)))"
    return f"({hi}-{rng}*{p})"  # OUT progressive (linear)


def _punch_terms(o_start: float, o_end: float, t: str) -> str:
    """Sum of gaussian micro-punch terms for a segment, '' if none."""
    terms: List[str] = []
    tp = o_start + config.PUNCH_EVERY
    while tp < o_end - 0.2:                       # leave the tail clean
        terms.append(
            f"{config.PUNCH_AMP}*exp(-pow(({t}-{tp:.3f})/{config.PUNCH_SIGMA:.4f},2))"
        )
        tp += config.PUNCH_EVERY
    return ("+" + "+".join(terms)) if terms else ""


def _flash_punch_terms(flash_times: Optional[List[float]], t: str) -> str:
    """Extra synced punch-zoom gaussians ADDED to the z-curve at key moments."""
    if not flash_times:
        return ""
    terms = [
        f"{config.FLASH_PUNCH_AMP}*exp(-pow(({t}-{tf:.3f})/{config.FLASH_PUNCH_SIGMA:.4f},2))"
        for tf in flash_times
    ]
    return ("+" + "+".join(terms)) if terms else ""


def _light_punch_terms(light_times: Optional[List[float]], t: str) -> str:
    """Tiny synced punch-zoom gaussians at each speech-pause light overlay."""
    if not light_times:
        return ""
    terms = [
        f"{config.LIGHT_OVERLAY_PUNCH_AMP}*exp(-pow(({t}-{tl:.3f})/{config.LIGHT_OVERLAY_PUNCH_SIGMA:.4f},2))"
        for tl in light_times
    ]
    return ("+" + "+".join(terms)) if terms else ""


def build_zoom_expr(ranges: List[dict], fps: int = config.FPS,
                    flash_times: Optional[List[float]] = None,
                    light_times: Optional[List[float]] = None) -> str:
    """
    Build the full piecewise zoompan ``z`` expression.

    Output segment boundaries come from the EDL ranges: kept range *i* occupies
    output time [o_start, o_start + range_len).  Time is inlined as (on/fps) so
    the expression stays a single statement (no ';' to escape in the filtergraph).

    *flash_times* (output seconds) add a synced punch-zoom at each key moment.
    *light_times* (output seconds) add a much smaller punch-zoom at each
    speech-pause light-leak overlay (see :func:`build_light_overlay_filter`).
    """
    t = f"(on/{fps})"
    o_start = 0.0
    bounds = []
    for r in ranges:
        dur = r["end"] - r["start"]
        bounds.append((o_start, o_start + dur, dur))
        o_start += dur

    # Build nested if() from last to first segment; the last segment also acts
    # as the held default past the end.
    nested = f"{config.KB_ZOOM_MAX}"
    for i in reversed(range(len(bounds))):
        o0, o1, dur = bounds[i]
        seg_z = _seg_curve(i, o0, dur, t) + _punch_terms(o0, o1, t)
        if i == len(bounds) - 1:
            nested = seg_z
        else:
            nested = f"if(lt({t},{o1:.3f}),{seg_z},{nested})"

    punch = _flash_punch_terms(flash_times, t) + _light_punch_terms(light_times, t)
    if punch:
        nested = f"({nested}{punch})"
    return nested


def build_light_overlay_filter(light_times: Optional[List[float]]) -> str:
    """Warm "light leak" sweep at each speech pause — a soft, time-based `eq`
    pulse train (brightness lift + warm gamma shift on r/b channels).

    Deliberately soft and warm: the face must stay clearly visible underneath,
    it should read as a light passing over the frame rather than a photo
    capture. (The old blinding white camera flash was removed on product
    request — the light-leak is now the ONLY light effect.) Returns '' when
    there is nothing to do, so the filter chain is unchanged for renders
    without detected pauses.
    """
    if not light_times:
        return ""
    bright_terms = "+".join(
        f"{config.LIGHT_OVERLAY_BRIGHTNESS}*exp(-pow((t-{tl:.3f})/{config.LIGHT_OVERLAY_SIGMA:.4f}\\,2))"
        for tl in light_times
    )
    warm_terms = "+".join(
        f"{config.LIGHT_OVERLAY_WARMTH}*exp(-pow((t-{tl:.3f})/{config.LIGHT_OVERLAY_SIGMA:.4f}\\,2))"
        for tl in light_times
    )
    return (
        f"eq=brightness='{bright_terms}'"
        f":gamma_r='1+({warm_terms})':gamma_b='1-({warm_terms})*0.6'"
        ":eval=frame"
    )


def build_vf(ranges: List[dict], flash_times: Optional[List[float]] = None,
            light_times: Optional[List[float]] = None,
            eq_light_times: Optional[List[float]] = None) -> str:
    """Full -vf chain: pre-scale x2 -> zoompan -> final 1080x1920 scale.

    The x/y expressions add a slow panoramic drift while the piecewise z curve
    does zoom-in/zoom-out plus micro-punches. This makes important moments feel
    dynamic instead of a static centered zoom.

    *flash_times* (output seconds) add a synced punch zoom at each key moment
    (the old white full-screen camera flash was removed — the punch zoom is
    the only accent kept there). *light_times* (output seconds) add a tiny
    punch zoom at every speech pause AND every motion-design transition cut.
    *eq_light_times* is the SUBSET that also gets the synthesized warm `eq`
    pulse: only the motion-design transition instants — pause instants now get
    the real light-leak video+audio overlay instead (composited separately),
    so they must NOT also receive the synthesized brightness/warmth pulse.
    """
    z = build_zoom_expr(ranges, flash_times=flash_times, light_times=light_times)
    t = f"(on/{config.FPS})"
    x = f"(iw-iw/zoom)*(0.50+0.10*sin({t}*0.85))"
    y = f"(ih-ih/zoom)*(0.50+0.06*cos({t}*0.65))"
    chain = (
        "scale=iw*2:ih*2,"
        f"zoompan=z='{z}'"
        f":x='{x}':y='{y}'"
        f":d=1:s={config.WIDTH}x{config.HEIGHT}:fps={config.FPS},"
        f"scale={config.WIDTH}:{config.HEIGHT}"
    )
    light = build_light_overlay_filter(eq_light_times)
    if light:
        chain += "," + light
    return chain


def prepare_light_leak_overlay_clip(out_path: str) -> str:
    """Convert the user's real light-leak asset into an alpha-keyed ProRes 4444
    overlay clip: black background -> transparent (via lumakey), then the
    whole alpha channel scaled down so the face stays visible underneath
    (reduced opacity, screen/lighten-style). Video only — the asset's real
    audio is mixed separately as the "light_leak_original" SFX cue.

    The asset is a 16:9 clip while the montage is 9:16 vertical: it is
    cover-scaled + center-cropped to the FULL 1080x1920 frame first, so the
    light sweep covers the whole video instead of a horizontal band.
    """
    ffmpeg_utils.ensure_ffmpeg()
    # VERTICAL_COVER est la formule canonique plein cadre suivante :
    # scale={config.WIDTH}:{config.HEIGHT}:force_original_aspect_ratio=increase,
    # crop={config.WIDTH}:{config.HEIGHT}
    vf = (
        f"{config.VERTICAL_COVER},"
        "lumakey=threshold=0.12:tolerance=0.08:softness=0.15,"
        f"colorchannelmixer=aa={config.LIGHT_OVERLAY_ASSET_OPACITY},"
        f"format={config.PRORES_PIX_FMT}"
    )
    ffmpeg_utils.run([
        ffmpeg_utils.FFMPEG, "-y", "-i", config.LIGHT_OVERLAY_ASSET_MP4,
        "-vf", vf, "-an",
        "-c:v", "prores_ks", "-profile:v", config.PRORES_PROFILE,
        "-pix_fmt", config.PRORES_PIX_FMT,
        out_path,
    ])
    return out_path


def apply_dynamics(base_only: str, edl_path: str, out_path: str,
                   flash_times: Optional[List[float]] = None,
                   light_times: Optional[List[float]] = None,
                   eq_light_times: Optional[List[float]] = None) -> str:
    ffmpeg_utils.ensure_ffmpeg()
    with open(edl_path, "r", encoding="utf-8") as fh:
        ranges = json.load(fh)["ranges"]

    vf = build_vf(ranges, flash_times=flash_times, light_times=light_times,
                  eq_light_times=eq_light_times)
    ffmpeg_utils.run([
        ffmpeg_utils.FFMPEG, "-y", "-i", base_only,
        "-vf", vf,
        "-c:v", "libx264", "-preset", config.ENGINE_INTERMEDIATE_PRESET,
        "-crf", str(config.ENGINE_INTERMEDIATE_CRF), "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        out_path,
    ])
    n_flash = len(flash_times or [])
    n_light = len(light_times or [])
    n_eq_light = len(eq_light_times or [])
    print(f"[video_dynamics] Ken Burns + micro-punches + {n_flash} key-moment "
          f"punch-zooms + {n_light} pause/transition punch-zooms "
          f"({n_eq_light} with warm eq pulse) over "
          f"{output_duration(ranges):.1f}s -> {out_path}")
    return out_path


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Ken Burns + micro-punches -> base_dyn.mp4")
    ap.add_argument("base_only", help="concatenated base video")
    ap.add_argument("edl", help="edl.json")
    ap.add_argument("-o", "--out", default="base_dyn.mp4")
    ap.add_argument("--print-expr", action="store_true", help="print zoom expr and exit")
    args = ap.parse_args(argv)
    if args.print_expr:
        with open(args.edl, "r", encoding="utf-8") as fh:
            print(build_zoom_expr(json.load(fh)["ranges"]))
        return 0
    apply_dynamics(args.base_only, args.edl, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
