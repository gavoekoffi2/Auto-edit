# AutoEdit — Architecture du pipeline vidéo V2

> Pipeline de montage vidéo automatique IA pour le marché africain francophone.
> Inspiré de `browser-use/video-use`, `heygen-com/hyperframes`, `Remotion`.

---

## 1. Objectifs produit

1. **Une vidéo brute → une vidéo prête à publier** (TikTok / Reels / Shorts) sans
   intervention humaine.
2. **Cible : entrepreneurs et entreprises africaines francophones** (Togo, Bénin,
   Côte d’Ivoire, Sénégal, Cameroun, RDC…).
3. **Pluggable** : chaque étape (transcription, B-roll, renderer) doit être
   remplaçable via interfaces et variables d’environnement.

---

## 2. Pipeline complet (vue d’ensemble)

```
       ┌────────────────────────────────────────────────┐
       │                Upload (FastAPI)                │
       └─────────────────────────┬──────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────┐
│  Celery task: process_video_v2(job_id, mode, options)  │
└────────────────────────────────────────────────────────┘
   │
   │  1. TranscriptionService    →  WordSegment[]   (timestamps mot-par-mot)
   │  2. SilenceDetector         →  SilenceRange[]  (RMS / VAD / auto-editor)
   │  3. EditDecisionService     →  EditDecisionList
   │       - cuts (silences + filler words + parties faibles)
   │       - segments narratifs
   │       - self-evaluation des cuts
   │  4. BrollPlanner            →  BrollCue[]      (segments à habiller B-roll)
   │  5. ImageGenerationService  →  ImageAsset[]    (OpenRouter, africain premium)
   │  6. BrollAnimationService   →  VideoClip[]     (Ken Burns FFmpeg)
   │  7. TemplateRenderer        →  OverlayClip[]   (HyperFrames / Remotion / FFmpeg)
   │  6bis. MotionDesign (engine) →  motion_clips/*.mov (scènes illustrées
   │        animées dérivées du transcript — voir app/autoedit_engine/motion_design.py)
   │  8. FFmpegRenderer          →  final.mp4
   │       - concat selon EDL
   │       - captions dynamiques (drawtext / ASS)
   │       - music ducking + SFX
   │       - export 9:16 1080×1920 ou 16:9 1920×1080
   ▼
       ┌────────────────────────────────────────────────┐
       │       Stockage + result JSON dans DB Jobs      │
       └────────────────────────────────────────────────┘
```

---

## 3. Modules backend

### 3.1 Arborescence cible

```
backend/app/processing/
├── __init__.py
├── pipeline.py                  # v1 (préservé, ne pas casser)
├── pipeline_v2.py               # nouveau pipeline modulaire
│
├── transcribe.py                # v1
├── silence.py                   # v1
├── scenes.py                    # v1
├── effects.py                   # v1
│
├── transcription_service.py     # v2 wrapper Whisper / faster-whisper / API
├── silence_detector.py          # v2 wrapper auto-editor + VAD
├── edit_decision_service.py     # v2 EDL + filler words + cuts
├── broll_planner.py             # v2 plan B-roll IA
├── image_generation_service.py  # v2 OpenRouter / provider abstrait
├── broll_animation_service.py   # v2 Ken Burns FFmpeg
├── template_renderer.py         # v2 abstraction overlays (ffmpeg/hyperframes/remotion)
├── ffmpeg_renderer.py           # v2 rendu final FFmpeg
│
└── providers/
    ├── __init__.py
    ├── image_provider_base.py   # interface ImageProvider
    └── openrouter_image.py      # implémentation OpenRouter
```

### 3.2 Contrats (interfaces Python)

#### `TranscriptionService`

```python
class TranscriptionService:
    def transcribe(self, audio_path: str, language: str | None = None) -> Transcript:
        ...

@dataclass
class Word:
    text: str
    start: float
    end: float
    confidence: float | None = None

@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: list[Word]

@dataclass
class Transcript:
    language: str
    text: str
    segments: list[Segment]
```

#### `SilenceDetector`

