#!/usr/bin/env node
/**
 * AutoEdit — wrapper minimal HyperFrames-style.
 *
 * Prend un template HTML, le sert localement, capture frame-par-frame via
 * Puppeteer, puis encode en MP4 via FFmpeg. Compatible avec un usage
 * "renderer=hyperframes" depuis `template_renderer.py`.
 *
 * Usage:
 *   node render.js \
 *     --template lower_third.html \
 *     --props='{"name":"Kossi A.","role":"Founder"}' \
 *     --out out/lower_third.mp4 \
 *     --duration 3 \
 *     --aspect 9:16
 *
 * NOTE: ce fichier est un *squelette documenté* — l'intégration complète
 * sera faite en Phase 2 dans un container Docker Node séparé. Voir
 * `docs/VIDEO_PIPELINE_ARCHITECTURE.md` §7.
 */
const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const args = require("yargs/yargs")(process.argv.slice(2))
  .option("template", { type: "string", demandOption: true })
  .option("props", { type: "string", default: "{}" })
  .option("out", { type: "string", demandOption: true })
  .option("duration", { type: "number", default: 3 })
  .option("aspect", { type: "string", default: "9:16" })
  .option("fps", { type: "number", default: 30 })
  .parse();

const RES = {
  "9:16": [1080, 1920],
  "16:9": [1920, 1080],
  "1:1": [1080, 1080],
};
const [w, h] = RES[args.aspect] || RES["9:16"];

async function main() {
  const templatePath = path.resolve(args.template);
  if (!fs.existsSync(templatePath)) {
    console.error(`Template introuvable: ${templatePath}`);
    process.exit(1);
  }

  // 1. Lit le template + injecte les props
  let html = fs.readFileSync(templatePath, "utf-8");
  const props = JSON.parse(args.props);
  for (const [key, value] of Object.entries(props)) {
    const safe = String(value).replace(/[<>&"']/g, (c) =>
      ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;", "'": "&#39;" }[c])
    );
    html = html.replaceAll(`{{${key}}}`, safe);
  }

  // 2. Phase 2: lance Puppeteer en mode "screencast" et capture chaque frame.
  // Pour l'instant on documente l'API attendue.
  console.log(JSON.stringify({
    ok: true,
    template: templatePath,
    props,
    out: args.out,
    resolution: `${w}x${h}`,
    fps: args.fps,
    duration: args.duration,
    note: "Implémentation Puppeteer + ffmpeg encodage en Phase 2. "
        + "Pour le MVP, le pipeline V2 utilise renderer=ffmpeg.",
  }, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
