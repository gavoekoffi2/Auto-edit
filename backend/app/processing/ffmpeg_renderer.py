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
    sfx_timestamps: list[float] | None = None
    sfx_volume: float = 0.22


@dataclass
class _TimelineBroll:
    """B-roll cue mapped from source-video time to rendered-output time."""

    start: float
    end: float
    clip_path: str


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

        # 2. Prépare les B-rolls pour le pass final.
        # Ancienne stratégie: remplacer un segment uniquement si le cue couvrait
        # exactement tout le cut. En pratique l'EDL contient souvent un seul cut
        # long, donc les B-rolls internes n'apparaissaient jamais. On mappe
        # maintenant chaque cue dans la timeline de sortie et on l'overlay en
        # plein écran pendant sa fenêtre.
        mapped_broll = self._map_broll_to_output_timeline(list(broll_cues or []), kept)

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

        # 4. Pass final: aspect/res, motion zoom, B-roll timeline, captions, overlays, music
        final_out = os.path.join(out_dir, "final_output.mp4")
        self._final_pass(
            concat_out,
            final_out,
            options,
            broll_cues=mapped_broll,
            overlays=list(overlays or []),
        )

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
    def _map_broll_to_output_timeline(
        self,
        broll_cues: list[BrollCue],
        kept_cuts: list[Cut],
    ) -> list[_TimelineBroll]:
        """Map B-roll source timestamps to the post-EDL output timeline."""
        mapped: list[_TimelineBroll] = []
        if not broll_cues or not kept_cuts:
            return mapped

        output_cursor = 0.0
        for cut in kept_cuts:
            for cue in broll_cues:
                if not cue.clip_path or not os.path.exists(cue.clip_path):
                    continue
                if cue.segment_end <= cut.source_start or cue.segment_start >= cut.source_end:
                    continue
                src_start = max(cue.segment_start, cut.source_start)
                src_end = min(cue.segment_end, cut.source_end)
                if src_end <= src_start:
                    continue
                mapped.append(
                    _TimelineBroll(
                        start=output_cursor + (src_start - cut.source_start),
                        end=output_cursor + (src_end - cut.source_start),
                        clip_path=cue.clip_path,
                    )
                )
            output_cursor += cut.duration
        return mapped

    def _final_pass(
        self,
        in_path: str,
        out_path: str,
        options: RenderOptions,
        broll_cues: list[_TimelineBroll] | None = None,
        overlays: list[OverlayClip] | None = None,
    ) -> None:
        width, height = _RES.get(options.aspect_ratio, _RES["9:16"])
        broll_cues = broll_cues or []
        overlays = overlays or []

        cmd = [self.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error", "-i", in_path]
        for cue in broll_cues:
            cmd += ["-i", cue.clip_path]

        music_input_index: int | None = None
        if options.music_path and os.path.exists(options.music_path):
            music_input_index = 1 + len(broll_cues)
            cmd += ["-i", options.music_path]

        sfx_indices: list[tuple[int, float]] = []
        sfx_times = [t for t in (options.sfx_timestamps or []) if t >= 0]
        # Limit SFX count so long videos do not create huge filtergraphs.
        for t in sfx_times[:18]:
            input_idx = len(cmd)  # placeholder, overwritten below is not reliable for inputs
            del input_idx
            sfx_indices.append((1 + len(broll_cues) + (1 if music_input_index is not None else 0) + len(sfx_indices), t))
            # Short high-low double tone: light "pop/whoosh" without external assets.
            cmd += [
                "-f", "lavfi",
                "-t", "0.18",
                "-i", "sine=frequency=920:sample_rate=44100:duration=0.18",
            ]

        filter_parts: list[str] = []
        base_vf = (
            f"scale={width * 1.08:.0f}:{height * 1.08:.0f}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}:"
            f"x='(in_w-out_w)/2+22*sin(t*1.15)':"
            f"y='(in_h-out_h)/2+18*cos(t*0.90)',"
            "eq=contrast=1.07:saturation=1.13:brightness=0.015,"
            "vignette=PI/7"
        )
        filter_parts.append(f"[0:v]{base_vf},format=yuv420p[v0]")
        current = "v0"

        for idx, cue in enumerate(broll_cues, start=1):
            dur = max(0.4, cue.end - cue.start)
            filter_parts.append(
                f"[{idx}:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},format=rgba,"
                f"fade=t=in:st=0:d=0.20:alpha=1,"
                f"fade=t=out:st={max(0.0, dur - 0.25):.3f}:d=0.25:alpha=1,"
                f"setpts=PTS-STARTPTS+{cue.start:.3f}/TB[br{idx}]"
            )
            out_label = f"vb{idx}"
            filter_parts.append(
                f"[{current}][br{idx}]overlay=0:0:"
                f"enable='between(t,{cue.start:.3f},{cue.end:.3f})':"
                f"eof_action=pass[{out_label}]"
            )
            current = out_label

        subtitle_filters: list[str] = []
        if options.burn_captions_srt and os.path.exists(options.burn_captions_srt):
            srt = _escape_filter_path(options.burn_captions_srt)
            style = (
                "FontName=Arial,FontSize=18,Bold=1,"
                "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                "BackColour=&H99000000,BorderStyle=3,Outline=2,Shadow=1,"
                "Alignment=2,MarginV=150"
            )
            subtitle_filters.append(f"subtitles='{srt}':force_style='{style}'")

        overlay_ass = self._write_overlay_ass(overlays, out_path + ".overlays.ass", width, height)
        if overlay_ass:
            subtitle_filters.append(f"subtitles='{_escape_filter_path(overlay_ass)}'")

        if subtitle_filters:
            filter_parts.append(f"[{current}]{','.join(subtitle_filters)}[vout]")
        else:
            filter_parts.append(f"[{current}]null[vout]")

        audio_inputs = ["[0:a]"]
        if music_input_index is not None:
            filter_parts.append(
                f"[{music_input_index}:a]volume={options.music_volume},"
                "aloop=loop=-1:size=2e9[music]"
            )
            audio_inputs.append("[music]")
        for sfx_i, (input_idx, timestamp) in enumerate(sfx_indices, start=1):
            delay_ms = int(max(0.0, timestamp) * 1000)
            label = f"sfx{sfx_i}"
            filter_parts.append(
                f"[{input_idx}:a]volume={options.sfx_volume},"
                f"afade=t=in:st=0:d=0.015,afade=t=out:st=0.12:d=0.06,"
                f"adelay={delay_ms}|{delay_ms}[{label}]"
            )
            audio_inputs.append(f"[{label}]")

        if len(audio_inputs) > 1:
            filter_parts.append(
                "".join(audio_inputs)
                + f"amix=inputs={len(audio_inputs)}:duration=first:dropout_transition=0[aout]"
            )
            cmd += ["-filter_complex", ";".join(filter_parts), "-map", "[vout]", "-map", "[aout]"]
        else:
            cmd += ["-filter_complex", ";".join(filter_parts), "-map", "[vout]", "-map", "0:a:0?"]

        cmd += [
            "-c:v", "libx264", "-preset", options.preset, "-crf", str(options.crf),
            "-c:a", "aac", "-b:a", options.audio_bitrate,
            "-pix_fmt", "yuv420p", "-r", str(options.fps),
            "-movflags", "+faststart", out_path,
        ]
        self._run(cmd)

    def _write_overlay_ass(
        self,
        overlays: list[OverlayClip],
        path: str,
        width: int,
        height: int,
    ) -> str | None:
        if not overlays:
            return None
        lines = [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {width}",
            f"PlayResY: {height}",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Intro,Arial,58,&H00FFFFFF,&H000000FF,&H00000000,&H99000000,1,0,0,0,100,100,0,0,3,2,0,8,70,70,250,1",
            "Style: Lower,Arial,44,&H00FFFFFF,&H000000FF,&H00000000,&H99000000,1,0,0,0,100,100,0,0,3,2,0,7,70,70,150,1",
            "Style: CTA,Arial,62,&H00FFFFFF,&H000000FF,&H00000000,&HAA000000,1,0,0,0,100,100,0,0,3,2,0,2,85,85,320,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
        written = 0
        for ov in overlays:
            title = str(ov.props.get("title") or ov.props.get("text") or "").strip()
            if not title:
                continue
            style = "Lower"
            if ov.kind == "intro_card":
                style = "Intro"
            elif ov.kind == "cta":
                style = "CTA"
            text = _escape_ass_text(title)
            # ASS fade tag: visible motion without drawtext dependency.
            lines.append(
                f"Dialogue: 2,{_ass_time(ov.start)},{_ass_time(ov.end)},{style},,0,0,0,,{{\\fad(180,180)}}{text}"
            )
            written += 1
        if not written:
            return None
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return path

    def _build_motion_overlay_filters(
        self,
        overlays: list[OverlayClip],
        width: int,
        height: int,
    ) -> str:
        """Generate timed drawbox/drawtext filters for intro cards and CTAs."""
        parts: list[str] = []
        for ov in overlays:
            title = _escape_drawtext(str(ov.props.get("title") or ov.props.get("text") or ""))
            if not title:
                continue
            enable = f"between(t,{ov.start:.3f},{ov.end:.3f})"
            if ov.kind == "intro_card":
                y = int(height * 0.16)
                box_h = int(height * 0.13)
                fs = int(height * 0.038)
                parts.append(
                    f",drawbox=x={int(width*0.06)}:y={y}:w={int(width*0.88)}:h={box_h}:"
                    f"color=black@0.58:t=fill:enable='{enable}'"
                )
                parts.append(
                    f",drawtext=text='{title}':fontcolor=white:fontsize={fs}:"
                    f"x=(w-text_w)/2:y={y + int(box_h*0.30)}:enable='{enable}'"
                )
            elif ov.kind == "cta":
                y = int(height * 0.72)
                box_h = int(height * 0.12)
                fs = int(height * 0.040)
                parts.append(
                    f",drawbox=x={int(width*0.08)}:y={y}:w={int(width*0.84)}:h={box_h}:"
                    f"color=black@0.62:t=fill:enable='{enable}'"
                )
                parts.append(
                    f",drawtext=text='{title}':fontcolor=white:fontsize={fs}:"
                    f"x=(w-text_w)/2:y={y + int(box_h*0.28)}:enable='{enable}'"
                )
            else:
                fs = int(height * 0.032)
                parts.append(
                    f",drawtext=text='{title}':fontcolor=white:fontsize={fs}:"
                    f"x={int(width*0.06)}:y={int(height*0.08)}:"
                    f"box=1:boxcolor=black@0.48:boxborderw=18:enable='{enable}'"
                )
        return "".join(parts)

    # ------------------------------------------------------------------
    def _run(self, cmd: list[str], timeout: int = 1800) -> None:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed (rc={proc.returncode}): {proc.stderr[:600] or proc.stdout[:600]}"
            )


def _escape_filter_path(path: str) -> str:
    return path.replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        s += 1
        cs = 0
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _escape_ass_text(text: str) -> str:
    return text.replace("{", "").replace("}", "").replace("\n", r"\N")


def _escape_drawtext(text: str) -> str:
    if not text:
        return ""
    return (
        text.replace("\\", "\\\\")
        .replace(":", r"\:")
        .replace("'", r"\'")
        .replace(",", r"\,")
        .replace("%", r"\%")
    )
