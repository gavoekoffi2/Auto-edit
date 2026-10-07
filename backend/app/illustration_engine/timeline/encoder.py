"""ClipWriter — stream PIL frames to a ProRes 4444 clip that keeps its alpha.

Reuses the montage engine's hardened ProRes pipe when it is importable (it
turns a silent BrokenPipeError into an ffmpeg error message that actually says
"No space left on device"), and falls back to an equivalent local pipe so the
illustration engine also runs standalone.
"""
from __future__ import annotations

import shutil
import subprocess
from typing import Optional

from PIL import Image

from .. import config


def ffmpeg_bin() -> str:
    try:
        from ...autoedit_engine import ffmpeg_utils
        return ffmpeg_utils.FFMPEG
    except Exception:  # noqa: BLE001
        return shutil.which("ffmpeg") or "ffmpeg"


class _LocalProResPipe:
    """Minimal stand-in for the montage engine's ProResPipe."""

    def __init__(self, out_path: str, width: int, height: int, fps: int):
        self.out_path, self.width, self.height = out_path, width, height
        self.proc: Optional[subprocess.Popen] = subprocess.Popen(
            [ffmpeg_bin(), "-y", "-v", "error",
             "-f", "rawvideo", "-pix_fmt", "rgba",
             "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0",
             "-c:v", "prores_ks", "-profile:v", config.PRORES_PROFILE,
             "-pix_fmt", config.PRORES_PIX_FMT, "-an", out_path],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE)

    def _fail(self, cause: str) -> None:
        err = ""
        if self.proc and self.proc.stderr:
            try:
                err = self.proc.stderr.read().decode("utf-8", "ignore")[-1200:]
            except OSError:
                pass
        code = None
        if self.proc:
            try:
                code = self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None
        raise RuntimeError(
            f"Encodage ProRes interrompu pour {self.out_path} "
            f"(ffmpeg code={code}): {err.strip() or cause}")

    def write(self, img: Image.Image) -> None:
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        if img.size != (self.width, self.height):
            img = img.resize((self.width, self.height))
        if not (self.proc and self.proc.stdin):
            self._fail("ffmpeg n'est plus disponible")
        try:
            self.proc.stdin.write(img.tobytes())
        except (BrokenPipeError, OSError):
            self._fail("ffmpeg s'est arrêté pendant l'encodage")

    def close(self) -> None:
        if not self.proc:
            return
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        err = ""
        if self.proc.stderr:
            try:
                err = self.proc.stderr.read().decode("utf-8", "ignore")[-1200:]
            except OSError:
                pass
        code = self.proc.wait()
        self.proc = None
        if code != 0:
            raise RuntimeError(
                f"Encodage ProRes échoué pour {self.out_path} (code={code}):\n{err}")


class ClipWriter:
    """Context manager: `with ClipWriter(path, w, h, fps) as w: w.write(img)`."""

    def __init__(self, out_path: str, width: int, height: int, fps: int = 30):
        self.out_path = out_path
        try:
            from ...autoedit_engine.render_utils import ProResPipe
            self._pipe = ProResPipe(out_path, width, height, fps)
        except Exception:  # noqa: BLE001 - standalone fallback
            self._pipe = _LocalProResPipe(out_path, width, height, fps)

    def write(self, image: Image.Image) -> None:
        self._pipe.write(image)

    def close(self) -> None:
        self._pipe.close()

    def __enter__(self) -> "ClipWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            proc = getattr(self._pipe, "proc", None)
            if proc is not None:
                try:
                    proc.kill()
                except OSError:
                    pass
                self._pipe.proc = None
            return
        self.close()
