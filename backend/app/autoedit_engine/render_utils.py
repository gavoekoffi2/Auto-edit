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

    If ffmpeg dies mid-encode (disk full, OOM-kill, bad build), a raw pipe
    write raises BrokenPipeError ("[Errno 32]") with ZERO context. This class
    converts that into a RuntimeError carrying ffmpeg's stderr tail so the job
    error actually says WHY (e.g. "No space left on device").
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
                ffmpeg_utils.FFMPEG, "-y", "-v", "error",
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

    def _stderr_tail(self) -> str:
        if not self.proc or not self.proc.stderr:
            return ""
        try:
            return self.proc.stderr.read().decode("utf-8", "ignore")[-1200:]
        except OSError:
            return ""

    def _raise_encode_failure(self, cause: str) -> None:
        err = self._stderr_tail()
        ret = None
        if self.proc:
            try:
                ret = self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None
        detail = err.strip() or cause
        raise RuntimeError(
            f"Encodage ProRes interrompu pour {self.out_path} "
            f"(ffmpeg code={ret}): {detail}"
        )

    def write(self, img: Image.Image) -> None:
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        if img.size != (self.width, self.height):
            img = img.resize((self.width, self.height))
        assert self.proc and self.proc.stdin
        try:
            self.proc.stdin.write(img.tobytes())
        except (BrokenPipeError, OSError):
            self._raise_encode_failure("ffmpeg s'est arrêté pendant l'encodage")

    def close(self) -> None:
        if not self.proc:
            return
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass  # ffmpeg already gone — the wait() below reports it
        err = self._stderr_tail()
        ret = self.proc.wait()
        self.proc = None
        if ret != 0:
            raise RuntimeError(
                f"Encodage ProRes échoué pour {self.out_path} (code={ret}):\n{err}"
            )

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
