"""
Sound effects module.

Generates simple sound effects programmatically using ffmpeg's audio
synthesis filters, and mixes them into a video at specified timestamps.
"""
import os
import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# SFX generation recipes — each maps to ffmpeg audio-filter expressions.
# --------------------------------------------------------------------------- #
SFX_RECIPES = {
    "whoosh": {
        # Frequency sweep from 200 Hz to 2000 Hz — a classic whoosh/transition.
        "filter": (
            "aevalsrc='sin(2*PI*(200+1800*t/{dur})*t)':"
            "s=44100:d={dur},"
            "afade=t=in:st=0:d=0.05,"
            "afade=t=out:st={fade_out_start}:d=0.15"
        ),
        "default_duration": 0.5,
    },
    "pop": {
        # Short sine burst — sounds like a pop/click.
        "filter": (
            "aevalsrc='sin(2*PI*880*t)*exp(-20*t)':"
            "s=44100:d={dur},"
            "afade=t=out:st={fade_out_start}:d=0.05"
        ),
        "default_duration": 0.15,
    },
    "rise": {
        # Ascending tone for intros.
        "filter": (
            "aevalsrc='0.5*sin(2*PI*(200+800*t/{dur})*t)':"
            "s=44100:d={dur},"
            "afade=t=in:st=0:d=0.1,"
            "afade=t=out:st={fade_out_start}:d=0.2"
        ),
        "default_duration": 1.0,
    },
    "drop": {
        # Descending tone with reverb feel for outros.
        "filter": (
            "aevalsrc='0.5*sin(2*PI*(1000-800*t/{dur})*t)*exp(-2*t)':"
            "s=44100:d={dur},"
            "afade=t=in:st=0:d=0.05,"
            "afade=t=out:st={fade_out_start}:d=0.3"
        ),
        "default_duration": 1.0,
    },
    "tick": {
        # Very short click — good for caption appearances.
        "filter": (
            "aevalsrc='sin(2*PI*1200*t)*exp(-50*t)':"
            "s=44100:d={dur},"
            "afade=t=out:st={fade_out_start}:d=0.02"
        ),
        "default_duration": 0.08,
    },
    "swoosh": {
        # Fast frequency sweep — quicker than whoosh, for B-roll transitions.
        "filter": (
            "aevalsrc='sin(2*PI*(500+3000*t/{dur})*t)*exp(-5*t)':"
            "s=44100:d={dur},"
            "afade=t=in:st=0:d=0.02,"
            "afade=t=out:st={fade_out_start}:d=0.1"
        ),
        "default_duration": 0.3,
    },
}

VALID_SFX_TYPES = set(SFX_RECIPES.keys())


# --------------------------------------------------------------------------- #
# Generate an individual sound-effect WAV
# --------------------------------------------------------------------------- #
def generate_sfx(
    sfx_type: str,
    output_path: str,
    duration: float = 0.5,
) -> str:
    """
    Generate a sound-effect audio file using ffmpeg audio synthesis.

    Args:
        sfx_type: One of the keys in ``SFX_RECIPES``.
        output_path: Where to write the resulting WAV file.
        duration: Length in seconds (clamped to [0.05, 5.0]).

    Returns:
        The *output_path* on success.

    Raises:
        ValueError: for unknown *sfx_type*.
        RuntimeError: if ffmpeg fails.
    """
    if sfx_type not in SFX_RECIPES:
        raise ValueError(
            f"Unknown sfx_type '{sfx_type}'. Valid types: {sorted(VALID_SFX_TYPES)}"
        )

    recipe = SFX_RECIPES[sfx_type]
    dur = max(0.05, min(5.0, duration))
    if duration <= 0:
        dur = recipe["default_duration"]

    fade_out_start = max(0.0, dur - 0.15)
    af = recipe["filter"].format(dur=dur, fade_out_start=fade_out_start)

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", af,
        "-t", f"{dur:.3f}",
        "-ac", "1",
        "-ar", "44100",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg SFX generation failed for '{sfx_type}': {result.stderr[-500:]}")

    return output_path


# --------------------------------------------------------------------------- #
# Mix multiple SFX into a video at given timestamps
# --------------------------------------------------------------------------- #
def mix_sfx_at_timestamps(
    video_path: str,
    sfx_entries: list[dict],
    output_path: str,
) -> str:
    """
    Mix sound-effect files into *video_path* at the specified timestamps.

    Args:
        video_path: Source video (must have an audio track).
        sfx_entries: List of dicts, each with:
            - ``path``: path to the SFX audio file
            - ``timestamp``: float, seconds into the video
            - ``volume``: float, volume multiplier (default 0.3)
        output_path: Where to write the result.

    Returns:
        *output_path* on success.
    """
    if not sfx_entries:
        import shutil
        shutil.copy2(video_path, output_path)
        return output_path

    # Build ffmpeg command with adelay + amix.
    inputs = ["-i", video_path]
    for entry in sfx_entries:
        inputs.extend(["-i", entry["path"]])

    # Filter complex: delay each SFX input to its timestamp, adjust volume,
    # then amix everything together with the original audio.
    filters = []
    mix_labels = ["[0:a]"]

    for idx, entry in enumerate(sfx_entries, start=1):
        delay_ms = max(0, int(entry.get("timestamp", 0) * 1000))
        vol = max(0.0, min(1.0, float(entry.get("volume", 0.3))))
        label = f"[sfx{idx}]"
        filters.append(
            f"[{idx}:a]adelay={delay_ms}|{delay_ms},volume={vol:.2f}{label}"
        )
        mix_labels.append(label)

    n_inputs = len(mix_labels)
    mix_input = "".join(mix_labels)
    filters.append(
        f"{mix_input}amix=inputs={n_inputs}:duration=first:dropout_transition=2[aout]"
    )

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", ";".join(filters),
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        output_path,
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=600, start_new_session=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg SFX mixing failed: {result.stderr[-500:]}")

    return output_path


