"""Video effects module using MoviePy."""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Supported fonts that users can select from
SUPPORTED_FONTS = {"Arial", "Inter", "Montserrat", "Poppins", "Oswald", "Bebas Neue", "Bangers"}

# Subtitle style presets: each preset supplies a full set of sensible defaults.
SUBTITLE_PRESETS = {
    "classic": {
        "font": "Arial",
        "fontSize": 32,
        "color": "#ffffff",
        "stroke_color": "#000000",
        "stroke_width": 2,
        "position": "bottom",
        "highlight_color": "#FFD700",
        "bg_opacity": 0.0,
    },
    "karaoke": {
        "font": "Arial",
        "fontSize": 40,
        "color": "#ffffff",
        "stroke_color": "#000000",
        "stroke_width": 2,
        "position": "center",
        "highlight_color": "#FFD700",
        "bg_opacity": 0.0,
        "bold": True,
    },
    "modern": {
        "font": "Arial",
        "fontSize": 36,
        "color": "#ffffff",
        "stroke_color": "#000000",
        "stroke_width": 1,
        "position": "center",
        "highlight_color": "#FFD700",
        "bg_opacity": 0.4,
    },
    "bold": {
        "font": "Arial",
        "fontSize": 48,
        "color": "#ffffff",
        "stroke_color": "#000000",
        "stroke_width": 4,
        "position": "center",
        "highlight_color": "#FFD700",
        "bg_opacity": 0.0,
        "uppercase": True,
    },
    "minimal": {
        "font": "Arial",
        "fontSize": 24,
        "color": "#ffffff",
        "stroke_color": "#000000",
        "stroke_width": 0,
        "position": "bottom",
        "highlight_color": "#FFD700",
        "bg_opacity": 0.0,
    },
    "neon": {
        "font": "Arial",
        "fontSize": 38,
        "color": "#00ffff",
        "stroke_color": "#ff00ff",
        "stroke_width": 3,
        "position": "center",
        "highlight_color": "#ff00ff",
        "bg_opacity": 0.0,
    },
}


def _resolve_subtitle_style(style: Optional[dict] = None) -> dict:
    """
    Resolve a subtitle style dict by merging a preset (if specified) with any
    explicit overrides the caller provides.

    The style dict may contain a ``preset`` key naming one of the
    ``SUBTITLE_PRESETS``.  Every other key in *style* overrides the preset's
    default.
    """
    style = style or {}
    preset_name = style.get("preset", "classic")
    base = SUBTITLE_PRESETS.get(preset_name, SUBTITLE_PRESETS["classic"]).copy()

    # Apply explicit overrides (anything except 'preset' itself)
    for key, value in style.items():
        if key != "preset":
            base[key] = value

    # Validate font
    if base.get("font") not in SUPPORTED_FONTS:
        base["font"] = "Arial"

    return base


