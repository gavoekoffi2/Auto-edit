"""
STEP 10 — SFX mix + loudnorm.

Generates the 19-sound numpy library (once), delays each cue to its time with a
-60 ms lead (to anticipate the attack), mixes everything under the voice, then
normalises to -14 LUFS / -1 dBTP / LRA 11.

    [i:a]adelay=ms|ms,volume=g[si]
    [0:a][s1]..[sN]amix=inputs=N+1:normalize=0[mix]
    [mix]loudnorm=I=-14:TP=-1:LRA=11[outa]

Usage:
    python -m engine.mix_sfx composite_nosfx.mp4 sfx_cues.json \
        -o composite_withsfx.mp4 [--sfxdir sfx]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, Optional

from . import config
from . import ffmpeg_utils
from . import sfx_lib


def _delay_ms(t: float) -> int:
    return max(0, int(round((t + config.SFX_OFFSET) * 1000)))


def _build_filter(cues: List[dict], sfx_index: Dict[str, str]) -> tuple[str, list]:
    """Return (filter_complex, ordered list of input paths after the video)."""
    inputs: List[str] = []
    parts: List[str] = []
    mix_labels = ["[0:a]"]

    for ci, cue in enumerate(cues, start=1):
        path = sfx_index.get(cue["sfx"])
        if path is None:
            continue
        inputs.append(path)
        idx = len(inputs)                       # ffmpeg input index (0 is video)
        ms = _delay_ms(float(cue["t"]))
        label = f"[s{ci}]"
        parts.append(
            f"[{idx}:a]adelay={ms}|{ms},volume={config.SFX_BUS_GAIN:.2f}{label}"
        )
        mix_labels.append(label)

    if len(mix_labels) == 1:                     # no SFX -> just loudnorm voice
        parts.append(f"[0:a]{config.LOUDNORM}[outa]")
        return ";".join(parts), inputs

    n = len(mix_labels)
    parts.append(
        "".join(mix_labels) +
        f"amix=inputs={n}:normalize=0:duration=first:dropout_transition=0[mix]"
    )
    parts.append(f"[mix]{config.LOUDNORM}[outa]")
    return ";".join(parts), inputs


def mix(video: str, cues_path: str, out_path: str, sfxdir: str = "sfx") -> str:
    ffmpeg_utils.ensure_ffmpeg()
    with open(cues_path, "r", encoding="utf-8") as fh:
        cues = json.load(fh)

    paths = sfx_lib.build_library(sfxdir)         # the 19 sounds (48 kHz mono)

    filt, inputs = _build_filter(cues, paths)
    cmd: List[str] = [ffmpeg_utils.FFMPEG, "-y", "-i", video]
    for p in inputs:
        cmd += ["-i", p]
    cmd += [
        "-filter_complex", filt,
        "-map", "0:v", "-map", "[outa]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        out_path,
    ]
    ffmpeg_utils.run(cmd)
    print(f"[mix_sfx] {len(inputs)} SFX hits mixed, loudnorm -14 LUFS -> {out_path}")
    return out_path


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Mix SFX + loudnorm -> composite_withsfx.mp4")
    ap.add_argument("video", help="composite_nosfx.mp4")
    ap.add_argument("cues", help="sfx_cues.json")
    ap.add_argument("-o", "--out", default="composite_withsfx.mp4")
    ap.add_argument("--sfxdir", default="sfx")
    ap.add_argument("--print-filter", action="store_true")
    args = ap.parse_args(argv)
    if args.print_filter:
        cues = json.load(open(args.cues, encoding="utf-8"))
        # use dummy paths just to render the filter graph
        idx = {n: f"{args.sfxdir}/{n}.wav" for n in config.SFX_NAMES}
        filt, _ = _build_filter(cues, idx)
        print(filt)
        return 0
    mix(args.video, args.cues, args.out, sfxdir=args.sfxdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
