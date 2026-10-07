# Moteur d'illustration CutForge

> Le moteur répond à une seule question, pour chaque instant du discours :
> **« qu'est-ce que le spectateur devrait voir maintenant pour mieux comprendre
> ce que la personne vient de dire ? »** — puis : quelle représentation, quelle
> animation, quelle synchronisation.
>
> Ce n'est pas un générateur d'effets. La vidéo originale reste le socle ; une
> illustration n'apparaît que lorsqu'elle apporte quelque chose.

---

## 1. Ce que ça fait

```
00:00 ───────────── TALKING HEAD ─────────────
00:35 ── PROCESSUS ──          « produit → trafic → livraison »
00:41 ───────────── TALKING HEAD ─────────────
01:25 ── DIAGRAMME ──          « client → serveur → entrepôt »
01:32 ───────────── TALKING HEAD ─────────────
02:40 ── WHITEBOARD ──         « les 3 piliers », dessiné à la main
02:47 ───────────── TALKING HEAD ─────────────
```

Le moteur **n'anime jamais toute la vidéo**, ne remplace pas la personne,
n'ajoute rien toutes les deux secondes. Trois garde-fous le garantissent, et
sont testés :

| Garde-fou | Réglage | Effet |
|---|---|---|
| Seuil de score visuel | `0,45` à `0,80` selon l'intensité | un passage sans valeur pédagogique n'est jamais illustré |
| Couverture maximale | 10 % / 18 % / 28 % | la part de vidéo illustrée est plafonnée |
| Espacement minimal | 16 s / 9 s / 5 s | le visage revient toujours entre deux scènes |

---

## 2. Architecture

```
transcript (vu.json)
   │
   ├── analyzer/    SemanticAnalyzer         → 10 patterns de discours
   │                ImportanceDetector       → poids rhétorique
   │                ConceptDetector          → concepts porteurs + domaines
   │                VisualOpportunityDetector→ visual_score ∈ [0,1]
   │
   ├── planner/     StoryboardPlanner        → sélection sous contraintes
   │                VisualTypeSelector       → 12 types de scènes
   │                ScenePlanner             → éléments + animations (0..1)
   │                TimingPlanner            → alignement mot à mot
   │
   ├── renderers/   RendererRouter           → Whiteboard | MotionGraphics
   │                                           | Diagram | Infographic
   │                                           | KineticText  (+ fallbacks)
   │
   ├── assets/      AssetManager             → SVG procédural → icônes →
   │                                           assets locaux → génération
   │
   ├── audio/       SFXPlanner               → un son par événement visuel
   │                AudioMixer               → VOIX > SFX > MUSIQUE
   │
   ├── timeline/    synchronization          → source → sortie (via l'EDL)
   │                Compositor               → incrustation ffmpeg
   │
   └── providers/   offline | free | cloud   → chaîne de repli
```

Point d'entrée unique : `IllustrationDirector` (`director.py`).

---

## 3. Analyse sémantique

Le moteur reconnaît **dix figures de discours**, en français et en anglais, sans
aucun modèle ni réseau :

| Figure | Déclencheur | Visuel produit |
|---|---|---|
| Liste | « il y a trois choses : … » | infographie numérotée |
| Étapes | « premièrement… ensuite… enfin… » | processus fléché |
| Comparaison | « avant… maintenant… », « au lieu de » | deux panneaux |
| Chiffre | « 87 % des… » | statistique plein écran |
| Cause → effet | « parce que… donc… » | flowchart |
| Problème → solution | « le problème… la solution… » | comparaison |
| Définition | « X, c'est… », « ça veut dire » | concept explainer |
| Processus | verbes de flux enchaînés | flowchart |
| Architecture | composants nommés | diagramme hub + satellites |
| Mot-clé | emphase sans structure | typographie cinétique |

La détection de listes est **générique** : elle ne dépend pas d'une liste figée
de noms. « trois habitudes : la répétition, la pratique et le repos » est
reconnu comme « trois choses : … », parce que la phrase annonce un compte
**et** énumère ensuite.

### Le score visuel

