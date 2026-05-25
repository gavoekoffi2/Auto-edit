"""Rendu final FFmpeg à partir d'une EDL.

Phase MVP — concat des segments gardés:
  1. Pour chaque `Cut` gardé de l'EDL, on crée un segment via `ffmpeg -ss/-to`.
  2. On concatène ces segments avec le demuxer `concat`.
  3. Optionnel: incrustation des B-roll clips comme **inserts** (remplace le
     segment principal pendant la fenêtre du cue).
  4. Optionnel: brûle les captions SRT/ASS.
  5. Optionnel: ducking de la musique.
  6. Force aspect ratio + résolution finaux.

L'objectif n'est pas le rendu "ultra haute qualité" — c'est d'avoir un
pipeline robuste qui produit un MP4 valide *même si certaines étapes
échouent partiellement*.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Iterable

from app.processing.types import BrollCue, Cut, EditDecisionList, OverlayClip

logger = logging.getLogger(__name__)


@dataclass
class RenderOptions:
    aspect_ratio: str = "9:16"
    fps: int = 30
    crf: int = 20
    preset: str = "veryfast"
    audio_bitrate: str = "192k"
    music_path: str | None = None
    music_volume: float = 0.25
    burn_captions_srt: str | None = None


_RES = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
}


class FFmpegRenderer:
    def __init__(self, ffmpeg_bin: str = "ffmpeg"):
        self.ffmpeg_bin = ffmpeg_bin

    # ------------------------------------------------------------------
    def render(
        self,
        edl: EditDecisionList,
        out_dir: str,
        broll_cues: Iterable[BrollCue] | None = None,
        overlays: Iterable[OverlayClip] | None = None,
        options: RenderOptions | None = None,
    ) -> str:
        if not shutil.which(self.ffmpeg_bin):
            raise RuntimeError("ffmpeg introuvable — installation requise")

        options = options or RenderOptions()
        os.makedirs(out_dir, exist_ok=True)

        kept = edl.kept_cuts()
        if not kept:
            raise RuntimeError("EDL vide: aucun cut à garder")

        # 1. Extrait les segments gardés
        segments_dir = os.path.join(out_dir, "_segments")
        os.makedirs(segments_dir, exist_ok=True)
        segment_paths: list[str] = []
        for i, cut in enumerate(kept, start=1):
            seg_path = os.path.join(segments_dir, f"seg_{i:04d}.mp4")
            self._extract_segment(edl.source_path, cut, seg_path, options)
            segment_paths.append(seg_path)

        # 2. Remplace certains segments par B-roll si cue couvre entièrement le segment
        if broll_cues:
            segment_paths = self._inject_broll(
                segment_paths=segment_paths,
                kept_cuts=kept,
                broll_cues=list(broll_cues),
                out_dir=segments_dir,
                options=options,
            )

        # 3. Concat
        concat_list = os.path.join(out_dir, "concat.txt")
        with open(concat_list, "w", encoding="utf-8") as f:
            for p in segment_paths:
                f.write(f"file '{os.path.abspath(p)}'\n")

        concat_out = os.path.join(out_dir, "_concat.mp4")
        self._run([
            self.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", concat_list,
            "-c", "copy", concat_out,
        ])

        # 4. Pass final: aspect/res, captions, music
        final_out = os.path.join(out_dir, "final_output.mp4")
        self._final_pass(concat_out, final_out, options)

        # cleanup segments
        try:
            shutil.rmtree(segments_dir, ignore_errors=True)
            if os.path.exists(concat_out):
                os.unlink(concat_out)
        except Exception:
            pass

        if not os.path.exists(final_out) or os.path.getsize(final_out) == 0:
            raise RuntimeError("FFmpegRenderer: empty final output")
        return final_out

    # ------------------------------------------------------------------
    def _extract_segment(self, source: str, cut: Cut, dest: str, options: RenderOptions) -> None:
        # On ré-encode pour pouvoir concat proprement (sinon problèmes de GOP).
        cmd = [
            self.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{cut.source_start:.3f}",
            "-to", f"{cut.source_end:.3f}",
            "-i", source,
            "-c:v", "libx264", "-preset", options.preset, "-crf", str(options.crf),
            "-c:a", "aac", "-b:a", options.audio_bitrate,
            "-pix_fmt", "yuv420p",
            "-r", str(options.fps),
            dest,
        ]
        self._run(cmd)

    # ------------------------------------------------------------------
    def _inject_broll(
        self,
        segment_paths: list[str],
        kept_cuts: list[Cut],
        broll_cues: list[BrollCue],
        out_dir: str,
        options: RenderOptions,
    ) -> list[str]:
        # Stratégie simple: si un cue (clip animé) couvre exactement (à ±0.3s)
        # un segment gardé, on substitue le segment par le cue.
        if not broll_cues:
            return segment_paths

        # ré-encode cues pour matcher fps/res
        for idx, cue in enumerate(broll_cues, start=1):
            if not cue.clip_path or not os.path.exists(cue.clip_path):
                continue
            for j, cut in enumerate(kept_cuts):
                same_start = abs(cut.source_start - cue.segment_start) < 0.3
                same_end = abs(cut.source_end - cue.segment_end) < 0.5
                if same_start and same_end:
                    matched = os.path.join(out_dir, f"seg_{j+1:04d}_broll.mp4")
                    self._normalize_clip(cue.clip_path, matched, options, source_segment=segment_paths[j])
                    segment_paths[j] = matched
                    break
        return segment_paths

    def _normalize_clip(self, clip_path: str, dest: str, options: RenderOptions, source_segment: str) -> None:
        # Récupère l'audio du segment original pour garder la voix
        cmd = [
            self.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-i", clip_path,
            "-i", source_segment,
            "-map", "0:v:0", "-map", "1:a:0?",
            "-c:v", "libx264", "-preset", options.preset, "-crf", str(options.crf),
            "-c:a", "aac", "-b:a", options.audio_bitrate,
            "-pix_fmt", "yuv420p",
            "-r", str(options.fps),
            "-shortest",
            dest,
        ]
        try:
            self._run(cmd)
        except Exception:
            # Pas d'audio dans le clip — réessaye sans map audio
            cmd_no_audio = [
                self.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
                "-i", clip_path,
                "-an",
                "-c:v", "libx264", "-preset", options.preset, "-crf", str(options.crf),
                "-pix_fmt", "yuv420p",
                "-r", str(options.fps),
                dest,
            ]
            self._run(cmd_no_audio)

    # ------------------------------------------------------------------
    def _final_pass(self, in_path: str, out_path: str, options: RenderOptions) -> None:
        width, height = _RES.get(options.aspect_ratio, _RES["9:16"])

        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )
        if options.burn_captions_srt and os.path.exists(options.burn_captions_srt):
            srt = options.burn_captions_srt.replace(":", r"\:").replace("'", r"\'")
            vf += f",subtitles='{srt}'"

        cmd = [
            self.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-i", in_path,
        ]
        if options.music_path and os.path.exists(options.music_path):
            cmd += [
                "-i", options.music_path,
                "-filter_complex",
                f"[0:v]{vf}[vout];"
                f"[1:a]volume={options.music_volume},aloop=loop=-1:size=2e9[mloop];"
                "[0:a][mloop]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                "-map", "[vout]", "-map", "[aout]",
            ]
        else:
            cmd += ["-vf", vf, "-c:a", "aac", "-b:a", options.audio_bitrate]

        cmd += [
            "-c:v", "libx264", "-preset", options.preset, "-crf", str(options.crf),
            "-pix_fmt", "yuv420p",
            "-r", str(options.fps),
            "-movflags", "+faststart",
            out_path,
        ]
        self._run(cmd)

    # ------------------------------------------------------------------
    def _run(self, cmd: list[str], timeout: int = 1800) -> None:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed (rc={proc.returncode}): {proc.stderr[:300] or proc.stdout[:300]}"
            )
