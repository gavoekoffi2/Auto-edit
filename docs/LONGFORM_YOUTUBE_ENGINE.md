# Moteur « YouTube long » (vidéos longues 16:9)

Montage automatique des vidéos YouTube longues (5 à 60 min) pour les
créateurs : face caméra, formation, analyse, interview. Porté de la méthode
de montage `youtube-clean` et adapté à CutForge et au public francophone.

Code : `backend/app/processing/longform/` · Modes : `youtube_long` (style qui
change d'une vidéo à l'autre), `youtube_long_sobre` (documentaire),
`youtube_long_energie` (créateur) · Famille frontend : « Vidéos longues YouTube ».

## Pipeline

| # | Module | Rôle |
|---|--------|------|
| 1 | `pipeline.transcribe` | ElevenLabs Scribe (mots horodatés), repli Whisper |
| 1b | `smart_cleanup` (existant) | relecture IA optionnelle des phrases redites/reformulées |
| 2 | `takes.py` | coupe de la voix : **la dernière prise gagne** (faux départs, phrases redites plus loin, phrases abandonnées), bégaiements, tics (« euh », « donc »…), marqueurs « je reprends », silences ; points de coupe dans les creux d'énergie RMS ; aucun micro-fragment isolé |
| 3 | `chapters.py` | chapitres YouTube (changement de sujet lexical + marqueurs de structure) ; titres IA si `OPENROUTER_API_KEY`, sinon mots-clés ; règles YouTube vérifiées |
| 4 | `graphics.py` | un seul ASS 1920×1080 : sous-titres karaoké FR, popups chiffres/mots forts (texte = ce qui est dit, jamais inventé), cartes chapitre plein écran animées ; chaque visuel émet sa cue SFX |
| 5 | `audio.py` | voix à −18 LUFS + passe-haut + compression, piste SFX par blocs (mémoire bornée), musique en boucle avec ducking sidechain, normalisation 2 passes **−14 LUFS / −1 dBTP** |
| 6 | `render.py` | **assemblage image/son 1:1** : un seul encodeur sur une horloge 30 i/s, un buffer audio sans trou, zoom alterné + étalonnage au décodage, habillage incrusté par le même encodeur |
| 7 | `pipeline.py` | mux, vérifications signal (images attendues = écrites, écart image/son ≤ 1 image, loudness), `chapitres.txt`, `rapport_montage.json` |

### Pourquoi pas « un fichier par coupe + concat »

Encoder chaque coupe à part arrondit chaque morceau à une image entière et
laisse des trous de timestamps : sur une vidéo longue, le visage finit une
demi-seconde en retard sur la voix. Ici l'image de sortie *i* montre toujours
l'image source `start_k + (i/30 − P_k/48000)` : les arrondis ne s'accumulent
jamais. Le test `test_end_to_end_cut_and_sync` le prouve (flash image + bip
son sur chaque mot, alignés à ≤ 1 image du début à la fin).

## Styles

`studio_clean` · `energie_createur` · `documentaire` · `tech_minimal` — typo,
couleurs, cartes, popups, force des zooms et palette SFX différentes. `auto`
choisit par une graine propre à la vidéo : deux vidéos successives n'ont pas
le même look.

## Options du job

`longform_style`, `dynamic_captions`, `keyword_popups`, `chapter_cards`,
`zoom_cuts`, `sfx`, `music`, `llm_titles`, `cleanup_level`.

## Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `LONGFORM_MUSIC_DIR` | — | dossier de musiques libres de droits (un titre choisi par vidéo) ; sans musique, pas de lit musical |
| `LONGFORM_X264_PRESET` | `veryfast` | compromis vitesse/poids du rendu |
| `LONGFORM_X264_CRF` | `19` | qualité du rendu |
| `LONGFORM_DECODE_PREFETCH` | `2` | décodeurs lancés en avance (cache le coût des recherches) |
| `LONGFORM_LLM_MODEL` | `PROMPT_REFINER_MODEL` | modèle OpenRouter des titres de chapitres |

## Performance mesurée

Vidéo 1080p de 6 min (76 plans) sur 2 cœurs : ~50 s de calcul par minute
montée (image ≈ 45 i/s, l'encodeur x264 est le goulot). L'étalonnage n'utilise
que le filtre `eq` : `colorbalance`/`curves` rendaient le décodage ~12× plus lent.

## Ligne de commande

```bash
cd backend
python -m app.processing.longform ma_video.mp4 --out rendu/ --style auto
```

## Limites connues (v1)

- Une seule source (caméra avec son). Le mode « caméra + enregistrement
  d'écran » de youtube-clean (voix du bon micro, image de la caméra,
  synchronisées par corrélation) n'est pas encore porté.
- Pas de B-roll ni d'interface recréée : l'habillage est typographique.
- Les vérifications sont signal (images, durées, loudness) — pas d'écoute.