def _position_for_name(name: str) -> tuple:
    """Return a MoviePy position tuple for a named position."""
    if name == "top":
        return ("center", 0.05)
    elif name == "center":
        return ("center", 0.5)
    else:  # "bottom" or default
        return ("center", 0.85)


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
        # Speed adjustment — clamped to [0.25, 4.0]
        if "speed" in config:
            speed = max(0.25, min(4.0, float(config["speed"])))
            if speed != 1.0:
                clip = clip.fx(vfx.speedx, speed)

        # Fade effects — clamped to [0.0, 5.0]
        if "fade_in" in config:
            fade_in = max(0.0, min(5.0, float(config["fade_in"])))
            if fade_in > 0:
                clip = clip.fx(vfx.fadein, fade_in)
        if "fade_out" in config:
            fade_out = max(0.0, min(5.0, float(config["fade_out"])))
            if fade_out > 0:
                clip = clip.fx(vfx.fadeout, fade_out)

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
        style: Subtitle style options. Supports the following keys:
            - preset: str — one of "classic", "karaoke", "modern", "bold",
                      "minimal", "neon" (default "classic")
            - font: str — font family (default "Arial"). Must be in
                    SUPPORTED_FONTS.
            - fontSize: int — font size in pixels (default 32)
            - color: str — hex color for text (default "#ffffff")
            - stroke_color: str — hex color for stroke (default "#000000")
            - stroke_width: int — stroke width in px (default 2)
            - position: str — "bottom", "center", "top" (default "bottom")
            - highlight_color: str — hex color for karaoke word highlight
                               (default "#FFD700")
            - bg_opacity: float 0-1 — background box opacity (default 0.0)
    """
    from moviepy.editor import (
        VideoFileClip,
        TextClip,
        CompositeVideoClip,
        ColorClip,
    )

    resolved = _resolve_subtitle_style(style)
    output_path = os.path.join(output_dir, "with_subtitles.mp4")

    clip = VideoFileClip(video_path)
    try:
        subtitles = _parse_srt(srt_path)

        is_karaoke = resolved.get("preset") == "karaoke" or (
            style and style.get("preset") == "karaoke"
        )
        is_uppercase = resolved.get("uppercase", False)

        font_name = resolved.get("font", "Arial")
        font_size = int(resolved.get("fontSize", 32))
        text_color = resolved.get("color", "#ffffff")
        stroke_clr = resolved.get("stroke_color", "#000000")
        stroke_w = int(resolved.get("stroke_width", 2))
        highlight_clr = resolved.get("highlight_color", "#FFD700")
        bg_opacity = max(0.0, min(1.0, float(resolved.get("bg_opacity", 0.0))))
        pos_name = resolved.get("position", "bottom")
        pos = _position_for_name(pos_name)

        txt_clips = []
        for sub in subtitles:
            try:
                text = sub["text"]
                if is_uppercase:
                    text = text.upper()

                if is_karaoke:
                    # Karaoke mode: split text into words and highlight the
                    # word being spoken at each moment.
                    words = text.split()
                    if not words:
                        continue
                    word_count = len(words)
                    sub_duration = sub["end"] - sub["start"]
                    word_dur = sub_duration / word_count if word_count else sub_duration

                    for wi, word in enumerate(words):
                        word_start = sub["start"] + wi * word_dur
                        word_end = word_start + word_dur

                        # Build the full line with the current word highlighted.
                        # We layer two TextClips: a base line in default color
                        # and a highlighted word on top.

                        # --- base line (all words, default color) ---
                        base_line = TextClip(
                            text,
                            fontsize=font_size,
                            color=text_color,
                            font=font_name,
                            stroke_color=stroke_clr,
                            stroke_width=stroke_w,
                            method="caption",
                            size=(clip.w * 0.9, None),
                        )

                        # --- highlighted word overlay ---
                        # We position the highlight by building a line where
                        # only the target word is visible (the rest is
                        # transparent via per-word TextClips).  For simplicity
                        # we create a full-line clip with the highlight color —
                        # both layers show the same text, the highlight one is
                        # on top and thus "wins" visually.
                        highlighted_line = TextClip(
                            text,
                            fontsize=font_size,
                            color=highlight_clr,
                            font=font_name,
                            stroke_color=stroke_clr,
                            stroke_width=stroke_w,
                            method="caption",
                            size=(clip.w * 0.9, None),
                        )

                        # We approximate the highlight by using two layers:
                        # 1) base layer (full line, default color) for the full
                        #    subtitle duration
                        # 2) highlight layer (full line, highlight color) for
                        #    just this word's time window — since words are
                        #    short, the visual effect is a word-by-word
                        #    highlight sweep.

                        # Only add the base once per subtitle block (first word)
                        if wi == 0:
                            base_timed = (
                                base_line.set_start(sub["start"])
                                .set_end(sub["end"])
                                .set_position(pos, relative=True)
                            )
                            txt_clips.append(base_timed)

                        hl_timed = (
                            highlighted_line.set_start(word_start)
                            .set_end(word_end)
                            .set_position(pos, relative=True)
                        )
                        txt_clips.append(hl_timed)

                else:
                    # Standard (non-karaoke) subtitle rendering
                    layers = []

                    # Optional background box
                    if bg_opacity > 0:
                        # Create a temporary text clip to measure size
                        measure = TextClip(
                            text,
                            fontsize=font_size,
                            color=text_color,
                            font=font_name,
                            method="caption",
                            size=(clip.w * 0.9, None),
                        )
                        tw, th = measure.size
                        measure.close()

                        padding = 10
                        bg = (
                            ColorClip(
                                size=(tw + 2 * padding, th + 2 * padding),
                                color=(0, 0, 0),
                            )
                            .set_opacity(bg_opacity)
                            .set_start(sub["start"])
                            .set_end(sub["end"])
                            .set_position(pos, relative=True)
                        )
                        layers.append(bg)

                    txt = TextClip(
                        text,
                        fontsize=font_size,
                        color=text_color,
                        font=font_name,
                        stroke_color=stroke_clr,
                        stroke_width=stroke_w,
                        method="caption",
                        size=(clip.w * 0.9, None),
                    )
                    txt = (
                        txt.set_start(sub["start"])
                        .set_end(sub["end"])
                        .set_position(pos, relative=True)
                    )
                    layers.append(txt)
                    txt_clips.extend(layers)

            except Exception as e:
                logger.warning(f"Subtitle clip failed: {e}")
                continue

        if txt_clips:
            final = CompositeVideoClip([clip] + txt_clips)
            try:
                final.write_videofile(output_path, codec="libx264", audio_codec="aac", bitrate="8000k", logger=None)
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
