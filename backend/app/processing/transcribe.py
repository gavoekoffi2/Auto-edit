"""Whisper-based audio transcription module."""
import os
import json
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

# Cache Whisper model per worker process to avoid reloading on every call
_model_cache: dict = {}
_model_lock = threading.Lock()


def _get_model(model_name: str):
    """Get or load a cached Whisper model (thread-safe)."""
    import whisper

    if model_name not in _model_cache:
        with _model_lock:
            # Double-check after acquiring lock
            if model_name not in _model_cache:
                logger.info(f"Loading Whisper model: {model_name} (will be cached for reuse)")
                _model_cache[model_name] = whisper.load_model(model_name)
    return _model_cache[model_name]


def transcribe_video(video_path: str, output_dir: str, model_name: str = "base") -> dict:
    """
    Transcribe audio from video using OpenAI Whisper.

    Returns dict with:
        - text: full transcription text
        - segments: list of {start, end, text} segments
        - srt_path: path to generated SRT subtitle file
        - language: detected language
    """
    model = _get_model(model_name)

    logger.info(f"Transcribing: {video_path}")
    result = model.transcribe(video_path, verbose=False)

    # Generate SRT file
    srt_path = os.path.join(output_dir, "subtitles.srt")
    _write_srt(result["segments"], srt_path)

    # Save full transcript as JSON
    transcript_path = os.path.join(output_dir, "transcript.json")
    with open(transcript_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "text": result["text"],
                "language": result.get("language", "unknown"),
                "segments": [
                    {
                        "start": seg["start"],
                        "end": seg["end"],
                        "text": seg["text"].strip(),
                    }
                    for seg in result["segments"]
                ],
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    return {
        "text": result["text"],
        "language": result.get("language", "unknown"),
        "segments": [
            {"start": s["start"], "end": s["end"], "text": s["text"].strip()}
            for s in result["segments"]
        ],
        "srt_path": srt_path,
        "transcript_path": transcript_path,
    }


def _write_srt(segments: list, output_path: str):
    """Write segments to SRT subtitle file."""
    with open(output_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            start = _format_timestamp(seg["start"])
            end = _format_timestamp(seg["end"])
            text = seg["text"].strip()
            f.write(f"{i}\n{start} --> {end}\n{text}\n\n")


def _format_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
