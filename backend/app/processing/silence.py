"""Silence removal module using auto-editor."""
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
        }

    except subprocess.TimeoutExpired:
        raise RuntimeError("Silence removal timed out (10 min limit)")


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
