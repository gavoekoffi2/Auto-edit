"""
Shared rendering helpers for RGBA overlay clips.

* easing / fade math
* ProResPipe: stream PIL RGBA frames to a ProRes 4444 .mov (alpha preserved)
  via a single ffmpeg subprocess (frame-by-frame, stdin raw pipe).
"""
from __future__ import annotations

import subprocess
from typing import Optional

from PIL import Image

from . import config
from . import ffmpeg_utils


# --------------------------------------------------------------------------- #
# easing
# --------------------------------------------------------------------------- #
def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def ease_out_cube(p: float) -> float:
    p = clamp(p)
    return 1.0 - (1.0 - p) ** 3


def ease_out_back(p: float, s: float = 1.70158) -> float:
    p = clamp(p)
    return 1.0 + (s + 1.0) * (p - 1.0) ** 3 + s * (p - 1.0) ** 2


def ease_in_out(p: float) -> float:
    p = clamp(p)
    return 3 * p * p - 2 * p * p * p


def alpha_fade(t: float, dur: float,
               fin: float = config.OVERLAY_FADE_IN,
               fout: float = config.OVERLAY_FADE_OUT) -> float:
    """Global opacity envelope: 0->1 over *fin*, hold, 1->0 over *fout*."""
    if t < fin:
        return clamp(t / fin) if fin > 0 else 1.0
    if t > dur - fout:
        return clamp((dur - t) / fout) if fout > 0 else 1.0
    return 1.0


# --------------------------------------------------------------------------- #
# ProRes 4444 RGBA writer
# --------------------------------------------------------------------------- #
class ProResPipe:
    """
    Stream RGBA frames to a ProRes 4444 (yuva444p10le) .mov.

        with ProResPipe(out, w, h, fps) as pipe:
            for ...:
                pipe.write(pil_rgba_image)
    """

    def __init__(self, out_path: str,
                 width: int = config.WIDTH, height: int = config.HEIGHT,
                 fps: int = config.FPS):
        ffmpeg_utils.ensure_ffmpeg()
        self.out_path = out_path
        self.width = width
        self.height = height
        self.proc: Optional[subprocess.Popen] = subprocess.Popen(
            [
                ffmpeg_utils.FFMPEG, "-y",
                "-f", "rawvideo", "-pix_fmt", "rgba",
                "-s", f"{width}x{height}", "-r", str(fps),
                "-i", "pipe:0",
                "-c:v", "prores_ks", "-profile:v", config.PRORES_PROFILE,
                "-pix_fmt", config.PRORES_PIX_FMT,
                "-an", out_path,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    def write(self, img: Image.Image) -> None:
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        if img.size != (self.width, self.height):
            img = img.resize((self.width, self.height))
        assert self.proc and self.proc.stdin
        self.proc.stdin.write(img.tobytes())

    def close(self) -> None:
        if not self.proc:
            return
        assert self.proc.stdin
        self.proc.stdin.close()
        err = self.proc.stderr.read().decode("utf-8", "ignore") if self.proc.stderr else ""
        ret = self.proc.wait()
        self.proc = None
        if ret != 0:
            raise RuntimeError(f"ProRes encode failed for {self.out_path}:\n{err[-1200:]}")

    def __enter__(self) -> "ProResPipe":
        return self

    def __exit__(self, *exc) -> None:
        if exc and exc[0] is not None and self.proc:
            # On error, tear the pipe down without raising a second error.
            try:
                self.proc.kill()
            except OSError:
                pass
            self.proc = None
        else:
            self.close()
