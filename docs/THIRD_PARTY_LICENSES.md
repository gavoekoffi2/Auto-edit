# Licences tierces — moteur d'illustration CutForge

CutForge est un **service commercial** (`backend/app/services/payment.py`,
`subscriptions.py`, `plans.py`). Toute dépendance doit donc autoriser un usage
commercial. Ce document dit, pour chaque projet consulté pendant la refonte du
moteur d'illustration : sa licence **constatée dans son dépôt**, ce que CutForge
en fait réellement, et les obligations qui en découlent.

> Les licences ci-dessous ont été lues dans les dépôts eux-mêmes au moment de
> l'intégration. Les éditeurs peuvent en changer : revérifiez avant toute mise à
> jour de version.

---

## Tableau de synthèse

| Projet | Licence constatée | Usage commercial | Ce que CutForge en fait |
|---|---|---|---|
| [whiteboard-animator](https://github.com/masihsultani/whiteboard-animator) | MIT | ✅ | **Code exécuté** — dépendance optionnelle |
| [anything2explainer](https://github.com/Vincentwei1021/anything2explainer) | PolyForm Noncommercial 1.0.0 | ❌ | **Aucun code, aucun asset.** Étude conceptuelle |
| [FreeLLMAPI](https://github.com/tashfeenahmed/freellmapi) | MIT | ⚠️ voir §3 | Provider optionnel, désactivé par défaut |
| [Remotion](https://github.com/remotion-dev/remotion) | Licence Remotion (double palier) | ⚠️ conditionnel | **Non intégré.** Étude conceptuelle |
| [Motion Canvas](https://github.com/motion-canvas/motion-canvas) | MIT | ✅ | Évalué, **non retenu** (raisons techniques) |
| [FFmpeg](https://github.com/FFmpeg/FFmpeg) | LGPL-2.1+ / GPL-2.0+ selon le build | ✅ | Exécutable appelé en sous-processus |
| [Whisper](https://github.com/openai/whisper) | MIT | ✅ | Transcription locale optionnelle |
| faster-whisper | MIT | ✅ | Alternative CPU recommandée |
| Polices (Montserrat, Anton, Poppins, Playfair, Bangers) | SIL Open Font License 1.1 | ✅ | Embarquées dans `autoedit_engine/assets/fonts/` |
| Effets sonores | Synthétisés par CutForge | ✅ | Voir `docs/SFX_LICENSES.md` |
| Icônes | Originales, écrites pour CutForge | ✅ | `illustration_engine/assets/icon_library.py` |

---

## 1. whiteboard-animator — intégration réelle

**Licence : MIT** (`LICENSE`, © 2026 Masih Sultani).

**Ce qu'on en fait.** `WhiteboardRenderer` l'appelle réellement quand le paquet
est installé :

```python
from whiteboard_animator import Scene, render_scene, WhiteboardAnimator
from whiteboard_animator.regions import Box, Region, SnippetRegionPlan
```

CutForge compose la scène en affiche encre-sur-blanc, la décrit en
`SnippetRegionPlan` pondéré par la narration, et laisse `render_scene()`
produire le dessin à la main (détection de texte CRAFT en ONNX,
squelettisation des traits, peintres de remplissage).

**Pourquoi c'est une dépendance optionnelle.** Le paquet tire
`opencv-python-headless`, `scikit-image`, `scipy`, `onnxruntime` et embarque un
modèle CRAFT de **80 Mo**. En faire une dépendance dure contredirait l'exigence
« le pipeline de base doit tourner sur VPS ». `WhiteboardRenderer` détecte donc
sa présence à l'import et, à défaut, bascule sur un moteur de révélation natif
(PIL + numpy seuls) qui produit le même dessin progressif à un coût bien
moindre.

**Obligations MIT respectées.** Avis de copyright et texte de licence conservés —
reproduits ci-dessous — et aucune garantie n'est revendiquée.

```
MIT License — Copyright (c) 2026 Masih Sultani

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**Installation (optionnelle) :**

```bash
pip install whiteboard-animator
```

Sans ce paquet, CutForge fonctionne — le rendu whiteboard passe simplement par
le moteur natif.

---

## 2. anything2explainer — étude conceptuelle, aucun code copié

**Licence : PolyForm Noncommercial 1.0.0.** Le dépôt précise :

> « noncommercial use is free; any commercial use of the toolkit requires prior
> authorization from the author. »

**CutForge étant monétisé, cette licence est incompatible.** En conséquence :

* ❌ aucune ligne de son code n'est présente dans CutForge ;
* ❌ aucun de ses assets (polices `template/public/fonts/`, templates Remotion,
  exemples, frames) n'est repris ;
* ❌ CutForge n'est pas une œuvre dérivée de ce projet.

**Ce qui a été retenu** relève des **idées et de l'architecture** — non
protégeables par le droit d'auteur — et a été **réimplémenté intégralement en
code original** :

| Idée étudiée | Implémentation originale dans CutForge |
|---|---|
| « une idée = une image = un jeu de régions révélées dans l'ordre » | `schemas/scene.py`, `planner/scene_planner.py` |
| séparation analyse du discours → storyboard → rendu | `analyzer/` → `planner/` → `renderers/` |
| timing de révélation pondéré par la narration | `timeline/synchronization.py::narration_weights` |
| contrôle qualité du storyboard (densité, redondance) | `planner/storyboard_planner.py` |

Ces mêmes concepts existent d'ailleurs **sous licence MIT** dans
whiteboard-animator (`build_narration_weighted_plan`), qui est notre source
d'implémentation effective.

---

## 3. FreeLLMAPI — réserve importante

**Licence du proxy : MIT** (© 2026 Tashfeen Ahmed).

⚠️ **La licence MIT du proxy ne dit rien des conditions d'utilisation des
fournisseurs situés derrière lui.** Un agrégateur open source peut router vers
des endpoints dont les CGU interdisent l'usage commercial, l'accès automatisé,
ou l'usage sans compte. **Le fait que le code soit open source ne transfère
aucun droit d'usage sur ces services tiers.**

**Décision d'architecture.** Le mode `free` est :

* **désactivé par défaut** (`ILLUSTRATION_AI_MODE=offline`) ;
* **inerte tant qu'il n'est pas explicitement configuré** — il faut fournir
  `FREELLM_BASE_URL` *et* `FREELLM_MODEL`, moment où l'exploitant assume la
  conformité aux CGU des fournisseurs amont ;
* **toujours doublé d'un repli** vers l'analyseur heuristique local.

Voir `providers/freellmapi_provider.py`, dont la docstring rappelle cette
distinction.

---

## 4. Remotion — non intégré

**Licence : licence propriétaire Remotion à double palier**, constatée dans
`LICENSE.md` du dépôt :

> « Individuals and small companies are allowed to use Remotion to create videos
> for free (even commercial), while a company license is required for for-profit
> organizations of a certain size. »

Sont éligibles à la licence gratuite : les particuliers, les organisations à but
lucratif **jusqu'à 3 salariés**, les organisations à but non lucratif, et
l'évaluation. Au-delà, une **Company License payante** est requise. Il est par
ailleurs interdit de copier ou modifier le code de Remotion pour vendre un
dérivé de Remotion.

**Décision.** Remotion **n'est pas ajouté** comme dépendance du moteur
d'illustration, pour trois raisons :

1. **la licence dépend de la taille de l'exploitant de CutForge**, ce qu'un
   moteur livré dans le produit ne peut pas décider à sa place ;
2. elle imposerait Node + Chromium headless dans l'image Docker du worker,
   contre l'exigence « éviter d'ajouter des dépendances inutiles » et « doit
   tourner sur VPS » ;
3. aucune ligne de code Remotion n'est copiée — seuls ses **concepts** ont été
   étudiés (timeline, compositions, interpolation, easing, transitions) et
   réimplémentés : `renderers/base.py` (easing, progression, transitions),
   `schemas/visual.py::AnimationInstruction` (interpolation déclarative).

> Le scaffolding préexistant `templates/remotion/` est antérieur à cette refonte
> et n'est pas utilisé par le moteur d'illustration. Si vous l'exploitez,
> vérifiez votre éligibilité à la licence gratuite.

---

## 5. Motion Canvas — évalué, non retenu

**Licence : MIT** — juridiquement compatible.

**Non retenu pour des raisons techniques**, pas juridiques : c'est un moteur
TypeScript qui rend via un navigateur headless. L'adopter imposerait Node +
Chromium dans le worker et un pont Python↔Node, pour des capacités
(timeline, formes, texte, transitions, diagrammes) que le moteur couvre déjà en
Python pur avec PIL + ffmpeg.

---

## 6. FFmpeg

**Licence : LGPL-2.1+ par défaut, GPL-2.0+ si compilé avec `--enable-gpl`.**

CutForge **n'établit aucun lien** avec les bibliothèques FFmpeg : il invoque
l'exécutable `ffmpeg` en **sous-processus** (`timeline/encoder.py`,
`timeline/compositor.py`, `audio/audio_mixer.py`). C'est une utilisation
« at arm's length » qui ne crée pas d'œuvre dérivée.

**Obligation de l'exploitant** : si vous redistribuez une image Docker
contenant un build FFmpeg, respectez les obligations du build utilisé
(mise à disposition des sources pour les composants LGPL/GPL).

---

## 7. Whisper / faster-whisper

**Licences : MIT** pour les deux (`openai/whisper`, © 2022 OpenAI ;
`SYSTRAN/faster-whisper`).

**Statut dans CutForge** : la transcription actuelle passe par ElevenLabs Scribe
(`autoedit_engine/transcribe.py`). Le moteur d'illustration ne consomme que le
format de sortie `{"language","duration","segments":[{"text","start","end",
"words":[…]}]}`, qui est exactement ce que Whisper produit avec
`word_timestamps=True`. Basculer sur une transcription **locale et gratuite**
ne demande donc aucun changement dans le moteur d'illustration.

Recommandation pour un VPS sans GPU : **faster-whisper** (CTranslate2), modèle
`small` ou `medium`, `compute_type="int8"`.

```bash
pip install faster-whisper
```

---

## 8. Polices

Toutes les polices embarquées dans `backend/app/autoedit_engine/assets/fonts/`
sont sous **SIL Open Font License 1.1**, qui autorise l'usage commercial et
l'embarquement. Obligation : conserver l'avis de licence et ne pas vendre les
fontes seules.

`DejaVuSans-Bold` (licence DejaVu, libre d'usage commercial) sert de repli
toujours présent : le rendu ne casse jamais faute de police.

---

## 9. Assets créés pour CutForge

| Asset | Emplacement | Statut |
|---|---|---|
| 42 icônes vectorielles | `illustration_engine/assets/icon_library.py` | **Originales**, écrites pour ce projet |
| Presets de style | `illustration_engine/styles.py` | **Originaux** |
| Effets sonores | générés par `autoedit_engine/sfx_lib.py` | **Synthétisés**, voir `SFX_LICENSES.md` |

Aucun asset d'origine inconnue n'est présent dans le moteur.