```python
@dataclass
class SilenceRange:
    start: float
    end: float
    reason: str  # "silence" | "noise" | "filler_word"

class SilenceDetector:
    def detect(self, audio_path: str, **opts) -> list[SilenceRange]: ...
```

#### `EditDecisionService` → EDL

```python
@dataclass
class Cut:
    source_start: float
    source_end: float
    keep: bool
    reason: str    # "silence" | "filler_word" | "weak" | "keep"

@dataclass
class EditDecisionList:
    source_path: str
    cuts: list[Cut]
    total_kept_duration: float
    metadata: dict
```

#### `BrollPlanner`

```python
@dataclass
class BrollCue:
    segment_start: float
    segment_end: float
    prompt: str                  # prompt image généré
    style: str                   # ex: "african_business_premium"
    aspect_ratio: str            # "9:16" / "16:9"
    priority: int                # 1..5
```

#### `ImageProvider` (abstrait)

```python
@dataclass
class GeneratedImage:
    bytes: bytes | None
    url: str | None
    mime_type: str
    provider: str
    model: str
    cost_estimate_usd: float | None
    prompt: str

class ImageProvider(Protocol):
    name: str
    def generate(
        self,
        prompt: str,
        aspect_ratio: str = "9:16",
        style: str | None = None,
        timeout_s: int = 60,
    ) -> GeneratedImage: ...
```

#### `BrollAnimationService`

```python
class BrollAnimationService:
    def animate(
        self,
        image_path: str,
        out_path: str,
        duration_s: float,
        motion: str = "ken_burns",  # ken_burns | zoom_in | zoom_out | pan_lr | pan_rl
        fade: bool = True,
        aspect_ratio: str = "9:16",
    ) -> str: ...
```

#### `TemplateRenderer`

```python
class TemplateRenderer:
    def __init__(self, backend: str = "ffmpeg"): ...  # ffmpeg|hyperframes|remotion
    def render_overlay(self, template: str, props: dict, out_path: str) -> str: ...
```

#### `FFmpegRenderer`

```python
class FFmpegRenderer:
    def render(
        self,
        edl: EditDecisionList,
        broll_clips: list[str],
        overlay_clips: list[str],
        captions_srt: str | None,
        music_path: str | None,
        sfx: list[dict],
        out_path: str,
        aspect_ratio: str = "9:16",
    ) -> str: ...
```

---

## 4. Jobs Celery

```
process_video        (v1, conservé)
process_video_v2     (nouveau, opt-in via PIPELINE_VERSION ou payload)
generate_broll       (sous-tâche optionnelle, future v2.1)
```

Le job v2 reste **idempotent** : il écrit dans `output_dir = uploads/{user}/{job}/`
et tous les artefacts intermédiaires sont rangés dans des sous-dossiers :

```
uploads/{user}/{job}/
├── transcript.json
├── words.json
├── edl.json
├── broll/
│   ├── 0001.png
│   ├── 0001.mp4         # clip animé
│   ├── ...
├── overlays/
│   ├── intro_card.mp4
│   ├── lower_third_01.mp4
│   └── cta_end.mp4
├── captions.ass
├── concat.txt
└── final_output.mp4
```

---

## 5. Formats de fichiers

### 5.1 EDL JSON (`edl.json`)

```json
{
  "source_path": "uploads/<user>/<video>.mp4",
  "total_kept_duration": 47.32,
  "cuts": [
    { "source_start": 0.00, "source_end": 0.82,  "keep": false, "reason": "silence" },
    { "source_start": 0.82, "source_end": 7.41,  "keep": true,  "reason": "keep" },
    { "source_start": 7.41, "source_end": 8.05,  "keep": false, "reason": "filler_word", "text": "euh" },
    { "source_start": 8.05, "source_end": 12.4,  "keep": true,  "reason": "keep" }
  ],
  "broll_cues": [
    {
      "segment_start": 2.0,
      "segment_end": 6.5,
      "prompt": "Jeune entrepreneur togolais souriant dans un bureau moderne...",
      "style": "african_business_premium",
      "aspect_ratio": "9:16",
      "asset_path": "broll/0001.mp4"
    }
  ],
  "overlays": [
    { "kind": "intro_card", "start": 0.0, "end": 2.0, "props": { "title": "Lance ton e-commerce" } },
    { "kind": "lower_third", "start": 6.0, "end": 9.0, "props": { "name": "Kossi A.", "role": "Founder" } },
    { "kind": "cta", "start": -3.0, "end": 0.0, "props": { "text": "Abonne-toi" } }
  ],
  "captions": { "style": "tiktok_viral", "srt_path": "captions.ass" },
  "audio": { "music": "music/afro_uplift_01.mp3", "ducking_db": -18 },
  "render": { "aspect_ratio": "9:16", "fps": 30, "width": 1080, "height": 1920 }
}
```

