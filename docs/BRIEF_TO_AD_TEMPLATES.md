# Brief vers publicité — architecture des templates

## Vision

Auto-edit propose désormais un parcours où l’utilisateur décrit son entreprise, son audience, son offre, ses preuves et son appel à l’action. Le service transforme ces informations en **storyboard structuré** avant le rendu final. Cette étape rend le montage explicable et permet à l’utilisateur de choisir une direction artistique au lieu de recevoir un résultat opaque.

## Familles de templates

| Template | Usage | Règles principales |
|---|---|---|
| Direct Response | Produit numérique, formation, service à vendre | Hook, problème, promesse, preuve, offre et CTA ; split-screen ; mockup persistant ; rythme dense |
| Urgence & Preuve | Offre avec douleur forte ou délai | Compte à rebours, contraste échec/réussite, témoignage, badge, barre de progression |
| Démonstration SaaS | Plateforme ou logiciel | Écrans produit, curseur, zooms d’interface, fonctionnalités par étapes, CTA de démonstration |
| Face caméra éditorial | Vidéo parlée éducative ou experte | Suppression des silences, captions en pilule, push-ins, B-roll contextuel et hiérarchie éditoriale |
| Face caméra néon | Réseaux sociaux à rythme élevé | Jump cuts, recadrages, mots-clés forts, accents lumineux et impacts sonores |
| Face caméra notes | Conseil, storytelling et contenu humain | Annotations, flèches, surlignages, transitions de page, captures et texture carnet |

## Contrat du storyboard

Le endpoint `POST /api/v1/briefs/preview` reçoit une description d’au moins 20 caractères ainsi que les champs facultatifs de marque, audience, offre, preuve, CTA, ton, format, durée et template. Il renvoie six scènes normalisées : `hook`, `problem`, `promise`, `proof`, `offer` et `cta`.

Chaque scène possède une plage temporelle, une narration, un overlay textuel, une direction visuelle, une règle de motion et une règle audio. Le champ `render_plan` décrit les options nécessaires au pipeline : captions, suppression des silences, B-roll, motion design, musique, effets sonores, ratio et CTA.

## Voix off et prérequis de rendu

Le backend contient maintenant `VoiceoverService`, un adaptateur TTS réel basé sur ElevenLabs. Il reçoit le texte des narrations, utilise `ELEVENLABS_API_KEY`, `TTS_VOICE_ID` et `TTS_MODEL`, puis persiste un fichier MP3 prêt à être mixé avec la musique et les effets sonores. Si la clé n’est pas configurée, le service échoue explicitement au lieu de produire un faux audio silencieux.

La génération du storyboard reste déterministe et transparente. Le rendu publicitaire entièrement autonome nécessite donc, en production, de configurer `ELEVENLABS_API_KEY` pour la voix off et `OPENROUTER_API_KEY` si les scènes doivent recevoir des images B-roll générées. Les assets de marque, captures produit et preuves sociales peuvent être fournis par l’utilisateur afin d’éviter des visuels génériques.

La prochaine liaison de production est l’orchestrateur de jobs : il doit créer un répertoire de rendu, appeler `VoiceoverService` pour le script, convertir les scènes en cues B-roll, appeler `ImageGenerationService`, puis transmettre la timeline enrichie au renderer FFmpeg/Hyperframes. Les contrats de données du storyboard et du plan de rendu sont déjà conçus pour cette orchestration.

Pour les vidéos face caméra, le chemin est déjà directement compatible avec le pipeline existant : l’utilisateur importe sa vidéo, choisit un template, puis les options de suppression des silences, captions, B-roll, motion, musique et SFX sont appliquées au job de montage.
