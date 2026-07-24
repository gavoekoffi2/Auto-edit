# Silhouettes personnalisées

Dépose ici tes propres `.svg` pour remplacer ou compléter les silhouettes
intégrées. Le nom du fichier devient le nom de la pose.

```
assets/silhouettes/
  presenter.svg      -> remplace la pose intégrée « presenter »
  ma_pose.svg        -> nouvelle pose, utilisable via scene["silhouette"] = "ma_pose"
```

Un SVG déposé ici est **prioritaire** sur la pose intégrée du même nom.

## Exporter les poses intégrées pour les retoucher

```bash
python -m app.autoedit_engine.silhouettes --export-svg /tmp/silhouettes
python -m app.autoedit_engine.silhouettes --preview /tmp/planche.png
python -m app.autoedit_engine.silhouettes --list
```

Ouvre le `.svg` dans Illustrator / Figma / Inkscape, modifie-le, puis
enregistre-le dans ce dossier.

## Contraintes

- Format **portrait** (le moteur met à l'échelle en conservant les proportions
  et centre la figure) ; ~2:3 donne le meilleur résultat.
- Fond **transparent** — la plaque claire est ajoutée par le moteur.
- La rasterisation passe par `svglib` (pur Python, aucune dépendance système).
  Si `svglib` n'est pas installé, les SVG d'ici sont **ignorés silencieusement**
  et les poses intégrées prennent le relais : un rendu n'échoue jamais à cause
  d'un SVG.
- Un SVG illisible est signalé sur stderr et ignoré, pas fatal.
