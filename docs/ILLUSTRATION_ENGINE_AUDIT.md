# Audit — Moteur d'illustration CutForge

> Phase 1–3 de la refonte. Ce document fige **l'état de l'ancien moteur**, les
> **contrats de données** que le nouveau moteur doit respecter, et l'**audit des
> licences** des dépôts de référence. Il sert de cahier des charges à
> `backend/app/illustration_engine/`.

---

## 1. Périmètre audité

| Zone | Chemin | Rôle |
|---|---|---|
| Moteur de montage | `backend/app/autoedit_engine/` | 28 modules, ~10 350 LOC — pipeline complet cut → grade → overlays → SFX → subs |
| **Ancien moteur d'animation** | `backend/app/autoedit_engine/motion_design.py` | **2 134 LOC** — compositeur de frames PIL monolithique |
| Décisions de contenu | `backend/app/autoedit_engine/content.py` | `derive_motion_scenes()` — heuristiques de sélection des beats |
| Orchestration CLI | `backend/app/autoedit_engine/pipeline.py` | 13 étapes, appelle `motion_design.render_all()` à l'étape 4 |
| Orchestration service | `backend/app/processing/pipeline_v2.py` | Pipeline de production (Celery), catalogue de modes d'édition |
| Planification overlays/SFX | `backend/app/autoedit_engine/plan_overlays.py` | Consomme `_motion_clips.json`, produit `edl.overlays` + `sfx_cues.json` |
| Compositing | `backend/app/autoedit_engine/composite.py` | Multi-passe ffmpeg, 12 overlays / batch (OOM-safe) |
| Moteurs collage | `backend/app/processing/collage/` | 12 modules — B-roll collage produit (hors périmètre de cette refonte) |

---

## 2. L'ancien moteur : `motion_design.py`

### 2.1 Qui l'appelle

Un **seul** site d'appel réel, `autoedit_engine/pipeline.py` étape 4 :

```python
motion_scenes = content.derive_motion_scenes(vu_data, demographic=broll_demographic)
if have_key and visual_mode != "credit_saver" and not disable_paid_images:
    motion_scenes = genimg.generate_illustrations(motion_scenes, p("motion"), ...)
rendered_scenes = motion_design.render_all(
    motion_scenes, p("motion_clips"), preset=motion_preset, seed_text=seed_text)
```

En amont, deux orchestrateurs activent/désactivent l'étape via un booléen
d'options :