### 5.2 Words JSON (`words.json`)

Output de `TranscriptionService` enrichi par `EditDecisionService` :

```json
[
  { "text": "Bonjour", "start": 0.82, "end": 1.12, "keep": true },
  { "text": "euh",     "start": 1.30, "end": 1.55, "keep": false, "reason": "filler" },
  { "text": "je",      "start": 1.60, "end": 1.72, "keep": true }
]
```

---

## 6. Intégration B-roll IA Afrique

### 6.1 Style par défaut

`BROLL_STYLE=african_business_premium` → injecte dans chaque prompt :

> "Premium realistic photography, modern African business context, soft natural
> light, shallow depth of field, photorealistic, 35mm, color graded, magazine
> quality, diverse young African professionals (Togo, Benin, Ivory Coast, Senegal,
> Cameroon, DRC), modern offices, clean streets, no stereotypes."

### 6.2 Génération du prompt par segment

`broll_planner.py` :

1. lit le transcript ;
2. groupe les words en phrases narratives de 2,5 à 8 s ;
3. pour chaque phrase, extrait les entités (commerce, formation, e-commerce,
   immobilier, restauration, mobile money, etc.) via heuristique + LLM optionnel ;
4. compose un prompt = `[contexte africain] + [scène concrète] + [style]` ;
5. enfile un `BrollCue`.

### 6.3 Fallback

- Si `ImageGenerationService.generate(...)` échoue (timeout, quota, modèle indispo) :
  - on logge en `WARNING` ;
  - on remplace par un overlay texte (TemplateRenderer) ;
  - le job continue, `result.broll_failures` liste les segments concernés.

---

## 7. Intégration templates (overlays animés)

`template_renderer.py` expose `render_overlay(template, props, out_path)`.

| Backend | Quand | Implémentation |
| --- | --- | --- |
| `ffmpeg` | MVP, overlays simples | drawtext, drawbox, fade |
| `hyperframes` | Cards / lower thirds / CTA riches | Node CLI dans un container Node séparé |
| `remotion` | Compositions React custom | `npx remotion render` |

Choix piloté par `VIDEO_RENDERER` ou `template.backend` dans l’EDL.

---

## 8. Intégration image generation

`providers/openrouter_image.py` :

- Endpoint : `https://openrouter.ai/api/v1/chat/completions` (mode image
  pour les modèles capables) ou `https://openrouter.ai/api/v1/images/generations`
  selon ce que le modèle expose.
- En-têtes : `Authorization: Bearer ${OPENROUTER_API_KEY}` (jamais en clair dans le repo).
- Modèle configurable : `IMAGE_GENERATION_MODEL`. Par défaut on documente
  `google/gemini-2.5-flash-image-preview` (Nano Banana via OpenRouter).
- Retry exponentiel 3x, timeout 60 s.
- Mesure coût estimatif `cost_estimate_usd` (basé sur tarif modèle si exposé).

---

## 9. Intégration FFmpeg

### 9.1 Étapes

1. **Couper** la source selon les `cuts` actifs → liste de segments `.mp4` ou
   `-filter_complex` `select=between(t,a,b)`.
2. **Concaténer** les segments avec `concat` demuxer.
3. **Coller** les B-roll comme overlay (`overlay`, `setpts`) ou comme cuts complets
   (selon `kind`).
