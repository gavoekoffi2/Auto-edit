# Auto Edit — viral montage engine

Automatic vertical **1080×1920 / 30 fps** reel generator. Drop in a talking-head
clip and the engine cuts it tight, grades it, adds dynamic zoom, graphic
overlays, **illustrated motion-design scenes**, AI B-roll, keyword popups,
sound design and animated karaoke subtitles — the full "MOTEUR AUTO EDIT —
SPEC v4" recipe, plus the v4.1 motion-design system.

```
cut + grade → dynamic zoom → motion design + overlays (ballotage) → SFX → ASS subtitles
```

## Pipeline (ORDRE D'EXÉCUTION)

| # | Module | Output |
|---|--------|--------|
| 1 | `transcribe.py` | `transcripts/<v>_vu.json` (ElevenLabs Scribe, word-level) |
| 2 | `build_edl.py` | `edl.json`, `clips_graded/seg_*.mp4`, `base_only.mp4` (cut + warm_cinematic grade + concat **filter**) |
| 3 | `overlays.py` | `animations/*.mov` (counters / progress / lists / stats / lower-thirds → ProRes 4444) |
| 4 | `motion_design.py` + `motion_3d.py` | `motion_clips/md_*.mov` — **scènes illustrées animées** qui montrent ce que la personne explique (illustration IA 3D quand une clé existe, sinon **scène 3D procédurale** rendue localement : volumes ombrés, caméra qui tourne, ombre de contact ; puis flèches dessinées, cercle marqueur, étapes numérotées, compteurs) |
| 5 | `genimg.py` | `broll/*.png` (OpenRouter `gemini-2.5-flash-image`, **n ≈ duration/5**, évite les beats motion) + `motion/*.png` (illustrations des scènes) |
| 6 | `broll_anim.py` | `broll_clips/br_*.mov` (punch/slide/rise/glitch/flash/… + Ken Burns + cyan brackets) |
| 7 | `plan_overlays.py` | `edl.json` overlays + `sfx_cues.json` (ballotage, priorité motion, riser+whoosh+pops par scène — chaque SFX est lié à un visuel, pas de gap-fill) |
| 8 | `keyword_popup.py` | `broll_clips/popup_*.mov` + edl patch (top-8 keywords ; jamais par-dessus une scène motion) |
| 9 | `video_dynamics.py` | `base_dyn.mp4` (Ken Burns alterné + gaussian micro-punches) |
| 10 | `composite.py` | `composite_nosfx.mp4` (multi-pass, 12 overlays / batch — OOM-safe) |
| 11 | `mix_sfx.py` | `composite_withsfx.mp4` (27-sound numpy library, variation pitch/gain par cue, −14 LUFS loudnorm) |
| 12 | `subs_ass.py` | `master.ass` (karaoke, `hl_scale=145`, 5 templates) |
| 13 | `finalize.py` | `final_montage_web.mp4` (CRF 26, preset slow, faststart) |

## Smart cut (v4.2)

`build_edl` ne coupe plus seulement les silences : les **faux départs** (une
phrase immédiatement re-commencée), les **phrases répétées** (la dernière prise
gagne), les marqueurs de reprise (« je reprends / on recommence / coupe ça »)
et les **bégaiements** (« il faut il faut ») sont supprimés. Chaque coupe tombe
sur une frontière de mot (+ marge MICRO_PAD) : la parole n'est jamais hachée.

## Sound design pro (v4.2)

**27 sons** synthétisés (8 nouveaux : `shutter_burst`, `camera_focus`,
`pen_scribble`, `tape_stop`, `bubble`, `snap`, `cinematic_hit`, `data_tick`),
pools distincts par type de visuel (B-roll = sons photo/caméra, motion =
pops/dessin, popups = blips UI) et **variation pitch/gain par occurrence** dans
`mix_sfx` : un même son ne se répète jamais à l'identique.

## Motion design illustré (v4.1)

