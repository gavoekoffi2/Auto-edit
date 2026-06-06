"""
STEP 8 — Timeline planning + SFX cues.

Converts SOURCE timings to OUTPUT timings (via the EDL ranges, s2o) and lays
out the montage:

  * Graphics: placed where the speaker STARTS the topic, minus 0.2 s lead.
  * B-roll : intercalated between graphics (ballotage), >= 0.4 s gap between
             clips.  B-roll sits ABOVE graphics, so it is listed after them.
  * SFX    : varied and alternated —
        graphics -> impact/sub_drop/boom/bass_hit/ding/chime/sparkle/pop
        B-roll   -> rotating BROLL_SFX_POOL, NEVER the same SFX twice in a row
                    (camera_flash, the signature photo sound, recurs)
  * After sorting, no identical SFX may immediately follow another.
  * Gap-fill (RÈGLE PRO #3): any gap > 4 s with no visual event gets a filler
    SFX injected at its middle.

Outputs: patched edl.json (overlays) + sfx_cues.json.

Usage:
    python -m engine.plan_overlays --edl edl.json \
        --overlays animations/_overlays.json \
        --broll broll_clips/_broll_clips.json --outdir .
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from . import config
from .timeline import output_duration, s2o_clamped


def _load(path: Optional[str]) -> list:
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return []


def _place_graphics(graphics: List[dict], ranges: List[dict]) -> List[dict]:
    placed = []
    for g in graphics:
        start = max(0.0, s2o_clamped(float(g["source_start"]), ranges) - config.GRAPHIC_LEAD)
        placed.append({
            "id": g["id"],
            "mov": g["mov"],
            "start": round(start, 3),
            "end": round(start + float(g["duration"]), 3),
            "kind": "graphic",
        })
    placed.sort(key=lambda o: o["start"])
    return placed


def _place_broll(brolls: List[dict], ranges: List[dict]) -> List[dict]:
    """Map each B-roll slot to output time; enforce >= BROLL_MIN_GAP spacing."""
    raw = []
    for b in brolls:
        dur = float(b.get("duration", config.BROLL_DURATION))  # real clip length
        start = s2o_clamped(float(b["source_start"]), ranges)
        raw.append({"id": b["id"], "mov": b["mov"], "start": start, "dur": dur,
                    "entrance": b.get("entrance")})
    raw.sort(key=lambda o: o["start"])

    placed = []
    prev_end = -1e9
    for b in raw:
        start = b["start"]
        if start < prev_end + config.BROLL_MIN_GAP:
            start = prev_end + config.BROLL_MIN_GAP
        end = start + b["dur"]
        placed.append({
            "id": b["id"], "mov": b["mov"],
            "start": round(start, 3), "end": round(end, 3),
            "kind": "broll", "entrance": b.get("entrance"),
        })
        prev_end = end
    return placed


def _dedupe_consecutive(cues: List[dict]) -> List[dict]:
    """Ensure no two consecutive cues share the same SFX (swap from a pool)."""
    alt_pool = config.GRAPHIC_SFX + config.GAPFILL_SFX_POOL
    for i in range(1, len(cues)):
        if cues[i]["sfx"] == cues[i - 1]["sfx"]:
            for cand in alt_pool:
                nxt = cues[i + 1]["sfx"] if i + 1 < len(cues) else None
                if cand != cues[i - 1]["sfx"] and cand != nxt:
                    cues[i]["sfx"] = cand
                    break
    return cues


def _gapfill(cues: List[dict], total: float) -> List[dict]:
    """Inject a filler SFX in any visual gap > GAPFILL_THRESHOLD."""
    if not cues:
        return cues
    times = sorted(c["t"] for c in cues)
    fillers: List[dict] = []
    pool_i = 0
    bounds = [0.0] + times + [total]
    for a, b in zip(bounds, bounds[1:]):
        if b - a > config.GAPFILL_THRESHOLD:
            mid = round((a + b) / 2.0, 3)
            sfx = config.GAPFILL_SFX_POOL[pool_i % len(config.GAPFILL_SFX_POOL)]
            pool_i += 1
            fillers.append({"sfx": sfx, "t": mid, "src": "gapfill"})
    return fillers


def plan(edl_path: str, overlays_json: Optional[str], broll_json: Optional[str],
         outdir: str = ".") -> dict:
    with open(edl_path, "r", encoding="utf-8") as fh:
        edl = json.load(fh)
    ranges = edl["ranges"]
    total = output_duration(ranges)

    graphics = _place_graphics(_load(overlays_json), ranges)
    brolls = _place_broll(_load(broll_json), ranges)

    # Graphics first, then B-roll (B-roll composites ABOVE graphics).
    edl["overlays"] = graphics + brolls
    with open(edl_path, "w", encoding="utf-8") as fh:
        json.dump(edl, fh, ensure_ascii=False, indent=2)

    # --- SFX cues --------------------------------------------------------- #
    cues: List[dict] = []
    for i, g in enumerate(graphics):
        cues.append({"sfx": config.GRAPHIC_SFX[i % len(config.GRAPHIC_SFX)],
                     "t": g["start"], "src": "graphic"})
    for i, b in enumerate(brolls):
        cues.append({"sfx": config.BROLL_SFX_POOL[i % len(config.BROLL_SFX_POOL)],
                     "t": b["start"], "src": "broll"})

    cues.sort(key=lambda c: c["t"])
    cues = _dedupe_consecutive(cues)
    cues += _gapfill(cues, total)
    cues.sort(key=lambda c: c["t"])
    cues = _dedupe_consecutive(cues)

    sfx_path = os.path.join(outdir, "sfx_cues.json")
    with open(sfx_path, "w", encoding="utf-8") as fh:
        json.dump(cues, fh, ensure_ascii=False, indent=2)

    print(f"[plan_overlays] {len(graphics)} graphics + {len(brolls)} broll, "
          f"{len(cues)} SFX cues -> {edl_path}, {sfx_path}")
    return {"overlays": edl["overlays"], "cues": cues}


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Plan overlay timeline + SFX cues")
    ap.add_argument("--edl", required=True)
    ap.add_argument("--overlays", help="animations/_overlays.json")
    ap.add_argument("--broll", help="broll_clips/_broll_clips.json")
    ap.add_argument("--outdir", default=".")
    args = ap.parse_args(argv)
    plan(args.edl, args.overlays, args.broll, outdir=args.outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