4. **Coller** les overlays (intro/lower third/CTA) en `xstack`/`overlay`.
5. **Caption** dynamique via `subtitles=captions.ass` (style ASS) ou `drawtext`
   pour mode TikTok viral (mots animés).
6. **Audio** : mixer voix + musique avec ducking (`sidechaincompress`) + SFX.
7. **Resize / crop** final en 9:16 (1080×1920) ou 16:9 (1920×1080).
8. Export H.264 + AAC, GOP 2 s, faststart.

### 9.2 Commande type (extrait)

```
ffmpeg -i input.mp4 \
       -i broll/0001.mp4 \
       -i overlays/cta_end.mp4 \
       -i music/afro_uplift_01.mp3 \
       -filter_complex "[0:v]trim=0.82:7.41,setpts=PTS-STARTPTS[v0]; \
                        [0:v]trim=8.05:12.4,setpts=PTS-STARTPTS[v1]; \
                        [v0][v1]concat=n=2:v=1:a=0[vmain]; \
                        [vmain]scale=1080:1920:force_original_aspect_ratio=increase, \
                               crop=1080:1920[vfit]; \
                        [vfit]subtitles=captions.ass[vout]; \
                        [0:a]atrim=0.82:7.41,asetpts=PTS-STARTPTS[a0]; \
                        [0:a]atrim=8.05:12.4,asetpts=PTS-STARTPTS[a1]; \
                        [a0][a1]concat=n=2:v=0:a=1[avoice]; \
                        [3:a]volume=0.4[amusic]; \
                        [avoice][amusic]amix=inputs=2:duration=first[aout]" \
       -map "[vout]" -map "[aout]" \
       -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p \
       -c:a aac -b:a 192k -movflags +faststart \
       final_output.mp4
```

---

## 10. Logique d’export

| Préset utilisateur | Aspect | Resolution | Captions | B-roll IA |
| --- | --- | --- | --- | --- |
| TikTok viral | 9:16 | 1080×1920 | mots animés | oui, agressif |
| Business premium africain | 9:16 ou 16:9 | 1080×1920 / 1920×1080 | sobres | oui, sobre |
| Publicité locale | 9:16 | 1080×1920 | gros CTA | oui, ciblé produit |
| Podcast propre | 16:9 ou 1:1 | 1920×1080 / 1080×1080 | optionnel | non |
| Formation / éducatif | 16:9 | 1920×1080 | clairs | optionnel |

Toggles utilisateur :

- `remove_silence` (default ON sauf podcast brut)
- `dynamic_captions` (default ON)
- `ai_broll` (default ON pour viral / publicité, OFF pour podcast)
- `music` (default ON)
- `sfx` (default ON pour TikTok viral, OFF pour podcast)
- `vertical_9_16` (default ON pour TikTok / Reels / Shorts)
- `final_cta` (default ON pour publicité, OFF pour podcast)

---

## 11. Variables d’environnement

Voir `.env.example`. Toutes nouvelles :

```
OPENROUTER_API_KEY=
IMAGE_GENERATION_PROVIDER=openrouter
IMAGE_GENERATION_MODEL=google/gemini-2.5-flash-image-preview
BROLL_STYLE=african_business_premium
BROLL_DEFAULT_ASPECT_RATIO=9:16
VIDEO_RENDERER=ffmpeg
ENABLE_AI_BROLL=true
ENABLE_DYNAMIC_CAPTIONS=true
ENABLE_SFX=true
ENABLE_MUSIC=true
PIPELINE_VERSION=v1
```

---

## 12. Phasage d’implémentation

| Phase | Livrable | Statut |
| --- | --- | --- |
| 1 | Audit + fix bugs + .env | ✅ |
| 2 | Architecture doc | ✅ |
| 3 | Modules processing/ v2 + provider OpenRouter | ✅ (squelette) |
| 4 | Frontend : styles africains + toggles | ✅ |
| 5 | Pipeline v2 utilisable end-to-end | partiel (orchestration en place, certains modules en stubs sûrs) |
| 6 | Templates HyperFrames / Remotion concrets | à faire post-MVP |
| 7 | Email reset, tests, S3, admin | à faire post-MVP |
