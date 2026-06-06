#!/usr/bin/env bash
# =============================================================================
#  Auto Edit — full pipeline (ORDRE D'EXÉCUTION, SPEC v4)
#
#  Usage:
#     ./engine/run_pipeline.sh INPUT.mp4 [WORKDIR] [TEMPLATE]
#
#  Env:
#     ELEVENLABS_API_KEY   transcription (Scribe)
#     OPENROUTER_API_KEY   B-roll image generation (gemini-2.5-flash-image)
#     FFMPEG_BIN/FFPROBE_BIN  optional override for a static ffmpeg 7+ build
#     VU_JSON              optional: reuse an existing transcript (skip step 1)
#
#  Run from the repo root so `python -m app.autoedit_engine.*` resolves.
# =============================================================================
set -euo pipefail

INPUT="${1:?usage: run_pipeline.sh INPUT.mp4 [WORKDIR] [TEMPLATE]}"
WORK="${2:-out}"
TEMPLATE="${3:-tiktok_yellow}"
STEM="$(basename "${INPUT%.*}")"

PY="${PYTHON:-python3}"
mkdir -p "$WORK/transcripts" "$WORK/animations" "$WORK/broll" "$WORK/broll_clips" "$WORK/sfx"

run() { echo; echo "=== $* ==="; "$@"; }

# 1 — Transcription (ElevenLabs Scribe) --------------------------------------
VU="${VU_JSON:-$WORK/transcripts/${STEM}_vu.json}"
if [[ -n "${VU_JSON:-}" ]]; then
  echo "=== 1 transcribe === reusing $VU_JSON"
else
  run "$PY" -m engine.transcribe "$INPUT" --out "$VU"
fi

# 2 — EDL + color grade + concat (base_only.mp4) -----------------------------
run "$PY" -m engine.build_edl "$INPUT" "$VU" --outdir "$WORK"

# 3 — Graphic overlays -------------------------------------------------------
run "$PY" -m engine.overlays --from-vu "$VU" --outdir "$WORK/animations"

# 4 & 5 — AI B-roll images + animation (n ~= duration/5) ---------------------
if [[ -n "${OPENROUTER_API_KEY:-}" ]]; then
  run "$PY" -m engine.genimg --from-vu "$VU" --outdir "$WORK/broll"
  run "$PY" -m engine.broll_anim "$WORK/broll/_broll_images.json" --outdir "$WORK/broll_clips"
  BROLL_ARG=(--broll "$WORK/broll_clips/_broll_clips.json")
else
  echo "=== 4-5 broll === skipped (no OPENROUTER_API_KEY)"
  BROLL_ARG=()
fi

# 6 — Plan timeline + SFX cues ----------------------------------------------
run "$PY" -m engine.plan_overlays --edl "$WORK/edl.json" \
  --overlays "$WORK/animations/_overlays.json" "${BROLL_ARG[@]}" --outdir "$WORK"

# 7 — Keyword popups ---------------------------------------------------------
run "$PY" -m engine.keyword_popup "$WORK/edl.json" --outdir "$WORK/broll_clips"

# 8 — Dynamic zoom (Ken Burns + micro-punches) -------------------------------
run "$PY" -m engine.video_dynamics "$WORK/base_only.mp4" "$WORK/edl.json" -o "$WORK/base_dyn.mp4"

# 9 — Multi-pass composite ---------------------------------------------------
run "$PY" -m engine.composite "$WORK/base_dyn.mp4" "$WORK/edl.json" -o "$WORK/composite_nosfx.mp4"

# 10 — SFX + loudnorm --------------------------------------------------------
run "$PY" -m engine.mix_sfx "$WORK/composite_nosfx.mp4" "$WORK/sfx_cues.json" \
  -o "$WORK/composite_withsfx.mp4" --sfxdir "$WORK/sfx"

# 11 — Animated ASS subtitles ------------------------------------------------
run "$PY" -m engine.subs_ass "$WORK/edl.json" -o "$WORK/master.ass" --template "$TEMPLATE"

# 12 — Burn subtitles -> deliverable -----------------------------------------
run "$PY" -m engine.finalize "$WORK/composite_withsfx.mp4" "$WORK/master.ass" \
  -o "$WORK/final_montage_web.mp4"

echo
echo "✅ Auto Edit complete -> $WORK/final_montage_web.mp4"
