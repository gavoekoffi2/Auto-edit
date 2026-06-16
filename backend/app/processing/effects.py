"""Video effects module using MoviePy."""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def apply_effects(
    video_path: str,
    output_dir: str,
    effects_config: Optional[dict] = None,
) -> dict:
    """
    Apply visual effects to video using MoviePy.

    Args:
        video_path: Path to input video
        output_dir: Directory for output
        effects_config: Dict with effect parameters:
            - fade_in: float (seconds)
            - fade_out: float (seconds)
            - speed: float (playback speed multiplier)
            - resize: tuple (width, height) or float scale
            - text_overlay: dict with {text, position, fontsize, color}
            - crop_vertical: bool (crop to 9:16 for TikTok/Reels)

    Returns dict with:
        - output_path: path to processed video
    """
    from moviepy.editor import (
        VideoFileClip,
        TextClip,
        CompositeVideoClip,
        vfx,
    )

    config = effects_config or {}
    output_path = os.path.join(output_dir, "with_effects.mp4")

    logger.info(f"Applying effects to: {video_path}")
    clip = VideoFileClip(video_path)
    try:
        # Speed adjustment
        if "speed" in config and config["speed"] != 1.0:
            clip = clip.fx(vfx.speedx, config["speed"])

        # Fade effects
        if "fade_in" in config:
            clip = clip.fx(vfx.fadein, config["fade_in"])
        if "fade_out" in config:
            clip = clip.fx(vfx.fadeout, config["fade_out"])

        # Resize
        if "resize" in config:
            clip = clip.resize(config["resize"])

        # Crop to vertical (9:16) for TikTok/Reels
        if config.get("crop_vertical"):
            w, h = clip.size
            target_ratio = 9 / 16
            current_ratio = w / h

            if current_ratio > target_ratio:
                new_w = int(h * target_ratio)
                x_center = w / 2
                clip = clip.crop(
                    x1=x_center - new_w / 2,
                    x2=x_center + new_w / 2,
                )
            clip = clip.resize((1080, 1920))

        # Text overlay
        if "text_overlay" in config:
            txt_config = config["text_overlay"]
            try:
                txt_clip = TextClip(
                    txt_config.get("text", ""),
                    fontsize=txt_config.get("fontsize", 40),
                    color=txt_config.get("color", "white"),
                    font=txt_config.get("font", "Arial"),
                )
                txt_clip = txt_clip.set_position(
                    txt_config.get("position", ("center", "bottom"))
                ).set_duration(clip.duration)

                clip = CompositeVideoClip([clip, txt_clip])
            except Exception as e:
                logger.warning(f"Text overlay failed (ImageMagick may be missing): {e}")

        # Write output
        clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            bitrate="8000k",
            logger=None,
        )
    finally:
        clip.close()

    logger.info(f"Effects applied: {output_path}")
    return {"output_path": output_path}


def add_subtitles(
    video_path: str,
    srt_path: str,
    output_dir: str,
    style: Optional[dict] = None,
) -> dict:
    """
    Burn subtitles into video.

    Args:
        video_path: Path to input video
        srt_path: Path to SRT subtitle file
        output_dir: Directory for output
        style: Subtitle style options (fontsize, color, bg_color)
    """
    from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip

    style = style or {}
    output_path = os.path.join(output_dir, "with_subtitles.mp4")

    clip = VideoFileClip(video_path)
    try:
        subtitles = _parse_srt(srt_path)

        txt_clips = []
        for sub in subtitles:
            try:
                txt = TextClip(
                    sub["text"],
                    fontsize=style.get("fontsize", 32),
                    color=style.get("color", "white"),
                    font=style.get("font", "Arial"),
                    stroke_color=style.get("stroke_color", "black"),
                    stroke_width=style.get("stroke_width", 1),
                    method="caption",
                    size=(clip.w * 0.9, None),
                )
                txt = (
                    txt.set_start(sub["start"])
                    .set_end(sub["end"])
                    .set_position(("center", 0.85), relative=True)
                )
                txt_clips.append(txt)
            except Exception as e:
                logger.warning(f"Subtitle clip failed: {e}")
                continue

        if txt_clips:
            final = CompositeVideoClip([clip] + txt_clips)
            try:
                final.write_videofile(
                    output_path,
                    codec="libx264",
                    audio_codec="aac",
                    bitrate="8000k",
                    logger=None,
                )
            finally:
                final.close()
        else:
            import shutil
            shutil.copy2(video_path, output_path)
    finally:
        clip.close()

    return {"output_path": output_path}


def _parse_srt(srt_path: str) -> list[dict]:
    """Parse SRT file into list of {start, end, text} dicts."""
    subtitles = []
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    blocks = content.split("\n\n")
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 3:
            time_line = lines[1]
            text = " ".join(lines[2:])

            try:
                start_str, end_str = time_line.split(" --> ")
                start = _srt_to_seconds(start_str.strip())
                end = _srt_to_seconds(end_str.strip())
                subtitles.append({"start": start, "end": end, "text": text})
            except (ValueError, IndexError):
                continue

    return subtitles


def _srt_to_seconds(timestamp: str) -> float:
    """Convert SRT timestamp to seconds."""
    timestamp = timestamp.replace(",", ".")
    parts = timestamp.split(":")
    hours = float(parts[0])
    minutes = float(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds
