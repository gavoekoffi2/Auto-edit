"""
Shared ffmpeg / ffprobe helpers.

The spec mandates a static ffmpeg 7+ build.  We resolve the binary from the
``FFMPEG_BIN`` / ``FFPROBE_BIN`` env vars first (handy for static builds that
are not on PATH) and fall back to the names on PATH.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Optional, Sequence

FFMPEG = os.environ.get("FFMPEG_BIN", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE_BIN", "ffprobe")


def ensure_ffmpeg() -> None:
    """Raise a clear error if ffmpeg is not resolvable (ffprobe is optional)."""
    if shutil.which(FFMPEG) is None and not os.path.isfile(FFMPEG):
        raise RuntimeError(
            f"ffmpeg not found (looked for '{FFMPEG}'). Install a static "
            f"ffmpeg 7+ build or set FFMPEG_BIN."
        )


def _default_timeout() -> int | None:
    """Return the configured media-command timeout.

    Import lazily to keep this low-level helper usable from standalone engine
    scripts. A value <= 0 disables the subprocess timeout.
    """
    try:
        from app.config import settings
        configured = int(getattr(settings, "FFMPEG_COMMAND_TIMEOUT_SECONDS", 21600) or 0)
    except Exception:
        configured = int(os.environ.get("FFMPEG_COMMAND_TIMEOUT_SECONDS", "21600") or 0)
    return configured if configured > 0 else None


def run(cmd: Sequence[str], *, timeout: int | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run an ffmpeg/ffprobe command, surfacing stderr on failure.

    The old 30-minute hardcoded timeout could kill longer AutoEdit renders in
    the middle of processing. Default to the app setting instead.
    """
    proc = subprocess.run(
        list(cmd),
        capture_output=True,
        text=True,
        timeout=_default_timeout() if timeout is None else timeout,
        start_new_session=True,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"command failed ({proc.returncode}): {' '.join(map(str, cmd[:6]))} ...\n"
            f"{proc.stderr[-1500:]}"
        )
    return proc


def probe_duration(path: str) -> float:
    """Return media duration in seconds (0.0 on failure)."""
    try:
        proc = run(
            [
                FFPROBE, "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            timeout=60,
            check=False,
        )
        return float(proc.stdout.strip())
    except (ValueError, RuntimeError, FileNotFoundError, subprocess.TimeoutExpired):
        return 0.0


def probe_resolution(path: str) -> tuple[int, int]:
    """Return (width, height) of the first video stream, or (0, 0)."""
    try:
        proc = run(
            [
                FFPROBE, "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "json",
                path,
            ],
            timeout=60,
            check=False,
        )
        data = json.loads(proc.stdout or "{}")
        stream = (data.get("streams") or [{}])[0]
        return int(stream.get("width", 0)), int(stream.get("height", 0))
    except (ValueError, RuntimeError, KeyError, FileNotFoundError, subprocess.TimeoutExpired):
        return 0, 0


def has_audio(path: str) -> bool:
    """True if the file has at least one audio stream."""
    try:
        proc = run(
            [
                FFPROBE, "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=index",
                "-of", "csv=p=0",
                path,
            ],
            timeout=60,
            check=False,
        )
        return bool(proc.stdout.strip())
    except (RuntimeError, FileNotFoundError, subprocess.TimeoutExpired):
        return False
