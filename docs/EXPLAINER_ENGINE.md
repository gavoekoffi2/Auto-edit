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
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | — / — / `auto:smart` | Passerelle LLM compatible OpenAI, **essayée en premier** (ex: FreeLLMAPI). |
| `OPENROUTER_API_KEY` | — | Script + entretien IA via OpenRouter (2e choix). Sans aucune IA : mode secours par règles. |
| `EXPLAINER_LLM_MODEL` | `google/gemini-2.5-flash` | Modèle OpenRouter. |
| `ELEVENLABS_API_KEY` / `ELEVENLABS_VOICE_ID` | — | Voix sous licence commerciale (recommandé en production). |
| `ADS_MAX_PER_MONTH_FREE` | 2 | Pubs par mois sur le plan Free. |
| `EXPLAINER_RENDER_WORKERS` | 0 (= CPU) | Navigateurs en parallèle pour le rendu. |

Rendu : ~6 min pour 30 s de pub sur 2 vCPU ; le temps baisse presque
linéairement avec le nombre de cœurs.

> ⚠️ edge-tts (voix sans clé) est un service non officiel : pas de garantie ni de
> licence commerciale. Configurer ElevenLabs avant d'ouvrir la fonction aux clients payants.

---

# Moteur « Motion Pro » (vidéo face caméra + animations plein écran)

Le client dépose sa vidéo face caméra et choisit un template. CutForge la monte
seul, comme un monteur motion designer :

```
Transcription mot à mot ─► Coupes (silences, faux départs, répétitions, bégaiements)
   faster-whisper            autoedit_engine.build_edl (+ nettoyage IA si clé)
        │
        ▼
Base 9:16, zoom alterné 1.0/1.1 à chaque coupe (masque les jump cuts)
        │
Plan des animations ─► Page HTML en mode incrustation (fond transparent)
 IA (OpenRouter)          même moteur web/engine.js que la Pub explicative
 ou règles locales        │
        ▼                 ▼
Animations ProRes 4444 avec alpha, entrée/sortie « whip/zoom/slide » par-dessus le visage
        │
Composition ffmpeg + sous-titres karaoké (hors animations) + SFX calés + musique −22 dB ─► MP4
```

| Fichier | Rôle |
| --- | --- |
| `backend/app/explainer/facecam.py` | Orchestration `run_facecam()` : transcription, coupes, base, rendu des animations, sous-titres, mixage, export. |
| `backend/app/explainer/facecam_planner.py` | Choix des passages à illustrer. **Règles locales sans clé** : listes (« avocats, médecins… » → cartes icônes), argent perdu / impôt → pièces aspirées, solution nommée (« grâce à… », « à travers… ») → emblème 3D, comparaison (« différence entre vous et un salarié ») → écran partagé, durée prononcée (« trente minutes ») → minuteur, exclusivité → foule, appel à l'action → bouton cliqué. Avec `OPENROUTER_API_KEY` : plan IA validé (aucun chiffre non prononcé). |
| `backend/app/processing/pipeline_v2.py` | `_run_motion_pro()` : les modes `motion_pro_*` y sont délégués. |
| `backend/app/api/v1/modes.py` | Famille « Motion Pro », 5 modes = 5 templates. |

Règles de montage : visage gardé sur l'accroche (1re seconde), au moins 1,4 s de
visage entre deux animations (ou enchaînement bord à bord), jamais plus de ~11 s
d'animations sans revenir au visage, pas deux fois la même scène coup sur coup.

Options du job : `motion_template` (prestige, neon, editorial, minimal, solaire),
`motion_density` (`light` ≈ 30 %, `medium` ≈ 50 %, `heavy` ≈ 68 % de la durée),
`brand_color` (#RRGGBB), `dynamic_captions`, `music`.

Test en ligne de commande :

```bash
python -c "from app.explainer.facecam import run_facecam; print(run_facecam('video.mp4', 'sortie', template='neon', density='medium'))"
```


## IA gratuite avec FreeLLMAPI

[FreeLLMAPI](https://github.com/tashfeenahmed/freellmapi) (MIT) regroupe les niveaux **gratuits
officiels** d'une trentaine de fournisseurs (Google AI Studio, Groq, Mistral, Cerebras,
OpenRouter free, Cloudflare…) derrière une seule adresse compatible OpenAI, avec bascule
automatique quand un fournisseur atteint sa limite.

1. Sur le serveur : `curl -fsSL https://freellmapi.co/install.sh | bash` (port 3001).
2. Dans son tableau de bord, ajouter ses propres clés gratuites (au moins Google AI Studio
   et Groq), puis copier la clé unifiée `freellmapi-…`.
3. Dans `.env` de CutForge :
   ```
   LLM_BASE_URL=http://host.docker.internal:3001/v1
   LLM_API_KEY=freellmapi-…
   LLM_MODEL=auto:smart
   ```
   (sous Linux, ajouter `extra_hosts: ["host.docker.internal:host-gateway"]` au backend et au worker,
   ou mettre FreeLLMAPI dans le même réseau Docker et utiliser son nom de service).

Ordre d'essai à chaque appel : passerelle → OpenRouter (si clé) → règles locales. Une pub ne
tombe donc jamais en panne à cause de l'IA.

À savoir : les niveaux gratuits n'ont pas de garantie de service, les quotas se remettent à zéro
à minuit UTC, et certains fournisseurs gratuits (ex. Google AI Studio) peuvent utiliser les
requêtes pour améliorer leurs modèles — ne pas y envoyer de données sensibles. Respecter les
conditions de chaque fournisseur : une clé par compte, pas de multiplication de comptes.