`visual_score` mesure l'**illustrabilité**, pas l'importance. Un passage peut
être rhétoriquement crucial (« croyez-moi, c'est essentiel ») sans rien à
montrer ; un passage modeste peut être très illustrable.

```
0,00 – 0,39   aucune animation
0,40 – 0,59   animation optionnelle
0,60 – 0,79   animation recommandée
0,80 – 1,00   animation fortement recommandée
```

Composantes : illustrabilité de la figure (40 %), matière réellement extraite
(26 %), importance rhétorique (18 %), concrétude du vocabulaire (16 %).

La **matière** est décisive : une « liste » dont aucun élément n'est
extractible produirait une carte vide — exactement l'animation décorative que
la spec interdit. Son score est donc écrasé.

---

## 4. Les douze types de scènes

`whiteboard` · `motion_graphics` · `diagram` · `flowchart` · `comparison`
`statistics` · `timeline` · `process` · `concept` · `ui_explainer`
`kinetic_typography` · `infographic`

Chaque type a une composition propre, exprimée en coordonnées **normalisées
0..1** : la même scène est donc valide en 1920×1080, 1080×1920 et 1080×1080
sans seconde passe de layout.

Le sélecteur évite qu'un type revienne deux fois de suite et qu'il dépasse 45 %
du storyboard — la variété est une contrainte, pas un effet de bord.

---

## 5. Renderers

| Renderer | Types | Particularité |
|---|---|---|
| `WhiteboardRenderer` | whiteboard | Dessin à la main, voir §6 |
| `InfographicRenderer` | infographic, statistics | Le chiffre domine l'écran |
| `DiagramRenderer` | diagram | Liens dessinés **sous** les nœuds |
| `KineticTextRenderer` | kinetic_typography | Typographie seule, mot à mot |
| `MotionGraphicsRenderer` | tous les autres | Langage graphique général |

**Chaîne de repli** (`RendererRouter`) :

```
WhiteboardRenderer  →  MotionGraphicsRenderer  →  KineticTextRenderer
```

Un renderer qui lève une exception ou produit un fichier vide passe la main au
suivant. Si toute la chaîne échoue, la scène est abandonnée et **le montage
continue** — jamais d'échec de job à cause d'une illustration.

Sortie : **ProRes 4444 avec alpha** (`yuva444p10le`), le format que le
compositeur du montage attend déjà.

---

## 6. Whiteboard : deux moteurs, un contrat

**Moteur 1 — whiteboard-animator (MIT), quand il est installé.**
La scène est composée en affiche encre-sur-blanc, décrite en
`SnippetRegionPlan` pondéré par la narration, puis confiée à `render_scene()` :
détection de texte CRAFT (ONNX), squelettisation des traits, peintres de
remplissage. C'est un vrai dessin à la main.

```bash
pip install whiteboard-animator   # optionnel
```

**Moteur 2 — révélation native, sinon.**
Les mêmes tracés vectoriels sont dessinés progressivement avec PIL + numpy
seuls : chaque icône, cadre, flèche et texte est tracé à une fraction exacte de
sa longueur de chemin. Aucune dépendance lourde, aucun modèle de 80 Mo.

Pourquoi ce choix : whiteboard-animator tire OpenCV, scikit-image, scipy,
onnxruntime et un modèle CRAFT de 80 Mo. En dépendance dure, cela
contredirait « doit tourner sur VPS ». Détail dans
`docs/THIRD_PARTY_LICENSES.md`.

---

## 7. Assets : priorité absolue au procédural

```
1. SVG procédural       ← 42 icônes vectorielles, toujours disponibles
2. formes vectorielles  ← cartes, flèches, barres, cadres
3. icônes locales
4. assets locaux
5. images déjà présentes dans le workdir
6. génération d'image   ← optionnelle, payante, JAMAIS requise
```

Le moteur produit **toutes** ses scènes sans aucune API d'image. La génération
n'est tentée que si `OPENROUTER_API_KEY` est présent **et** que le mode visuel
du montage l'autorise.

Les icônes couvrent le vocabulaire réel de l'audience : mobile money,
e-commerce, livraison, boutique, client, vendeur, téléphone, réseaux sociaux,
entreprise, IA, éducation, agriculture, finance. Elles sont **symboliques** —
objets et outils — et ne représentent jamais de personnes de façon
caricaturale.

---

## 8. Son

`SFXPlanner` attache un son à **chaque événement visuel**, jamais pour combler
un silence :

```
carte qui apparaît   → pop
trait dessiné        → pencil
transition de scène  → whoosh / transition
chiffre clé          → subtle_hit, puis success quand il atterrit
entrée de scène      → riser, 0,45 s AVANT l'image
```

Sur une scène whiteboard, tout gratte (`pencil`) sauf les flèches qui balaient.

`AudioMixer` applique la priorité **VOIX > SFX > MUSIQUE** avec de vrais
side-chains ffmpeg : la musique recule sous la voix, les SFX aussi (plus
doucement), et le tout est normalisé à −14 LUFS.

Aucun asset audio tiers : tous les sons sont synthétisés. Voir
`docs/SFX_LICENSES.md`.

---

## 9. Synchronisation

Le montage coupe les silences et les faux départs : une scène planifiée à
`t=32,4 s` **source** n'atterrit pas à `32,4 s` en sortie. Le moteur réutilise
l'**EDL du montage** pour le mapping, plutôt que d'en inventer un second qui
pourrait diverger.

Une scène dont le beat a été supprimé par la coupe est **abandonnée**, pas
déplacée : une illustration qui ne correspond plus à ce qui est dit est pire
que pas d'illustration.

Une scène tronquée par la fin de vidéo est également abandonnée si elle perd
plus de 40 % de sa durée : elle n'aurait pas le temps de finir de se révéler.

---

## 10. Modes de fonctionnement

```bash
ILLUSTRATION_ENGINE_ENABLED=true
ILLUSTRATION_AI_MODE=offline      # offline | free | cloud
```

### offline — le défaut

Aucun appel réseau. Ni OpenAI, ni Anthropic, ni Gemini, ni OpenRouter, ni
FreeLLMAPI. L'analyse repose sur les heuristiques, les règles et le lexique
bilingue ; les visuels sur le SVG procédural et les icônes locales.

### free

Peut utiliser FreeLLMAPI pour affiner l'analyse. **Inerte tant qu'il n'est pas
explicitement configuré** — il faut `FREELLM_BASE_URL` *et* `FREELLM_MODEL` :

```bash
ILLUSTRATION_AI_MODE=free
FREELLM_BASE_URL=https://votre-instance/v1
FREELLM_MODEL=le-modele
```

⚠️ Le code de FreeLLMAPI est MIT, **mais cela ne dit rien des CGU des
fournisseurs derrière lui**. En activant ce mode, l'exploitant assume cette
conformité. Voir `docs/THIRD_PARTY_LICENSES.md` §3.

### cloud

N'importe quel endpoint compatible OpenAI. **Aucun fournisseur n'est codé en
dur** :

```bash
ILLUSTRATION_AI_MODE=cloud
ILLUSTRATION_CLOUD_BASE_URL=https://openrouter.ai/api/v1
ILLUSTRATION_CLOUD_MODEL=...
ILLUSTRATION_CLOUD_API_KEY_ENV=OPENROUTER_API_KEY
```

### Repli

```
CloudProvider indisponible
        ↓
FreeLLMAPI indisponible
        ↓
LocalSemanticProvider  →  analyseur heuristique  →  storyboard
```

La sortie d'un modèle est **validée et bornée** : un index hors transcript, un
pattern inconnu, un score aberrant sont écartés — jamais propagés. Un modèle
qui répond partiellement améliore le plan ; il ne peut pas le dégrader.

---

## 11. Styles

Dix presets : `professional` `education` `business` `technology` `finance`
`marketing` `minimal` `whiteboard` `dark_premium` `clean`.

Un style contrôle la palette, la typographie, l'épaisseur de trait, la vitesse
d'animation, la transition, la densité et le traitement des icônes.

---

## 12. Formats

Préréglage principal **YouTube 16:9 — 1920×1080**. Également supportés :
`9:16` (1080×1920) et `1:1` (1080×1080). Le bridge déduit le format du canevas
du montage, donc le pipeline vertical existant continue de fonctionner sans
changement.

---

## 12 bis. Transcription : locale et gratuite par défaut

Le moteur d'illustration ne transcrit pas lui-même : il consomme le format
mot-à-mot du pipeline

```json
{"language": "fr", "duration": 92.4, "segments": [
  {"text": "...", "start": 0.0, "end": 4.2,
   "words": [{"word": "Bonjour", "start": 0.0, "end": 0.4}]}]}
```

Ce format vient, par ordre de préférence :

| Source | Coût | Quand |
|---|---|---|
| ElevenLabs Scribe | payant | seulement si `ELEVENLABS_API_KEY` est défini |
| **faster-whisper** | **gratuit, local** | si le paquet est installé (défaut recommandé) |
| openai-whisper | gratuit, local | repli toujours disponible |

**Aucune clé n'est requise.** Sans `ELEVENLABS_API_KEY`, le pipeline transcrit
localement ; si Scribe échoue en vol, il retombe aussi sur le local.

`faster-whisper` (CTranslate2) est 4 à 5 fois plus rapide qu'openai-whisper sur
CPU et bien plus sobre en mémoire en `int8` — c'est ce qui rend la
transcription locale réaliste sur un VPS sans GPU. Le choix est automatique :

```bash
WHISPER_BACKEND=auto          # auto | faster_whisper | whisper
WHISPER_COMPUTE_TYPE=int8     # int8 | int8_float16 | float32
WHISPER_MODEL=small
```

Si `faster-whisper` est absent, ou si son modèle ne peut pas être téléchargé,
le service journalise la raison et bascule sur `openai-whisper` — le job n'est
jamais perdu pour ça.

Les deux moteurs produisent le même contrat, `confidence` comprise, donc rien
en aval ne sait lequel a tourné.

---

## 13. Installation

```bash
pip install -r backend/requirements.txt     # numpy + Pillow suffisent au moteur
pip install whiteboard-animator             # optionnel — dessin à la main
pip install faster-whisper                  # recommandé — transcription locale rapide
```

`ffmpeg` 6+ doit être sur le `PATH` (ou `FFMPEG_BIN`).

**Aucune clé API n'est nécessaire.**

---

## 14. Utilisation

### Depuis le pipeline (automatique)

Le moteur est branché sur l'étape 4 du montage. Rien à faire.

```bash
python -m app.autoedit_engine.pipeline video.mp4 --workdir out \
    --illustration-style whiteboard \
    --illustration-intensity high \
    --illustration-ai-mode offline
```

Pour revenir à l'ancien moteur :

```bash
python -m app.autoedit_engine.pipeline video.mp4 --workdir out --legacy-motion
# ou : ILLUSTRATION_ENGINE_ENABLED=false
```

### Depuis l'API

```json
{
  "video_id": "...",
  "options": {
    "motion_design": true,
    "illustration_style": "whiteboard",
    "illustration_intensity": "high",
    "illustration_ai_mode": "offline"
  }
}
```

Le résultat du job porte `illustrationEngine` (rapport) et `illustrationPlan`
(ce qui a été illustré, quand, et avec quel score).

### Routes dédiées (lecture seule)

Le **rendu** passe par l'API Jobs : une illustration n'a de sens que dans un
montage, et dupliquer le pipeline créerait un second chemin à maintenir. Ces
routes donnent ce que l'API Jobs ne peut pas donner — savoir ce que le moteur
ferait **avant** de dépenser du CPU :

| Route | Rôle |
|---|---|
| `GET /api/v1/illustrations/capabilities` | styles, intensités, modes, formats, types de scènes, et si le dessin à la main est installé sur cet hôte |
| `POST /api/v1/illustrations/analyze` | comment le moteur lit un passage : figure de discours, matière extraite, score, justification |
| `POST /api/v1/illustrations/storyboard` | le plan complet, sans rendre une frame — depuis un `transcript` ou un `job_id` |

```bash
curl -X POST /api/v1/illustrations/analyze \
     -H 'Authorization: Bearer <token>' \
     -d '{"text": "Il y a trois choses : le produit, le trafic et la livraison."}'
# -> {"pattern": "list", "items": ["Produit","Trafic","Livraison"],
#     "visual_score": 0.82, "band": "strongly_recommended", ...}
```

### En Python

```python
from app.illustration_engine import IllustrationDirector

director = IllustrationDirector(style="professional", intensity="medium",
                                aspect="16:9")
result = director.run(vu_transcript, "out/illustrations")

result.storyboard.plan_summary()   # ce qui a été décidé
result.legacy_clips                # clips prêts pour le compositeur
result.report                      # observabilité complète
```

---

## 15. Configuration

| Variable | Défaut | Rôle |
|---|---|---|
| `ILLUSTRATION_ENGINE_ENABLED` | `true` | bascule vers l'ancien moteur si `false` |
| `ILLUSTRATION_AI_MODE` | `offline` | `offline` / `free` / `cloud` |
| `ILLUSTRATION_STYLE` | `professional` | style par défaut |
| `ILLUSTRATION_INTENSITY` | `medium` | `low` / `medium` / `high` |
| `ILLUSTRATION_ASPECT` | `16:9` | `16:9` / `9:16` / `1:1` |
| `ILLUSTRATION_FPS` | `30` | images par seconde |
| `ILLUSTRATION_MIN_DUR` / `_MAX_DUR` | `3.0` / `7.0` | bornes de durée d'une scène |
| `ILLUSTRATION_MIN_GAP` | `9.0` | secondes de visage entre deux scènes |
| `ILLUSTRATION_MAX_SCENES` | `40` | plafond absolu |
| `ILLUSTRATION_USE_WHITEBOARD_ANIMATOR` | `true` | désactive le moteur tiers |
| `ILLUSTRATION_RENDER_WORKERS` | `0` (auto) | rendus parallèles |
| `ILLUSTRATION_PREVIEW_SCALE` / `_FPS` | `0.5` / `15` | qualité des aperçus |
| `ILLUSTRATION_SFX_ENABLED` | `true` | coupe les SFX |
| `ILLUSTRATION_MUSIC_DUCK_DB` | `-9.0` | ducking musique |

**Aucune clé API ne doit être commitée.** Utilisez `.env` ; `.env.example` ne
contient que des placeholders.

---

## 16. Performance VPS

* **Pas de GPU requis**, nulle part.
* Rendu parallèle borné à 2 scènes par défaut : chaque scène pilote son propre
  ffmpeg, et saturer un petit VPS le rendrait inutilisable.
* Compositing **par lots de 12 overlays**, chaque passe reprenant la sortie de
  la précédente — un seul ffmpeg avec trente filtres `overlay` est un OOM kill
  assuré.
* Mode aperçu : `preview=True` divise la résolution par deux et passe à 15 fps.
* Le moteur natif de whiteboard évite 80 Mo de modèle et la pile
  OpenCV/scipy/ONNX.

---

## 17. Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| Aucune scène produite | aucun passage au-dessus du seuil | `illustration_intensity=high`, ou vérifier `board.notes` |
| « couverture maximale » dans les notes | plafond atteint | intensité plus élevée, ou vidéo plus longue |
| Scènes sans dessin à la main | `whiteboard-animator` absent | `pip install whiteboard-animator` (optionnel) |
| `Encodage ProRes échoué` | ffmpeg absent ou disque plein | vérifier `ffmpeg -version` et l'espace disque |
| Le mode `free` ne fait rien | non configuré, **par conception** | définir `FREELLM_BASE_URL` **et** `FREELLM_MODEL` |
| Polices en gras absentes | fontes non trouvées | repli DejaVuSans automatique, rendu non bloqué |
| Illustrations décalées | EDL non transmis | passer `edl_ranges` à `director.run()` |

Le rapport du job (`results["illustrationEngine"]`) contient toujours : mode IA,
provider effectif, scènes planifiées/rendues, couverture, histogramme des
types, renderers utilisés, replis déclenchés, tiers d'assets servis, et les
notes de rejet.

---

## 18. Licences

Voir **`docs/THIRD_PARTY_LICENSES.md`** et **`docs/SFX_LICENSES.md`**.

Points essentiels : whiteboard-animator est MIT et réellement intégré ;
anything2explainer est non-commercial et **aucun de son code n'est présent** ;
Remotion n'est pas une dépendance ; tous les sons sont synthétisés ; toutes les
icônes sont originales.

---

## 19. Ancien moteur

`backend/app/autoedit_engine/motion_design.py` n'est **plus le moteur
principal**. Il n'est pas supprimé : le pipeline y retombe si le nouveau moteur
est désactivé ou échoue, et plusieurs suites de tests le couvrent encore. Il est
marqué `LEGACY` dans sa docstring.

N'y ajoutez pas de nouveaux types de scènes.