Les beats explicatifs les plus importants du discours (énumérations, chiffres,
phrases d'emphase « important / secret / méthode / étape… ») sont détectés dans
le transcript et illustrés par une **prise d'écran complète animée** de
4,6–5,4 s pendant que la voix continue :

* scène `idea`   — illustration + gros mot-clé + flèches dessinées à la main ;
* scène `steps`  — pastilles d'étapes numérotées qui apparaissent en cascade ;
* scène `number` — compteur animé doré (pourcentages / chiffres clés).

L'illustration vient de l'API image (rendu 3D cinéma, sans texte) ; sans clé
API — ou en mode économique — la scène est rendue par le **moteur 3D
procédural** `motion_3d.py` (voir plus bas). Chaque scène exporte ses
`events` (entrée / éléments / sortie) que `plan_overlays` convertit en SFX :
`riser` 0,45 s avant, `whoosh`/`transition` à l'entrée, `pop`/`ding`/`click`
sur chaque élément, `swoosh_down` à la sortie. Les B-rolls évitent ces spans et
les popups ne s'affichent jamais par-dessus.

## Moteur 3D procédural (`motion_3d.py`)

Le repli sans image IA n'est plus un dessin au trait — quatre lignes blanches ne
racontent rien sur un montage réel. C'est désormais une **vraie scène 3D**,
rendue localement, sans crédit image et sans asset externe :

* **primitives ombrées** — prisme extrudé (polygone 2D extrudé en Z, faces
  latérales éclairées par leur normale, arêtes ciselées) et sphère (normale par
  pixel, Blinn-Phong : ambiante + diffuse + spéculaire + rim light) ;
* **caméra** yaw/pitch avec perspective faible qui **tourne pendant la scène** :
  c'est la rotation qui fait lire le volume ;
* **studio** par style (dégradé, halo, sol, vignette) + **ombre de contact**
  floutée, cascade d'apparition des pièces, balayage de lumière à l'entrée ;
* **34 modèles** (argent, croissance, fusée, bouclier, cadenas, horloge,
  téléphone, panier, engrenages, globe, banque, carte…) composés à partir des
  primitives et indexés sur les icônes que `content.icon_for_text` détecte déjà
  dans le discours : l'objet 3D illustre donc ce que la personne dit ;
* **5 styles** — `clay_studio` (pâte à modeler), `glass_neon` (verre néon),
  `chrome_metal` (chrome), `iso_blocks` (isométrique), `paper_relief` (papier en
  relief). Le style suit la famille de preset (`motion_presets.style_3d_for`),
  qui elle-même tourne par graine stable : deux vidéos ne rendent pas le même 3D,
  un même job reste reproductible.

Les couleurs d'objet sont des **rôles** (`primary` / `secondary` / `light` /
`dark` / `shade`) résolus par la palette de la famille : un même modèle
s'habille correctement dans les cinq directions artistiques.

Rollback / réglage :

```bash
MOTION_3D=0                    # revient au repli au trait
MOTION_3D_STYLE=glass_neon     # force un style pour tous les montages
python -m app.autoedit_engine.motion_3d growth --style iso_blocks --out planche.png
python -m app.autoedit_engine.motion_3d --list
```

Shared helpers: `config.py` (every spec constant), `content.py` (transcript →
montage decisions: overlays, scènes motion design, idées B-roll), `timeline.py` (`s2o` source→output mapping), `sfx_lib.py`
(the 27 sounds), `fonts.py`, `render_utils.py` (ProRes RGBA pipe + easing),
`ffmpeg_utils.py`.

## Requirements

- Python 3.11+, `pip install -r app/autoedit_engine/requirements.txt` (numpy, Pillow, requests)
- **ffmpeg 7+** (static build) on `PATH`, or set `FFMPEG_BIN` / `FFPROBE_BIN`
- Fonts: DejaVuSans-Bold is the always-present fallback; for the exact look drop
  Montserrat / Anton / Bangers / Bebas Neue into `~/.fonts/`
- API keys: `ELEVENLABS_API_KEY` (transcription), `OPENROUTER_API_KEY` (B-roll)

## Usage

Run everything (from the repo root):

```bash
export ELEVENLABS_API_KEY=... OPENROUTER_API_KEY=...
./app/autoedit_engine/run_pipeline.sh input.mp4 out tiktok_yellow
# -> out/final_montage_web.mp4
```

…or the Python orchestrator:

```bash
python -m app.autoedit_engine.pipeline input.mp4 --workdir out --template gold_lux
python -m app.autoedit_engine.pipeline input.mp4 --workdir out --vu cached_vu.json --no-broll
```

Every step is also a standalone CLI, e.g.:

```bash
python -m app.autoedit_engine.build_edl input.mp4 out/transcripts/input_vu.json --outdir out
python -m app.autoedit_engine.overlays --from-vu out/transcripts/input_vu.json --outdir out/animations
python -m app.autoedit_engine.subs_ass out/edl.json -o out/master.ass --template neon_pop
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
