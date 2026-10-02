#!/usr/bin/env node
/*
 * Rendu d'une page « pub explicative » (window.seek / window.READY).
 *
 *   node render.js page.html --events events.json
 *   node render.js page.html --stills 1.2,3.4 --outdir stills/
 *   node render.js page.html --video part.mp4 --from 0 --to 450 --fps 30 --sub 3
 *
 * Utilise puppeteer-core (image Docker CutForge, Chromium système) ou, à défaut,
 * playwright (développement).
 */
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

const argv = process.argv.slice(2);
const page = argv[0];
const opt = {};
for (let i = 1; i < argv.length; i += 2) opt[argv[i].replace(/^--/, '')] = argv[i + 1];

const VW = +(opt.w || 1080), VH = +(opt.h || 1920);

async function launch() {
  const exe = process.env.PUPPETEER_EXECUTABLE_PATH || process.env.CHROMIUM_PATH;
  try {
    const pp = require('puppeteer-core');
    const candidates = [exe, '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome'].filter(Boolean);
    const bin = candidates.find((p) => { try { return fs.existsSync(p); } catch (e) { return false; } });
    if (!bin) throw new Error('no chromium');
    const b = await pp.launch({ executablePath: bin, headless: 'new', args: ['--no-sandbox', '--disable-dev-shm-usage', '--font-render-hinting=none', '--force-color-profile=srgb'] });
    const p = await b.newPage(); await p.setViewport({ width: VW, height: VH, deviceScaleFactor: 1 });
    return { b, p, shot: (o) => p.screenshot(o), cdp: () => p.target().createCDPSession(), close: () => b.close() };
  } catch (e) {
    const { chromium } = require('playwright');
    const b = await chromium.launch({ args: ['--font-render-hinting=none'] });
    const p = await b.newPage({ viewport: { width: VW, height: VH } });
    return { b, p, shot: (o) => p.screenshot(o), cdp: () => p.context().newCDPSession(p), close: () => b.close() };
  }
}

(async () => {
  const { p, shot, cdp, close } = await launch();
  const errors = [];
  p.on('pageerror', (e) => errors.push(String(e && e.message || e)));
  p.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await p.goto('file://' + path.resolve(page) + '?render', { waitUntil: 'load' });
  await p.evaluate(() => window.READY);
  const info = await p.evaluate(() => ({ T: window.DURATION, n: (window.EVENTS || []).length }));

  if (opt.events) {
    const evs = await p.evaluate(() => window.EVENTS);
    fs.writeFileSync(opt.events, JSON.stringify({ duration: info.T, events: evs, errors }, null, 1));
  }
  if (opt.stills) {
    fs.mkdirSync(opt.outdir || '.', { recursive: true });
    const ts = opt.stills.split(',').map(Number);
    for (let i = 0; i < ts.length; i++) {
      await p.evaluate((t) => window.seekAsync ? window.seekAsync(t) : window.seek(t), ts[i]);
      await shot({ path: path.join(opt.outdir || '.', `still_${String(i).padStart(3, '0')}.png`), omitBackground: opt.alpha === '1' });
    }
  }
  if (opt.video) {
    const FPS = +(opt.fps || 30), K = +(opt.sub || 3), f0 = +(opt.from || 0);
    const f1 = +(opt.to || Math.round(info.T * FPS));
    const ALPHA = opt.alpha === '1';
    const enc = ALPHA ? ['-c:v', 'prores_aw', '-profile:v', '4', '-pix_fmt', 'yuva444p10le']
      : ['-c:v', 'libx264', '-crf', '17', '-preset', 'veryfast', '-pix_fmt', 'yuv420p'];
    // Alpha: capture CDP PNG « rapide » (≈4x plus rapide que screenshot omitBackground).
    // Une ligne de 1 px toujours transparente garantit que CHAQUE image garde son canal
    // alpha (sinon Chromium encode les images opaques en RGB et ffmpeg perd des images).
    let grab = null;
    if (ALPHA) {
      const cs = await cdp();
      await cs.send('Emulation.setDefaultBackgroundColorOverride', { color: { r: 0, g: 0, b: 0, a: 0 } });
      await p.addStyleTag({ content: 'body{clip-path:inset(0 0 1px 0)}' });
      grab = async () => Buffer.from((await cs.send('Page.captureScreenshot', { format: 'png', optimizeForSpeed: true })).data, 'base64');
    }
    const ff = spawn(process.env.FFMPEG_BIN || 'ffmpeg', ['-loglevel', 'error', '-y', '-f', 'image2pipe', '-framerate', String(FPS * K), '-c:v', ALPHA ? 'png' : 'mjpeg', '-i', '-',
      '-vf', `${ALPHA ? 'format=rgba,' : ''}tmix=frames=${K},select='eq(mod(n\\,${K})\\,${K - 1})',setpts=N/(${FPS})/TB`, '-r', String(FPS),
      ...enc, opt.video]);
    ff.stderr.on('data', (d) => process.stderr.write(d));
    for (let f = f0; f < f1; f++) {
      for (let k = 0; k < K; k++) {
        const t = Math.max(0, f / FPS + (k - (K - 1) / 2) / (FPS * 2 * K));
        await p.evaluate((tt) => window.seekAsync ? window.seekAsync(tt) : window.seek(tt), t);
        const buf = ALPHA ? await grab() : await shot({ type: 'jpeg', quality: 92 });
        if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
      }
      if (opt.progress && f % 15 === 0) fs.writeFileSync(opt.progress, String((f - f0) / Math.max(1, f1 - f0)));
    }
    ff.stdin.end(); await new Promise((r) => ff.on('close', r));
  }
  if (errors.length) console.error('PAGE_ERRORS', JSON.stringify(errors.slice(0, 5)));
  await close();
})().catch((e) => { console.error(e); process.exit(1); });
