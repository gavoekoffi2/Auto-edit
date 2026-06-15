"""
STEP 9 — Multi-pass composite.

Overlays (graphics, then B-roll, then popups — the edl order is the z-order)
are burned onto ``base_dyn.mp4`` to produce ``composite_nosfx.mp4``.

OOM guard: NEVER one ffmpeg with every overlay.  Process in batches of
COMPOSITE_BATCH (12); each pass takes the previous pass output as its base.

Per overlay in a batch:
    [N:v]setpts=PTS-STARTPTS+START/TB[aN]
    [prev][aN]overlay=enable='between(t,START,END)'[vN]
Finalised with [vN]null[outv]; mapped with the base audio (-c:a copy).

Usage:
    python -m engine.composite base_dyn.mp4 edl.json -o composite_nosfx.mp4
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from typing import List, Optional

from . import config
from . import ffmpeg_utils


def _batch_filter(overlays: List[dict]) -> str:
    """Build the filter_complex chaining a batch of overlays onto input 0."""
    parts: List[str] = []
    prev = "[0:v]"
    for i, ov in enumerate(overlays, start=1):
        s, e = float(ov["start"]), float(ov["end"])
        parts.append(f"[{i}:v]setpts=PTS-STARTPTS+{s:.3f}/TB[a{i}]")
        out = f"[v{i}]"
        parts.append(f"{prev}[a{i}]overlay=enable='between(t,{s:.3f},{e:.3f})':eof_action=pass{out}")
        prev = out
    parts.append(f"{prev}null[outv]")
    return ";".join(parts)


def _run_pass(base: str, overlays: List[dict], out_path: str) -> str:
    cmd: List[str] = [ffmpeg_utils.FFMPEG, "-y", "-i", base]
    for ov in overlays:
        cmd += ["-i", ov["mov"]]
    cmd += [
        "-filter_complex", _batch_filter(overlays),
        "-map", "[outv]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", config.ENGINE_INTERMEDIATE_PRESET,
        "-crf", str(config.ENGINE_INTERMEDIATE_CRF), "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        out_path,
    ]
    ffmpeg_utils.run(cmd)
    return out_path


def composite(base_dyn: str, edl_path: str, out_path: str,
              workdir: Optional[str] = None) -> str:
    ffmpeg_utils.ensure_ffmpeg()
    with open(edl_path, "r", encoding="utf-8") as fh:
        overlays = json.load(fh).get("overlays", [])

    # A missing .mov (failed render of one overlay) must not abort the whole
    # composite — drop it with a warning and keep the montage going.
    missing = [ov for ov in overlays if not os.path.exists(ov.get("mov", ""))]
    for ov in missing:
        print(f"[composite] WARN overlay {ov.get('id')} skipped (missing {ov.get('mov')})")
    overlays = [ov for ov in overlays if os.path.exists(ov.get("mov", ""))]

    if not overlays:
        shutil.copy2(base_dyn, out_path)
        print(f"[composite] no overlays -> copied base to {out_path}")
        return out_path

    workdir = workdir or os.path.dirname(os.path.abspath(out_path)) or "."
    os.makedirs(workdir, exist_ok=True)

    current = base_dyn
    batches = [overlays[i:i + config.COMPOSITE_BATCH]
               for i in range(0, len(overlays), config.COMPOSITE_BATCH)]
    tmp_files: List[str] = []
    for bi, batch in enumerate(batches):
        is_last = bi == len(batches) - 1
        dest = out_path if is_last else os.path.join(workdir, f"_composite_pass{bi}.mp4")
        _run_pass(current, batch, dest)
        if not is_last:
            tmp_files.append(dest)
        current = dest
        print(f"[composite] pass {bi + 1}/{len(batches)} ({len(batch)} overlays) -> {dest}")

    for f in tmp_files:                          # keep only the final output
        if os.path.exists(f) and f != out_path:
            os.remove(f)
    print(f"[composite] {len(overlays)} overlays in {len(batches)} pass(es) -> {out_path}")
    return out_path


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Multi-pass overlay composite")
    ap.add_argument("base_dyn", help="base_dyn.mp4")
    ap.add_argument("edl", help="edl.json with overlays")
    ap.add_argument("-o", "--out", default="composite_nosfx.mp4")
    ap.add_argument("--print-filter", action="store_true",
                    help="print the first-batch filter_complex and exit")
    args = ap.parse_args(argv)
    if args.print_filter:
        overlays = json.load(open(args.edl, encoding="utf-8")).get("overlays", [])
        print(_batch_filter(overlays[:config.COMPOSITE_BATCH]))
        return 0
    composite(args.base_dyn, args.edl, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
