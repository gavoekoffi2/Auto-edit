"""Smart transcript-based cuts for repeated or weak takes.

This module complements auto-editor silence removal. It uses the Whisper segment
text to identify near-duplicate phrases and removes later repeated takes before
standard silence cleanup runs.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable


@dataclass
class SmartCutRange:
    start: float
    end: float
    reason: str
    score: float = 0.0


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-zàâçéèêëîïôûùüÿñæœ0-9\s]", " ", text)
    tokens = [t for t in text.split() if t not in {"euh", "heu", "hum", "ok", "donc", "alors"}]
    return " ".join(tokens)


def detect_repeated_segments(
    transcription: dict,
    similarity_threshold: float = 0.88,
    min_text_chars: int = 18,
    lookback: int = 4,
) -> list[SmartCutRange]:
    segments = transcription.get("segments") or []
    normalized: list[tuple[dict, str]] = []
    drops: list[SmartCutRange] = []
    for seg in segments:
        norm = normalize_text(seg.get("text", ""))
        if len(norm) < min_text_chars:
            normalized.append((seg, norm))
            continue
        for prev, prev_norm in normalized[-lookback:]:
            if len(prev_norm) < min_text_chars:
                continue
            score = SequenceMatcher(None, prev_norm, norm).ratio()
            if score >= similarity_threshold:
                drops.append(
                    SmartCutRange(
                        start=float(seg.get("start", 0.0)),
                        end=float(seg.get("end", 0.0)),
                        reason="repetition",
                        score=round(score, 3),
                    )
                )
                break
        normalized.append((seg, norm))
    return [d for d in drops if d.end - d.start >= 0.25]


def subtract_ranges(total_duration: float, drops: Iterable[SmartCutRange], pad: float = 0.08) -> list[tuple[float, float]]:
    merged = []
    for d in sorted(drops, key=lambda r: r.start):
        start = max(0.0, d.start - pad)
        end = min(total_duration, d.end + pad)
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    keeps = []
    cursor = 0.0
    for start, end in merged:
        if start > cursor:
            keeps.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < total_duration:
        keeps.append((cursor, total_duration))
    return [(s, e) for s, e in keeps if e - s >= 0.2]


def get_duration(video_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def apply_smart_cuts(video_path: str, output_dir: str, transcription: dict, enabled: bool = True) -> dict:
    if not enabled or not transcription:
        return {"skipped": "disabled_or_no_transcription", "output_path": video_path, "removed_seconds": 0.0, "cuts": []}
    duration = get_duration(video_path)
    drops = detect_repeated_segments(transcription)
    if not drops:
        return {"skipped": "no_repetitions_detected", "output_path": video_path, "removed_seconds": 0.0, "cuts": []}
    keeps = subtract_ranges(duration, drops)
    out = Path(output_dir) / "smart_cuts.mp4"
    list_file = Path(output_dir) / "smart_cuts_concat.txt"
    segments_dir = Path(output_dir) / "smart_cuts_segments"
    segments_dir.mkdir(parents=True, exist_ok=True)

    segment_paths = []
    for i, (start, end) in enumerate(keeps, 1):
        seg_path = segments_dir / f"keep_{i:04d}.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", video_path,
                "-c", "copy", str(seg_path),
            ],
            check=True,
        )
        segment_paths.append(seg_path)
    list_file.write_text("".join(f"file '{p}'\n" for p in segment_paths), encoding="utf-8")
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out)],
        check=True,
    )
    removed = sum(d.end - d.start for d in drops)
    return {
        "output_path": str(out),
        "removed_seconds": round(removed, 3),
        "cuts": [d.__dict__ for d in drops],
        "kept_segments": len(keeps),
    }
