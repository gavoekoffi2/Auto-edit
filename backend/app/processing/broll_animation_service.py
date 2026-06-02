"""Anime une image statique en clip vidéo court via FFmpeg (Ken Burns).

Le service est volontairement minimal et 100% FFmpeg pour le MVP. Plus tard
on pourra brancher Remotion / HyperFrames via `template_renderer.py`.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Iterable, Literal

from app.processing.types import BrollCue

logger = logging.getLogger(__name__)


MotionKind = Literal["ken_burns", "zoom_in", "zoom_out", "pan_lr", "pan_rl", "static"]


_RESOLUTIONS = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
}


@dataclass
class AnimationConfig:
    fps: int = 30
    fade_in: float = 0.3
    fade_out: float = 0.3
    zoom_strength: float = 0.18  # 0..0.5
    aspect_ratio: str = "9:16"


class BrollAnimationService:
    def __init__(self, config: AnimationConfig | None = None, ffmpeg_bin: str = "ffmpeg"):
        self.config = config or AnimationConfig()
        self.ffmpeg_bin = ffmpeg_bin

    # ------------------------------------------------------------------
    def animate_cues(self, cues: Iterable[BrollCue], out_dir: str) -> list[BrollCue]:
        os.makedirs(out_dir, exist_ok=True)
        results: list[BrollCue] = []
        if not shutil.which(self.ffmpeg_bin):
            logger.warning("[broll_animation] ffmpeg introuvable, skip animation")
            for c in cues:
                c.failure_reason = "ffmpeg_missing"
                results.append(c)
            return results

        for idx, cue in enumerate(cues, start=1):
            if not cue.image_path or not os.path.exists(cue.image_path):
                results.append(cue)
                continue
            out_path = os.path.join(out_dir, f"{idx:04d}.mp4")
            try:
                self.animate_image(
                    image_path=cue.image_path,
                    out_path=out_path,
                    duration_s=max(0.5, cue.duration),
                    motion=self._pick_motion(idx),
                    aspect_ratio=cue.aspect_ratio,
                )
                cue.clip_path = out_path
            except Exception as e:
                logger.warning("[broll_animation] cue %d failed: %s", idx, e)
                cue.failure_reason = (cue.failure_reason or "") + f"|animate_failed:{e}"[:200]
            results.append(cue)
        return results

    # ------------------------------------------------------------------
    def animate_image(
        self,
        image_path: str,
        out_path: str,
        duration_s: float,
        motion: MotionKind = "ken_burns",
        aspect_ratio: str = "9:16",
    ) -> str:
        cfg = self.config
        width, height = _RESOLUTIONS.get(aspect_ratio, _RESOLUTIONS[cfg.aspect_ratio])
        total_frames = max(2, int(round(duration_s * cfg.fps)))

        vf = self._build_zoompan_filter(
            width=width,
            height=height,
            total_frames=total_frames,
            fps=cfg.fps,
            motion=motion,
            zoom_strength=cfg.zoom_strength,
            duration_s=duration_s,
            fade_in=cfg.fade_in,
            fade_out=cfg.fade_out,
        )

        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-loop", "1",
            "-i", image_path,
            "-vf", vf,
            "-t", f"{duration_s:.3f}",
            "-r", str(cfg.fps),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-an",
            out_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg animate failed: {proc.stderr[:200]}")
        if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            raise RuntimeError("ffmpeg animate produced empty file")
        return out_path

    # ------------------------------------------------------------------
    @staticmethod
    def _pick_motion(index: int) -> MotionKind:
        # Alterne pour éviter la monotonie
        kinds: list[MotionKind] = ["ken_burns", "zoom_in", "pan_lr", "zoom_out", "pan_rl"]
        return kinds[(index - 1) % len(kinds)]

    @staticmethod
    def _build_zoompan_filter(
        *,
        width: int,
        height: int,
        total_frames: int,
        fps: int,
        motion: MotionKind,
        zoom_strength: float,
        duration_s: float,
        fade_in: float,
        fade_out: float,
    ) -> str:
        # Base: zoompan a besoin d'un input scalé large pour avoir de la marge
        scale_w = int(width * 1.4)
        scale_h = int(height * 1.4)

        # `zoompan` calcule un zoom 1..(1+strength). On peut piloter x/y selon le motion.
        zmax = 1.0 + max(0.05, min(0.5, zoom_strength))
        # FFmpeg zoompan does not expose a `total` variable; bake the frame count into expressions.
        frame_denominator = max(1, total_frames - 1)
        if motion == "zoom_in":
            z_expr = f"min(zoom+0.0008,{zmax})"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = "ih/2-(ih/zoom/2)"
        elif motion == "zoom_out":
            z_expr = f"if(eq(on,1),{zmax},max(zoom-0.0008,1.0))"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = "ih/2-(ih/zoom/2)"
        elif motion == "pan_lr":
            z_expr = f"{zmax}"
            x_expr = f"on/{frame_denominator}*(iw-iw/zoom)"
            y_expr = "ih/2-(ih/zoom/2)"
        elif motion == "pan_rl":
            z_expr = f"{zmax}"
            x_expr = f"(1-on/{frame_denominator})*(iw-iw/zoom)"
            y_expr = "ih/2-(ih/zoom/2)"
        else:  # ken_burns
            z_expr = f"min(zoom+0.0006,{zmax})"
            x_expr = f"on/{frame_denominator}*(iw-iw/zoom)"
            y_expr = "ih/2-(ih/zoom/2)"

        zoompan = (
            f"scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase,"
            f"crop={scale_w}:{scale_h},"
            f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}'"
            f":d={total_frames}:s={width}x{height}:fps={fps}"
        )

        fade = []
        if fade_in > 0:
            fade.append(f"fade=t=in:st=0:d={fade_in}")
        if fade_out > 0:
            fade_start = max(0.0, duration_s - fade_out)
            fade.append(f"fade=t=out:st={fade_start}:d={fade_out}")
        if fade:
            return zoompan + "," + ",".join(fade)
        return zoompan
