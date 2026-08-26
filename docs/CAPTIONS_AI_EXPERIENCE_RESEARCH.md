# Recherche d’expérience — Captions AI

## Objet

Cette note documente les éléments publics de l’expérience **Captions / Captions AI** qui peuvent inspirer Auto-edit, sans reproduire ses marques, ses textes propriétaires ou ses assets. L’objectif est de transformer les observations en composants originaux et compatibles avec le pipeline CutForge existant.

## Résumé exécutif

Captions présente l’édition comme un parcours très court : importer une vidéo, choisir une direction artistique, puis obtenir un rendu prêt à publier. Son différenciateur d’interface n’est pas seulement la présence d’un moteur automatique, mais la manière dont le style est rendu tangible avant le traitement : galerie de vignettes vidéo, fiche de style, promesse d’effets associés et possibilité d’exprimer des changements en langage naturel. [1] [2]

Le système de style est composé plutôt qu’un simple filtre. Les pages publiques décrivent des combinaisons de coupes, B-roll, transitions, musique, effets sonores, typographie, overlays et traitement colorimétrique. Dans l’exemple Paper II, le rendu combine texture papier, colorimétrie chaude légèrement vieillie, police machine à écrire, transitions de page et effets analogiques. [3]

La plateforme place également les sous-titres au niveau d’un composant de design : transcription synchronisée, choix de langue, styles nombreux, hiérarchie typographique et accentuation des mots. La page officielle annonce plus de 100 langues et plus de 100 styles de captions. [4]

## Décomposition de l’expérience

| Surface produit | Observation publique | Traduction pour Auto-edit |
|---|---|---|
| Import | Zone d’ajout de footage très visible, suivie d’un bouton de création | Conserver l’upload existant et rendre le choix de style immédiatement compréhensible |
| Galerie | Vignettes verticales, noms courts, description esthétique et regroupement par thèmes | Présenter les moteurs CutForge comme des directions artistiques avec aperçu visuel |
| AI Edit | Un style applique automatiquement coupes, B-roll, transitions, musique et autres éléments | Utiliser le catalogue backend existant comme source de vérité et exposer les effets actifs |
| Prompt d’édition | L’utilisateur peut demander du B-roll, des zooms ou des effets sonores en langage naturel | Ajouter une commande textuelle qui transforme des intentions simples en options de rendu |
| Preview | Présentation verticale avec traitement colorimétrique, texte intégré et contrôle de lecture | Renforcer le lien entre style choisi, preview et rendu final 9:16 |
| Captions | Transcription et synchronisation automatiques, styles et langues multiples | Conserver le modèle mot-à-mot et afficher captions, synchronisation et format comme attributs du rendu |
| Export | Rendu décrit comme prêt à publier et adaptable aux usages sociaux | Mettre en avant format, état du job et téléchargement sans interrompre le traitement |

## Templates et directions visuelles observées

La galerie publique organise les styles par thèmes tels que Trending, New, Bold, Business, Cinematic et d’autres catégories d’usage. Les exemples visibles comprennent notamment Bloom, Elevate, Ember, Ignite, Impact II, Paper II, Prime, Sketch, Sonnet, Volt, Y2K, Chalk, Evo, Focus, Lift, Linen, Prism Pro, Stack, Form, Grit, Pulse, Rocket, Velocity, Blueprint, Growth, Magazine, Align, Vinyl II, Analog, Cinematic II, Film, Neon et Story. [2]

Les descriptions reposent sur des promesses visuelles faciles à comprendre : « soft, dewy aesthetic », « premium, refined », « warm, golden-hour tones », « bold, electric edits », « moody literary vibes », « futuristic and modern » ou « playful and artistic ». Ce vocabulaire est utile pour une interface de sélection, mais Auto-edit doit garder ses propres noms et sa propre direction artistique.

## Montage vidéo : modèle fonctionnel recommandé

Le modèle le plus pertinent pour Auto-edit est un **style composé** dont chaque preset regroupe une intention, des attributs de rendu et une stratégie de coût. Le preset doit pouvoir décrire la typographie des captions, le traitement colorimétrique, les overlays, le rythme des coupes, la densité de B-roll, les transitions, la musique, les effets sonores, le ratio d’export et les règles de fallback.

Le dépôt possède déjà des briques adaptées à cette approche : catalogue de modes côté backend, pipeline V2, EDL, transcription mot-à-mot, B-roll, motion design, renderer FFmpeg et options de sous-titres. La modification frontend ajoute une couche de lisibilité produit : aperçu de direction artistique, indicateurs « Captions », « B-roll & motion » et « Sound design », attributs actifs et prompt de modification.

> Principe d’intégration : reproduire la clarté du parcours et la logique de composition des styles, pas l’identité graphique ni les assets de Captions.

## Choix d’implémentation dans Auto-edit

L’éditeur expose désormais une section **Direction artistique** sous le rail des moteurs. Elle adapte son thème aux modes connus (`collage_premium`, `pill_editorial`, `neon_hype`, `handwritten_note` et `board_pitch`) et fournit un fallback visuel pour les autres modes. Les cartes de preview sont générées en CSS afin d’éviter d’ajouter des assets lourds au frontend.

Le panneau **Modifier avec un prompt** accepte des intentions courantes en français ou en anglais. Il active les options correspondantes pour le prochain job : captions, suppression des pauses, B-roll, musique, effets sonores et format vertical ou horizontal. Des actions rapides permettent de préremplir trois demandes fréquentes. Le traitement réel reste piloté par le pipeline backend existant au clic sur « Forger le montage ».

## Limites et points à approfondir

Les pages marketing ne révèlent pas les algorithmes exacts de montage, les règles de sélection du B-roll, les modèles de ranking des styles ni la structure propriétaire de leur timeline. La version intégrée doit donc être considérée comme une **expérience équivalente par principes**, non comme une reproduction exacte de l’implémentation interne.

La prochaine amélioration technique recommandée est de relier la preview de style au lecteur vidéo et à la timeline afin que la sélection d’une scène, d’un caption ou d’un cue B-roll puisse déplacer le playhead et afficher les métadonnées du rendu. Cela nécessitera de faire évoluer les props de `VideoPlayer` et `Timeline` ainsi que le résultat JSON du job.

## Références

[1]: https://captions.ai/ — *Captions: AI That Edits Like a Professional Editor*, page officielle consultée le 26 août 2026.
[2]: https://captions.ai/styles — *Explore our video styles*, galerie officielle des styles AI Edit.
[3]: https://captions.ai/styles/paper — *The Easiest Way to Make Dark Academia Videos*, fiche officielle du style Paper II.
[4]: https://captions.ai/features/add-captions-to-videos — *AI Video Caption Generator: Stylized & Accurate*, page officielle des captions.
[5]: https://captions.ai/features/edit-with-ai — *AI Edit | Make Fully Edited Videos in Minutes*, page officielle du workflow AI Edit.
