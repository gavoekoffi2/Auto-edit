# Moteur « Shorts TikTok face caméra »

Mode `shorts_facecam` — page `/shorts`. Les rushes bruts (1 à 10 fichiers, filmés dans n'importe
quel ordre, avec des reprises) deviennent une vidéo verticale 1080x1920 prête à poster.
Les autres moteurs (Studio, Motion Pro, Auto Edit, legacy `youtube`) ne sont pas modifiés.

## Pipeline (`backend/app/explainer/shorts/`)

| Étape | Fichier | Qui décide |
|---|---|---|
| Transcription mot à mot de chaque rush, suivi du visage (Haar, 1 img/s) | `rushes.py` | Whisper (`SHORTS_WHISPER_MODEL`, sinon `WHISPER_MODEL`) |
| Découpage en passages (phrases), ids courts `A12`, `B3`… | `rushes.py` | règles |
| Reprises (même phrase dite plusieurs fois, dans un rush ou entre rushes), faux départs, apartés | `takes.py` | **Jev**, sinon règles (dernière prise complète) |
| Ordre final du récit entre les rushes, chapitres, corrections de transcription, cartes | `director.py` | **LLM** (FreeLLMAPI puis OpenRouter), sinon règles |
| Thème visuel, cadrage, vérification de chaque carte (fidèle ? verset pertinent ?) | `director.py` | **Jev**, sinon règles |
| Versets bibliques | `bible.py` | texte exact Louis Segond 1910 embarqué (`data/lsg1910.txt.gz`, domaine public, eBible.org) — jamais écrit par l'IA |
| Plans, silences coupés, zoom alterné aux coupes visibles, mots dans le temps final, repères des cartes | `timeline.py` | règles |
| Base 9:16 (fenêtre 4:5 sur fond flouté, ou plein écran centré visage) | `render.py` | ffmpeg |
| Habillage (bandeau chapitre, sous-titres mot à mot, cartes, scènes plein écran) rendu par tranches de 20 s puis incrusté | `render.py` + `web/shorts.html` | Chromium |
| Voix nettoyée, SFX calés sur les animations, musique, -14 LUFS | `engine.py` | `audio.mix` |

## Partage des rôles entre modèles (économie de jetons)

- **Jev** (`typesafe/jev-1.13`, OpenRouter *Decisions API* `POST /api/alpha/decisions`) ne génère pas de
  texte : il renvoie des probabilités calibrées pour des questions typées (`noul`, `choice`, `score`),
  ~0,042 $ / million de jetons d'entrée, sortie gratuite, ~0,2 s. Il prend tous les **arbitrages** :
  meilleure prise, reprise ou répétition voulue, faux départ, thème, cadrage, vérification des cartes
  proposées par le LLM. Les questions sur un même contexte partent en un seul appel (lots de 40).
- **LLM** : seulement ce qui demande d'écrire (ordre du récit, titres, contenu des cartes, corrections).
  Il reçoit un transcript déjà dédoublonné par Jev, sans timecodes (`B12: texte`) : un seul appel par vidéo.
- **Règles** : tout fonctionne sans IA (ordre des rushes, versets cités à voix haute, appel à s'abonner).

## Variables

`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` (passerelle gratuite), `OPENROUTER_API_KEY` (repli LLM + Jev),
`JEV_ENABLED` (0 pour couper), `JEV_MODEL`, `TYPESAFE_API_KEY` (accès Jev direct en secours),
`SHORTS_WHISPER_MODEL`, `SHORTS_KEEP_WORK=1` (garde les intermédiaires pour déboguer).

## API

`POST /jobs` avec `mode: "shorts_facecam"`, `video_id` = premier rush, `extra_video_ids` = les autres
(9 max, vérifiés : appartiennent à l'utilisateur, encore sur disque, durée totale ≤ limite du plan),
`options.shorts_theme` (`auto|or_noir|braise|ocean|menthe|royal`), `options.shorts_layout` (`auto|cadre|plein`),
`options.vocabulary`, `dynamic_captions`, `music`.

## Lancer à la main

```bash
cd backend
python -m app.explainer.shorts.engine /tmp/sortie rush1.mp4 rush2.mp4 rush3.mp4
```

Tests : `python -m pytest tests/test_shorts.py -q`.
