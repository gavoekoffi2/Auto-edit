"""
STEP 12 — Burn subtitles into the deliverable.

    ffmpeg -i composite_withsfx.mp4 -vf "ass=master.ass" \
      -c:v libx264 -preset slow -crf 26 -pix_fmt yuv420p \
      -c:a aac -b:a 128k -movflags +faststart final_montage_web.mp4

Target size ~ 25-35 MB for a 90-120 s clip.

Usage:
    python -m engine.finalize composite_withsfx.mp4 master.ass -o final_montage_web.mp4
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

from . import config
from . import ffmpeg_utils


def _escape_filter_path(path: str) -> str:
    """Escape a path for use inside an ffmpeg filter argument."""
    return path.replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def burn_subs(video: str, ass_path: str, out_path: str) -> str:
    ffmpeg_utils.ensure_ffmpeg()
    # fontsdir: libass résout les familles via fontconfig; en pointant AUSSI
    # les polices OFL embarquées dans le repo, le style est garanti même sur
    # une machine où elles ne sont pas installées système (pas de fallback
    # silencieux vers une sans-serif générique).
    fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "assets", "fonts")
    vf = f"ass={_escape_filter_path(ass_path)}"
    if os.path.isdir(fonts_dir):
        vf += f":fontsdir={_escape_filter_path(fonts_dir)}"
    ffmpeg_utils.run([
        ffmpeg_utils.FFMPEG, "-y", "-i", video,
        "-vf", vf,
        "-c:v", "libx264", "-preset", config.FINAL_PRESET,
        "-crf", str(config.FINAL_CRF), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", config.FINAL_AUDIO_BITRATE,
        "-movflags", "+faststart",
        out_path,
    ])
    size_mb = os.path.getsize(out_path) / 1e6 if os.path.exists(out_path) else 0.0
    print(f"[finalize] burned subs -> {out_path} ({size_mb:.1f} MB)")
    return out_path


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Burn ASS subtitles -> final deliverable")
    ap.add_argument("video", help="composite_withsfx.mp4")
    ap.add_argument("ass", help="master.ass")
    ap.add_argument("-o", "--out", default="final_montage_web.mp4")
    args = ap.parse_args(argv)
    burn_subs(args.video, args.ass, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