# --------------------------------------------------------------------------- #
# High-level: auto-place SFX based on scenes and subtitles
# --------------------------------------------------------------------------- #
def add_sound_effects(
    video_path: str,
    output_dir: str,
    sfx_config: dict,
    scenes: Optional[dict] = None,
    subtitles_srt: Optional[str] = None,
) -> dict:
    """
    Add sound effects to a video based on *sfx_config*.

    Args:
        video_path: Path to the input video.
        output_dir: Directory for temporary and output files.
        sfx_config: Configuration dict with:
            - ``enabled``: bool (must be True to proceed)
            - ``intensity``: "subtle", "normal", or "intense"
            - ``types``: list of SFX type names to use (subset of VALID_SFX_TYPES)
        scenes: Optional scene-detection result dict (from ``detect_scenes``).
            Expected to have a ``scene_list`` key with list of
            ``{start_time, end_time}`` dicts.
        subtitles_srt: Optional path to an SRT file — used to align tick/pop
            sounds with subtitle appearances.

    Returns:
        dict with ``output_path`` and ``sfx_placed`` count.
    """
    if not sfx_config.get("enabled", False):
        return {"output_path": video_path, "sfx_placed": 0, "skipped": "disabled"}

    intensity = sfx_config.get("intensity", "normal")
    allowed_types = set(sfx_config.get("types", list(VALID_SFX_TYPES))) & VALID_SFX_TYPES
    if not allowed_types:
        allowed_types = VALID_SFX_TYPES.copy()

    sfx_dir = os.path.join(output_dir, "_sfx")
    os.makedirs(sfx_dir, exist_ok=True)

    # Pre-generate all needed SFX files.
    sfx_files: dict[str, str] = {}
    for stype in allowed_types:
        try:
            path = os.path.join(sfx_dir, f"{stype}.wav")
            generate_sfx(stype, path, duration=SFX_RECIPES[stype]["default_duration"])
            sfx_files[stype] = path
        except Exception as e:
            logger.warning("Failed to generate SFX '%s': %s", stype, e)

    if not sfx_files:
        logger.warning("No SFX files could be generated — skipping")
        return {"output_path": video_path, "sfx_placed": 0, "skipped": "generation_failed"}

    # Volume map by intensity
    volume_map = {"subtle": 0.15, "normal": 0.25, "intense": 0.4}
    base_vol = volume_map.get(intensity, 0.25)

    entries: list[dict] = []

    # --- Probe video duration to place rise/drop ---
    video_duration = _probe_duration(video_path)

    # Rise at start
    if "rise" in sfx_files:
        entries.append({"path": sfx_files["rise"], "timestamp": 0.0, "volume": base_vol})

    # Drop at end
    if "drop" in sfx_files and video_duration and video_duration > 2.0:
        entries.append({
            "path": sfx_files["drop"],
            "timestamp": max(0, video_duration - 1.5),
            "volume": base_vol,
        })

    # --- Scene transitions: whoosh / swoosh ---
    scene_list = (scenes or {}).get("scene_list", [])
    transition_sfx = "whoosh" if "whoosh" in sfx_files else ("swoosh" if "swoosh" in sfx_files else None)
    if transition_sfx and scene_list:
        max_transitions = {"subtle": 3, "normal": 8, "intense": 999}
        limit = max_transitions.get(intensity, 8)
        for i, scene in enumerate(scene_list[:limit]):
            ts = scene.get("start_time")
            if ts is not None and ts > 0.5:
                entries.append({
                    "path": sfx_files[transition_sfx],
                    "timestamp": max(0, ts - 0.2),
                    "volume": base_vol * 0.8,
                })

    # --- Subtitle appearances: tick / pop ---
    caption_sfx = "tick" if "tick" in sfx_files else ("pop" if "pop" in sfx_files else None)
    if caption_sfx and subtitles_srt and os.path.exists(subtitles_srt):
        try:
            from app.processing.effects import _parse_srt
            subs = _parse_srt(subtitles_srt)
            max_ticks = {"subtle": 5, "normal": 15, "intense": 999}
            limit = max_ticks.get(intensity, 15)
            for sub in subs[:limit]:
                entries.append({
                    "path": sfx_files[caption_sfx],
                    "timestamp": sub["start"],
                    "volume": base_vol * 0.5,
                })
        except Exception as e:
            logger.warning("Failed to parse SRT for SFX placement: %s", e)

    if not entries:
        return {"output_path": video_path, "sfx_placed": 0, "skipped": "no_placements"}

    output_path = os.path.join(output_dir, "with_sfx.mp4")
    try:
        mix_sfx_at_timestamps(video_path, entries, output_path)
    except Exception as e:
        logger.error("SFX mixing failed: %s", e)
        return {"output_path": video_path, "sfx_placed": 0, "error": str(e)}

    logger.info("Sound effects applied: %d placements -> %s", len(entries), output_path)
    return {"output_path": output_path, "sfx_placed": len(entries)}


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #
def _probe_duration(video_path: str) -> Optional[float]:
    """Return video duration in seconds, or None on failure."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        pass
    return None
