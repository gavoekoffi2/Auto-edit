# Licences des effets sonores

**Aucun effet sonore d'origine inconnue n'est utilisé par CutForge.**

## 1. Les sons du moteur sont synthétisés, pas échantillonnés

Les effets sonores du moteur d'illustration ne sont pas des enregistrements :
ils sont **calculés numériquement au moment du rendu** par
`backend/app/autoedit_engine/sfx_lib.py`, à partir d'oscillateurs, de bruit
filtré et d'enveloppes en numpy. Il n'existe donc :

* aucun fichier audio téléchargé ;
* aucun échantillon issu d'une banque de sons ;
* aucune licence d'échantillon à obtenir, créditer ou renouveler.

Ces sons sont une **œuvre originale de CutForge** et suivent la licence du
dépôt.

Vérifiable en une commande :

```bash
python -m app.autoedit_engine.sfx_lib /tmp/sfx   # écrit les WAV depuis zéro
```

## 2. Correspondance vocabulaire → générateur

Le moteur d'illustration expose onze sons contextuels
(`illustration_engine/audio/sfx_library.py`), adossés aux générateurs
synthétisés :

| Sens dans le montage | Nom moteur | Générateur synthétisé | Gain |
|---|---|---|---|
| Transition, balayage | `whoosh` | `whoosh` | 0,52 |
| Apparition d'une carte | `pop` | `pop` | 0,60 |
| Élément secondaire | `click` | `click` | 0,42 |
| Trait de feutre | `marker` | `pen_scribble` | 0,38 |
| Dessin au crayon | `pencil` | `pen_scribble` | 0,38 |
| Écriture d'un texte | `writing` | `pen_scribble` | 0,38 |
| Entrée de scène | `transition` | `transition` | 0,58 |
| Impact narratif | `impact` | `cinematic_hit` | 0,66 |
| Notification / UI | `notification` | `digi_blip` | 0,46 |
| Résolution positive | `success` | `chime` | 0,54 |
| Chiffre clé qui atterrit | `subtle_hit` | `bass_hit` | 0,44 |
| Anticipation (−0,45 s) | `riser` | `riser` | 0,50 |
| Sortie de scène | `exit` | `swoosh_down` | 0,50 |

Les gains sont plafonnés à 0,7 : **aucun effet ne peut couvrir la voix**, et le
mixeur les side-chaîne en plus sur la piste voix (`audio/audio_mixer.py`).

## 3. Ajouter vos propres sons

Un exploitant peut remplacer n'importe quel son en déposant un WAV ici :

```
backend/app/illustration_engine/assets_data/audio/sfx/<nom>.wav
```

où `<nom>` est un nom du tableau ci-dessus (`pop.wav`, `pencil.wav`, …). Le
fichier local est prioritaire sur le son synthétisé.

⚠️ **La licence de tout fichier déposé là relève de la responsabilité de
l'exploitant.** CutForge n'en fournit aucun et n'en vérifie aucun. Si vous
ajoutez des sons, documentez leur provenance et leur licence dans ce fichier,
sous le tableau ci-dessous.

### Sons ajoutés par l'exploitant

| Fichier | Source | Licence | Attribution requise |
|---|---|---|---|
| _(aucun)_ | — | — | — |

## 4. Le son d'ambiance non synthétisé

`autoedit_engine/assets/light_leak_original.wav` accompagne l'overlay de fuite
de lumière du moteur de montage. Il est **fourni par le propriétaire du dépôt**
et précède cette refonte ; le moteur d'illustration ne l'utilise pas.
