#!/usr/bin/env node
/**
 * AutoEdit HyperFrames-compatible overlay renderer.
 *
 * Renders one HTML/CSS overlay template into a chroma-key MP4. The final
 * FFmpegRenderer keys out #00ff00 and composites it on the edited video.
 */
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");
const puppeteer = require("puppeteer-core");

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
  "4:5": [1080, 1350],
};
const [w, h] = RES[args.aspect] || RES["9:16"];

function escapeHtml(value) {
  return String(value ?? "").replace(/[<>&"']/g, (c) =>
    ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function findChromium() {
  const candidates = [
    process.env.PUPPETEER_EXECUTABLE_PATH,
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
  ].filter(Boolean);
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  throw new Error("Chromium introuvable. Set PUPPETEER_EXECUTABLE_PATH ou installe chromium-browser.");
}

async function main() {
  const templatePath = path.resolve(args.template);
  if (!fs.existsSync(templatePath)) throw new Error(`Template introuvable: ${templatePath}`);
  const props = JSON.parse(args.props || "{}");
  let html = fs.readFileSync(templatePath, "utf-8");
  const normalized = {
    kind: props.kind || "lower_third",
    step: props.step || "•",
    title: props.title || props.text || "AutoEdit",
    subtitle: props.subtitle || props.role || "Montage premium",
    ...props,
  };
  for (const [key, value] of Object.entries(normalized)) {
    html = html.replaceAll(`{{${key}}}`, escapeHtml(value));
  }
  // Remove any unreplaced mustache placeholders.
  html = html.replace(/{{[^}]+}}/g, "");

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "autoedit-hf-"));
  const framesDir = path.join(tmpDir, "frames");
  fs.mkdirSync(framesDir, { recursive: true });
  const htmlPath = path.join(tmpDir, "overlay.html");
  fs.writeFileSync(htmlPath, html);

  const browser = await puppeteer.launch({
    executablePath: findChromium(),
    headless: "new",
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: w, height: h, deviceScaleFactor: 1 });
    await page.goto(`file://${htmlPath}`, { waitUntil: "networkidle0" });
    const frames = Math.max(1, Math.round(args.duration * args.fps));
    const start = Date.now();
    for (let i = 0; i < frames; i++) {
      const targetElapsed = (i / args.fps) * 1000;
      const delay = Math.max(0, targetElapsed - (Date.now() - start));
      if (delay) await new Promise((resolve) => setTimeout(resolve, delay));
      const framePath = path.join(framesDir, `frame_${String(i).padStart(5, "0")}.png`);
      await page.screenshot({ path: framePath, omitBackground: false });
    }
  } finally {
    await browser.close();
  }

  fs.mkdirSync(path.dirname(path.resolve(args.out)), { recursive: true });
  const ffmpeg = spawnSync("ffmpeg", [
    "-y", "-hide_banner", "-loglevel", "error",
    "-framerate", String(args.fps),
    "-i", path.join(framesDir, "frame_%05d.png"),
    "-c:v", "libx264",
    "-pix_fmt", "yuv420p",
    "-r", String(args.fps),
    "-movflags", "+faststart",
    args.out,
  ], { encoding: "utf-8" });
  if (ffmpeg.status !== 0) {
    throw new Error(`ffmpeg encode failed: ${ffmpeg.stderr || ffmpeg.stdout}`);
  }
  const stat = fs.statSync(args.out);
  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log(JSON.stringify({ ok: true, out: args.out, bytes: stat.size, resolution: `${w}x${h}`, fps: args.fps, duration: args.duration }, null, 2));
}

main().catch((err) => {
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
});
