"""
STEP 2 & 3 — Edit Decision List + color grade + concat.

Cut rules (RÈGLE PRO #1 RYTHME):
  * GAP_CUT = 0.65 s : any silence >= 0.65 s between two words is a cut.
  * PAD = 0.25 s : keep 0.25 s of audio margin around each retained run.
  * FILLERS : runs containing ONLY filler words are dropped.
  * 30 ms afade in/out at every cut.

SMART CUT (v4.2) — the montage keeps only the GOOD take:
  * false starts : a short run immediately re-spoken by the next run
    ("aujourd'hui je vais…" → "aujourd'hui je vais vous montrer la méthode")
    is dropped — the LAST take always wins;
  * repeated sentences : when the speaker says the same thing twice in a row,
    the first occurrence is dropped;
  * retake markers : "je reprends / on recommence / coupe ça…" trims the run
    from the marker to its end;
  * stutters : immediate word/bigram repeats ("je je", "il faut il faut")
    are cut out when the repeat is long enough to survive the pads.
  Every smart cut lands ON WORD BOUNDARIES (+ MICRO_PAD margin) so speech is
  never chopped mid-word and the result stays coherent.

Color grade (STEP 3): the warm_cinematic preset is baked into each segment at
encode time, together with a cover-crop to the mandated 1080x1920.

Concat: uses the ffmpeg concat *filter* (not the demuxer) so audio/video
timestamps are cleanly resynchronised.  Segment seeks are INPUT-SIDE (-ss
before -i) — never output-side + afade (that bug makes the fade cover the whole
segment).

Usage:
    python -m app.autoedit_engine.build_edl source.mp4 transcripts/source_vu.json \
        [--outdir .] [--no-encode]
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

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


# --------------------------------------------------------------------------- #
# SMART CUT — retakes / repetitions / stutters
# --------------------------------------------------------------------------- #
def _run_tokens(run: List[dict]) -> List[str]:
    toks = [_norm(w["word"]) for w in run]
    return [t for t in toks if t]


def _similar(a: List[str], b: List[str]) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def trim_trailing_marker(run: List[dict]) -> List[dict]:
    """Cut a run at a retake marker ("… non je reprends") — marker included."""
    toks = [_norm(w["word"]) for w in run]
    joined = " ".join(toks)
    best: Optional[int] = None
    for marker in config.RETAKE_MARKERS:
        m_toks = marker.split()
        n = len(m_toks)
        for i in range(len(toks) - n, -1, -1):
            if toks[i:i + n] == m_toks:
                # Only trim TAIL markers — a marker mid-sentence is ambiguous.
                if len(toks) - (i + n) <= 4:
                    best = i if best is None else min(best, i)
                break
    return run[:best] if best is not None else run


def drop_false_starts(runs: List[List[dict]]) -> List[List[dict]]:
    """Drop run A when run B (the next one) restarts or repeats it.

    The LAST take always wins — exactly what a human editor does with retakes.
    Chains ("a… / a… / a b c") collapse naturally since each run is compared
    to its immediate successor.
    """
    kept: List[List[dict]] = []
    for i, run in enumerate(runs):
        nxt = runs[i + 1] if i + 1 < len(runs) else None
        if nxt is not None:
            a, b = _run_tokens(run), _run_tokens(nxt)
            if config.RETAKE_MIN_WORDS <= len(a) <= config.RETAKE_MAX_WORDS and b:
                is_false_start = (len(b) > len(a)
                                  and _similar(a, b[:len(a)]) >= config.RETAKE_SIMILARITY)
                is_duplicate = (abs(len(a) - len(b)) <= 2
                                and _similar(a, b) >= config.RETAKE_SIMILARITY)
                if is_false_start or is_duplicate:
                    continue                      # the next take replaces this one
        kept.append(run)
    return kept


def drop_repeated_sentences(runs: List[List[dict]]) -> List[List[dict]]:
    """Remove a run when a LATER run (within a window) says almost the same thing.

    Catches repeated/re-recorded sentences that are NOT back-to-back (the
    speaker flubbed a take, said other things, then re-did it). The last
    occurrence is the clean one and is kept. Short runs (greetings, "ok") are
    ignored to avoid nuking legitimately recurring short phrases.
    """
    if not config.REMOVE_REPEATED_SENTENCES:
        return runs
    n = len(runs)
    drop = [False] * n
    toks = [_run_tokens(r) for r in runs]
    for i in range(n):
        if drop[i] or len(toks[i]) < config.REPEAT_MIN_WORDS:
            continue
        for j in range(i + 1, min(n, i + 1 + config.REPEAT_WINDOW)):
            if drop[j] or len(toks[j]) < config.REPEAT_MIN_WORDS:
                continue
            if _similar(toks[i], toks[j]) >= config.REPEAT_SIMILARITY:
                drop[i] = True               # keep the LATER take (j)
                break
    return [r for k, r in enumerate(runs) if not drop[k]]


def split_stutters(run: List[dict]) -> List[Tuple[List[dict], bool, bool]]:
    """Remove immediate word/bigram/trigram repeats inside a run.

    Returns [(subrun, micro_start, micro_end)] — the flags mark boundaries
    created by a stutter cut (tight MICRO_PAD) as opposed to natural silence
    (full PAD). Both sides of a cut must be tight, otherwise the pads would
    re-include the audio that was just removed. Repeats shorter than
    STUTTER_MIN_SPAN are left alone: the pads would swallow the cut anyway.
    """
    toks = [_norm(w["word"]) for w in run]
    subruns: List[Tuple[List[dict], bool, bool]] = []
    cur: List[dict] = []
    cur_micro_start = False
    i = 0
    while i < len(run):
        cut_k = 0
        for k in (3, 2, 1):
            if i + 2 * k > len(run):
                continue
            first, second = toks[i:i + k], toks[i + k:i + 2 * k]
            if first != second or not all(first):
                continue
            span = float(run[i + k]["start"]) - float(run[i]["start"])
            if span >= config.STUTTER_MIN_SPAN:
                cut_k = k
                break
        if cut_k:
            if cur:
                subruns.append((cur, cur_micro_start, True))   # ends at a micro cut
            cur, cur_micro_start = [], True       # next subrun starts at a micro cut
            i += cut_k                            # skip the FIRST occurrence
        else:
            cur.append(run[i])
            i += 1
    if cur:
        subruns.append((cur, cur_micro_start, False))
    return subruns


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

    # 3) SMART CUT: markers -> false starts -> repeated sentences -> stutters.
    pieces: List[Tuple[List[dict], bool, bool]] = []
    if config.REMOVE_RETAKES:
        runs = [trim_trailing_marker(r) for r in runs]
        runs = [r for r in runs if r and not _is_filler_run(r)]
        runs = drop_false_starts(runs)
        runs = drop_repeated_sentences(runs)
        for run in runs:
            pieces.extend(split_stutters(run))
    else:
        pieces = [(r, False, False) for r in runs]

    # 4) Pad each piece (PAD at silence boundaries, MICRO_PAD at smart cuts)
    #    and clamp to media bounds. Boundaries always sit on word edges.
    #    The kept silence between two pieces is hard-capped at MAX_SILENCE_KEPT
    #    so a generous pad can NEVER re-introduce dead air at a cut.
    side_cap = config.MAX_SILENCE_KEPT / 2.0
    ranges: List[dict] = []
    for piece, micro_start, micro_end in pieces:
        if not piece:
            continue
        lead = min(config.MICRO_PAD if micro_start else config.PAD, side_cap)
        tail = min(config.MICRO_PAD if micro_end else config.PAD, side_cap)
        start = max(0.0, float(piece[0]["start"]) - lead)
        end = float(piece[-1]["end"]) + tail
        if duration:
            end = min(duration, end)
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
