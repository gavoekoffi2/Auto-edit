"""
STEP 1 — Transcription (ElevenLabs Scribe).

Sends the clip to ElevenLabs Scribe (speech-to-text, language auto-detected),
keeps only ``type == "word"`` tokens for word-level timestamps, and converts
them to the *video-use* format:

    {"language", "duration", "segments": [
        {"text", "start", "end", "words": [{"word", "start", "end"}, ...]},
        ...
    ]}

Result is written to ``transcripts/<video>_vu.json``.

Usage:
    python -m engine.transcribe input.mp4 [--out transcripts/input_vu.json]
    (requires ELEVENLABS_API_KEY)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Optional

import requests

from . import config
from . import ffmpeg_utils

# Sentence-ending punctuation used to break the word stream into segments.
_SENTENCE_END = re.compile(r"[.!?…]+$")


def extract_audio(video_path: str) -> tuple[str, bool]:
    """
    Extract a mono 16 kHz MP3 from *video_path* to shrink the upload.

    Returns (path, is_temp).  Falls back to the original file if ffmpeg is
    unavailable so transcription still works (ElevenLabs accepts video too).
    """
    try:
        ffmpeg_utils.ensure_ffmpeg()
    except RuntimeError:
        return video_path, False

    fd, audio_path = tempfile.mkstemp(suffix=".mp3", prefix="scribe_")
    os.close(fd)
    ffmpeg_utils.run([
        ffmpeg_utils.FFMPEG, "-y", "-i", video_path,
        "-vn", "-ac", "1", "-ar", "16000", "-b:a", "96k",
        audio_path,
    ])
    return audio_path, True


def scribe_transcribe(audio_path: str, api_key: str, language: Optional[str] = None) -> dict:
    """Call ElevenLabs Scribe and return the raw JSON response."""
    headers = {"xi-api-key": api_key}
    data = {
        "model_id": config.SCRIBE_MODEL_ID,
        "timestamps_granularity": "word",
        "tag_audio_events": "false",
    }
    if language:
        data["language_code"] = language

    with open(audio_path, "rb") as fh:
        files = {"file": (os.path.basename(audio_path), fh, "application/octet-stream")}
        resp = requests.post(
            config.ELEVENLABS_STT_URL,
            headers=headers,
            data=data,
            files=files,
            timeout=600,
        )
    if resp.status_code != 200:
        raise RuntimeError(f"ElevenLabs Scribe failed ({resp.status_code}): {resp.text[:500]}")
    return resp.json()


def to_video_use(scribe_json: dict, duration: float = 0.0) -> dict:
    """
    Convert a raw Scribe response into the video-use segment format.

    Only ``type == "word"`` tokens are kept.  Words are grouped into segments
    on sentence-ending punctuation or on a silence gap >= ``GAP_CUT``.
    """
    raw_words = [
        w for w in scribe_json.get("words", [])
        if w.get("type", "word") == "word" and (w.get("text") or "").strip()
    ]

    segments: list[dict] = []
    cur: list[dict] = []
    prev_end: Optional[float] = None

    def flush() -> None:
        if not cur:
            return
        text = " ".join(w["word"] for w in cur).strip()
        segments.append({
            "text": text,
            "start": cur[0]["start"],
            "end": cur[-1]["end"],
            "words": [dict(w) for w in cur],
        })

    for tok in raw_words:
        word = {
            "word": tok["text"].strip(),
            "start": round(float(tok["start"]), 3),
            "end": round(float(tok["end"]), 3),
        }
        gap = (word["start"] - prev_end) if prev_end is not None else 0.0
        if cur and gap >= config.GAP_CUT:
            flush()
            cur = []
        cur.append(word)
        prev_end = word["end"]
        if _SENTENCE_END.search(word["word"]):
            flush()
            cur = []
            prev_end = None
    flush()

    if not duration and segments:
        duration = segments[-1]["end"]

    return {
        "language": scribe_json.get("language_code") or scribe_json.get("language", "auto"),
        "duration": round(duration, 3),
        "segments": segments,
    }


def transcribe(video_path: str, out_path: Optional[str] = None,
               api_key: Optional[str] = None, language: Optional[str] = None) -> str:
    """Full step-1 entry point. Returns the path of the written _vu.json."""
    api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is required for transcription")

    if out_path is None:
        stem = Path(video_path).stem
        out_path = os.path.join("transcripts", f"{stem}_vu.json")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    duration = ffmpeg_utils.probe_duration(video_path)
    audio_path, is_temp = extract_audio(video_path)
    try:
        raw = scribe_transcribe(audio_path, api_key, language=language)
    finally:
        if is_temp and os.path.exists(audio_path):
            os.remove(audio_path)

    vu = to_video_use(raw, duration=duration)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(vu, fh, ensure_ascii=False, indent=2)

    print(f"[transcribe] {len(vu['segments'])} segments, "
          f"{vu['duration']:.1f}s -> {out_path}")
    return out_path


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="ElevenLabs Scribe transcription -> video-use JSON")
    ap.add_argument("video", help="input video/audio file")
    ap.add_argument("--out", help="output _vu.json path")
    ap.add_argument("--language", help="force language code (default: auto-detect)")
    args = ap.parse_args(argv)
    transcribe(args.video, out_path=args.out, language=args.language)
    return 0


if __name__ == "__main__":
    sys.exit(main())
