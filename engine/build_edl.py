"""
STEP 2 & 3 — Edit Decision List + color grade + concat.

Cut rules (RÈGLE PRO #1 RYTHME):
  * GAP_CUT = 0.65 s : any silence >= 0.65 s between two words is a cut.
  * PAD = 0.25 s : keep 0.25 s of audio margin around each retained run.
  * FILLERS : runs containing ONLY filler words are dropped.
  * 30 ms afade in/out at every cut.

Color grade (STEP 3): the warm_cinematic preset is baked into each segment at
encode time, together with a cover-crop to the mandated 1080x1920.

Concat: uses the ffmpeg concat *filter* (not the demuxer) so audio/video
timestamps are cleanly resynchronised.  Segment seeks are INPUT-SIDE (-ss
before -i) — never output-side + afade (that bug makes the fade cover the whole
segment).

Usage:
    python -m engine.build_edl source.mp4 transcripts/source_vu.json \
        [--outdir .] [--no-encode]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional

from . import config
from . import ffmpeg_utils

_PUNCT = re.compile(r"[^\wàâäéèêëïîôöùûüÿçœæ' ]+", re.UNICODE)


def load_vu(vu_path: str) -> dict:
    with open(vu_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _flatten_words(vu: dict) -> List[dict]:
    """All words across all segments, in order."""
    words: List[dict] = []
    for seg in vu.get("segments", []):
        for w in seg.get("words", []):
            if (w.get("word") or "").strip():
                words.append(w)
    words.sort(key=lambda w: float(w["start"]))
    return words


def _norm(token: str) -> str:
    return _PUNCT.sub("", token.lower()).strip()


def _is_filler_run(words: List[dict]) -> bool:
    """True if the run consists only of filler words (or is empty)."""
    toks = [_norm(w["word"]) for w in words]
    toks = [t for t in toks if t]
    if not toks:
        return True
    joined = " ".join(toks)
    if joined in config.FILLERS:          # multiword fillers, e.g. "en fait"
        return True
    return all(t in config.FILLERS for t in toks)


def build_ranges(vu: dict) -> List[dict]:
    """Apply the cut rules and return the list of kept source ranges."""
    words = _flatten_words(vu)
    if not words:
        return []

    duration = float(vu.get("duration") or words[-1]["end"])

    # 1) Split the word stream into runs at silences >= GAP_CUT.
    runs: List[List[dict]] = []
    cur: List[dict] = [words[0]]
    for prev, nxt in zip(words, words[1:]):
        gap = float(nxt["start"]) - float(prev["end"])
        if gap >= config.GAP_CUT:
            runs.append(cur)
            cur = [nxt]
        else:
            cur.append(nxt)
    runs.append(cur)

    # 2) Drop filler-only runs.
    runs = [r for r in runs if not _is_filler_run(r)]

    # 3) Pad each run and clamp to media bounds.
    ranges: List[dict] = []
    for run in runs:
        start = max(0.0, float(run[0]["start"]) - config.PAD)
        end = min(duration, float(run[-1]["end"]) + config.PAD) if duration else float(run[-1]["end"]) + config.PAD
        # Prevent overlap with the previous padded range.
        if ranges and start < ranges[-1]["end"]:
            start = ranges[-1]["end"]
        if end - start > 0.05:
            ranges.append({"start": round(start, 3), "end": round(end, 3)})
    return ranges


def write_edl(ranges: List[dict], vu_path: str, out_path: str) -> str:
    edl = {
        "ranges": ranges,
        "overlays": [],
        "transcripts_vu": vu_path,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(edl, fh, ensure_ascii=False, indent=2)
    return out_path


def encode_segments(source: str, ranges: List[dict], clips_dir: str) -> List[str]:
    """
    Encode each kept range as a graded 1080x1920 segment.

    INPUT-SIDE seek (-ss before -i) + afade in/out, libx264 crf 18, aac 48 kHz.
    """
    ffmpeg_utils.ensure_ffmpeg()
    os.makedirs(clips_dir, exist_ok=True)
    grade = f"{config.VERTICAL_COVER},{config.GRADE_WARM_CINEMATIC}"
    seg_paths: List[str] = []

    for i, rng in enumerate(ranges):
        dur = rng["end"] - rng["start"]
        out = os.path.join(clips_dir, f"seg_{i:04d}.mp4")
        fade_out_start = max(0.0, dur - config.AUDIO_FADE)
        af = (
            f"afade=t=in:st=0:d={config.AUDIO_FADE},"
            f"afade=t=out:st={fade_out_start:.3f}:d={config.AUDIO_FADE}"
        )
        ffmpeg_utils.run([
            ffmpeg_utils.FFMPEG, "-y",
            "-ss", f"{rng['start']:.3f}", "-t", f"{dur:.3f}",  # INPUT-SIDE seek
            "-i", source,
            "-vf", grade,
            "-af", af,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-r", str(config.FPS),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            out,
        ])
        seg_paths.append(out)
    return seg_paths


def concat_segments(seg_paths: List[str], out_path: str) -> str:
    """Concatenate graded segments with the ffmpeg concat FILTER."""
    if not seg_paths:
        raise RuntimeError("no segments to concatenate")
    ffmpeg_utils.ensure_ffmpeg()

    cmd: List[str] = [ffmpeg_utils.FFMPEG, "-y"]
    for path in seg_paths:
        cmd += ["-i", path]
    n = len(seg_paths)
    streams = "".join(f"[{i}:v][{i}:a]" for i in range(n))
    filt = f"{streams}concat=n={n}:v=1:a=1[v][a]"
    cmd += [
        "-filter_complex", filt,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        out_path,
    ]
    ffmpeg_utils.run(cmd)
    return out_path


def build(source: str, vu_path: str, outdir: str = ".", encode: bool = True) -> dict:
    """Full step-2/3 entry point."""
    os.makedirs(outdir, exist_ok=True)
    vu = load_vu(vu_path)
    ranges = build_ranges(vu)
    if not ranges:
        raise RuntimeError("EDL produced no ranges — transcript may be empty")

    edl_path = os.path.join(outdir, "edl.json")
    write_edl(ranges, vu_path, edl_path)

    kept = sum(r["end"] - r["start"] for r in ranges)
    print(f"[build_edl] {len(ranges)} ranges, {kept:.1f}s kept -> {edl_path}")

    result = {"edl": edl_path, "ranges": ranges, "output_duration": round(kept, 3)}

    if encode:
        clips_dir = os.path.join(outdir, "clips_graded")
        seg_paths = encode_segments(source, ranges, clips_dir)
        base = os.path.join(outdir, "base_only.mp4")
        concat_segments(seg_paths, base)
        print(f"[build_edl] encoded {len(seg_paths)} segments -> {base}")
        result["segments"] = seg_paths
        result["base_only"] = base

    return result


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Build EDL + graded segments + base_only.mp4")
    ap.add_argument("source", help="source video")
    ap.add_argument("vu_json", help="transcripts/<video>_vu.json")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--no-encode", action="store_true",
                    help="only write edl.json (skip ffmpeg encode/concat)")
    args = ap.parse_args(argv)
    build(args.source, args.vu_json, outdir=args.outdir, encode=not args.no_encode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