* `processing/pipeline_v2.py` — `options["motion_design"]` (défini par le
  catalogue de modes d'édition, lignes 45–226) ;
* `processing/clips_pipeline.py:247` — même drapeau pour les clips courts ;
* `schemas/job.py:40` — `motion_design: Optional[bool]` exposé à l'API.

**Conséquence :** le point d'insertion du nouveau moteur est unique et net.
Remplacer l'étape 4 suffit à changer de moteur sans toucher aux étapes 5→13.

### 2.2 Ce qu'il reçoit

`derive_motion_scenes()` produit une liste de dicts. Schéma effectif :

```python
{
  "id": "md_001",              # identifiant stable
  "kind": "idea|steps|number", # SEULEMENT 3 archétypes
  "priority": 0.87,            # score heuristique du beat
  "source_start": 32.4,        # temps SOURCE (avant montage)
  "source_end": 37.8,
  "duration": 5.4,             # borné [3.2, 6.0] s
  "headline": "TROIS PILIERS", # ≤ 4 mots
  "kicker": "À RETENIR",
  "steps": ["produit", "trafic", "livraison"],
  "value": 87.0, "raw": "87%", # pour kind == "number"
  "concepts": ["ecommerce", "produit"],
  "excerpt": "…",              # extrait parlé, ≤ 190 car.
  "spoken_line": "…",          # ≤ 112 car., affiché à l'écran
  "icon": "cart",              # 1 des ~30 icônes line-art
  "prompt": "…",               # prompt d'illustration IA
}
```

### 2.3 Ce qu'il produit

`render_all()` renvoie la liste enrichie, sérialisée dans
`motion_clips/_motion_clips.json` :

```python
{
  **scene,
  "mov": "motion_clips/md_001.mov",  # ProRes 4444 (yuva444p10le), alpha
  "duration": 5.4,
  "illustrated": True,                # une image IA payante a été utilisée
  "silhouette": "presenter"|None,
  "events": {                         # timings RELATIFS, pour le SFX planner
     "entrance": 0.0,
     "elements": [0.35, 0.85, 1.35],
     "exit": 5.0,
     "draw": 0.30,                    # présent seulement si dessin procédural
  },
}
```

### 2.4 Comment les clips sont intégrés

`plan_overlays.plan()` est le consommateur :

1. `_place_motion()` mappe `source_start` → temps de sortie via `timeline.s2o()`
   (la source a été recoupée par `build_edl`), clampe sur la durée finale et
   émet `{"kind": "motion", "start", "end", "mov", …}` ;
2. `motion_spans` sert de **zone d'exclusion** : les cartons graphiques
   (`_place_graphics`), les B-rolls et les collages (`_place_broll`, marge de
   respiration) et les popups de mots-clés évitent ces intervalles ;
3. `_motion_cues()` convertit `events` en cues SFX (riser −0,45 s, whoosh à
   l'entrée, pop/ding par élément, `pen_scribble` si `draw`, swoosh à la sortie) ;
4. Z-order final : `graphics + brolls + collages + motions` — **le motion est
   toujours au-dessus** ;
5. `composite.py` incruste les `.mov` par lots de 12 en ffmpeg multi-passe.

### 2.5 Interfaces qui en dépendent

| Dépendance | Nature | Impact d'un remplacement |
|---|---|---|
| `plan_overlays._place_motion` / `_motion_cues` | lit `mov`, `source_start`, `duration`, `events` | **Contrat à préserver** |
| `content.motion_scene_spans()` | exclusion B-roll | à réémettre |
| `genimg.generate_illustrations()` | ajoute `scene["image"]` | optionnel, à conserver |
| `schemas/job.py` `motion_design` | drapeau API/frontend | conservé + nouveaux champs |
| `tests/test_motion_design.py`, `test_motion_3d_styles.py`, `test_plan_overlays_motion.py`, `test_visual_coherence.py`, `test_visual_variety.py` | tests de l'ancien moteur | doivent continuer à passer → **l'ancien moteur reste importable (LEGACY)** |

### 2.6 Limites identifiées (le « pourquoi » de la refonte)

| # | Limite | Conséquence produit |
|---|---|---|
| L1 | **3 archétypes seulement** (`idea`, `steps`, `number`) | Aucune comparaison, causalité, processus, définition, architecture. Le visuel ne peut pas *expliquer*. |
| L2 | **Analyse purement lexicale** — `_beat_score()` compte des mots d'emphase et la densité de mots-clés | Sélectionne des beats « qui sonnent important », pas des beats *illustrables*. Pas de détection de structure du discours. |
| L3 | **Pas de score de valeur visuelle** — cadence fixe (`MOTION_EVERY_SHORT=11 s`) | Animation posée au métronome, pas là où elle apporte quelque chose. Exactement le défaut listé dans la mission. |
| L4 | **Monolithe de 2 134 LOC** : détection, layout, dessin, easing, transitions, encodage dans un seul module ; 60+ fonctions `_draw_*` privées | Ajouter un type de scène = éditer le monolithe. Intestable unitairement. |
| L5 | **Un seul back-end de rendu** (PIL frame-par-frame) | Pas de whiteboard réel, pas de SVG, pas de rendu stroke-by-stroke. |
| L6 | **Pas de couche provider** — l'intelligence est du `if/elif` sur des regex FR | Impossible de brancher un LLM ; impossible d'améliorer sans réécrire. |
| L7 | **Vertical 1080×1920 câblé** (`config.WIDTH/HEIGHT`) | Cible YouTube 16:9 impossible. |
| L8 | **Style couplé au hasard** — `select_palette(seed)` tire la palette d'un hash | Le style n'est pas pilotable par l'utilisateur. |
| L9 | **Éléments décoratifs** — `_confetti_layer`, `_sparkles`, `_rays_layer`, `_orbits_layer` | Décore au lieu d'expliquer. |

---

## 3. Contrats à préserver (non négociables)

Le nouveau moteur est un **remplacement drop-in** de l'étape 4. Il doit :

1. **Émettre le même schéma de sortie** que `motion_design.render_all()`
   (§ 2.3) — `mov` + `source_start` + `duration` + `events` — pour que
   `plan_overlays`, `composite` et `mix_sfx` fonctionnent sans modification ;
2. **Écrire du ProRes 4444 avec alpha** via `render_utils.ProResPipe` ;
3. **Exposer des spans** pour l'exclusion B-roll/popup ;
4. **Ne jamais faire échouer le job** — une scène qui plante est ignorée, le
   montage continue (comportement actuel de `render_all`) ;
5. **Fonctionner sans clé API** — `OPENROUTER_API_KEY` absent ⇒ rendu procédural.

---

## 4. Audit des licences des dépôts de référence

CutForge est un **SaaS commercial** (`app/services/payment.py`,
`subscriptions.py`, `plans.py`). Toute dépendance doit donc autoriser l'usage
commercial. Verdicts :

| Projet | Licence constatée | Usage commercial | Décision |
|---|---|---|---|
| **whiteboard-animator** | **MIT** (`LICENSE`, © 2026 Masih Sultani) | ✅ Oui | **Intégration réelle** en dépendance optionnelle |
| **anything2explainer** | **PolyForm Noncommercial 1.0.0** | ❌ **Non** — « any commercial use requires prior authorization » | **Aucun code copié.** Étude conceptuelle seulement |
| **freellmapi** | **MIT** (© 2026 Tashfeen Ahmed) | ✅ pour le code | Provider **optionnel**, jamais requis (voir réserve ci-dessous) |
| **Remotion** | Licence propriétaire — gratuite pour les particuliers et ≤ 3 personnes, **Company License payante** au-delà | ⚠️ Conditionnel | **Non ajouté en dépendance.** Étude conceptuelle (timeline, interpolation, easing) |
| **Motion Canvas** | MIT | ✅ Oui | Évalué, **non retenu** : impose Node + navigateur headless sur le VPS |
| **FFmpeg** | LGPL-2.1+ / GPL-2.0+ selon le build | ✅ via exécutable séparé | **Conservé**, invoqué en sous-processus (pas de lien) |
| **Whisper / faster-whisper** | MIT | ✅ Oui | Transcription locale, dépendance optionnelle |

### 4.1 anything2explainer — décision juridique motivée

Le dépôt est sous **PolyForm Noncommercial 1.0.0**, qui interdit explicitement
l'usage commercial sans autorisation préalable. CutForge étant monétisé, **aucune
ligne de son code, aucun de ses assets (fonts, templates Remotion, exemples) n'est
copié dans CutForge.**

Ce qui *a* été retenu relève des **idées et de l'architecture**, non protégeables
par le droit d'auteur, et réimplémenté intégralement en code original :

* le principe « une idée = une image = un jeu de régions révélées dans l'ordre » ;
* la séparation *analyse du discours* → *storyboard* → *rendu* ;
* la pondération du timing de révélation par la part de narration ;
* la notion de contrôle qualité du storyboard (densité, lisibilité, redondance).

Ces concepts sont d'ailleurs également présents, sous licence MIT, dans
whiteboard-animator (`build_narration_weighted_plan`), qui est notre source
d'implémentation effective.

### 4.2 whiteboard-animator — intégration réelle

Licence MIT ⇒ intégration directe autorisée (attribution conservée dans
`docs/THIRD_PARTY_LICENSES.md`). API publique utilisée :

```python
from whiteboard_animator import Scene, render_scene, WhiteboardAnimator
from whiteboard_animator.regions import SnippetRegionPlan, Region, Box
```

`render_scene()` transforme une image d'encre sur blanc en vidéo de dessin à la
main (CRAFT ONNX pour le texte, squelettisation pour les traits, peintres de
remplissage), avec un `region_plan` qui pondère la révélation par la narration.

**Réserve d'exploitation :** le paquet tire `opencv-python-headless`,
`scikit-image`, `scipy`, `onnxruntime` et embarque un modèle CRAFT de **80 Mo**.
C'est incompatible avec l'exigence « pipeline de base doit tourner sur VPS » si
on en fait une dépendance dure. **Décision : dépendance optionnelle** —
`WhiteboardRenderer` détecte le paquet à l'import ; s'il est absent ou s'il
échoue, il bascule sur un moteur de révélation natif (PIL + numpy seuls) qui
produit le même effet de dessin progressif à un coût CPU bien plus faible.

### 4.3 freellmapi — réserve importante

Le code du proxy est MIT, **mais cela ne dit rien des conditions d'utilisation des
fournisseurs situés derrière**. Un agrégateur open source peut router vers des
endpoints dont les CGU interdisent l'usage commercial, le scraping, ou l'usage
sans compte. **La licence MIT du proxy ne transfère aucun droit d'usage sur ces
services tiers.**

**Décision :** le mode `free` est **désactivé par défaut**, isolé derrière
`ILLUSTRATION_AI_MODE=free` + une URL explicitement configurée par
l'exploitant, qui assume la conformité aux CGU des fournisseurs. Le mode
`offline` reste le défaut et ne contacte aucun réseau.

---

## 5. Architecture retenue

```
transcript (vu.json)
   │
   ├── analyzer/     SemanticAnalyzer → patterns de discours (liste, étapes,
   │                 comparaison, chiffre, cause→effet, problème→solution,
   │                 définition, processus, architecture)
   │                 ImportanceDetector → poids rhétorique
   │                 ConceptDetector    → entités/concepts porteurs
   │                 VisualOpportunityDetector → visual_score ∈ [0,1]
   │
   ├── planner/      StoryboardPlanner → sélection sous contraintes
   │                 (seuil, espacement, durée, diversité, anti-répétition)
   │                 VisualTypeSelector → 12 types de scènes
   │                 ScenePlanner  → VisualElement[] + AnimationInstruction[]
   │                 TimingPlanner → alignement mot-à-mot sur la voix
   │
   ├── renderers/    RendererRouter → Whiteboard | MotionGraphics | Diagram
   │                 | Infographic | KineticText   (chaîne de fallback)
   │
   ├── assets/       AssetManager : SVG procédural → formes → icônes locales
   │                 → assets locaux → images existantes → génération (option)
   │
   ├── audio/        SFXPlanner contextuel + ducking
   │
   └── timeline/     Synchronisation + Compositor (ffmpeg)
```

Le `providers/` fournit l'intelligence sémantique en trois modes —
`offline` (heuristiques, défaut), `free` (FreeLLMAPI), `cloud` (configurable) —
avec dégradation automatique vers l'analyseur heuristique.

---

## 6. Sort de l'ancien moteur

`motion_design.py` **n'est plus le moteur principal** mais **n'est pas supprimé** :

* il reste importable et testé (5 fichiers de tests en dépendent) ;
* il est marqué `LEGACY` dans sa docstring et dans `autoedit_engine/README.md` ;
* `pipeline.py` route vers `illustration_engine` par défaut
  (`ILLUSTRATION_ENGINE_ENABLED=true`) et retombe sur `motion_design` si le
  nouveau moteur est explicitement désactivé ou s'il ne produit aucune scène.

Cette bascule est réversible par variable d'environnement, sans redéploiement.
