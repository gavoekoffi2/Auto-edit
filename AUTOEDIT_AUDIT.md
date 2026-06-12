# Audit technique — CutForge (ex-AutoEdit)

---

## ⭐ Itération v4 — juin 2026 (rebranding CutForge + production-ready)

> Suite de l'audit v3, sur demande produit : rebranding complet, landing
> premium animée, fixes download/upload, smart cut, sound design pro,
> transitions, économie d'API et précision des images.

### A. Rebranding « CutForge » + landing premium

- Marque centralisée (`frontend/src/brand.ts`), nouveau logo SVG (lame de
  coupe + play forgé), favicon, meta/OG, Navbar/Footer/Login/Signup/Pricing/
  Editor, emails et API backend renommés.
- **Landing page réécrite** : simulation de montage animée dans un téléphone
  (captions karaoké, popup mot-clé, B-roll avec flash photo, scène motion
  design avec dessin qui se trace + compteur + cercle marqueur + flèche,
  pastilles SFX — boucle de 12 s synchronisée), aurora + grille de points +
  parallaxe curseur, marquee, 3 étapes avec connecteur dessiné, vitrine des
  3 types de scènes motion design, features, stats produit, pricing, FAQ, CTA.
  Le tout en CSS pur (Landing : 173 KB → 31 KB de JS) avec
  `prefers-reduced-motion` respecté. Les faux témoignages (photos Unsplash +
  noms inventés) de l'ancienne landing ont été SUPPRIMÉS.

### B. Bugs corrigés

| # | Zone | Problème → correction |
| --- | --- | --- |
| 1 | Téléchargement | Le bouton « Download » récupérait la vidéo en blob XHR (RAM mobile + CORS Netlify→VPS + token 15 min expiré pendant les longs rendus → 401 silencieux). → Refresh de session avant, **téléchargement natif par lien direct** (streaming disque, pas de CORS), blob en dernier recours. |
| 2 | Téléchargement | Starlette épinglé ignore les en-têtes `Range` (pas de reprise, seek impossible). → `app/services/media.py::ranged_file_response` (206 Partial Content) sur `/jobs/{id}/download` et `/videos/{id}/stream` + `proxy_force_ranges` nginx. |
| 3 | Upload lent | nginx bufferisait TOUT le body sur disque avant de le rejouer vers FastAPI (barre à 100 % puis longue attente). → `proxy_request_buffering off` sur la route d'upload : streaming direct, une seule écriture. |
| 4 | Mots-clés | Contractions françaises (« c'est », « j'ai »…) absentes des stopwords → devenaient mots-clés/headlines. → Liste complétée. |

### C. Moteur v4.2

1. **Smart cut** (`build_edl`) : suppression des faux départs (la dernière
   prise gagne), des phrases répétées, des marqueurs « je reprends / on
   recommence / coupe ça » et des bégaiements — coupes toujours sur frontière
   de mot (MICRO_PAD), la parole n'est jamais hachée. Flag
   `ENGINE_REMOVE_RETAKES`.
