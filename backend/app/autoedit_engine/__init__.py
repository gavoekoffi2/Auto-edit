"""
Auto Edit — automatic viral video montage engine.

A faithful implementation of the "MOTEUR AUTO EDIT — SPEC v4" recipe:
cut+grade -> dynamic zoom -> overlays (ballotage) -> SFX -> animated ASS subs,
rendered as a vertical 1080x1920 / 30 fps reel.

Each step is a self-contained module (importable and runnable as a CLI):
    transcribe, build_edl, video_dynamics, overlays, motion_design, genimg,
    broll_anim, keyword_popup, plan_overlays, composite, mix_sfx, subs_ass,
    finalize.

``engine.pipeline`` (and ``run_pipeline.sh``) wire them together.
"""

__version__ = "4.1.0"
