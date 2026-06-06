"""
Auto Edit — Python orchestrator (mirror of run_pipeline.sh).

Runs the full viral-montage pipeline end to end:

  1  transcribe        -> transcripts/<stem>_vu.json
  2  build_edl         -> edl.json, clips_graded/seg_*.mp4, base_only.mp4
  3  overlays          -> animations/*.mov  (+ _overlays.json)
  4  genimg            -> broll/*.png       (n ~= duration/5)
  5  broll_anim        -> broll_clips/br_*.mov (+ _broll_clips.json)
  6  plan_overlays     -> edl.json (overlays) + sfx_cues.json
  7  keyword_popup     -> broll_clips/popup_*.mov + edl patch
  8  video_dynamics    -> base_dyn.mp4
  9  composite         -> composite_nosfx.mp4
  10 mix_sfx           -> composite_withsfx.mp4
  11 subs_ass          -> master.ass
  12 finalize          -> final_montage_web.mp4

Usage:
    python -m engine.pipeline input.mp4 --workdir out [--template tiktok_yellow]
    python -m engine.pipeline input.mp4 --workdir out --vu cached_vu.json --no-broll
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from . import (
    broll_anim,
    build_edl,
    composite,
    config,
    content,
    finalize,
    genimg,
    keyword_popup,
    mix_sfx,
    overlays,
    plan_overlays,
    subs_ass,
    transcribe,
    video_dynamics,
)


def _log(step: str, msg: str = "") -> None:
    print(f"\n=== {step} === {msg}")


def run(source: str, workdir: str, *, vu: Optional[str] = None,
        template: str = config.DEFAULT_TEMPLATE, do_broll: bool = True) -> str:
    os.makedirs(workdir, exist_ok=True)
    stem = Path(source).stem
    p = lambda *a: os.path.join(workdir, *a)  # noqa: E731 - tiny path helper

    # 1) Transcription -------------------------------------------------------
    _log("1 transcribe")
    vu_path = vu or transcribe.transcribe(
        source, out_path=p("transcripts", f"{stem}_vu.json"))
    vu_data = json.load(open(vu_path, encoding="utf-8"))

    # 2) EDL + grade + base_only --------------------------------------------
    _log("2 build_edl")
    edl_path = p("edl.json")
    build_res = build_edl.build(source, vu_path, outdir=workdir, encode=True)
    base_only = build_res["base_only"]

    # 3) Graphic overlays ----------------------------------------------------
    _log("3 overlays")
    specs = content.derive_overlay_specs(vu_data)
    rendered_overlays = overlays.render_all(specs, p("animations"))
    overlays_json = p("animations", "_overlays.json")
    json.dump(rendered_overlays, open(overlays_json, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    # 4 & 5) B-roll images + animation --------------------------------------
    broll_json: Optional[str] = None
    have_key = bool(os.environ.get("OPENROUTER_API_KEY"))
    if do_broll and have_key:
        _log("4 genimg")
        ideas = content.derive_broll_ideas(vu_data)
        images = genimg.generate_brolls(ideas, p("broll"))
        if images:
            _log("5 broll_anim")
            clips = broll_anim.render_all(images, p("broll_clips"))
            broll_json = p("broll_clips", "_broll_clips.json")
            json.dump(clips, open(broll_json, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
    else:
        _log("4-5 broll", "skipped (no OPENROUTER_API_KEY or --no-broll)")

    # 6) Plan timeline + SFX cues -------------------------------------------
    _log("6 plan_overlays")
    plan_overlays.plan(edl_path, overlays_json, broll_json, outdir=workdir)

    # 7) Keyword popups ------------------------------------------------------
    _log("7 keyword_popup")
    keyword_popup.build_popups(edl_path, p("broll_clips"))

    # 8) Dynamic zoom --------------------------------------------------------
    _log("8 video_dynamics")
    base_dyn = video_dynamics.apply_dynamics(base_only, edl_path, p("base_dyn.mp4"))

    # 9) Composite -----------------------------------------------------------
    _log("9 composite")
    nosfx = composite.composite(base_dyn, edl_path, p("composite_nosfx.mp4"), workdir=workdir)

    # 10) SFX + loudnorm -----------------------------------------------------
    _log("10 mix_sfx")
    withsfx = mix_sfx.mix(nosfx, p("sfx_cues.json"), p("composite_withsfx.mp4"),
                          sfxdir=p("sfx"))

    # 11) Subtitles ----------------------------------------------------------
    _log("11 subs_ass")
    ass_path = subs_ass.generate(edl_path, p("master.ass"), template=template)

    # 12) Final burn ---------------------------------------------------------
    _log("12 finalize")
    final = finalize.burn_subs(withsfx, ass_path, p("final_montage_web.mp4"))

    print(f"\n✅ Auto Edit complete -> {final}")
    return final


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Run the full Auto Edit pipeline")
    ap.add_argument("source", help="input video")
    ap.add_argument("--workdir", default="out")
    ap.add_argument("--vu", help="use an existing transcript _vu.json (skip step 1)")
    ap.add_argument("--template", default=config.DEFAULT_TEMPLATE,
                    choices=list(config.ASS_TEMPLATES.keys()))
    ap.add_argument("--no-broll", action="store_true", help="skip AI B-roll generation")
    args = ap.parse_args(argv)
    run(args.source, args.workdir, vu=args.vu, template=args.template,
        do_broll=not args.no_broll)
    return 0


if __name__ == "__main__":
    sys.exit(main())