2. **Sound design pro** : 27 sons (8 nouveaux dont rafale photo, autofocus,
   crayon qui dessine, tape-stop, hit cinématique), pools distincts par type
   de visuel (B-roll = sons photo/caméra), **variation pitch/gain par
   occurrence** (jamais deux fois le même son à l'identique), son de crayon
   pendant les dessins procéduraux, blips sur les popups (avant : muets).
3. **Belles transitions** : sorties animées des B-rolls appariées à leur
   entrée (slide-out, punch-out, drop, glitch-out…) ; entrées/sorties variées
   des scènes motion (sweep lumineux / iris circulaire / slide avec rebond —
   scale-fade / slide-down / iris-close), cyclées pour ne jamais répéter.
4. **Économie d'API** : cadence B-roll réduite (1/6 s shorts, 1/9-12 s long),
   cap `MAX_BROLL_IMAGES=8`, scènes motion plus fréquentes (gratuites), cap
   `MOTION_AI_ILLUSTRATIONS_MAX=3` (les scènes les plus importantes seulement,
   par priorité ; les autres en dessin procédural).
5. **Précision des images** : raffineur de prompts LLM (modèle texte bon
   marché, lot unique, fallback heuristique) qui réécrit chaque extrait parlé
   en scène visuelle littérale ; démographie **africaine uniquement par
   défaut** (formulation renforcée), réglable dans l'éditeur avant le
   traitement.

### D. Vérifications

- **72 tests pytest** (16 nouveaux : smart cut, design SFX) ; build frontend
  `tsc` + Vite OK ; rendu de bout en bout validé sur vidéo synthétique
  (bégaiement coupé mot-safe, 3 scènes motion dont une « étapes », 31 SFX
  variés, frames inspectées).

---

## ⭐ Audit v3 — juin 2026 (motion design illustré + corrections)

> Branche `claude/gifted-pascal-evwopb`. Revue complète du moteur Auto Edit,
> du pipeline v2, de l'API et du frontend, avec pour mission principale la
> partie **motion design** non aboutie précédemment.

### A. Le problème constaté

Le « motion design » livré jusqu'ici était **uniquement textuel** : cartes
stat/progression/listes (`overlays.py`) et popups de mots-clés dorés
(`keyword_popup.py`). Aucune **illustration animée** ne dessinait ce que la
personne explique. Pire : l'ancien pipeline modulaire affichait des cartes
« explicatives » au contenu **codé en dur** (« ENRÔLER — Dépôts + PDV »,
« LOCALISER — Google Maps »…) à des timestamps fixes sur **n'importe quelle
vidéo** — du contenu inventé sans lien avec le discours.

### B. Nouveau système : motion design illustré (`motion_design.py`, moteur v4.1)

1. **Sélection des beats** (`content.derive_motion_scenes`) : les passages
   importants sont détectés dynamiquement dans le transcript (énumérations,
   chiffres/%, phrases d'emphase « important / secret / méthode / étape… »,
   densité de mots-clés), espacés d'au moins 12 s, ~1 scène / 18 s (shorts)
   ou 30 s (vidéos longues), 6 max.
2. **Trois types de scènes plein écran** (4,6–5,4 s, la voix continue) :
   `idea` (illustration + gros mot-clé entouré au marqueur + flèches dessinées
   à la main), `steps` (pastilles d'étapes numérotées en cascade), `number`
   (compteur animé doré).
3. **Illustration double source** : image IA flat-design (OpenRouter, préfixe
   de style dédié, « no text ») **ou repli procédural** — bibliothèque de
   14 icônes line-art (argent, croissance, téléphone, clients, panier, idée,
   cible, engrenage, livre, mégaphone, bouclier, horloge, fusée, carte) qui se
   **tracent à l'écran trait par trait** façon whiteboard. La fonctionnalité
   marche donc **avec ou sans clé API**.
4. **Transitions + sound design** : light sweep + flash à l'entrée ; chaque
   scène exporte ses `events` (entrée / éléments / sortie) convertis par
   `plan_overlays` en SFX — `riser` 0,45 s avant, `whoosh`/`transition` à la
   prise d'écran, `pop`/`click`/`ding`/`sparkle` sur chaque apparition
   d'élément, `swoosh_down` à la sortie.
5. **Anti-collision** : les B-rolls évitent les spans motion
   (`avoid_spans`), un B-roll qui chevauche une scène est droppé
   (priorité motion), et les popups de mots-clés ne s'affichent jamais
   par-dessus une scène.
6. **Produit** : option `motion_design` (API + presets de modes + toggle
   éditeur « Motion design illustré »), flag `ENABLE_MOTION_DESIGN`.

### C. Bugs corrigés

| # | Fichier | Sévérité | Problème → correction |
| --- | --- | --- | --- |
| 1 | `processing/pipeline_v2.py` | Haute | `OPENROUTER_API_KEY` lu depuis `.env` par pydantic n'était jamais propagé à `os.environ`, que seul lit le moteur → B-roll/illustrations silencieusement désactivés. Propagation explicite ajoutée. |
| 2 | `processing/pipeline_v2.py` | Haute | Cartes explicatives legacy au contenu codé en dur affichées sur toute vidéo → neutralisées (le motion design réel vit dans le moteur). |
| 3 | `autoedit_engine/run_pipeline.sh` | Haute | Script invoquait `python -m engine.*` — package inexistant (`app.autoedit_engine`) → script inutilisable. Chemins corrigés + étape motion ajoutée. |
| 4 | `autoedit_engine/motion_design.py` | Haute | (introduit puis corrigé pendant le dev) `ImageDraw` **remplace** les pixels alpha au lieu de fusionner + vignette collée en `paste` → la vidéo transparaissait à travers les scènes. Encre dessinée sur calque composité + vignette en `alpha_composite`. |
| 5 | `autoedit_engine/plan_overlays.py` | Moyenne | Les B-rolls décalés par l'anti-chevauchement pouvaient **déborder après la fin de la vidéo** → clamp + drop. |
| 6 | `autoedit_engine/composite.py` | Moyenne | Un `.mov` d'overlay manquant (rendu partiel) faisait échouer tout le composite ffmpeg → overlays manquants ignorés avec warning. |
| 7 | `autoedit_engine/config.py` | Moyenne | Stopwords FR incomplets (`vos`, `nos`, formes de « aller/vouloir/pouvoir ») → « VOS » pouvait devenir LE mot-clé headline/popup. Liste complétée. |
| 8 | `autoedit_engine/keyword_popup.py` | Basse | Nom de fichier construit avec le mot-clé brut (apostrophes/accents) → sanitisation. |
| 9 | `autoedit_engine/video_dynamics.py` | Basse | FPS codé en dur `(on/30)` dans les expressions de pan → `config.FPS`. |

### D. Vérifications

- **56 tests pytest** passent (42 existants + 14 nouveaux : dérivation de
  scènes, mapping d'icônes, draw-on, événements, priorité motion vs B-roll,
  design SFX, rendus ProRes réels).
- **Build frontend** : `tsc --noEmit` + `vite build` OK.
- **Rendu de bout en bout** validé sur vidéo synthétique 40 s : 2 scènes
  motion (number + idea), 18 cues SFX, composite 12 overlays, mix −14 LUFS,
  sous-titres karaoké, MP4 final 12 MB — frames inspectées visuellement.

---
>
> Objectif : transformer AutoEdit en plateforme IA de montage vidéo automatique pour le
> marché africain francophone (TikTok / Reels / Shorts), en intégrant un nouveau pipeline
> autour de `video-use`, `HyperFrames`, `Remotion`, et la génération B-roll IA via
> OpenRouter.

---

## 1. État actuel du projet

### 1.1 Stack confirmée

| Couche | Technologie | Statut |
| --- | --- | --- |
| API | FastAPI 0.109 + Pydantic v2 | OK |
| ORM | SQLAlchemy 2 async + asyncpg | OK |
| Migrations | Alembic 1.13 | OK (1 bug enum) |
| Queue | Celery 5.3 + Redis 7 | OK |
| DB | PostgreSQL 15 | OK |
| Frontend | React 18 + Vite 5 + TS + Tailwind + Zustand | OK |
| Vidéo | Whisper, auto-editor, PySceneDetect, MoviePy | OK base |
| Paiement | FedaPay (XOF / USD) | OK base |
| Infra | Docker Compose + Nginx | OK |

### 1.2 Cartographie fonctionnelle

- **Auth complète** : signup, login, refresh, me, change password, reset (token généré
  mais email **non envoyé**).
- **Upload vidéo** : streaming par chunks, validation MIME par extension, quotas par plan,
  ffprobe pour la durée.
- **Jobs Celery** : `process_video` avec retry + progress callback + cancellation via revoke.
- **Pipeline vidéo v1** : 7 étapes (transcribe / silence / scenes / effects / subtitles
  / export / cleanup) avec presets `tiktok`, `youtube`, `podcast`.
- **Paiements FedaPay** : checkout, webhook signé, history, plans.
- **Frontend SPA** : routes lazy, error boundary, toast, dashboard paginé, éditeur
  + JobProgress polling 2s.

---

## 2. Ce qui fonctionne

- Backend démarre (FastAPI + Celery via docker-compose).
- Healthcheck `/api/health` qui ping Postgres + Redis.
- Pipeline vidéo v1 traite réellement une vidéo avec Whisper + auto-editor + MoviePy.
- Frontend build via Vite, navigation et upload fonctionnels.
- Authentification JWT + refresh + rate limit Redis (fail-open).
- Quotas plan free vs pro appliqués à l’upload.
- Génération SRT, JSON transcript, CSV de scènes.

---

## 3. Ce qui est incomplet ou cassé

### 3.1 Bugs corrigés dans ce PR (Phase 1)

| # | Fichier | Sévérité | Description | Correction |
| --- | --- | --- | --- | --- |
| 1 | `backend/alembic/versions/001_initial.py` | Haute | Enum `job_status` ne contient pas `cancelled` alors que le modèle ORM, l’API `cancel` et `config.py` l’utilisent → migration plantera ou job inconsistant. | Migration `002_add_cancelled_status` ajoute la valeur. |
| 2 | `backend/app/processing/pipeline.py` | Haute | `intermediate_files.append(... if ... else None)` insère `None` dans la liste → `cleanup_directory` lève potentiellement `TypeError`. | Append conditionnel propre + filtrage des `None`. |
| 3 | `backend/app/api/v1/videos.py` | Moyenne | `media_type="video/mp4"` codé en dur → erreur quand le fichier est `.mov`, `.webm`, etc. | Détection via `mimetypes.guess_type` + fallback. |
| 4 | `backend/app/workers/tasks.py` | Moyenne | Dans le `except`, on rouvre la session mais on n’utilise pas le `Job` rouvert proprement → risque NPE silencieux. | Garde + log. |
| 5 | `frontend/src/pages/Editor.tsx` | Moyenne | Cast `as { scenes: ... }` sans garde → crash si `scenes` est un autre shape. | Type guard runtime + accès safe. |
| 6 | `docker-compose.yml` | Haute | `SECRET_KEY` regénéré à chaque restart (env vide → fallback `secrets.token_urlsafe`) → toutes les sessions JWT invalidées. | `.env` requis + warning explicite documenté. |

### 3.2 Manques fonctionnels prioritaires

- **Reset password par email** : token généré mais jamais envoyé (`auth.py:160`).
- **Aucun test automatisé** (ni Pytest ni Vitest).
- **Pas de WebSocket** pour le progress (polling 2s suffisant pour MVP mais à prévoir).
- **Pas de thumbnails vidéo**.
- **Pas d’admin panel**.
- **Stockage local uniquement** : pas de S3 / R2 / GCS.
- **Pas de pré-téléchargement des modèles Whisper** dans l’image Docker.

### 3.3 Manques structurants pour la mission

- Aucun moteur de **B-roll IA** (pas d’appel image, pas d’asset planning).
- Aucun moteur de **templates animés** (HyperFrames / Remotion absents).
- Aucune **EDL (Edit Decision List)** structurée, le pipeline opère séquentiellement
  sans plan de montage explicite.
- Aucun découpage **mot-par-mot** ni détection de filler words ("euh", "donc",
  "voilà", "en fait"…).
- Aucun **self-evaluation** des cuts (cf. `video-use`).
- Aucun **renderer abstrait** : MoviePy est cablé en dur dans `effects.py`.

---

## 4. Risques techniques

1. **MoviePy 1.0.3** est lent et fragile (ImageMagick obligatoire pour le text). Pour la
   v2 on passe sur **FFmpeg direct** + Remotion/HyperFrames pour les overlays riches.
2. **Whisper local** sur CPU → coûteux et lent ; prévoir option `faster-whisper` ou API
   distante (OpenAI / Replicate) configurable via `TRANSCRIPTION_PROVIDER`.
3. **auto-editor CLI** : dépendance d’un binaire shell → bien encadrer le timeout
   (déjà 10 min) et capter stderr.
4. **OpenRouter image** : la disponibilité des modèles image varie ; il faut un provider
   abstrait + fallback (Replicate, Stability, image stock) pour ne pas bloquer le pipeline.
5. **Worker concurrency=1** : pas de parallélisme. À documenter pour la prod.
6. **SECRET_KEY auto-généré** : déjà loggé en warning, mais doit être bloquant en prod
   (à ajouter dans `entrypoint.sh`).
7. **Stockage local** : crash worker = perte d’uploads non répliqués.

---

## 5. Architecture cible (haut niveau)

```
┌─────────────────────────────────────────────────────────────────────┐
│                          FRONTEND (React)                            │
│   Mode + style africain + toggles (B-roll, captions, music, SFX…)   │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ REST
┌───────────────────────────▼─────────────────────────────────────────┐
│                          FastAPI                                     │
│   /videos /jobs (v1) + /jobs?version=2 (pipeline_v2)                 │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ Celery
┌───────────────────────────▼─────────────────────────────────────────┐
│                       Pipeline V2                                    │
│                                                                      │
│  1. TranscriptionService     (Whisper / faster-whisper / API)        │
│  2. SilenceDetector          (auto-editor / VAD)                     │
│  3. EditDecisionService      (filler words, cuts, EDL JSON)          │
│  4. BrollPlanner             (segmente le transcript, choisit cues)  │
│  5. ImageGenerationService   (OpenRouter, prompts africains)         │
│  6. BrollAnimationService    (Ken Burns FFmpeg, clips B-roll)        │
│  7. TemplateRenderer         (ffmpeg | hyperframes | remotion)       │
│  8. FFmpegRenderer           (concat + captions + music + SFX)       │
│  9. Export                   (MP4 9:16 / 16:9, output_path)          │
└─────────────────────────────────────────────────────────────────────┘
```

Détails dans `docs/VIDEO_PIPELINE_ARCHITECTURE.md`.

---

## 6. Plan d’intégration des dépendances cibles

### 6.1 video-use (browser-use/video-use)

- Inspiration directe pour `edit_decision_service.py` : détection filler words,
  word-level cuts, self-evaluation, génération d’EDL puis rendu FFmpeg.
- On commence par réimplémenter le service en Python natif (pas d’import direct car
  le repo est jeune et sa surface API n’est pas stable). On garde les concepts.
- Documenté comme moteur **`renderer="video_use"`** dans `template_renderer.py` quand
  un binding stable sera disponible.

### 6.2 HyperFrames (heygen-com/hyperframes)

- Sert au rendu HTML/CSS/JS → MP4 pour overlays animés (titres, cards, CTA, lower
  thirds, transitions).
- Intégration via une **interface `TemplateRenderer`** (`renderer="hyperframes"`).
- Pour la phase 1 on documente le contrat ; un wrapper Node CLI sera ajouté en phase 2
  (image Docker `node:20-alpine` séparée pour ne pas alourdir le worker Python).

### 6.3 Remotion

- Alternative React/TS aux templates HyperFrames.
- On expose `renderer="remotion"` dans `TemplateRenderer`.
- Une compo Remotion minimale (`templates/remotion/IntroCard.tsx`) sera scaffold en
  phase 2 avec script `npx remotion render`.

### 6.4 OpenRouter (B-roll IA africain)

- Provider abstrait `ImageProvider` (interface) → implémentation `OpenRouterImageProvider`.
- Variables d’env :
  - `IMAGE_GENERATION_PROVIDER=openrouter`
  - `IMAGE_GENERATION_MODEL=` (configurable, ex: `google/gemini-2.5-flash-image-preview`)
  - `OPENROUTER_API_KEY=` (jamais committée)
  - `BROLL_STYLE=african_business_premium`
- Prompts générés par `broll_planner.py` à partir du transcript, orientés Afrique
  francophone, business, réaliste, moderne.
- Fallback si l’API échoue : image placeholder + texte stylisé (HyperFrames/Remotion).

---

## 7. Plan B-roll IA Afrique (résumé)

1. Découpe le transcript en **segments narratifs** (par phrase / changement de sujet).
2. Pour chaque segment qui dépasse un seuil (ex : 3,5 s), planifie un **cue B-roll**.
3. `BrollPlanner` génère un **prompt image** orienté Afrique :
   - personnes africaines modernes, entrepreneurs, bureaux propres ;
   - villes africaines (Lomé, Cotonou, Abidjan, Dakar, Douala, Kinshasa…) ;
   - contexte business : e-commerce, restauration, immobilier, formation, beauté,
     transport, recrutement…
   - style premium, photographie réaliste, lumière naturelle.
4. `ImageGenerationService.generate(prompt, aspect_ratio, style)` → URL/bytes image.
5. `BrollAnimationService` transforme l’image en clip via FFmpeg (Ken Burns / pan /
   zoom / fade) à la durée du segment.
6. Le clip est inséré dans l’EDL comme overlay ou cut B-roll.
7. Si l’image échoue : placeholder texte + transition courte ; le pipeline ne s’arrête
   pas.

---

## 8. Étapes MVP prioritaires (post-audit)

| Ordre | Tâche | Sortie |
| --- | --- | --- |
| 1 | Audit + fix bugs critiques | ce document, migration 002, patches |
| 2 | `.env.example` enrichi + flags | toutes les vars produit/IA |
| 3 | Architecture cible documentée | `docs/VIDEO_PIPELINE_ARCHITECTURE.md` |
| 4 | Squelette modulaire `processing/` v2 | services + interfaces |
| 5 | `ImageGenerationService` OpenRouter | génération B-roll IA Afrique |
| 6 | `BrollAnimationService` FFmpeg Ken Burns | clips B-roll prêts à monter |
| 7 | `pipeline_v2` opt-in (feature flag) | sans casser `pipeline.py` v1 |
| 8 | Editor frontend : styles africains + toggles | UI cohérente |
| 9 | Tests pytest + script de smoke | confiance avant déploiement |
| 10 | Templates HyperFrames / Remotion | Phase 2 (post-MVP) |

---

## 9. Critères de réussite (rappel mission)

- [x] Projet audité et bugs critiques identifiés
- [x] Bugs critiques corrigés sans casser les endpoints existants
- [x] Architecture documentée (`docs/VIDEO_PIPELINE_ARCHITECTURE.md`)
- [x] Pipeline v2 préparé (modules + interfaces)
- [x] B-roll IA africain conçu comme module pluggable
- [x] OpenRouter prévu (provider abstrait + variable d’env)
- [x] HyperFrames / Remotion / video-use positionnés dans l’architecture
- [x] Code modulaire, lisible, sans secrets en clair
- [x] V1 pipeline et endpoints existants préservés

---

## 10. Variables d’environnement nouvelles

Voir `.env.example`. Récap :

```
# IA B-roll
OPENROUTER_API_KEY=
IMAGE_GENERATION_PROVIDER=openrouter
IMAGE_GENERATION_MODEL=google/gemini-2.5-flash-image-preview
BROLL_STYLE=african_business_premium
BROLL_DEFAULT_ASPECT_RATIO=9:16

# Pipeline v2 / renderers
VIDEO_RENDERER=ffmpeg
ENABLE_AI_BROLL=true
ENABLE_DYNAMIC_CAPTIONS=true
ENABLE_SFX=true
ENABLE_MUSIC=true
PIPELINE_VERSION=v1   # ou v2 pour activer le nouveau pipeline
```
