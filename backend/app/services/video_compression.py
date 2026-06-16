"""Fast ingest video compression using FFmpeg.

Re-encodes uploaded videos with lightweight settings (CRF 26, veryfast preset)
to reduce working-file size by 40–70% before the main processing pipeline runs.
All downstream steps (Whisper, scene detection, FFmpeg compositing) then work
on a smaller file, cutting total job time significantly.

The final output of the main pipeline still uses CRF 20 + medium preset
(high quality). This compression only affects the intermediate working copy.
"""
import os
import logging
import subprocess
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


def compress_for_ingest(input_path: str, output_path: str) -> bool:
    """Re-encode video with fast/lightweight settings to reduce working-file size.

    Returns True if the compressed file is smaller than the original (and
    therefore worth using). Returns False if compression was not beneficial
    (e.g. input was already well-compressed) or if FFmpeg failed.
    """
    cmd = [
        "ffmpeg",
        "-i", input_path,
        "-c:v", "libx264",
        "-crf", str(settings.INGEST_COMPRESS_CRF),
        "-preset", settings.INGEST_COMPRESS_PRESET,
        "-c:a", "aac",
        "-b:a", settings.INGEST_COMPRESS_AUDIO_BITRATE,
        "-movflags", "+faststart",
        "-threads", "0",   # let FFmpeg pick optimal thread count
        "-y",
        output_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=settings.FFMPEG_COMMAND_TIMEOUT_SECONDS or 21600,
        )
        if result.returncode != 0:
            logger.error(
                "Ingest compression FFmpeg error (code %d): %s",
                result.returncode,
                result.stderr[-2000:],
            )
            return False

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            logger.error("Ingest compression produced empty output: %s", output_path)
            return False

        orig_size = os.path.getsize(input_path)
        compressed_size = os.path.getsize(output_path)

        if compressed_size >= orig_size:
            logger.info(
                "Ingest compression not beneficial: %d MB → %d MB (keeping original)",
                orig_size // 1_000_000,
                compressed_size // 1_000_000,
            )
            return False

        ratio = (1 - compressed_size / orig_size) * 100
        logger.info(
            "Ingest compression: %d MB → %d MB (%.0f%% saved)",
            orig_size // 1_000_000,
            compressed_size // 1_000_000,
            ratio,
        )
        return True

    except subprocess.TimeoutExpired:
        logger.error("Ingest compression timed out for %s", input_path)
        return False
    except FileNotFoundError:
        logger.error("ffmpeg not found — ingest compression skipped")
        return False
    except Exception as exc:
        logger.error("Ingest compression unexpected error: %s", exc, exc_info=True)
        return False


def safe_replace_with_compressed(original_path: str, compressed_path: str) -> tuple[str, int]:
    """Atomically replace original video with compressed version.

    Returns (final_path, new_size_bytes). If the compressed file has a
    different extension (we always produce .mp4), the returned path reflects
    the new name so the caller can update the database accordingly.
    """
    orig = Path(original_path)
    compressed = Path(compressed_path)

    # Always output .mp4; rename if input had a different container.
    if orig.suffix.lower() != ".mp4":
        final_path = orig.with_suffix(".mp4")
    else:
        final_path = orig

    # os.replace is atomic on POSIX (rename(2)) — no partial-file window.
    os.replace(compressed_path, str(final_path))

    # Remove the old file if we renamed (e.g. input.mkv → input.mp4).
    if final_path != orig and orig.exists():
        try:
            orig.unlink()
        except OSError as exc:
            logger.warning("Could not remove old source file %s: %s", orig, exc)

    new_size = os.path.getsize(str(final_path))
    return str(final_path), new_size
