"""Silence removal module using auto-editor."""
import copy
import os
import re
import subprocess
import logging

logger = logging.getLogger(__name__)

# Validation patterns for auto-editor parameters
_MARGIN_PATTERN = re.compile(r"^\d+(\.\d+)?s$")
_THRESHOLD_PATTERN = re.compile(r"^\d+(\.\d+)?%$")


def remove_silence(
    video_path: str,
    output_dir: str,
    margin: str = "0.2s",
    threshold: str = "4%",
    speed_silent: float = 99999,
) -> dict:
    """
    Remove silent segments from video using auto-editor.

    Args:
        video_path: Path to input video
        output_dir: Directory for output
        margin: Keep margin around non-silent sections
        threshold: Audio threshold for silence detection
        speed_silent: Speed multiplier for silent parts (99999 = cut)

    Returns dict with:
        - output_path: path to processed video
        - duration_saved: estimated seconds saved
    """
    # Validate parameters to prevent command injection
    if not _MARGIN_PATTERN.match(margin):
        raise ValueError(f"Invalid margin format: {margin}. Expected format: '0.2s'")
    if not _THRESHOLD_PATTERN.match(threshold):
        raise ValueError(f"Invalid threshold format: {threshold}. Expected format: '4%'")
    if not (0 < speed_silent <= 99999):
        raise ValueError(f"Invalid speed_silent: {speed_silent}. Must be between 0 and 99999")

    output_filename = "no_silence.mp4"
    output_path = os.path.join(output_dir, output_filename)

    cmd = [
        "auto-editor",
        video_path,
        "--margin", margin,
        "--edit", f"audio:threshold={threshold}",
        "--silent-speed", str(speed_silent),
        "--output", output_path,
        "--no-open",
    ]

    logger.info(f"Running auto-editor: {' '.join(cmd)}")

    timeline = build_silence_timeline(video_path, margin=margin)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
            start_new_session=True,  # Create process group for clean kill
        )

        if result.returncode != 0:
            logger.error(f"auto-editor failed: {result.stderr}")
            raise RuntimeError(f"auto-editor failed: {result.stderr}")

        logger.info(f"Silence removal complete: {output_path}")

        return {
            "output_path": output_path,
            "stdout": result.stdout,
            **timeline,
        }

    except subprocess.TimeoutExpired:
        raise RuntimeError("Silence removal timed out (10 min limit)")


def _parse_seconds(value: str | float | int) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text.endswith("s"):
        text = text[:-1]
    try:
        return float(text)
    except ValueError:
        return 0.0


def _probe_duration(video_path: str) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def detect_silence_ranges_ffmpeg(video_path: str, noise_db: str = "-35dB", min_duration: float = 0.35) -> list[dict]:
    """Detect silence ranges using ffmpeg silencedetect.

    This powers caption retiming when auto-editor does not expose a JSON
    timeline. It is intentionally fail-soft: an empty list means "no known
    silence ranges", not a hard pipeline failure.
    """
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        video_path,
        "-af",
        f"silencedetect=noise={noise_db}:d={min_duration}",
        "-f",
        "null",
        "-",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except Exception as exc:
        logger.warning("silencedetect failed: %s", exc)
        return []

    text = "\n".join([result.stdout or "", result.stderr or ""])
    ranges: list[dict] = []
    current_start = None
    for line in text.splitlines():
        start_match = re.search(r"silence_start:\s*([0-9.]+)", line)
        if start_match:
            current_start = float(start_match.group(1))
            continue
        end_match = re.search(r"silence_end:\s*([0-9.]+)", line)
        if end_match and current_start is not None:
            end = float(end_match.group(1))
            if end > current_start:
                ranges.append({"start": current_start, "end": end, "duration": end - current_start})
            current_start = None
    return ranges


def build_kept_ranges(duration: float, silence_ranges: list[dict], margin: str = "0.2s") -> list[dict]:
    """Convert source silence ranges into source->output kept ranges."""
    if duration <= 0:
        return []
    pad = _parse_seconds(margin)
    cut_ranges = []
    for item in silence_ranges:
        start = max(0.0, float(item.get("start", 0.0)) + pad)
        end = min(duration, float(item.get("end", 0.0)) - pad)
        if end - start >= 0.05:
            cut_ranges.append((start, end))

    kept = []
    cursor = 0.0
    out_cursor = 0.0
    for start, end in sorted(cut_ranges):
        if start > cursor:
            kept_end = start
            kept.append({
                "source_start": cursor,
                "source_end": kept_end,
                "output_start": out_cursor,
                "output_end": out_cursor + (kept_end - cursor),
            })
            out_cursor += kept_end - cursor
        cursor = max(cursor, end)
    if cursor < duration:
        kept.append({
            "source_start": cursor,
            "source_end": duration,
            "output_start": out_cursor,
            "output_end": out_cursor + (duration - cursor),
        })
    return kept


def build_silence_timeline(video_path: str, margin: str = "0.2s") -> dict:
    duration = _probe_duration(video_path)
    silences = detect_silence_ranges_ffmpeg(video_path)
    kept = build_kept_ranges(duration, silences, margin=margin)
    kept_duration = kept[-1]["output_end"] if kept else duration
    return {
        "source_duration": duration,
        "silence_ranges": silences,
        "kept_ranges": kept,
        "removed_seconds_estimate": max(0.0, duration - kept_duration),
    }


def remap_transcription_to_kept_ranges(transcription: dict, kept_ranges: list[dict]) -> dict:
    """Retiming transcript segments after silence cuts.

    Segments overlapping kept ranges are clipped and mapped to the compacted
    output timeline. This prevents Remotion captions from drifting after
    auto-editor removes silence.
    """
    if not transcription or not kept_ranges:
        return transcription
    remapped = copy.deepcopy(transcription)
    new_segments = []
    for segment in transcription.get("segments") or []:
        s0 = float(segment.get("start", 0.0))
        s1 = float(segment.get("end", s0))
        if s1 <= s0:
            continue
        for keep in kept_ranges:
            k0 = float(keep["source_start"])
            k1 = float(keep["source_end"])
            overlap_start = max(s0, k0)
            overlap_end = min(s1, k1)
            if overlap_end - overlap_start <= 0.05:
                continue
            out_start = float(keep["output_start"]) + (overlap_start - k0)
            out_end = float(keep["output_start"]) + (overlap_end - k0)
            clipped = copy.deepcopy(segment)
            clipped["start"] = round(out_start, 3)
            clipped["end"] = round(out_end, 3)
            new_segments.append(clipped)
    remapped["segments"] = new_segments
    return remapped


def detect_silence_regions(
    video_path: str,
    threshold: str = "4%",
) -> list[dict]:
    """
    Detect silent regions without processing.
    Returns list of {start, end, duration} for silent segments.
    """
    cmd = [
        "auto-editor",
        video_path,
        "--edit", f"audio:threshold={threshold}",
        "--export", "json",
        "--output", "/dev/stdout",
        "--no-open",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            logger.warning(f"Silence detection failed: {result.stderr}")
            return []

        import json
        data = json.loads(result.stdout)
        return data

    except Exception as e:
        logger.warning(f"Silence detection error: {e}")
        return []
