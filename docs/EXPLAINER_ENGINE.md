# Moteur « Pub explicative » (motion design sans vidéo source)

Le client discute avec un « motion designer IA », puis CutForge produit seul une
pub verticale 9:16 : script, voix off, animation plein écran de chaque phrase,
effets sonores, musique et mixage. Aucune vidéo à filmer.

```
Entretien (brief) ─► Script + storyboard ─► Voix off minutée ─► Page HTML animée
     /ads/interview     IA OpenRouter           edge-tts ou          web/engine.js
                        ou gabarits (sans clé)  ElevenLabs            (seek(t) pur)
                                                                          │
      MP4 ◄── mux ◄── mixage (voix + musique + SFX) ◄── rendu Chromium parallèle
```

## Code

| Fichier | Rôle |
| --- | --- |
| `backend/app/explainer/interview.py` | Entretien sans état serveur. Questionnaire guidé, enrichi par l'IA si `OPENROUTER_API_KEY`. « Choisis pour moi » déduit l'angle. |
| `backend/app/explainer/writer.py` | Brief → storyboard. IA (catalogue de scènes + règles) ou **mode secours sans clé** (gabarits d'angles). `sanitize()` retire tout chiffre non fourni par le client, garantit CTA + carte de fin, évite deux scènes identiques d'affilée. |
| `backend/app/explainer/templates.py` | **Templates** (packs de style : couleurs, typo, transition, grain, secousse, musique), **angles** publicitaires, **catalogue de scènes**. |
| `backend/app/explainer/tts.py` | Voix off phrase par phrase + minutage mot par mot (WordBoundary / alignment). ElevenLabs si clé, sinon edge-tts. |
| `backend/app/explainer/web/engine.js` | Moteur d'animation : 15 scènes paramétriques, ressorts physiques, texte cinétique, emblème 3D extrudé, transitions, grain, caméra. Chaque scène déclare ses SFX. |
| `backend/app/explainer/composer.py` | Storyboard + voix + template → page HTML autonome (polices embarquées). |
| `backend/app/explainer/renderer.py` + `web/render.js` | Chromium (puppeteer-core en prod, playwright en dev) : repères SFX, vignette, rendu vidéo en tranches parallèles avec flou de mouvement. |
| `backend/app/explainer/audio.py` | 21 sons de synthèse, musique (tension → humeur du template), ducking sous la voix, loudnorm −14 LUFS. |
| `backend/app/explainer/pipeline.py` | Orchestration + progression. CLI : `python -m app.explainer brief.json --out dossier`. |
| `backend/app/api/v1/ads.py` | API `/ads` (catalogue, entretien, aperçu du script, création, suivi, vidéo, vignette, annulation, suppression). Quotas du plan. |
| `backend/app/workers/tasks.py` | Tâche Celery `process_ad_project`. |
| `backend/alembic/versions/006_ad_projects.py` | Table `ad_projects`. |
| `frontend/src/pages/AdStudio.tsx` | Studio : chat, aperçu du storyboard, création, suivi, lecture et téléchargement. Route `/pub`. |

## Scènes disponibles

`title_slam`, `icon_cards`, `checklist`, `loss_drain`, `hero_reveal`, `split_compare`,
`bars_compare`, `crowd_select`, `toggle_decision`, `choice_cards`, `timer_ring`,
`cta_button`, `chat_bubbles`, `stat_number` (seulement avec un chiffre du client),
`end_card`. Une phrase peut prolonger la scène précédente avec `{"type": "continue"}`.

## Ajouter un template

Ajouter une entrée dans `TEMPLATES` (`templates.py`) : couleurs de base, police de
titre (`Anton`, `Bebas`, `DMSerif`), `transition` (`whip`, `zoom`, `slide`),
`music` (`hopeful`, `energetic`, `calm`), `bpm`, `grain`, `shake`. Les couleurs
dérivées (clair/foncé de l'accent, texte sur accent) sont calculées automatiquement,
et la couleur de marque du client remplace l'accent.

## Réglages (.env)

| Variable | Défaut | Rôle |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | — | Script + entretien IA. Sans clé : mode secours. |
| `EXPLAINER_LLM_MODEL` | `google/gemini-2.5-flash` | Modèle OpenRouter. |
| `ELEVENLABS_API_KEY` / `ELEVENLABS_VOICE_ID` | — | Voix sous licence commerciale (recommandé en production). |
| `ADS_MAX_PER_MONTH_FREE` | 2 | Pubs par mois sur le plan Free. |
| `EXPLAINER_RENDER_WORKERS` | 0 (= CPU) | Navigateurs en parallèle pour le rendu. |

Rendu : ~6 min pour 30 s de pub sur 2 vCPU ; le temps baisse presque
linéairement avec le nombre de cœurs.

> ⚠️ edge-tts (voix sans clé) est un service non officiel : pas de garantie ni de
> licence commerciale. Configurer ElevenLabs avant d'ouvrir la fonction aux clients payants.
