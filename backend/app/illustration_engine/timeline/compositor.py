"""Compositor — burn the illustration clips onto the original video.

The product rule is that the talking head stays the backbone: the compositor
overlays clips onto the original footage, it never replaces the video track.

Overlays are applied in batches, each pass taking the previous pass output as
its base. That is deliberate: a single ffmpeg invocation with thirty overlay
filters is an out-of-memory kill on a small VPS.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import List, Optional, Sequence

from .. import config
from .encoder import ffmpeg_bin

# How many overlays per ffmpeg pass. Matches the montage engine's OOM guard.
BATCH = 12


def build_batch_filter(overlays: Sequence[dict]) -> str:
    """filter_complex chaining one batch of overlays onto input 0."""
    parts: List[str] = []
    previous = "[0:v]"
    for index, overlay in enumerate(overlays, start=1):
        start = float(overlay["start"])
        end = float(overlay["end"])
        parts.append(f"[{index}:v]setpts=PTS-STARTPTS+{start:.3f}/TB[c{index}]")
        label = f"[v{index}]"
        parts.append(
            f"{previous}[c{index}]overlay=enable='between(t,{start:.3f},"
            f"{end:.3f})':eof_action=pass{label}")
        previous = label
    parts.append(f"{previous}null[outv]")
    return ";".join(parts)


class Compositor:
    def __init__(self, timeout: int = 3600):
        self.timeout = timeout

    def _run_pass(self, base: str, overlays: Sequence[dict], out_path: str) -> str:
        cmd: List[str] = [ffmpeg_bin(), "-y", "-v", "error", "-i", base]
        for overlay in overlays:
            cmd += ["-i", overlay["mov"]]
        cmd += ["-filter_complex", build_batch_filter(overlays),
                "-map", "[outv]"]
        # Keep whatever audio the base already has, untouched: the mixer owns it.
        cmd += ["-map", "0:a?", "-c:a", "copy",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", out_path]
        subprocess.run(cmd, check=True, capture_output=True, timeout=self.timeout)
        return out_path

    def composite(self, base_video: str, overlays: Sequence[dict],
                  out_path: str, workdir: Optional[str] = None) -> str:
        """Overlay every clip onto `base_video`. Returns the produced path."""
        usable = [o for o in overlays
                  if o.get("mov") and os.path.exists(o["mov"])
                  and float(o["end"]) > float(o["start"])]
        if not usable:
            if os.path.abspath(base_video) != os.path.abspath(out_path):
                shutil.copyfile(base_video, out_path)
            return out_path

        workdir = workdir or os.path.dirname(out_path) or "."
        os.makedirs(workdir, exist_ok=True)
        current = base_video
        temporaries: List[str] = []
        batches = [usable[i:i + BATCH] for i in range(0, len(usable), BATCH)]
        try:
            for index, batch in enumerate(batches):
                last = index == len(batches) - 1
                target = out_path if last else os.path.join(
                    workdir, f"_ill_pass{index:02d}.mp4")
                self._run_pass(current, batch, target)
                if not last:
                    temporaries.append(target)
                current = target
        finally:
            for path in temporaries:
                try:
                    os.unlink(path)
                except OSError:
                    pass
        return out_path


def composite_illustrations(base_video: str, overlays: Sequence[dict],
                            out_path: str, workdir: Optional[str] = None
                            ) -> str:
    """Convenience wrapper. Never raises past a clear message."""
    try:
        return Compositor().composite(base_video, overlays, out_path, workdir)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b"").decode("utf-8", "ignore")[-1200:]
        raise RuntimeError(
            f"Compositing des illustrations échoué: {stderr.strip()}") from exc
