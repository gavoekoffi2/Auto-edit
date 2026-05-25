# AutoEdit — templates de rendu

Templates de rendu **optionnels** consommés par `backend/app/processing/template_renderer.py`
quand `VIDEO_RENDERER` vaut `remotion` ou `hyperframes`.

Le pipeline V2 fonctionne sans ces templates (renderer `ffmpeg` par défaut).
Ils sont prévus pour la Phase 2 quand on veut des overlays plus riches
(intro cards animées, lower thirds dynamiques, CTA stylisés…).

## Arborescence

```
templates/
├── remotion/         # Compositions React rendues via `npx remotion render`
│   ├── package.json
│   ├── remotion.config.ts
│   └── src/
│       ├── index.tsx
│       ├── Root.tsx
│       └── IntroCard.tsx
└── hyperframes/      # Templates HTML/CSS/JS rendus via le projet HeyGen HyperFrames
    ├── package.json
    ├── render.js
    └── lower_third.html
```

## Remotion

### Install

```bash
cd templates/remotion
npm install
```

### Render un IntroCard (CLI)

```bash
npx remotion render src/index.tsx IntroCard \
  out/intro.mp4 \
  --props='{"title":"Lance ton e-commerce","subtitle":"Cours offert"}' \
  --width 1080 --height 1920 --fps 30 --duration 60
```

Le `backend/app/processing/template_renderer.py` appellera cette commande
quand l'override `VIDEO_RENDERER=remotion` sera défini et qu'on aura ajouté
le binding `_remotion_overlay`.

## HyperFrames

`render.js` est un wrapper Node minimal qui prend un template HTML, le
remplit avec des props, et l'enregistre en MP4 via FFmpeg + Puppeteer (ou
le SDK officiel HeyGen quand il sera publié).

### Install (à venir — sidecar Node)

```bash
cd templates/hyperframes
npm install
```

### Render un lower third

```bash
node render.js \
  --template lower_third.html \
  --props='{"name":"Kossi A.","role":"Founder"}' \
  --out out/lower_third.mp4 \
  --aspect 9:16
```

> ⚠️ Ces scripts sont des **squelettes documentés**. Ils ne sont pas
> exécutés par le pipeline V2 actuel. Voir
> `docs/VIDEO_PIPELINE_ARCHITECTURE.md` §7 pour la roadmap d'intégration.
