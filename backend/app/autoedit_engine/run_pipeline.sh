#!/usr/bin/env bash
# =============================================================================
#  Auto Edit — full pipeline (ORDRE D'EXÉCUTION, SPEC v4 + motion design)
#
#  Usage:
#     ./app/autoedit_engine/run_pipeline.sh INPUT.mp4 [WORKDIR] [TEMPLATE]
#
#  Env:
#     ELEVENLABS_API_KEY   transcription (Scribe)
#     OPENROUTER_API_KEY   B-roll + motion-design illustrations (gemini image)
#     FFMPEG_BIN/FFPROBE_BIN  optional override for a static ffmpeg 7+ build
#     VU_JSON              optional: reuse an existing transcript (skip step 1)
#     ENGINE_MODULE        optional module root (default: app.autoedit_engine)
#
#  Run from backend/ so `python -m app.autoedit_engine.*` resolves.
# =============================================================================
set -euo pipefail

INPUT="${1:?usage: run_pipeline.sh INPUT.mp4 [WORKDIR] [TEMPLATE]}"
WORK="${2:-out}"
TEMPLATE="${3:-tiktok_yellow}"
STEM="$(basename "${INPUT%.*}")"

PY="${PYTHON:-python3}"
MOD="${ENGINE_MODULE:-app.autoedit_engine}"
mkdir -p "$WORK/transcripts" "$WORK/animations" "$WORK/broll" "$WORK/broll_clips" \
         "$WORK/motion" "$WORK/motion_clips" "$WORK/sfx"

run() { echo; echo "=== $* ==="; "$@"; }

# 1 — Transcription (ElevenLabs Scribe) --------------------------------------
VU="${VU_JSON:-$WORK/transcripts/${STEM}_vu.json}"
if [[ -n "${VU_JSON:-}" ]]; then
  echo "=== 1 transcribe === reusing $VU_JSON"
else
  run "$PY" -m "$MOD.transcribe" "$INPUT" --out "$VU"
fi

# 2 — EDL + color grade + concat (base_only.mp4) -----------------------------
run "$PY" -m "$MOD.build_edl" "$INPUT" "$VU" --outdir "$WORK"

# 3 — Graphic overlays -------------------------------------------------------
run "$PY" -m "$MOD.overlays" --from-vu "$VU" --outdir "$WORK/animations"

# 4 — Motion design (illustrated scenes; AI image optional, fallback drawing) -
run "$PY" -m "$MOD.motion_design" --from-vu "$VU" --dump-scenes "$WORK/motion/_scenes.json"
if [[ -n "${OPENROUTER_API_KEY:-}" ]]; then
  # Re-derive with generated illustrations inside the python pipeline is the
  # normal path; standalone CLI keeps the procedural drawings.
  echo "=== 4b motion illustrations === (procedural fallback in CLI mode)"
fi
run "$PY" -m "$MOD.motion_design" "$WORK/motion/_scenes.json" --outdir "$WORK/motion_clips"
MOTION_ARG=(--motion "$WORK/motion_clips/_motion_clips.json")

# 5 & 6 — AI B-roll images + animation (avoids the motion beats) -------------
if [[ -n "${OPENROUTER_API_KEY:-}" ]]; then
  run "$PY" -m "$MOD.genimg" --from-vu "$VU" --outdir "$WORK/broll"
  run "$PY" -m "$MOD.broll_anim" "$WORK/broll/_broll_images.json" --outdir "$WORK/broll_clips"
  BROLL_ARG=(--broll "$WORK/broll_clips/_broll_clips.json")
else
  echo "=== 5-6 broll === skipped (no OPENROUTER_API_KEY)"
  BROLL_ARG=()
fi

# 7 — Plan timeline + SFX cues ------------------------------------------------
run "$PY" -m "$MOD.plan_overlays" --edl "$WORK/edl.json" \
  --overlays "$WORK/animations/_overlays.json" "${BROLL_ARG[@]}" \
  "${MOTION_ARG[@]}" --outdir "$WORK"

# 8 — Keyword popups -----------------------------------------------------------
run "$PY" -m "$MOD.keyword_popup" "$WORK/edl.json" --outdir "$WORK/broll_clips"

# 9 — Dynamic zoom (Ken Burns + micro-punches) ---------------------------------
run "$PY" -m "$MOD.video_dynamics" "$WORK/base_only.mp4" "$WORK/edl.json" -o "$WORK/base_dyn.mp4"

# 10 — Multi-pass composite -----------------------------------------------------
run "$PY" -m "$MOD.composite" "$WORK/base_dyn.mp4" "$WORK/edl.json" -o "$WORK/composite_nosfx.mp4"

# 11 — SFX + loudnorm -----------------------------------------------------------
run "$PY" -m "$MOD.mix_sfx" "$WORK/composite_nosfx.mp4" "$WORK/sfx_cues.json" \
  -o "$WORK/composite_withsfx.mp4" --sfxdir "$WORK/sfx"

# 12 — Animated ASS subtitles ----------------------------------------------------
run "$PY" -m "$MOD.subs_ass" "$WORK/edl.json" -o "$WORK/master.ass" --template "$TEMPLATE"

# 13 — Burn subtitles -> deliverable ----------------------------------------------
run "$PY" -m "$MOD.finalize" "$WORK/composite_withsfx.mp4" "$WORK/master.ass" \
  -o "$WORK/final_montage_web.mp4"

echo
echo "✅ Auto Edit complete -> $WORK/final_montage_web.mp4"
