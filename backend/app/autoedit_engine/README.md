# Auto Edit — viral montage engine

Automatic vertical **1080×1920 / 30 fps** reel generator. Drop in a talking-head
clip and the engine cuts it tight, grades it, adds dynamic zoom, graphic
overlays, AI B-roll, keyword popups, sound design and animated karaoke
subtitles — the full "MOTEUR AUTO EDIT — SPEC v4" recipe.

```
cut + grade → dynamic zoom → overlays (ballotage) → SFX → ASS subtitles
```

## Pipeline (ORDRE D'EXÉCUTION)

| # | Module | Output |
|---|--------|--------|
| 1 | `transcribe.py` | `transcripts/<v>_vu.json` (ElevenLabs Scribe, word-level) |
| 2 | `build_edl.py` | `edl.json`, `clips_graded/seg_*.mp4`, `base_only.mp4` (cut + warm_cinematic grade + concat **filter**) |
| 3 | `overlays.py` | `animations/*.mov` (counters / progress / lists / stats / lower-thirds → ProRes 4444) |
| 4 | `genimg.py` | `broll/*.png` (OpenRouter `gemini-2.5-flash-image`, **n ≈ duration/5**) |
| 5 | `broll_anim.py` | `broll_clips/br_*.mov` (punch/slide/rise/glitch/flash/… + Ken Burns + cyan brackets) |
| 6 | `plan_overlays.py` | `edl.json` overlays + `sfx_cues.json` (ballotage placement, alternating SFX, gap-fill) |
| 7 | `keyword_popup.py` | `broll_clips/popup_*.mov` + edl patch (top-8 keywords, gold chips @ y≈450) |
| 8 | `video_dynamics.py` | `base_dyn.mp4` (Ken Burns alterné + gaussian micro-punches) |
| 9 | `composite.py` | `composite_nosfx.mp4` (multi-pass, 12 overlays / batch — OOM-safe) |
| 10 | `mix_sfx.py` | `composite_withsfx.mp4` (19-sound numpy library, −14 LUFS loudnorm) |
| 11 | `subs_ass.py` | `master.ass` (karaoke, `hl_scale=145`, 5 templates) |
| 12 | `finalize.py` | `final_montage_web.mp4` (CRF 26, preset slow, faststart) |

Shared helpers: `config.py` (every spec constant), `content.py` (transcript →
montage decisions), `timeline.py` (`s2o` source→output mapping), `sfx_lib.py`
(the 19 sounds), `fonts.py`, `render_utils.py` (ProRes RGBA pipe + easing),
`ffmpeg_utils.py`.

## Requirements

- Python 3.11+, `pip install -r engine/requirements.txt` (numpy, Pillow, requests)
- **ffmpeg 7+** (static build) on `PATH`, or set `FFMPEG_BIN` / `FFPROBE_BIN`
- Fonts: DejaVuSans-Bold is the always-present fallback; for the exact look drop
  Montserrat / Anton / Bangers / Bebas Neue into `~/.fonts/`
- API keys: `ELEVENLABS_API_KEY` (transcription), `OPENROUTER_API_KEY` (B-roll)

## Usage

Run everything (from the repo root):

```bash
export ELEVENLABS_API_KEY=... OPENROUTER_API_KEY=...
./engine/run_pipeline.sh input.mp4 out tiktok_yellow
# -> out/final_montage_web.mp4
```

…or the Python orchestrator:

```bash
python -m engine.pipeline input.mp4 --workdir out --template gold_lux
python -m engine.pipeline input.mp4 --workdir out --vu cached_vu.json --no-broll
```

Every step is also a standalone CLI, e.g.:

```bash
python -m engine.build_edl input.mp4 out/transcripts/input_vu.json --outdir out
python -m engine.overlays --from-vu out/transcripts/input_vu.json --outdir out/animations
python -m engine.subs_ass out/edl.json -o out/master.ass --template neon_pop
```

Subtitle templates: `tiktok_yellow`, `neon_pop`, `bold_box`, `gold_lux`,
`bangers_fun`.

## Anti-collision safe zones

```
y <  850   face          → free
y 880–1430 graphics       → counters / progress / lists / stats
y ≈ 450    keyword popups → above the face (TikTok style)
y ≈ 1500   subtitles      → ≥ 50 px below the overlays
```

## What to commit

Per spec, **do not** commit heavy intermediates (`*.mov`, `base_only.mp4`,
`base_dyn.mp4`, `composite*.mp4`, `clips_graded/`) — they are git-ignored.
Keepable artifacts: B-roll PNGs, SFX WAVs, the transcript JSON, `master.ass`,
and `final_montage_web.mp4` (~25–35 MB for 90–120 s).

## Tuning

All knobs live in `config.py`: `GAP_CUT`, `PAD`, `FILLERS`, the `GRADE`
string, Ken Burns / micro-punch params, overlay fades & zones, B-roll
entrances, keyword popup rules, SFX pools & gains, loudnorm target, ASS
templates and the final render settings.
