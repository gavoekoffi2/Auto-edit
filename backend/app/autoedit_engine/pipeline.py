"""
Auto Edit — Python orchestrator (mirror of run_pipeline.sh).

Runs the full viral-montage pipeline end to end:

  1   transcribe        -> transcripts/<stem>_vu.json
  2   build_edl         -> edl.json, clips_graded/seg_*.mp4, base_only.mp4
  3   overlays          -> animations/*.mov  (+ _overlays.json)
  4   motion_design     -> motion/*.png + motion_clips/md_*.mov
                           (illustrated scenes for the key explanatory beats)
  5   genimg            -> broll/*.png       (n ~= duration/5, avoids motion beats)
  6   broll_anim        -> broll_clips/br_*.mov (+ _broll_clips.json)
  7   plan_overlays     -> edl.json (overlays) + sfx_cues.json
  8   keyword_popup     -> broll_clips/popup_*.mov + edl patch
  9   video_dynamics    -> base_dyn.mp4
  10  composite         -> composite_nosfx.mp4
  11  mix_sfx           -> composite_withsfx.mp4
  12  subs_ass          -> master.ass
  13  finalize          -> final_montage_web.mp4

Usage:
    python -m app.autoedit_engine.pipeline input.mp4 --workdir out [--template tiktok_yellow]
    python -m app.autoedit_engine.pipeline input.mp4 --workdir out --vu cached_vu.json --no-broll
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
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
    key_moments,
    keyword_popup,
    mix_sfx,
    motion_design,
    overlays,
    plan_overlays,
    subs_ass,
    timeline,
    transcribe,
    video_dynamics,
)


def _log(step: str, msg: str = "") -> None:
    print(f"\n=== {step} === {msg}")


def plan_visual_mode(visual_mode: str, *, do_broll: bool, have_key: bool,
                     disable_paid_images: bool) -> tuple[bool, Optional[str]]:
    """Decide whether the PAID image API may run for a render.

    Pure + deterministic so it is trivially testable. Returns
    ``(attempt_ai, fallback_reason)``:

      * ``attempt_ai``      whether to call the paid image generator at all.
      * ``fallback_reason`` why AI images are skipped (None when attempting, or
                            None for an explicit credit_saver choice).

    Guarantees: ``credit_saver`` NEVER attempts (no paid call, ever), and a
    disabled / keyless / toggled-off environment never attempts either.
    """
    if visual_mode == "credit_saver":
        return False, None  # explicit choice — not a fallback
    if visual_mode not in ("ai_broll", "auto_fallback"):
        return False, None
    if disable_paid_images:
        return False, "disabled"
    if not have_key:
        return False, "missing_api_key"
    if not do_broll:
        return False, "broll_disabled"
    return True, None


# Heavy intermediates left in the workdir after a render. A single job can
# write SEVERAL GB of ProRes .mov + mp4 passes — on a small VPS the disk fills
# after a handful of jobs and ffmpeg dies mid-encode ("[Errno 32] Broken
# pipe"). Light artifacts (final video, transcript, edl, .ass, B-roll PNGs)
# are kept.
_INTERMEDIATE_DIRS = ("clips_graded", "animations", "motion_clips", "broll_clips", "sfx")
_INTERMEDIATE_FILES = ("base_only.mp4", "base_dyn.mp4",
                       "composite_nosfx.mp4", "composite_withsfx.mp4")


def cleanup_intermediates(workdir: str) -> int:
    """Delete heavy render intermediates from *workdir*; returns bytes freed."""
    freed = 0
    for name in _INTERMEDIATE_DIRS:
        path = os.path.join(workdir, name)
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                for f in files:
                    try:
                        freed += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass
            shutil.rmtree(path, ignore_errors=True)
    patterns = list(_INTERMEDIATE_FILES)
    try:
        patterns += [f for f in os.listdir(workdir) if f.startswith("_composite_pass")]
    except OSError:
        pass
    for name in patterns:
        path = os.path.join(workdir, name)
        try:
            if os.path.isfile(path):
                freed += os.path.getsize(path)
                os.remove(path)
        except OSError:
            pass
    if freed:
        print(f"[pipeline] cleanup: {freed / 1e6:.0f} MB d'intermédiaires libérés")
    return freed


def run(source: str, workdir: str, *, vu: Optional[str] = None,
        template: str = config.DEFAULT_TEMPLATE, do_broll: bool = True,
        do_motion: bool = True, broll_demographic: str = "african",
        visual_mode: str = "auto_fallback", motion_preset: Optional[str] = None,
        style_seed_text: Optional[str] = None, disable_paid_images: bool = False,
        progress_callback=None, report: Optional[dict] = None,
        cleanup: bool = True) -> str:
    os.makedirs(workdir, exist_ok=True)
    stem = Path(source).stem
    p = lambda *a: os.path.join(workdir, *a)  # noqa: E731 - tiny path helper
    # Observability: every visual decision lands in this report so the job
    # result can PROVE what the montage contains (scenes, B-roll, popups, SFX).
    rep = report if report is not None else {}
    rep.update({
        "template": template,
        "motion_enabled": do_motion,
        "visual_mode_requested": visual_mode,
        # Effective values, refined as the render progresses.
        "visual_mode_used": "credit_saver",
        "ai_images_skipped": True,
        "fallback_reason": None,
        "motion_preset": motion_preset,
        "source_duration_s": 0.0,
        "kept_duration_s": 0.0,
        "removed_duration_s": 0.0,
        "segments_kept": 0,
        "motion_scenes_derived": 0,
        "motion_scenes_rendered": 0,
        "motion_ai_illustrations": 0,
        "broll_images": 0,
        "keyword_popups": 0,
        "key_moments": 0,
        "camera_flashes": 0,
        "shutter_sfx": 0,
        "light_overlays": 0,
        "motion_transitions_lit": 0,
        "sfx_cues": 0,
    })
    if visual_mode not in {"ai_broll", "credit_saver", "auto_fallback"}:
        visual_mode = "auto_fallback"

    def _p(pct: int, label: str, msg: str = "") -> None:
        _log(label, msg)
        if progress_callback:
            progress_callback(pct, label)

    # 1) Transcription -------------------------------------------------------
    _p(8, "1 transcribe")
    vu_path = vu or transcribe.transcribe(
        source, out_path=p("transcripts", f"{stem}_vu.json"))
    vu_data = json.load(open(vu_path, encoding="utf-8"))

    # 2) EDL + grade + base_only --------------------------------------------
    _p(20, "2 build_edl")
    edl_path = p("edl.json")
    build_res = build_edl.build(source, vu_path, outdir=workdir, encode=True)
    base_only = build_res["base_only"]
    # Preuve de découpe: durée d'origine vs gardée (silences/répétitions retirés).
    orig = float(vu_data.get("duration") or 0.0)
    kept = float(build_res.get("output_duration") or 0.0)
    rep["source_duration_s"] = round(orig, 2)
    rep["kept_duration_s"] = round(kept, 2)
    rep["removed_duration_s"] = round(max(0.0, orig - kept), 2)
    rep["segments_kept"] = len(build_res.get("ranges") or [])

    # 2bis) Key moments — hook / numbers / CTA / emotional words / topic shifts.
    # These drive the camera flashes + shutter SFX that make the credit-saver
    # edit feel premium WITHOUT any AI image. Times are mapped SOURCE -> OUTPUT
    # via the EDL ranges so they land on the cut timeline.
    edl_ranges = build_res.get("ranges") or []
    km_cues = key_moments.plan_key_moments(vu_data)
    rep["key_moments"] = len(km_cues)

    def _to_output(src_times: list, min_gap: float = config.FLASH_MIN_GAP) -> list:
        out = sorted({round(timeline.s2o_clamped(t, edl_ranges), 3) for t in src_times})
        # Re-enforce the minimum gap in OUTPUT time (cuts can compress moments).
        spaced: list = []
        for t in out:
            if not spaced or (t - spaced[-1]) >= min_gap:
                spaced.append(t)
        return spaced

    flash_times_out = _to_output(key_moments.flash_times(km_cues))
    shutter_times_out = _to_output(key_moments.shutter_times(km_cues))
    rep["camera_flashes"] = len(flash_times_out)
    rep["shutter_sfx"] = len(shutter_times_out)
    n_topic_shift = sum(1 for c in km_cues if c.reason == "topic_shift")

    # 2ter) Speech-pause light-leak overlay — fires at EVERY meaningful pause
    # (not just the scored/capped key moments) so a plain talking-head edit
    # without B-roll stays visually dynamic throughout. Soft warm flash +
    # whoosh SFX, never closer to a camera flash than its own min gap.
    light_src = key_moments.plan_light_overlays(vu_data)
    light_overlay_times_out = _to_output(light_src, min_gap=config.LIGHT_OVERLAY_MIN_GAP)
    light_overlay_times_out = [
        t for t in light_overlay_times_out
        if all(abs(t - tf) >= config.LIGHT_OVERLAY_MIN_GAP for tf in flash_times_out)
    ]
    rep["light_overlays"] = len(light_overlay_times_out)

    # 3) Graphic overlays ----------------------------------------------------
    _p(34, "3 overlays")
    specs = content.derive_overlay_specs(vu_data)
    rendered_overlays = overlays.render_all(specs, p("animations"))
    overlays_json = p("animations", "_overlays.json")
    json.dump(rendered_overlays, open(overlays_json, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    have_key = bool(os.environ.get("OPENROUTER_API_KEY"))

    # 4) Motion design — illustrated scenes for the key explanatory beats ----
    # Scenes are derived BEFORE the B-roll so the two systems never compete
    # for the same moment of speech (B-roll skips the motion spans).
    motion_json: Optional[str] = None
    motion_scenes: list = []
    if do_motion:
        _p(40, "4 motion_design")
        motion_scenes = content.derive_motion_scenes(
            vu_data, demographic=broll_demographic)
        rep["motion_scenes_derived"] = len(motion_scenes)
        if motion_scenes:
            # AI illustrations are a PAID image call — only when the visual mode
            # allows it (never in credit_saver / when paid generation is off).
            if have_key and visual_mode != "credit_saver" and not disable_paid_images:
                motion_scenes = genimg.generate_illustrations(motion_scenes, p("motion"))
            # Stable per-job look: a seed (job/video id or transcript) keeps a
            # given render reproducible while different videos vary.
            seed_text = style_seed_text or vu_data.get("text") or "".join(
                s.get("text", "") for s in vu_data.get("segments", []))[:400]
            rendered_scenes = motion_design.render_all(
                motion_scenes, p("motion_clips"),
                preset=motion_preset, seed_text=seed_text)
            rep["motion_scenes_rendered"] = len(rendered_scenes)
            rep["motion_ai_illustrations"] = sum(
                1 for s in rendered_scenes if s.get("illustrated"))
            if rendered_scenes:
                motion_json = p("motion_clips", "_motion_clips.json")
                json.dump(rendered_scenes, open(motion_json, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=2)
            else:
                print("[pipeline] WARN motion_design: scenes derived but none "
                      "rendered — check ffmpeg/PIL in this environment",
                      file=sys.stderr)
    else:
        _p(40, "4 motion_design", "skipped (--no-motion)")

    # 5 & 6) B-roll images + animation ---------------------------------------
    # Visual mode decides whether the PAID image API may run:
    #   credit_saver  -> never (motion + flashes + SFX carry the video)
    #   ai_broll      -> yes, generate AI B-roll when possible
    #   auto_fallback -> try, but continue cleanly if it fails / no credits
    # A failure NEVER blocks the render — it falls back to the credit-saver
    # visual plan and records WHY in the report.
    broll_json: Optional[str] = None
    attempt_ai, fallback_reason = plan_visual_mode(
        visual_mode, do_broll=do_broll, have_key=have_key,
        disable_paid_images=disable_paid_images)
    rep["fallback_reason"] = fallback_reason

    if not attempt_ai:
        why = fallback_reason or "credit_saver"
        _p(58, "5-6 broll", f"skipped ({why}) — credit-saver visual plan")
    else:
        _p(48, "5 genimg")
        try:
            ideas = content.derive_broll_ideas(
                vu_data, demographic=broll_demographic, graphic_specs=specs,
                avoid_spans=content.motion_scene_spans(motion_scenes),
            )
            if not ideas:
                rep["fallback_reason"] = "no_ideas"
            else:
                images = genimg.generate_brolls(ideas, p("broll"))
                rep["broll_images"] = len(images)
                if images:
                    _p(58, "6 broll_anim")
                    clips = broll_anim.render_all(images, p("broll_clips"))
                    broll_json = p("broll_clips", "_broll_clips.json")
                    json.dump(clips, open(broll_json, "w", encoding="utf-8"),
                              ensure_ascii=False, indent=2)
                    # AI images actually landed -> this render used them.
                    rep["visual_mode_used"] = "ai_broll"
                    rep["ai_images_skipped"] = False
                    rep["fallback_reason"] = None
                else:
                    # Every idea failed (credits/quota/timeout…): keep rendering.
                    rep["fallback_reason"] = "image_generation_failed"
        except Exception as exc:  # noqa: BLE001 - never fail the render on B-roll
            reason = genimg.classify_image_error(exc)
            rep["fallback_reason"] = reason
            print(f"[pipeline] WARN B-roll generation failed ({reason}); "
                  f"continuing in credit-saver mode: {exc}", file=sys.stderr)
            _p(58, "5-6 broll", f"failed ({reason}) — credit-saver fallback")

    # 7) Plan timeline + SFX cues -------------------------------------------
    _p(62, "7 plan_overlays")
    planned = plan_overlays.plan(edl_path, overlays_json, broll_json,
                                 motion_json=motion_json, outdir=workdir)
    rep["sfx_cues"] = len(planned.get("cues", []))

    # 7bis) Motion-design transitions — bonne pratique de montage: au lieu
    # d'un cut sec, la même lumière chaude qui marque les pauses de parole
    # sert aussi de TRANSITION quand on bascule vers (et qu'on revient de)
    # une scène de motion design. Elle est ajoutée à l'instant exact du cut
    # sur la vidéo de base; comme la scène motion fond depuis la transparence
    # à son entrée/sortie (alpha_fade), la lumière chaude transparaît à
    # travers ce fondu — c'est un vrai effet de transition, pas un flash en
    # plus. Purement visuel ici: la scène motion a déjà son riser/whoosh/
    # swoosh audio propre, pas besoin d'un second SFX au même instant.
    motion_overlays = [o for o in planned.get("overlays", []) if o.get("kind") == "motion"]
    motion_transition_times = sorted({
        round(float(o["start"]), 3) for o in motion_overlays
    } | {
        round(float(o["end"]), 3) for o in motion_overlays
    })
    rep["motion_transitions_lit"] = len(motion_transition_times)

    dynamics_light_times = sorted(set(light_overlay_times_out) | set(motion_transition_times))
    spaced_dynamics_light_times: list = []
    for t in dynamics_light_times:
        if not spaced_dynamics_light_times or (
            t - spaced_dynamics_light_times[-1]) >= config.LIGHT_OVERLAY_MIN_GAP:
            spaced_dynamics_light_times.append(t)

    # 8) Keyword popups ------------------------------------------------------
    _p(66, "8 keyword_popup")
    popup_res = keyword_popup.build_popups(edl_path, p("broll_clips"))
    rep["keyword_popups"] = int(popup_res.get("added", 0))
    rep["sfx_cues"] += int(popup_res.get("sfx_added", 0))

    # 8bis) Key-moment shutter / camera SFX — the AUDIBLE half of the photo
    # capture effect, synced to the white flashes. Merged into the SFX plan so
    # mix_sfx renders them; ducking keeps them under the voice.
    added_key_sfx = _inject_key_moment_sfx(p("sfx_cues.json"), shutter_times_out)
    rep["sfx_cues"] += added_key_sfx

    # 8ter) Speech-pause light-leak whoosh SFX — the audible half of the warm
    # light sweep, synced to the soft flashes added below.
    added_light_sfx = _inject_light_overlay_sfx(p("sfx_cues.json"), light_overlay_times_out)
    rep["sfx_cues"] += added_light_sfx

    # 9) Dynamic zoom + key-moment camera flashes + pause light-leaks --------
    _p(74, "9 video_dynamics")
    base_dyn = video_dynamics.apply_dynamics(
        base_only, edl_path, p("base_dyn.mp4"), flash_times=flash_times_out,
        light_times=spaced_dynamics_light_times)

    # 10) Composite ----------------------------------------------------------
    _p(85, "10 composite")
    nosfx = composite.composite(base_dyn, edl_path, p("composite_nosfx.mp4"), workdir=workdir)

    # 11) SFX + loudnorm -----------------------------------------------------
    _p(91, "11 mix_sfx")
    withsfx = mix_sfx.mix(nosfx, p("sfx_cues.json"), p("composite_withsfx.mp4"),
                          sfxdir=p("sfx"))

    # 12) Subtitles ----------------------------------------------------------
    _p(94, "12 subs_ass")
    ass_path = subs_ass.generate(edl_path, p("master.ass"), template=template)

    # 13) Final burn ---------------------------------------------------------
    _p(97, "13 finalize")
    final = finalize.burn_subs(withsfx, ass_path, p("final_montage_web.mp4"))

    # Final, truthful effect tally — proves the credit-saver edit is dynamic
    # even with zero AI images.
    rep["effects_applied"] = {
        "cameraFlashes": rep["camera_flashes"],
        "shutterSfx": rep["shutter_sfx"],
        "lightOverlays": rep["light_overlays"],
        "motionTransitionsLit": rep["motion_transitions_lit"],
        "motionCards": rep["motion_scenes_rendered"],
        "transitions": (rep["motion_scenes_rendered"] + rep["broll_images"]
                        + n_topic_shift),
    }
    # If AI images never landed, the effective mode is credit_saver regardless
    # of what was requested (the render still happened — never blocked).
    if rep["broll_images"] <= 0:
        rep["visual_mode_used"] = "credit_saver"
        rep["ai_images_skipped"] = True

    if cleanup and os.environ.get("ENGINE_KEEP_INTERMEDIATES") not in {"1", "true"}:
        cleanup_intermediates(workdir)

    if progress_callback:
        progress_callback(100, "done")
    print(f"\n✅ Auto Edit complete ({rep['visual_mode_used']}, "
          f"{rep['camera_flashes']} flashes, "
          f"{rep['light_overlays']} pause light-leaks) -> {final}")
    return final


def _inject_key_moment_sfx(sfx_cues_path: str, shutter_times: list) -> int:
    """Merge camera-shutter SFX at key-moment instants into the SFX plan.

    Alternates the photo-capture sounds (the engine already synthesises them
    locally — no API) so the flashes are AUDIBLE as well as visible, and avoids
    stacking two identical SFX back-to-back. Returns the number added.
    """
    if not shutter_times or not os.path.exists(sfx_cues_path):
        return 0
    try:
        with open(sfx_cues_path, "r", encoding="utf-8") as fh:
            cues = json.load(fh)
    except (OSError, ValueError):
        return 0
    pool = ["camera_flash", "shutter", "camera_flash", "shutter_burst"]
    existing = {(round(float(c.get("t", -1)), 2), c.get("sfx")) for c in cues}
    added = 0
    for i, t in enumerate(shutter_times):
        sfx = pool[i % len(pool)]
        if (round(float(t), 2), sfx) in existing:
            continue
        cues.append({"sfx": sfx, "t": round(float(t), 3), "src": "key_moment"})
        added += 1
    cues.sort(key=lambda c: float(c.get("t", 0.0)))
    with open(sfx_cues_path, "w", encoding="utf-8") as fh:
        json.dump(cues, fh, ensure_ascii=False, indent=2)
    return added


def _inject_light_overlay_sfx(sfx_cues_path: str, light_times: list) -> int:
    """Merge a soft whoosh SFX at each speech-pause light-leak overlay.

    Alternates the breath/transition sounds the engine already synthesises
    locally so the warm light sweep is also AUDIBLE, and avoids stacking two
    identical SFX back-to-back. Returns the number added.
    """
    if not light_times or not os.path.exists(sfx_cues_path):
        return 0
    try:
        with open(sfx_cues_path, "r", encoding="utf-8") as fh:
            cues = json.load(fh)
    except (OSError, ValueError):
        return 0
    pool = ["whoosh", "swoosh_up", "transition", "reverse_swell"]
    existing = {(round(float(c.get("t", -1)), 2), c.get("sfx")) for c in cues}
    added = 0
    for i, t in enumerate(light_times):
        sfx = pool[i % len(pool)]
        if (round(float(t), 2), sfx) in existing:
            continue
        cues.append({"sfx": sfx, "t": round(float(t), 3), "src": "light_overlay"})
        added += 1
    cues.sort(key=lambda c: float(c.get("t", 0.0)))
    with open(sfx_cues_path, "w", encoding="utf-8") as fh:
        json.dump(cues, fh, ensure_ascii=False, indent=2)
    return added


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Run the full Auto Edit pipeline")
    ap.add_argument("source", help="input video")
    ap.add_argument("--workdir", default="out")
    ap.add_argument("--vu", help="use an existing transcript _vu.json (skip step 1)")
    ap.add_argument("--template", default=config.DEFAULT_TEMPLATE,
                    choices=list(config.ASS_TEMPLATES.keys()))
    ap.add_argument("--no-broll", action="store_true", help="skip AI B-roll generation")
    ap.add_argument("--no-motion", action="store_true",
                    help="skip illustrated motion-design scenes")
    ap.add_argument("--visual-mode", default="auto_fallback",
                    choices=["ai_broll", "credit_saver", "auto_fallback"],
                    help="ai_broll | credit_saver | auto_fallback (default)")
    ap.add_argument("--motion-preset", default=None,
                    help="force a motion-design family (clean_fintech, neon_social, …)")
    ap.add_argument("--disable-paid-images", action="store_true",
                    help="never call the paid image API (credit safe)")
    args = ap.parse_args(argv)
    report: dict = {}
    run(args.source, args.workdir, vu=args.vu, template=args.template,
        do_broll=not args.no_broll, do_motion=not args.no_motion,
        visual_mode=args.visual_mode, motion_preset=args.motion_preset,
        disable_paid_images=args.disable_paid_images, report=report)
    print("\n[report]", json.dumps(report.get("effects_applied", {}), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
