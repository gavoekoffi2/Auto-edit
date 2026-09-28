/* CutForge — moteur « Pub explicative ».
 *
 * Page 1080x1920 dont chaque image est une fonction pure du temps: seek(t).
 * Aucune transition CSS, aucun timer: n'importe quelle image peut être rendue
 * seule (rendu parallèle par tranches + flou de mouvement par sous-images).
 *
 * Entrée:  window.STORY = { duration, template, shots:[{start,end,words,scene,tone}], brand }
 * Sortie:  window.seek(t), window.DURATION, window.EVENTS (repères SFX), window.READY
 */
(function () {
  'use strict';
  const STORY = window.STORY;
  const TPL = STORY.template;
  const C = TPL.colors;
  const W = 1080, H = 1920;

  // ------------------------------------------------------------------ utils
  const $ = (id) => document.getElementById(id);
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const lerp = (a, b, u) => a + (b - a) * u;
  const eo = (x) => { x = clamp(x); return 1 - Math.pow(1 - x, 3); };
  const eio = (x) => { x = clamp(x); return x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
  // réponse indicielle d'un ressort amorti (forme close)
  const S = (tau, w = 14, z = 0.62) => {
    if (tau <= 0) return 0;
    if (z < 1) { const wd = w * Math.sqrt(1 - z * z); return 1 - Math.exp(-z * w * tau) * (Math.cos(wd * tau) + z * w / wd * Math.sin(wd * tau)); }
    return 1 - Math.exp(-w * tau) * (1 + w * tau);
  };
  const pop = (t, t0, w = 16, z = 0.55) => S(t - t0, w, z);
  const vis = (el, o) => { el.style.opacity = o.toFixed(3); el.style.visibility = o < 0.003 ? 'hidden' : 'visible'; };
  const tf = (el, s) => { el.style.transform = s; };
  const rnd = (i) => { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const norm = (s) => String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9%]/g, '');
  const up = (s) => (TPL.textCase === 'upper' ? String(s).toUpperCase() : String(s));
  const mk = (parent, cls, html, style) => { const d = document.createElement('div'); if (cls) d.className = cls; if (html != null) d.innerHTML = html; if (style) d.style.cssText = style; parent.appendChild(d); return d; };

  // ------------------------------------------------------------------ SFX events
  const EVENTS = [];
  const ev = (t, name, gain = 1) => { if (isFinite(t) && t >= 0) EVENTS.push({ t: +t.toFixed(3), sfx: name, gain }); };
  const IMPACTS = [];

  // ------------------------------------------------------------------ icons (Lucide, ISC)
  const IC = {
    user: '<circle cx="12" cy="7" r="4"/><path d="M5 21v-2a4 4 0 0 1 4-4h6a4 4 0 0 1 4 4v2"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    family: '<circle cx="9" cy="7" r="3"/><circle cx="17" cy="9" r="2.4"/><path d="M3 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2M15 21v-1.5a3 3 0 0 1 3-3h1a3 3 0 0 1 3 3V21"/>',
    briefcase: '<path d="M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/><rect x="2" y="6" width="20" height="14" rx="2"/>',
    building: '<path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2M10 6h4M10 10h4M10 14h4M10 18h4"/>',
    store: '<path d="M3 9h18l-2-5H5Z"/><path d="M5 9v11h14V9M9 20v-6h6v6"/>',
    scale: '<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1ZM2 16l3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1ZM7 21h10M12 3v18M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>',
    stethoscope: '<path d="M11 2v2M5 2v2M5 3H4a2 2 0 0 0-2 2v4a6 6 0 0 0 12 0V5a2 2 0 0 0-2-2h-1M8 15a6 6 0 0 0 12 0v-3"/><circle cx="20" cy="10" r="2"/>',
    heart: '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>',
    hospital: '<path d="M12 6v4M14 8h-4M18 12h2a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2h2"/><path d="M18 22V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v18M10 22v-4h4v4"/>',
    shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    coin: '<circle cx="12" cy="12" r="10"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8M12 18V6"/>',
    wallet: '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
    trendUp: '<path d="M22 7 13.5 15.5 8.5 10.5 2 17"/><path d="M16 7h6v6"/>',
    trendDown: '<path d="M22 17 13.5 8.5 8.5 13.5 2 7"/><path d="M16 17h6v-6"/>',
    chart: '<path d="M3 3v18h18"/><path d="M7 16v-4M12 16V8M17 16v-7"/>',
    percent: '<path d="M19 5 5 19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/>',
    clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    phone: '<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M12 18h.01"/>',
    message: '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>',
    cart: '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>',
    truck: '<path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2M15 18H9M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.62l-3.48-4.35A1 1 0 0 0 17.52 8H14"/><circle cx="17" cy="18" r="2"/><circle cx="7" cy="18" r="2"/>',
    home: '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z"/>',
    car: '<path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9L18.7 10.6 16 6H8l-2.7 4.6L3.5 11.1C2.7 11.3 2 12.1 2 13v3c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><circle cx="17" cy="17" r="2"/>',
    graduation: '<path d="M22 10 12 5 2 10l10 5 10-5Z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/>',
    book: '<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/>',
    rocket: '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09Z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2Z"/>',
    target: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    bulb: '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5M9 18h6M10 22h4"/>',
    lock: '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    key: '<circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6M15.5 7.5l3 3L22 7l-3-3"/>',
    star: '<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z"/>',
    gift: '<rect x="3" y="8" width="18" height="4" rx="1"/><path d="M12 8v13M19 12v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-7M7.5 8a2.5 2.5 0 0 1 0-5C11 3 12 8 12 8s1-5 4.5-5a2.5 2.5 0 0 1 0 5"/>',
    sparkle: '<path d="M9.94 15.5A2 2 0 0 0 8.5 14.06l-6.14-1.58a.5.5 0 0 1 0-.96L8.5 9.94A2 2 0 0 0 9.94 8.5l1.58-6.14a.5.5 0 0 1 .96 0L14.06 8.5A2 2 0 0 0 15.5 9.94l6.14 1.58a.5.5 0 0 1 0 .96L15.5 14.06a2 2 0 0 0-1.44 1.44l-1.58 6.14a.5.5 0 0 1-.96 0z"/>',
    globe: '<circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
    bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    camera: '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/>',
    video: '<path d="m22 8-6 4 6 4V8Z"/><rect x="2" y="6" width="14" height="12" rx="2"/>',
    mic: '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v3"/>',
    tool: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
    leaf: '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>',
    food: '<path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2M7 2v20M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7"/>',
    plane: '<path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"/>',
    school: '<path d="M14 22v-4a2 2 0 1 0-4 0v4M18 10l4 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-8l4-2M18 5v17M4 6l8-4 8 4M6 5v17"/><circle cx="12" cy="9" r="2"/>',
    arrowRight: '<path d="M5 12h14M13 5l7 7-7 7"/>',
    arrowDown: '<path d="M12 5v14M19 12l-7 7-7-7"/>',
    alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4M12 17h.01"/>',
    hourglass: '<path d="M5 22h14M5 2h14M17 22v-4.17a2 2 0 0 0-.59-1.42L12 12l-4.41 4.41A2 2 0 0 0 7 17.83V22M7 2v4.17a2 2 0 0 0 .59 1.42L12 12l4.41-4.41A2 2 0 0 0 17 6.17V2"/>',
    handshake: '<path d="m11 17 2 2a1 1 0 1 0 3-3M14 14l2.5 2.5a1 1 0 1 0 3-3l-3.88-3.88a3 3 0 0 0-4.24 0l-.88.88a1 1 0 1 1-3-3l2.81-2.81a5.79 5.79 0 0 1 7.06-.87l.47.28a2 2 0 0 0 1.42.25L21 4M21 3l1 11h-2M3 3 2 14l6.5 6.5a1 1 0 1 0 3-3M3 4h8"/>',
    crown: '<path d="m2 4 3 12h14l3-12-6 7-4-7-4 7-6-7zm3 16h14"/>',
    bolt: '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
  };
  const icon = (n, sz, col, sw = 2) => `<svg width="${sz}" height="${sz}" viewBox="0 0 24 24" fill="none" stroke="${col}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round">${IC[n] || IC.sparkle}</svg>`;

  // ------------------------------------------------------------------ time helpers
  // Instant où un mot (ou le début d'un mot) est prononcé dans le plan.
  function wordTime(shot, token, frac) {
    const fallback = shot.start + (shot.speechEnd - shot.start) * (frac == null ? 0.5 : frac);
    if (typeof token === 'number' && isFinite(token)) return token; // instant absolu fourni par le planificateur
    if (!token) return fallback;
    const parts = String(token).split(/\s+/).map(norm).filter(Boolean);
    if (!parts.length) return fallback;
    const ws = shot.words;
    for (let i = 0; i < ws.length; i++) {
      if (norm(ws[i].w).startsWith(parts[0]) || (parts[0].length > 3 && norm(ws[i].w).startsWith(parts[0].slice(0, 4)))) {
        return ws[i].s;
      }
    }
    return fallback;
  }
  // n instants répartis, chacun collé à son mot si possible.
  function itemTimes(shot, items, t0, t1) {
    const n = items.length;
    const a = t0 == null ? shot.start + 0.15 : t0, b = t1 == null ? shot.speechEnd - 0.2 : t1;
    let prev = -1;
    return items.map((it, i) => {
      let t = it && it.at ? wordTime(shot, it.at, null) : NaN;
      const even = a + (b - a) * (n <= 1 ? 0 : i / (n - 1)) * 0.85;
      if (!isFinite(t) || (it && it.at && t === shot.start + (shot.speechEnd - shot.start) * 0.5)) t = even;
      if (t <= prev + 0.25) t = prev + 0.35;
      prev = t; return t;
    });
  }

  // ------------------------------------------------------------------ kinetic text
  // Texte qui tombe lettre par lettre. `hl` = mots mis en couleur d'accent.
  function prepDrop(el, text, hl) {
    const hls = (hl || []).map(norm);
    const words = String(text).replace(/ ([?!:;»%])/g, '\u00a0$1').replace(/(«) /g, '$1\u00a0').split(/ +/).filter(Boolean);
    el.innerHTML = words.map((w, wi) => {
      if (w === '|') return '<br>';
      const isHl = hls.some((h) => h && norm(w).startsWith(h));
      const inner = [...w].map((c) => `<span class="ch">${esc(c)}</span>`).join('');
      return `<span class="wd${isHl ? ' hl' : ''}">${inner}</span>`;
    }).join(' ');
    el._ch = [...el.querySelectorAll('.ch')];
  }
  function drop(el, t, t0, st = 0.026) {
    const n = el._ch.length; st = Math.min(st, 0.9 / Math.max(1, n));
    el._ch.forEach((c, i) => {
      const s = pop(t, t0 + i * st, 18, 0.5);
      c.style.opacity = clamp(s * 1.6).toFixed(3);
      c.style.transform = `translateY(${((1 - s) * -80).toFixed(1)}px) rotate(${((1 - s) * -12).toFixed(1)}deg) scale(${(0.6 + 0.4 * clamp(s, 0, 1.2)).toFixed(3)})`;
    });
  }
  function dropEvents(el, t0, st = 0.026) { const n = el._ch.length; st = Math.min(st, 0.9 / Math.max(1, n)); for (let i = 0; i < n; i += 2) ev(t0 + i * st, 'tick', 0.8); }
  // Taille de police qui fait tenir le texte dans maxW x maxLines.
  function fit(el, maxW, maxSize, minSize, maxH) {
    let s = maxSize; el.style.fontSize = s + 'px';
    while (s > minSize && (el.scrollWidth > maxW + 2 || el.offsetWidth > maxW + 2 || (maxH && el.scrollHeight > maxH))) { s -= 4; el.style.fontSize = s + 'px'; }
    return s;
  }

  // ------------------------------------------------------------------ illustrations
  function person(x, y, sc, mood = 'neutral', op = 1, tone = 'light') {
    const good = mood === 'good', bad = mood === 'bad';
    const coat = bad ? '#c9ccd3' : (tone === 'light' ? '#ffffff' : '#f4f5f8');
    const tie = bad ? '#7a808c' : C.accent;
    const skin = bad ? '#6f5040' : '#8a5a3c';
    const mouth = good ? '<path d="M-24 -36 q24 22 48 0" fill="none" stroke="#1b1b1b" stroke-width="6" stroke-linecap="round"/>'
      : bad ? '<path d="M-22 -30 q22 -12 44 0" fill="none" stroke="#1b1b1b" stroke-width="6" stroke-linecap="round"/><path d="M-36 -82 l20 6 M36 -82 l-20 6" stroke="#1b1b1b" stroke-width="5" stroke-linecap="round"/>'
      : '<path d="M-18 -34 h36" stroke="#1b1b1b" stroke-width="6" stroke-linecap="round"/>';
    return `<g transform="translate(${x.toFixed(1)} ${y.toFixed(1)}) scale(${sc.toFixed(3)})" opacity="${op.toFixed(2)}"><ellipse cx="0" cy="192" rx="125" ry="18" fill="rgba(0,0,0,.25)"/>
    <path d="M-120 190 v-70 a90 90 0 0 1 90-90 h60 a90 90 0 0 1 90 90 v70Z" fill="${coat}"/>
    <path d="M-30 30 l30 80 l30-80Z" fill="${bad ? '#aeb2ba' : '#dfe6f5'}"/><path d="M0 44 l-12 18 l12 62 l12-62Z" fill="${tie}"/>
    <rect x="-22" y="-12" width="44" height="46" rx="10" fill="${skin}"/><circle cx="0" cy="-70" r="68" fill="${skin}"/>
    <path d="M-68 -78 a68 68 0 0 1 136 0 q-68 -34 -136 0Z" fill="#161616"/>
    <circle cx="-24" cy="-66" r="7" fill="#1b1b1b"/><circle cx="24" cy="-66" r="7" fill="#1b1b1b"/>${mouth}</g>`;
  }
  function coin(x, y, r) {
    const ry = r * 0.34;
    return `<ellipse cx="${x}" cy="${y + 10}" rx="${r}" ry="${ry}" fill="#9a6a06"/><rect x="${x - r}" y="${y}" width="${2 * r}" height="10" fill="#b57d0a"/><ellipse cx="${x}" cy="${y}" rx="${r}" ry="${ry}" fill="url(#cg)" stroke="#FFE39A" stroke-width="2"/><ellipse cx="${x}" cy="${y}" rx="${r * 0.62}" ry="${ry * 0.62}" fill="none" stroke="#c98a0b" stroke-width="3"/>`;
  }
  const COIN_DEFS = '<defs><linearGradient id="cg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFE39A"/><stop offset="1" stop-color="#E0A21A"/></linearGradient></defs>';
  // Emblème 3D extrudé: 14 couches SVG empilées en preserve-3d.
  const EMBLEM = {
    shield: { vb: '3.6 1.6 16.8 20.8', d: 'M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z', mark: 'M8 12.5l3 3 5.5-6', ratio: 1.15 },
    star: { vb: '1.6 1.6 20.8 20', d: 'M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z', mark: '', ratio: 0.96 },
    bolt: { vb: '2.6 1.6 18.8 20.8', d: 'M13 2 3 14h9l-1 8 10-12h-9l1-8z', mark: '', ratio: 1.1 },
    circle: { vb: '1.6 1.6 20.8 20.8', d: 'M12 2a10 10 0 1 0 0 20 10 10 0 1 0 0-20z', mark: 'M7.5 12.5l3 3 6-7', ratio: 1 },
    crown: { vb: '1.4 3.4 21.2 17.4', d: 'M2 4l3 12h14l3-12-6 7-4-7-4 7-6-7zM5 17h14v3H5z', mark: '', ratio: 0.82 },
  };
  let _emb = 0;
  function emblem(el, kind, w, depth = 34) {
    const E = EMBLEM[kind] || EMBLEM.shield; const h = Math.round(w * E.ratio); const id = 'eg' + (++_emb);
    let s = ''; const N = 14;
    for (let i = 0; i < N; i++) {
      const z = -depth / 2 + depth * i / (N - 1); const top = i === N - 1;
      s += `<svg class="a" style="left:0;top:0;transform:translateZ(${z.toFixed(1)}px)" width="${w}" height="${h}" viewBox="${E.vb}">` +
        (top ? `<defs><linearGradient id="${id}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${C.accentLight}"/><stop offset=".45" stop-color="${C.accent}"/><stop offset="1" stop-color="${C.accentDark}"/></linearGradient></defs><path d="${E.d}" fill="url(#${id})"/>${E.mark ? `<path d="${E.mark}" fill="none" stroke="${C.onAccent}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>` : ''}<path d="${E.d}" fill="none" stroke="#fff" stroke-opacity=".5" stroke-width=".25"/>`
          : `<path d="${E.d}" fill="${i % 2 ? C.accentDeep : C.accentDark}"/>`) + '</svg>';
    }
    el.style.width = w + 'px'; el.style.height = h + 'px'; el.style.transformStyle = 'preserve-3d';
    el.innerHTML = s; return h;
  }
  function rays(svg, col) {
    let s = ''; for (let i = 0; i < 24; i++) { const a = i * Math.PI / 12; s += `<path d="M960 960 L${960 + 1400 * Math.cos(a - 0.06)} ${960 + 1400 * Math.sin(a - 0.06)} L${960 + 1400 * Math.cos(a + 0.06)} ${960 + 1400 * Math.sin(a + 0.06)}Z" fill="${col}"/>`; }
    svg.innerHTML = `<g>${s}</g>`;
  }
  function chevrons(svg, col, w, h) {
    let s = ''; for (let i = 0; i < 3; i++) s += `<path d="M${w * 0.15} ${20 + i * h * 0.3} L${w / 2} ${20 + i * h * 0.3 + w * 0.3} L${w * 0.85} ${20 + i * h * 0.3}" fill="none" stroke="${col}" stroke-width="${Math.round(w * 0.09)}" stroke-linecap="round" stroke-linejoin="round"/>`;
    svg.innerHTML = s; return [...svg.children];
  }
  const HAND = '<svg viewBox="0 0 34 40" width="170" height="200"><path d="M9 18V5.5a2.5 2.5 0 0 1 5 0V15l1-.5a2.5 2.5 0 0 1 3 .5V16l1-.3a2.5 2.5 0 0 1 3 1.3l1 .2a2.5 2.5 0 0 1 2.5 2.5V28c0 5-3 9-8 9h-3c-3 0-5-1.5-6.5-4L5 25a2.3 2.3 0 0 1 3.7-2.7L9 23z" fill="#fff" stroke="#0B1B3A" stroke-width="1.6" stroke-linejoin="round"/></svg>';
  const CURSOR = '<svg viewBox="0 0 40 56" width="62" height="86"><path d="M3 3 L3 41 L12.5 32 L19 47 L25.5 44.2 L19.2 29.8 L32 29.8 Z" fill="#0B1B3A" stroke="#fff" stroke-width="2.6" stroke-linejoin="round"/></svg>';

  // Couleurs de texte selon le fond du plan.
  const inkFor = (tone) => (tone === 'light' ? C.ink : C.paper);
  const subFor = (tone) => (tone === 'light' ? C.inkSoft : C.paperSoft);

  // ================================================================== SCENES
  // Chaque scène: build(root, shot, ctx) -> update(t). Elle enregistre ses SFX via ev().
  const SC = {};

  // 1. Titre choc (accroche, question, affirmation)
  SC.title_slam = function (root, shot, p) {
    const ink = inkFor(shot.tone);
    const big = mk(root, 'a anton ctr', '', `top:260px;font-size:1000px;color:${C.accent};opacity:.08;line-height:1`);
    big.textContent = p.glyph || (/\?\s*$/.test(p.title || '') ? '?' : '!');
    const kick = p.kicker ? mk(root, 'a ctr', esc(up(p.kicker)), `top:430px;font-size:40px;font-weight:700;letter-spacing:.22em;color:${subFor(shot.tone)}`) : null;
    const tt = mk(root, 'a anton ctr head', '', `top:560px;left:70px;width:940px;color:${ink};line-height:1.02`);
    prepDrop(tt, up(p.title || ''), p.highlight);
    fit(tt, 940, 190, 84, 600);
    const sub = p.sub ? mk(root, 'a ctr', esc(p.sub), `top:${560 + tt.scrollHeight + 50}px;left:90px;width:900px;font-size:50px;font-weight:700;color:${subFor(shot.tone)};line-height:1.25`) : null;
    const t0 = wordTime(shot, p.at, 0) , tSub = p.sub ? wordTime(shot, p.sub_at, 0.55) : 0;
    ev(t0, 'impact', 0.8); dropEvents(tt, t0); if (sub) ev(tSub, 'pop', 0.8);
    IMPACTS.push(t0);
    return (t) => {
      tf(big, `rotateY(${((t - shot.start) * 35).toFixed(1)}deg)`);
      if (kick) vis(kick, clamp((t - shot.start) / 0.3));
      drop(tt, t, t0);
      if (sub) { const u = clamp((t - tSub) / 0.3); vis(sub, u); tf(sub, `translateY(${((1 - eo(u)) * 30).toFixed(0)}px)`); }
    };
  };

  // 2. Cartes icône + libellé (cibles, étapes, catégories)
  SC.icon_cards = function (root, shot, p) {
    const items = (p.items || []).slice(0, 5); const n = Math.max(1, items.length);
    const ink = inkFor(shot.tone);
    const title = p.title ? mk(root, 'a anton ctr', esc(up(p.title)), `top:300px;left:60px;width:960px;color:${ink}`) : null;
    if (title) fit(title, 960, 110, 60);
    const gap = 26, availTop = title ? 470 : 380, avail = 1560 - availTop;
    const ch = Math.min(250, (avail - gap * (n - 1)) / n);
    const block = n * ch + (n - 1) * gap, top0 = Math.max(availTop, Math.round(1010 - block / 2));
    if (title) title.style.top = (top0 - 170) + 'px';
    const cards = items.map((it, i) => {
      const c = mk(root, 'card', '', `left:90px;top:${top0 + i * (ch + gap)}px;width:900px;height:${ch}px;background:${shot.tone === 'light' ? '#fff' : 'rgba(255,255,255,.10)'};border:2px solid ${shot.tone === 'light' ? '#E6E9F0' : 'rgba(255,255,255,.18)'}`);
      const s = ch - 70;
      c.innerHTML = `<div class="a ib" style="left:35px;top:35px;width:${s}px;height:${s}px;border-radius:${s * 0.26}px;background:${C.accent};display:flex;align-items:center;justify-content:center">${icon(it.icon, s * 0.6, C.onAccent, 2)}</div>`;
      const lab = mk(c, 'a anton', esc(up(it.label || '')), `left:${s + 70}px;top:0;height:${ch}px;display:flex;align-items:center;color:${ink};white-space:nowrap`);
      fit(lab, 900 - s - 110, Math.min(110, ch * 0.45), 40);
      c._ib = c.querySelector('.ib');
      return c;
    });
    const ts = itemTimes(shot, items);
    ts.forEach((t) => { ev(t - 0.12, 'whoosh', 0.5); ev(t, 'impact', 0.45); });
    return (t) => {
      if (title) vis(title, clamp((t - shot.start) / 0.25));
      cards.forEach((c, i) => {
        const s = pop(t, ts[i], 13, 0.6); vis(c, clamp((t - ts[i]) * 6));
        const act = t >= ts[i] && (i === n - 1 || t < ts[i + 1]);
        tf(c, `perspective(1400px) rotateX(${((1 - s) * -95).toFixed(1)}deg) scale(${act ? 1.03 : 1})`);
        c.style.borderColor = act ? C.accent : (shot.tone === 'light' ? '#E6E9F0' : 'rgba(255,255,255,.18)');
      });
    };
  };

  // 3. Liste d'avantages cochés
  SC.checklist = function (root, shot, p) {
    const items = (p.items || []).slice(0, 4); const n = Math.max(1, items.length);
    const ink = inkFor(shot.tone);
    const title = mk(root, 'a anton ctr', esc(up(p.title || '')), `top:300px;left:60px;width:960px;color:${ink}`); fit(title, 960, 110, 60);
    const ch = Math.min(300, (1100 - 30 * (n - 1)) / n), block = n * ch + (n - 1) * 30, top0 = Math.max(470, Math.round(1000 - block / 2));
    title.style.top = (top0 - 170) + 'px';
    const cards = items.map((it, i) => {
      const c = mk(root, 'card', '', `left:70px;top:${top0 + i * (ch + 30)}px;width:940px;height:${ch}px;background:#fff;border:2px solid #E6E9F0;box-shadow:0 30px 60px -25px rgba(0,0,0,.35)`);
      const s = Math.min(200, ch - 80);
      c.innerHTML = `<div class="a" style="left:36px;top:${(ch - s) / 2}px;width:${s}px;height:${s}px;border-radius:${s * 0.22}px;background:${C.dark1};display:flex;align-items:center;justify-content:center">${icon(it.icon || 'check', s * 0.55, C.accent, 2)}</div>
        <div class="a ck" style="right:30px;top:30px;width:72px;height:72px;border-radius:50%;background:${C.accent};display:flex;align-items:center;justify-content:center">${icon('check', 44, C.onAccent, 3)}</div>`;
      const txt = mk(c, 'a', '', `left:${s + 80}px;top:0;height:${ch}px;width:${940 - s - 200}px;display:flex;flex-direction:column;justify-content:center;color:${C.ink}`);
      txt.innerHTML = `<div style="font-size:46px;font-weight:700;line-height:1.15">${esc(it.label || '')}</div>${it.detail ? `<div class="hlw" style="margin-top:8px;font-size:46px;font-weight:800;line-height:1.15;align-self:flex-start;padding:0 12px;border-radius:10px">${esc(it.detail)}</div>` : ''}`;
      fit(txt.firstElementChild, 940 - s - 200, 50, 30);
      c._ck = c.querySelector('.ck'); c._hl = c.querySelector('.hlw');
      return c;
    });
    const ts = itemTimes(shot, items);
    ts.forEach((t) => { ev(t - 0.2, 'whoosh', 0.45); ev(t + 0.75, 'ding', 0.7); });
    return (t) => {
      vis(title, clamp((t - shot.start) / 0.25));
      cards.forEach((c, i) => {
        const s = pop(t, ts[i] - 0.05, 12, 0.62); const act = t >= ts[i] && (i === n - 1 || t < ts[i + 1]);
        c.style.opacity = (clamp((t - ts[i] + 0.05) * 6) * (act ? 1 : 0.6)).toFixed(3);
        c.style.visibility = t < ts[i] - 0.1 ? 'hidden' : 'visible';
        tf(c, `perspective(1400px) rotateX(${((1 - s) * 85).toFixed(1)}deg) scale(${act ? 1.03 : 0.97})`);
        tf(c._ck, `scale(${Math.max(0, pop(t, ts[i] + 0.75, 20, 0.5)).toFixed(3)})`);
        if (c._hl) c._hl.style.background = `rgba(${C.accentRGB},${clamp((t - ts[i] - 0.4) / 0.2)})`;
      });
    };
  };

  // 4. Perte d'argent (pièces aspirées) — problème, gaspillage, fuite
  SC.loss_drain = function (root, shot, p) {
    const tagEl = p.tag ? mk(root, 'a ctr', `<span class="pill anton" style="background:${C.bad};color:#fff;font-size:100px;padding:12px 44px;display:inline-block;transform:rotate(-4deg)">${esc(up(p.tag))}</span>`, 'top:300px') : null;
    if (tagEl) fit(tagEl.firstElementChild, 960, 100, 56);
    const svg = mk(root, 'a', '<svg width="1080" height="1920"></svg>', 'left:0;top:0').firstElementChild;
    const chips = (p.chips || []).slice(0, 2).map((c, i) => mk(root, 'a', `<span class="pill" style="background:rgba(255,255,255,.12);border:2px solid rgba(255,255,255,.35);font-weight:700;font-size:40px;color:#fff">${esc(up(c))}</span>`, `${i ? 'right' : 'left'}:90px;top:640px`));
    const stamp = mk(root, 'a anton ctr', `<span style="display:inline-block;border:14px solid ${C.bad};padding:0 40px;border-radius:30px">${esc(up(p.label || 'PERTE'))}</span>`, `top:1290px;font-size:230px;color:${C.bad}`);
    fit(stamp.firstElementChild, 960, 230, 100);
    const tTag = wordTime(shot, p.tag_at, 0.1), tDrain = wordTime(shot, p.drain_at, 0.55), tStamp = wordTime(shot, p.label_at || p.label, 0.9);
    const tChips = chips.map((_, i) => wordTime(shot, (p.chips_at || [])[i] || p.chips[i], 0.3 + i * 0.15));
    if (tagEl) { ev(tTag, 'pop', 0.9); ev(tTag - 0.15, 'whoosh', 0.4); }
    tChips.forEach((t) => ev(t, 'pop', 0.7));
    for (let i = 0; i < 24; i++) ev(shot.start + 0.1 + i * 0.03, 'coin', 0.5);
    ev(tDrain, 'whoosh_rev', 0.9); for (let i = 0; i < 14; i++) ev(tDrain + 0.1 + i * 0.04, 'coin', 0.45);
    ev(tStamp, 'stamp', 1); IMPACTS.push(tStamp);
    const stacks = [[270, 1080, 10], [540, 1140, 13], [810, 1080, 9]];
    return (t) => {
      if (tagEl) { const q = pop(t, tTag, 15, 0.5); vis(tagEl, clamp((t - tTag) * 7)); tf(tagEl, `scale(${(0.3 + 0.7 * q).toFixed(3)})`); }
      chips.forEach((c, i) => { const q = pop(t, tChips[i], 16, 0.55); vis(c, clamp((t - tChips[i]) * 7) * (1 - clamp((t - tStamp) / 0.3))); tf(c, `translateY(${((1 - q) * 40).toFixed(1)}px)`); });
      let s = COIN_DEFS + `<defs><radialGradient id="vx"><stop offset="0" stop-color="${C.bad}" stop-opacity=".9"/><stop offset="1" stop-color="${C.bad}" stop-opacity="0"/></radialGradient></defs>`;
      const vo = clamp((t - tDrain + 0.2) / 0.4);
      s += `<ellipse cx="540" cy="1420" rx="${(380 * vo).toFixed(0)}" ry="${(120 * vo).toFixed(0)}" fill="url(#vx)" opacity="${(0.5 + 0.2 * Math.sin(t * 9)).toFixed(2)}"/>`;
      stacks.forEach(([x, y, n], si) => {
        for (let k = 0; k < n; k++) {
          const id = si * 20 + k; const tk = shot.start + 0.05 + id * 0.02; if (t < tk) continue;
          const fly = clamp((t - (tDrain + 0.04 * (n - k) + si * 0.07)) / 0.55); const e = fly * fly; if (fly >= 1) continue;
          const cx = lerp(x, 540 + (rnd(id) - 0.5) * 80, e), cy = lerp(y - k * 28, 1420, e);
          s += `<g opacity="${(1 - e * 0.6).toFixed(2)}" transform="rotate(${(e * 260 * (rnd(id + 3) - 0.5)).toFixed(1)} ${cx.toFixed(0)} ${cy.toFixed(0)})">${coin(cx, cy - (1 - pop(t, tk, 18, 0.6)) * 80, lerp(95, 16, e))}</g>`;
        }
      });
      svg.innerHTML = s;
      const sp = pop(t, tStamp, 22, 0.45); vis(stamp, clamp((t - tStamp) * 10)); tf(stamp, `scale(${(2.4 - 1.4 * sp).toFixed(3)}) rotate(-8deg)`);
    };
  };

  // 5. Révélation héros: emblème 3D + nom de la solution / du produit
  SC.hero_reveal = function (root, shot, p) {
    const rs = mk(root, 'a', '<svg width="1920" height="1920"></svg>', 'left:-420px;top:-60px').firstElementChild; rays(rs, `rgba(${C.accentRGB},.13)`);
    const kick = p.kicker ? mk(root, 'a ctr', esc(up(p.kicker)), `top:380px;font-size:44px;font-weight:800;letter-spacing:.14em;color:${subFor(shot.tone)}`) : null;
    const em = mk(root, 'a', '', 'left:340px;top:480px'); const eh = emblem(em, p.emblem || 'shield', 400);
    em.style.left = (540 - 200) + 'px';
    const n1 = mk(root, 'a anton ctr', esc(up(p.name || '')), `top:${480 + eh + 60}px;left:60px;width:960px;color:${inkFor(shot.tone)};line-height:1.02`);
    fit(n1, 960, 150, 70, 330);
    const n2 = p.sub ? mk(root, 'a ctr', esc(p.sub), `top:${480 + eh + 80 + n1.scrollHeight}px;left:80px;width:920px;font-size:48px;font-weight:700;color:${C.accent};line-height:1.2`) : null;
    const tH = wordTime(shot, p.at || p.name, 0.35), tN = tH + 0.2, tS = p.sub ? wordTime(shot, p.sub_at || p.sub, 0.75) : 0;
    // Texte d'amorce (ce qui est dit AVANT la révélation) pour ne jamais laisser l'écran vide.
    let leadTxt = p.lead;
    if (!leadTxt && tH - shot.start > 1.0) leadTxt = shot.words.filter((w) => w.s < tH - 0.05).map((w) => w.w).join(' ').replace(/[,:;.]+$/, '');
    const lead = leadTxt ? mk(root, 'a anton ctr', '', `top:760px;left:60px;width:960px;color:${inkFor(shot.tone)};line-height:1.05`) : null;
    if (lead) { prepDrop(lead, up(leadTxt.split(/\s+/).slice(0, 9).join(' '))); fit(lead, 960, 130, 64, 420); dropEvents(lead, shot.start + 0.1); }
    ev(tH - 1.2, 'riser', 0.8); ev(tH, 'impact_big', 1); ev(tH + 0.05, 'shimmer', 0.9); if (n2) ev(tS, 'pop', 0.8);
    IMPACTS.push(tH); FLASHES.push(tH);
    return (t) => {
      rs.firstChild.setAttribute('transform', `rotate(${(t * 12).toFixed(1)} 960 960)`); vis(rs, clamp((t - tH + 0.1) / 0.4));
      if (kick) vis(kick, clamp((t - shot.start) / 0.3));
      if (lead) { drop(lead, t, shot.start + 0.1); const o = eio((t - tH + 0.25) / 0.35); lead.style.opacity = (1 - o).toFixed(3); lead.style.visibility = o >= 1 ? 'hidden' : 'visible'; lead.style.marginTop = (-o * 260).toFixed(0) + 'px'; }
      const h = pop(t, tH, 9, 0.55); vis(em, clamp((t - tH) * 5));
      tf(em, `perspective(1600px) translateY(${((1 - h) * 500).toFixed(0)}px) rotateY(${((1 - h) * -200 + Math.sin((t - tH) * 2.2) * 14).toFixed(1)}deg) rotateX(8deg) scale(${(0.6 + 0.4 * h).toFixed(3)})`);
      const q = pop(t, tN, 16, 0.5); vis(n1, clamp((t - tN) * 7)); tf(n1, `scale(${(0.3 + 0.7 * q).toFixed(3)})`);
      if (n2) { const u = clamp((t - tS) / 0.3); vis(n2, u); tf(n2, `translateY(${((1 - eo(u)) * 30).toFixed(0)}px)`); }
    };
  };

  // 6. Comparaison haut/bas: sans vs avec la solution
  SC.split_compare = function (root, shot, p) {
    const a = p.a || {}, b = p.b || {};
    const top = mk(root, 'a', '', `left:0;top:0;width:1080px;height:960px;background:radial-gradient(ellipse at 50% 55%,#3a3f4b 0%,#1b1e25 70%,#0e1014 100%)`);
    const bot = mk(root, 'a', '', `left:0;top:960px;width:1080px;height:960px;background:radial-gradient(ellipse at 50% 45%,${C.dark2} 0%,${C.dark1} 65%,#03070f 100%)`);
    const em = mk(root, 'a', '', 'left:600px;top:1110px'); emblem(em, p.emblem || 'shield', 360, 36); em.querySelectorAll('path[d^="M8 12.5"],path[d^="M7.5 12.5"]').forEach((e) => e.remove());
    const svg = mk(root, 'a', '<svg width="1080" height="1920"></svg>', 'left:0;top:0').firstElementChild;
    const la = mk(root, 'a', `<span class="pill" style="background:rgba(255,255,255,.14);font-weight:800;font-size:38px;color:#fff">${esc(up(a.label || 'AVANT'))}</span>`, 'left:60px;top:250px');
    const lb = mk(root, 'a', `<span class="pill" style="background:${C.accent};color:${C.onAccent};font-weight:800;font-size:38px">${esc(up(b.label || 'APRÈS'))}</span>`, 'left:60px;top:1010px');
    const ta = a.tag ? mk(root, 'a', `<span class="pill anton" style="background:${C.bad};color:#fff;font-size:56px;padding:8px 30px">${esc(up(a.tag))}</span>`, 'right:60px;top:250px') : null;
    const tb = b.tag ? mk(root, 'a anton', esc(up(b.tag)), `right:60px;top:1010px;text-align:right;font-size:58px;color:${C.accent};line-height:1.02;max-width:560px`) : null;
    const dimT = mk(root, 'a', '', 'left:0;top:0;width:1080px;height:960px;background:#000');
    const dimB = mk(root, 'a', '', 'left:0;top:960px;width:1080px;height:960px;background:#000');
    const tB = wordTime(shot, b.at, 0.5), tA = wordTime(shot, a.at, 0.12);
    const tTagA = wordTime(shot, a.tag_at || a.tag, 0.2), tTagB = wordTime(shot, b.tag_at || b.tag, 0.6);
    const bites = [0, 1, 2].map((i) => lerp(tTagA + 0.5, tB - 0.4, (i + 0.5) / 3));
    const tGrow = tB + 0.8, tDef = tB + Math.min(2.4, (shot.speechEnd - tB) * 0.55);
    ev(shot.start, 'whoosh', 0.5); if (ta) ev(tTagA, 'pop', 0.8);
    bites.forEach((k) => { ev(k, 'whoosh', 0.3); ev(k + 0.05, 'coin', 0.6); ev(k + 0.02, 'pop_low', 0.5); });
    ev(tB - 0.9, 'riser', 0.5); ev(tB, 'impact', 0.8); ev(tB + 0.05, 'shimmer', 0.6); if (tb) ev(tTagB, 'pop', 0.8);
    for (let i = 0; i < 7; i++) ev(tGrow + i * 0.18, 'coin', 0.45);
    ev(tDef, 'ping', 0.9); ev(tDef, 'thud', 0.5); IMPACTS.push(tB);
    return (t) => {
      const focusB = t >= tB - 0.2;
      vis(dimT, focusB ? 0.62 * clamp((t - tB + 0.2) / 0.4) : 0);
      vis(dimB, focusB ? 0.62 * (1 - clamp((t - tB + 0.2) / 0.4)) : 0.62 * clamp((t - tA) / 0.4));
      const earn = Math.floor(12 * clamp((t - shot.start - 0.1) / 1.4));
      let lost = 0; bites.forEach((k) => { if (t > k) lost += 2; });
      let s = COIN_DEFS + `<line x1="${540 - 540 * eio((t - shot.start) / 0.5)}" y1="960" x2="${540 + 540 * eio((t - shot.start) / 0.5)}" y2="960" stroke="${C.accent}" stroke-width="6"/>`;
      s += person(240, 700, 1.2, 'bad') + person(240, 1590, 1.15, 'good');
      const nT = Math.max(0, earn - lost); for (let k = 0; k < nT; k++) s += coin(760, 860 - k * 22, 64);
      bites.forEach((k) => {
        const u = clamp((t - k) / 0.7); if (u <= 0 || u >= 1) return; const e = eo(u);
        s += `<g transform="translate(900 ${(560 - e * 140).toFixed(0)})" opacity="${(1 - u * u).toFixed(2)}"><rect x="-120" y="-40" width="240" height="80" rx="40" fill="${C.bad}"/><text x="0" y="16" text-anchor="middle" font-family="Anton" font-size="46" fill="#fff">${esc(up(a.loss || '− ARGENT'))}</text></g>`;
        for (let j = 0; j < 2; j++) { const cx = 760 + e * (260 + j * 60), cy = 860 - (nT + 1 - j) * 22 - e * 420 + e * e * 80; s += `<g opacity="${(1 - u).toFixed(2)}">${coin(cx, cy, 64 * (1 - 0.4 * e))}</g>`; }
      });
      const nB = earn + Math.floor(7 * clamp((t - tGrow) / 1.3)); for (let k = 0; k < nB; k++) s += coin(780, 1470 - k * 16, 46);
      if (t > tGrow) { const u = eo((t - tGrow) / 0.6); s += `<g opacity="${u.toFixed(2)}" transform="translate(930 ${(1330 - u * 40).toFixed(0)})"><path d="M0 60 V-40 M-34 -6 L0 -40 L34 -6" fill="none" stroke="#3ddc84" stroke-width="16" stroke-linecap="round" stroke-linejoin="round"/></g>`; }
      if (t > tDef - 0.5 && t < tDef + 0.9) {
        const u = (t - (tDef - 0.5)) / 1.4, hu = 0.36; let cx, cy, r = 0;
        if (u < hu) { const e = u / hu; cx = lerp(1150, 930, e); cy = lerp(1150, 1260, e); } else { const e = (u - hu) / (1 - hu); cx = 930 + e * 300; cy = 1260 - e * 300 + e * e * 500; r = e * 400; }
        s += `<g transform="translate(${cx.toFixed(0)} ${cy.toFixed(0)}) rotate(${r.toFixed(0)})" opacity="${(u < 0.85 ? 1 : (1 - u) / 0.15).toFixed(2)}"><rect x="-110" y="-38" width="220" height="76" rx="38" fill="${C.bad}"/><text x="0" y="15" text-anchor="middle" font-family="Anton" font-size="42" fill="#fff">${esc(up(a.loss || '− ARGENT'))}</text></g>`;
        if (u > hu && u < hu + 0.2) { const q = (u - hu) / 0.2; s += `<circle cx="935" cy="1260" r="${(30 + q * 120).toFixed(0)}" fill="none" stroke="${C.accent}" stroke-width="${(10 * (1 - q)).toFixed(1)}"/>`; }
      }
      svg.innerHTML = s;
      const h = pop(t, tB - 0.1, 9, 0.55); vis(em, clamp((t - tB + 0.1) * 5) * 0.95);
      tf(em, `perspective(1600px) translateY(${((1 - h) * 600).toFixed(0)}px) rotateY(${((1 - h) * -180 + Math.sin(t * 2) * 10).toFixed(1)}deg) scale(${(0.6 + 0.4 * h).toFixed(3)})`);
      vis(la, clamp((t - shot.start - 0.3) * 5)); vis(lb, clamp((t - shot.start - 0.4) * 5));
      if (ta) { const q = pop(t, tTagA, 16, 0.5); vis(ta, clamp((t - tTagA) * 6)); tf(ta, `scale(${(0.3 + 0.7 * q).toFixed(3)}) rotate(-3deg)`); }
      if (tb) { const q = pop(t, tTagB, 16, 0.5); vis(tb, clamp((t - tTagB) * 6)); tf(tb, `scale(${(0.3 + 0.7 * q).toFixed(3)})`); tb.style.transformOrigin = '100% 0'; }
    };
  };

  // 7. Barres comparatives (résultat illustratif, jamais de chiffres inventés)
  SC.bars_compare = function (root, shot, p) {
    const ink = inkFor(shot.tone);
    const t1 = mk(root, 'a anton ctr', '', `top:260px;left:60px;width:960px;color:${ink}`); prepDrop(t1, up(p.title || '')); fit(t1, 960, 120, 64, 130);
    const cap = p.caption ? mk(root, 'a anton ctr', esc(up(p.caption)), `top:420px;left:60px;width:960px;color:${ink};line-height:1.05`) : null; if (cap) fit(cap, 960, 90, 50, 200);
    const svg = mk(root, 'a', '<svg width="1080" height="1920"></svg>', 'left:0;top:0').firstElementChild;
    const note = mk(root, 'a ctr', esc(p.disclaimer || 'Illustration — les résultats dépendent de chaque situation.'), `top:1770px;font-size:26px;font-weight:500;color:${subFor(shot.tone)}`);
    const tT = wordTime(shot, p.at, 0.05), tBar = tT + 0.3, tCap = wordTime(shot, p.caption_at || p.caption, 0.6);
    dropEvents(t1, tT); ev(tBar, 'riser_short', 0.6); ev(tBar + 1.3, 'ding', 0.7); if (cap) ev(tCap, 'impact', 0.6);
    const va = clamp(p.a_value == null ? 0.35 : p.a_value, 0.1, 1), vb = clamp(p.b_value == null ? 1 : p.b_value, 0.1, 1);
    return (t) => {
      drop(t1, t, tT);
      if (cap) { const q = pop(t, tCap, 15, 0.55); vis(cap, clamp((t - tCap) * 6)); tf(cap, `scale(${(0.4 + 0.6 * q).toFixed(3)})`); }
      const base = 1560, M = 640, hA = M * va * eo((t - tBar) / 1.0), hB = M * vb * eo((t - tBar - 0.2) / 1.6);
      let s = `<line x1="120" y1="${base}" x2="960" y2="${base}" stroke="${ink}" stroke-width="5" stroke-linecap="round"/>`;
      s += `<rect x="200" y="${base - hA}" width="240" height="${hA}" rx="20" fill="#9aa0ab"/><rect x="640" y="${base - hB}" width="240" height="${hB}" rx="20" fill="${C.accent}"/>`;
      s += person(320, base - hA - 150, 0.55, 'bad') + person(760, base - hB - 150, 0.55, 'good');
      s += `<text x="320" y="${base + 70}" text-anchor="middle" font-family="Anton" font-size="50" fill="${ink}">${esc(up(p.a_label || 'SANS'))}</text><text x="760" y="${base + 70}" text-anchor="middle" font-family="Anton" font-size="50" fill="${ink}">${esc(up(p.b_label || 'AVEC'))}</text>`;
      svg.innerHTML = s; vis(note, clamp((t - tBar - 0.5) / 0.4) * 0.9);
    };
  };

  // 8. Exclusivité: une foule, seuls quelques-uns s'allument
  SC.crowd_select = function (root, shot, p) {
    const t1 = mk(root, 'a anton ctr', '', `top:230px;left:60px;width:960px;color:${inkFor(shot.tone)};line-height:1.02`); prepDrop(t1, up(p.title || 'PAS POUR TOUT LE MONDE')); fit(t1, 960, 120, 64, 260);
    const svg = mk(root, 'a', '<svg width="1080" height="1920"></svg>', 'left:0;top:0').firstElementChild;
    const cap = p.caption ? mk(root, 'a ctr', esc(p.caption), `top:1360px;left:60px;width:960px;font-size:52px;font-weight:700;color:${subFor(shot.tone)}`) : null;
    const hl = p.highlight ? mk(root, 'a anton ctr', esc(up(p.highlight)), `top:1440px;left:60px;width:960px;color:${C.accent}`) : null; if (hl) fit(hl, 960, 130, 60);
    const tT = wordTime(shot, p.at, 0.02), tSel = wordTime(shot, p.select_at, 0.35), tCap = wordTime(shot, p.caption_at, 0.62), tHl = wordTime(shot, p.highlight_at || p.highlight, 0.85);
    dropEvents(t1, tT); for (let i = 0; i < 8; i++) ev(shot.start + 0.1 + i * 0.07, 'tick', 0.6);
    ev(tSel, 'whoosh_rev', 0.5); ev(tSel + 0.35, 'shimmer', 0.7); if (hl) { ev(tHl, 'pop', 0.9); ev(tHl, 'impact', 0.4); }
    const chosen = [8, 12, 24, 42, 48];
    return (t) => {
      drop(t1, t, tT);
      let s = '';
      for (let r = 0; r < 8; r++) for (let c = 0; c < 7; c++) {
        const i = r * 7 + c, x = 150 + c * 130, y = 560 + r * 100, k = shot.start + 0.1 + (r + c) * 0.04; if (t < k) continue;
        const ch = chosen.includes(i), fade = clamp((t - tSel - rnd(i) * 0.4) / 0.4), q = pop(t, k, 18, 0.6);
        const col = ch ? (fade > 0 ? C.accent : '#C9D3E8') : `rgba(201,211,232,${(1 - 0.8 * fade).toFixed(2)})`;
        const sc = (0.5 + 0.5 * q) * (ch ? 1 + 0.35 * eo((t - tSel - 0.3) / 0.4) : 1 - 0.25 * fade);
        s += `<g transform="translate(${x} ${y}) scale(${sc.toFixed(3)})"><circle cx="0" cy="-22" r="16" fill="${col}"/><path d="M-26 30 a26 26 0 0 1 52 0 Z" fill="${col}"/>${ch && fade > 0.5 ? `<circle cx="0" cy="0" r="52" fill="none" stroke="${C.accent}" stroke-opacity="${(0.5 * fade).toFixed(2)}" stroke-width="3"/>` : ''}</g>`;
      }
      svg.innerHTML = s;
      if (cap) vis(cap, clamp((t - tCap) / 0.3));
      if (hl) { const b = pop(t, tHl, 15, 0.5); vis(hl, clamp((t - tHl) * 6)); tf(hl, `scale(${(0.3 + 0.7 * b).toFixed(3)})`); }
    };
  };

  // 9. Décision: interrupteur qui passe sur ON
  SC.toggle_decision = function (root, shot, p) {
    const q = mk(root, 'a anton ctr', '?', `top:250px;font-size:420px;color:${C.accent}`);
    const d1 = p.kicker ? mk(root, 'a ctr', esc(p.kicker), `top:760px;font-size:56px;font-weight:700;color:${subFor(shot.tone)}`) : null;
    const d2 = mk(root, 'a anton ctr', '', `top:850px;left:60px;width:960px;color:${inkFor(shot.tone)}`); prepDrop(d2, up(p.title || 'UNE SEULE DÉCISION')); fit(d2, 960, 150, 70);
    const tg = mk(root, 'a', '', 'left:380px;top:1080px;width:320px;height:160px;border-radius:80px'); const knob = mk(tg, 'a', '', 'top:14px;width:132px;height:132px;border-radius:50%;background:#fff');
    const d3 = p.caption ? mk(root, 'a ctr', `<span class="pill anton" style="background:${C.accent};color:${C.onAccent};font-size:84px;padding:10px 40px">${esc(up(p.caption))}</span>`, 'top:1320px') : null;
    const tQ = shot.start + 0.1, tT = wordTime(shot, p.at, 0.3), tOn = wordTime(shot, p.on_at, 0.62), tC = wordTime(shot, p.caption_at || p.caption, 0.85);
    ev(tQ, 'heartbeat', 0.9); ev(tQ + 0.85, 'heartbeat', 0.8); ev(tQ, 'impact', 0.4); dropEvents(d2, tT); ev(tOn, 'click', 1); ev(tOn + 0.02, 'impact', 0.8); ev(tOn + 0.05, 'shimmer', 0.6); if (d3) ev(tC, 'pop', 0.8);
    IMPACTS.push(tOn);
    return (t) => {
      const qq = pop(t, tQ, 14, 0.5); vis(q, clamp((t - tQ) * 6) * (1 - 0.6 * clamp((t - tT) / 0.4))); tf(q, `scale(${(0.3 + 0.7 * qq).toFixed(3)}) rotate(${(Math.sin(t * 3) * 4).toFixed(1)}deg)`);
      if (d1) vis(d1, clamp((t - tQ) / 0.3)); drop(d2, t, tT);
      const on = clamp((t - tOn) / 0.18); vis(tg, clamp((t - tT - 0.2) * 5)); tg.style.background = on > 0.5 ? C.accent : '#3a4560'; tf(knob, `translateX(${(14 + on * 160).toFixed(1)}px)`);
      tg.style.boxShadow = on > 0.5 ? `0 0 ${(40 + 20 * Math.sin(t * 8)).toFixed(0)}px rgba(${C.accentRGB},.7)` : 'none';
      if (d3) { const pp = pop(t, tC, 16, 0.5); vis(d3, clamp((t - tC) * 6)); tf(d3, `scale(${(0.3 + 0.7 * pp).toFixed(3)})`); }
    };
  };

  // 10. Choix entre deux profils — le curseur choisit le bon
  SC.choice_cards = function (root, shot, p) {
    const a = p.a || {}, b = p.b || {};
    const t1 = mk(root, 'a anton ctr', '', `top:300px;left:60px;width:960px;color:${inkFor(shot.tone)};line-height:1.02`); prepDrop(t1, up(p.title || 'LEQUEL VOULEZ-VOUS ÊTRE ?')); fit(t1, 960, 110, 60, 260);
    const mkCard = (x, d, good) => {
      const c = mk(root, 'card', '', `left:${x}px;top:640px;width:430px;height:640px;background:${good ? '#fff' : '#eef0f4'};border:${good ? `4px solid ${C.accent}` : '3px solid #d6dae3'};box-shadow:0 30px 60px -25px rgba(0,0,0,.4)`);
      c.innerHTML = `<svg class="a" style="left:0;top:40px" width="430" height="360">${person(215, 150, 0.95, good ? 'good' : 'bad')}</svg>
      <div class="a anton" style="left:0;width:430px;text-align:center;top:410px;font-size:58px;color:${C.ink}">${esc(up(d.label || ''))}</div>
      <div class="a" style="left:0;width:430px;text-align:center;top:490px;font-size:34px;font-weight:700;color:${good ? C.ink : '#7a808c'}">${esc(d.sub || '')}</div>
      <div class="a" style="left:175px;top:555px;width:80px;height:80px;border-radius:50%;background:${good ? C.accent : '#c9ccd3'};display:flex;align-items:center;justify-content:center">${icon(good ? 'check' : 'x', 48, good ? C.onAccent : '#fff', 3)}</div>`;
      fit(c.children[1], 400, 58, 34); return c;
    };
    const ka = mkCard(80, a, false), kb = mkCard(570, b, true);
    const cur = mk(root, 'a', CURSOR, 'left:0;top:0');
    const tT = wordTime(shot, p.at, 0.05), tIn = shot.start + 0.1, tPick = wordTime(shot, p.pick_at, 0.8);
    dropEvents(t1, tT); ev(tIn, 'whoosh', 0.5); ev(tIn + 0.15, 'whoosh', 0.5); ev(tPick - 0.6, 'tick', 0.9); ev(tPick, 'click', 1); ev(tPick + 0.05, 'ding', 0.9); ev(tPick + 0.1, 'shimmer', 0.6);
    return (t) => {
      drop(t1, t, tT);
      [[ka, tIn, false], [kb, tIn + 0.15, true]].forEach(([c, k, good]) => {
        const s = pop(t, k, 12, 0.62); vis(c, clamp((t - k) * 6));
        const chosen = good && t > tPick, other = !good && t > tPick, hov = !good && t > tPick - 0.7 && t < tPick - 0.3;
        tf(c, `perspective(1400px) rotateY(${((1 - s) * (good ? 90 : -90)).toFixed(1)}deg) scale(${(chosen ? 1 + 0.08 * pop(t, tPick, 14, 0.5) : (hov ? 1.04 : (other ? 0.92 : 1))).toFixed(3)})`);
        if (other) c.style.opacity = (1 - 0.55 * clamp((t - tPick) / 0.3)).toFixed(2);
        if (good) c.style.boxShadow = chosen ? `0 0 ${(50 + 15 * Math.sin(t * 8)).toFixed(0)}px rgba(${C.accentRGB},.8)` : '0 30px 60px -25px rgba(0,0,0,.4)';
      });
      const cx = t < tPick - 0.55 ? lerp(1150, 300, eio((t - (tPick - 1.3)) / 0.6)) : lerp(300, 790, eio((t - (tPick - 0.35)) / 0.35));
      const pr = Math.max(0, 1 - Math.abs(t - tPick) / 0.1); vis(cur, clamp((t - (tPick - 1.3)) * 5));
      tf(cur, `translate(${cx.toFixed(0)}px,1000px) scale(${(1 - 0.15 * pr).toFixed(3)})`);
    };
  };

  // 11. Minuteur / durée (ex: « 30 minutes »)
  SC.timer_ring = function (root, shot, p) {
    const val = Math.max(1, Math.min(999, parseInt(p.value, 10) || 30));
    const t1 = p.title ? mk(root, 'a anton ctr', esc(up(p.title)), `top:300px;left:60px;width:960px;color:${inkFor(shot.tone)}`) : null; if (t1) fit(t1, 960, 110, 60);
    const ring = mk(root, 'a', `<svg width="560" height="560" viewBox="0 0 560 560"><circle cx="280" cy="280" r="236" fill="#fff" stroke="#E6E9F0" stroke-width="36"/><circle class="arc" cx="280" cy="280" r="236" fill="none" stroke="${C.accent}" stroke-width="36" stroke-linecap="round" transform="rotate(-90 280 280)" stroke-dasharray="0 2000"/></svg><div class="a anton ctr num" style="left:0;width:560px;top:150px;font-size:210px;color:${C.ink}">0</div><div class="a ctr" style="left:0;width:560px;top:390px;font-size:42px;font-weight:700;color:#7F8BA8">${esc(up(p.unit || 'MINUTES'))}</div>`, 'left:260px;top:520px;width:560px;height:560px');
    const arc = ring.querySelector('.arc'), num = ring.querySelector('.num');
    const cap = p.caption ? mk(root, 'a ctr', '', `top:1160px;left:70px;width:940px;font-size:52px;font-weight:700;color:${inkFor(shot.tone)};line-height:1.3`) : null;
    if (cap) cap.innerHTML = esc(p.caption).replace(esc(p.caption_highlight || '\u0000'), `<span class="hlw" style="padding:0 14px;border-radius:12px">${esc(p.caption_highlight || '')}</span>`);
    const hlw = cap ? cap.querySelector('.hlw') : null;
    const tR = wordTime(shot, p.at || String(val), 0.2), tC = wordTime(shot, p.caption_at, 0.55), tH = wordTime(shot, p.caption_highlight, 0.85);
    ev(tR - 0.1, 'pop', 0.8); for (let i = 0; i < 10; i++) ev(tR + i * 0.09, 'tock', 0.7); ev(tR + 0.95, 'ding', 0.8); if (cap) ev(tC, 'pop', 0.6);
    const frac = p.fraction == null ? Math.min(1, val / 60) : clamp(p.fraction);
    return (t) => {
      if (t1) vis(t1, clamp((t - shot.start) / 0.3));
      const q = pop(t, tR - 0.1, 14, 0.55); vis(ring, clamp((t - tR + 0.1) * 6)); tf(ring, `scale(${(0.4 + 0.6 * q).toFixed(3)})`);
      const f = eio((t - tR) / 0.9); arc.setAttribute('stroke-dasharray', `${(f * frac * 2 * Math.PI * 236).toFixed(1)} 2000`); num.textContent = String(Math.round(f * val));
      if (cap) { const u = clamp((t - tC) / 0.3); vis(cap, u); tf(cap, `translateY(${((1 - eo(u)) * 40).toFixed(0)}px)`); }
      if (hlw) hlw.style.background = `rgba(${C.accentRGB},${clamp((t - tH) / 0.2)})`;
    };
  };

  // 12. Appel à l'action: bouton + main qui clique + chevrons
  SC.cta_button = function (root, shot, p) {
    const t1 = mk(root, 'a anton ctr', '', `top:300px;left:50px;width:980px;color:${inkFor(shot.tone)};line-height:1.02`); prepDrop(t1, up(p.title || 'CLIQUEZ SUR LE BOUTON')); fit(t1, 980, 110, 60, 250);
    const btn = mk(root, 'a', `<span class="anton" style="font-size:88px;color:${C.onDark}">${esc(up(p.button || 'CLIQUEZ ICI'))}</span>${icon('arrowRight', 84, C.accent, 2.6)}`, `left:140px;top:640px;width:800px;height:180px;border-radius:90px;background:${C.dark1};display:flex;align-items:center;justify-content:center;gap:26px;box-shadow:0 30px 60px -20px rgba(0,0,0,.55)`);
    fit(btn.firstElementChild, 640, 88, 48);
    const rip = mk(root, 'a', '', `width:40px;height:40px;border-radius:50%;border:6px solid ${C.accent}`);
    const chv = mk(root, 'a', '<svg width="200" height="240"></svg>', 'left:440px;top:850px'); const chs = chevrons(chv.firstElementChild, C.accent, 200, 240);
    const hand = mk(root, 'a', HAND, 'left:0;top:0');
    const cap = p.caption ? mk(root, 'a ctr', esc(p.caption), `top:1180px;left:70px;width:940px;font-size:52px;font-weight:700;color:${inkFor(shot.tone)};line-height:1.3`) : null;
    const tT = wordTime(shot, p.at, 0.02), tB = shot.start + 0.05, tClick = wordTime(shot, p.click_at || 'bouton', 0.35), tDown = wordTime(shot, p.down_at || 'bas', 0.55), tC = wordTime(shot, p.caption_at, 0.7);
    dropEvents(t1, tT); ev(tB, 'pop', 0.7); ev(tClick, 'click', 1); ev(tClick + 0.02, 'pop_high', 0.6); for (let i = 0; i < 3; i++) ev(tDown + i * 0.08, 'blip', 0.6); if (cap) ev(tC, 'pop', 0.6);
    return (t) => {
      drop(t1, t, tT);
      const bp = pop(t, tB, 14, 0.55), press = Math.max(0, 1 - Math.abs(t - tClick) / 0.12);
      vis(btn, clamp((t - tB) * 6)); tf(btn, `scale(${((0.4 + 0.6 * bp) * (1 - 0.07 * press) * (1 + 0.03 * Math.sin(t * 8) * (t > tClick + 0.3 ? 1 : 0))).toFixed(3)})`);
      const hx = t < tClick ? lerp(900, 560, eio((t - (tClick - 0.55)) / 0.5)) : lerp(560, 880, eio((t - tClick - 0.25) / 0.5));
      const hy = t < tClick ? lerp(1300, 720, eio((t - (tClick - 0.55)) / 0.5)) : lerp(720, 1250, eio((t - tClick - 0.25) / 0.5));
      vis(hand, clamp((t - (tClick - 0.55)) * 5) * (1 - clamp((t - tClick - 0.8) * 4))); tf(hand, `translate(${hx.toFixed(0)}px,${hy.toFixed(0)}px) scale(${(1 - 0.12 * press).toFixed(3)})`);
      const rp = clamp((t - tClick) / 0.5); vis(rip, rp > 0 && rp < 1 ? 1 - rp : 0); tf(rip, `translate(540px,710px) scale(${(1 + rp * 9).toFixed(2)})`);
      chs.forEach((e, i) => { const k = tDown + i * 0.08; e.style.opacity = (clamp((t - k) * 5) * (0.4 + 0.6 * Math.max(0, Math.sin((t - k) * 6 - i * 0.9)))).toFixed(2); });
      tf(chv, `translateY(${(Math.sin(t * 6) * 10).toFixed(1)}px)`);
      if (cap) { const u = clamp((t - tC) / 0.3); vis(cap, u); tf(cap, `translateY(${((1 - eo(u)) * 40).toFixed(0)}px)`); }
    };
  };

  // 13. Conversation (messages qui arrivent) — WhatsApp, avis, questions clients
  SC.chat_bubbles = function (root, shot, p) {
    const msgs = (p.messages || []).slice(0, 5);
    const phone = mk(root, 'a', '', `left:140px;top:300px;width:800px;height:1300px;border-radius:70px;background:${shot.tone === 'light' ? '#fff' : '#0f1626'};border:14px solid #111;box-shadow:0 40px 90px -30px rgba(0,0,0,.6);overflow:hidden`);
    mk(phone, 'a', `<div style="display:flex;align-items:center;gap:20px;padding:0 36px;height:150px">${`<div style="width:84px;height:84px;border-radius:50%;background:${C.accent};display:flex;align-items:center;justify-content:center">${icon(p.avatar || 'user', 48, C.onAccent, 2)}</div>`}<div style="font-size:40px;font-weight:700;color:${shot.tone === 'light' ? C.ink : '#fff'}">${esc(p.contact || 'Client')}</div></div>`, `left:0;top:0;width:772px;height:150px;background:${shot.tone === 'light' ? '#f1f3f7' : '#172036'}`);
    let y = 200;
    const bubbles = msgs.map((m) => {
      const me = m.from === 'me';
      const b = mk(phone, 'a', esc(m.text).replace(/ ([?!:;»])/g, '\u00a0$1'), `${me ? 'right' : 'left'}:30px;top:${y}px;max-width:560px;padding:26px 32px;border-radius:36px;${me ? 'border-bottom-right-radius:10px' : 'border-bottom-left-radius:10px'};font-size:40px;font-weight:600;line-height:1.3;background:${me ? C.accent : (shot.tone === 'light' ? '#eef1f6' : '#23304d')};color:${me ? C.onAccent : (shot.tone === 'light' ? C.ink : '#fff')}`);
      y += b.offsetHeight + 28; return b;
    });
    const ts = itemTimes(shot, msgs);
    ts.forEach((t, i) => { ev(t, msgs[i].from === 'me' ? 'blip' : 'pop', 0.8); });
    return (t) => {
      const q = pop(t, shot.start, 12, 0.6); vis(phone, clamp((t - shot.start) * 5)); tf(phone, `translateY(${((1 - q) * 300).toFixed(0)}px)`);
      bubbles.forEach((b, i) => { const s = pop(t, ts[i], 18, 0.55); vis(b, clamp((t - ts[i]) * 7)); tf(b, `scale(${(0.5 + 0.5 * s).toFixed(3)})`); b.style.transformOrigin = msgs[i].from === 'me' ? '100% 100%' : '0 100%'; });
    };
  };

  // 14. Chiffre clé (uniquement si fourni par le client)
  SC.stat_number = function (root, shot, p) {
    const raw = String(p.value || '').trim(); const m = raw.match(/^([^0-9]*)([0-9]+(?:[.,][0-9]+)?)(.*)$/);
    const pre = m ? m[1] : '', num = m ? parseFloat(m[2].replace(',', '.')) : 0, post = m ? m[3] : raw, dec = m && /[.,]/.test(m[2]) ? 1 : 0;
    const big = mk(root, 'a anton ctr', '', `top:520px;left:40px;width:1000px;font-size:330px;color:${C.accent};line-height:1;white-space:nowrap`);
    const lab = mk(root, 'a anton ctr', esc(up(p.label || '')), `top:900px;left:60px;width:960px;color:${inkFor(shot.tone)};line-height:1.05`); fit(lab, 960, 110, 56, 260);
    const src = p.source ? mk(root, 'a ctr', esc(p.source), `top:1700px;font-size:26px;color:${subFor(shot.tone)}`) : null;
    const svg = mk(root, 'a', '<svg width="1080" height="1920"></svg>', 'left:0;top:0').firstElementChild;
    const tN = wordTime(shot, p.at || raw, 0.1), tL = wordTime(shot, p.label_at, 0.45);
    ev(tN, 'impact', 0.9); for (let i = 0; i < 12; i++) ev(tN + i * 0.07, 'tick', 0.6); ev(tN + 0.9, 'ding', 0.6); ev(tL, 'pop', 0.8); IMPACTS.push(tN);
    return (t) => {
      const f = m ? eo((t - tN) / 0.9) : 1; big.textContent = m ? `${pre}${(num * f).toFixed(dec).replace('.', ',')}${post}` : raw;
      fit(big, 1000, 330, 120); const q = pop(t, tN, 14, 0.5); vis(big, clamp((t - tN) * 6)); tf(big, `scale(${(0.4 + 0.6 * q).toFixed(3)})`);
      const u = clamp((t - tL) / 0.3); vis(lab, u); tf(lab, `translateY(${((1 - eo(u)) * 30).toFixed(0)}px)`);
      if (src) vis(src, u * 0.9);
      let s = ''; for (let i = 0; i < 14; i++) { const a = i / 14 * Math.PI * 2, r = 330 + 60 * eo((t - tN) / 0.6); const o = clamp(1 - (t - tN) / 0.8); s += `<circle cx="${540 + r * Math.cos(a)}" cy="${690 + r * Math.sin(a) * 0.6}" r="10" fill="${C.accent}" opacity="${o.toFixed(2)}"/>`; }
      svg.innerHTML = t > tN ? s : '';
    };
  };

  // 15. Carte de fin (marque, slogan, bouton pulsant, mention légale)
  SC.end_card = function (root, shot, p) {
    const rs = mk(root, 'a', '<svg width="1920" height="1920"></svg>', 'left:-420px;top:-300px').firstElementChild; rays(rs, `rgba(${C.accentRGB},.10)`);
    const em = mk(root, 'a', '', 'left:390px;top:320px'); const eh = emblem(em, p.emblem || 'shield', 300, 26);
    const brand = p.brand ? mk(root, 'a ctr', esc(up(p.brand)), `top:${340 + eh + 20}px;font-size:40px;font-weight:800;letter-spacing:.2em;color:${subFor(shot.tone)}`) : null;
    const e1 = mk(root, 'a anton ctr', '', `top:${420 + eh + 40}px;left:50px;width:980px;color:${C.accent};line-height:1.02`); prepDrop(e1, up(p.slogan || '')); fit(e1, 980, 150, 70, 330);
    const btn = mk(root, 'a', `<span class="anton" style="font-size:66px;color:${C.onAccent}">${esc(up(p.button || 'CLIQUEZ SUR LE BOUTON'))}</span>`, `left:170px;top:1200px;width:740px;height:150px;border-radius:75px;background:${C.accent};display:flex;align-items:center;justify-content:center`);
    fit(btn.firstElementChild, 680, 66, 36);
    const chv = mk(root, 'a', '<svg width="140" height="170"></svg>', 'left:470px;top:1370px'); const chs = chevrons(chv.firstElementChild, C.accent, 140, 170);
    const disc = p.disclaimer ? mk(root, 'a ctr', esc(p.disclaimer), `top:1580px;left:80px;width:920px;font-size:24px;font-weight:500;color:${subFor(shot.tone)};line-height:1.35`) : null;
    const tE = shot.start + 0.05, tS = wordTime(shot, p.at, 0.1), tB = Math.max(tS + 0.9, shot.start + 0.9);
    ev(tE, 'impact', 0.7); ev(tE + 0.05, 'shimmer', 0.7); dropEvents(e1, tS); ev(tB, 'pop', 0.9); ev(tB + 0.05, 'ding', 0.7);
    return (t) => {
      rs.firstChild.setAttribute('transform', `rotate(${(t * 10).toFixed(1)} 960 960)`);
      const h = pop(t, tE, 10, 0.6); vis(em, clamp((t - tE) * 5));
      tf(em, `perspective(1600px) translateY(${((1 - h) * -300).toFixed(0)}px) rotateY(${(Math.sin((t - tE) * 2) * 18 + (1 - h) * 180).toFixed(1)}deg) scale(${(0.6 + 0.4 * h + 0.03 * Math.sin(t * 4)).toFixed(3)})`);
      if (brand) vis(brand, clamp((t - tE - 0.3) / 0.3));
      drop(e1, t, tS);
      const b = pop(t, tB, 14, 0.5); vis(btn, clamp((t - tB) * 6)); tf(btn, `scale(${((0.4 + 0.6 * b) * (1 + 0.04 * Math.max(0, Math.sin((t - tB) * 7)))).toFixed(3)})`);
      chs.forEach((e, i) => { e.style.opacity = (clamp((t - tB - 0.3 - i * 0.1) * 5) * (0.4 + 0.6 * Math.max(0, Math.sin((t - tB) * 6 - i * 0.9)))).toFixed(2); });
      if (disc) vis(disc, clamp((t - tB - 0.3) / 0.4) * 0.9);
    };
  };


  // 16. Plan 2D → maquette 3D (architecture, immobilier, construction, aménagement)
  //     Le plan se dessine trait par trait, l'IA le scanne, puis il bascule en
  //     perspective et les murs sortent du sol.
  SC.plan_to_3d = function (root, shot, p) {
    const PW = 700, PH = 520, WH = 150; // plan en unités px, hauteur des murs
    const walls = [[0, 0, 700, 0], [700, 0, 700, 520], [700, 520, 0, 520], [0, 520, 0, 0],
      [300, 0, 300, 210], [0, 300, 190, 300], [280, 300, 700, 300], [480, 380, 480, 520]];
    const rooms = [[0, 0, 300, 300, 'SÉJOUR'], [300, 0, 400, 300, 'CUISINE'], [0, 300, 480, 220, 'CHAMBRE'], [480, 300, 220, 220, 'BAIN']];
    const ink = inkFor(shot.tone), line = shot.tone === 'light' ? C.ink : '#EAF2FF';
    // grille « papier calque »
    const grid = mk(root, 'a', '', `left:0;top:0;width:1080px;height:1920px;background-image:linear-gradient(rgba(${C.accentRGB},.10) 1px,transparent 1px),linear-gradient(90deg,rgba(${C.accentRGB},.10) 1px,transparent 1px);background-size:60px 60px`);
    const t1 = mk(root, 'a anton ctr', '', `top:250px;left:60px;width:960px;color:${ink};line-height:1.02`); prepDrop(t1, up(p.title || 'DU PLAN 2D À LA 3D')); fit(t1, 960, 120, 64, 260);
    const tag = mk(root, 'a ctr', '', 'top:1620px');
    tag.innerHTML = `<span class="pill anton" style="font-size:64px;background:${C.accent};color:${C.onAccent};padding:10px 40px"><span class="l2">${esc(up(p.label_2d || 'PLAN 2D'))}</span><span class="l3" style="display:none">${esc(up(p.label_3d || 'MODÈLE 3D'))}</span></span>`;
    const l2 = tag.querySelector('.l2'), l3 = tag.querySelector('.l3');
    const wrap = mk(root, 'a', '', `left:${540 - PW / 2}px;top:${1010 - PH / 2}px;width:${PW}px;height:${PH}px;perspective:2400px;perspective-origin:50% 30%`);
    const iso = mk(wrap, 'a', '', `left:0;top:0;width:${PW}px;height:${PH}px;transform-style:preserve-3d;transform-origin:50% 50%`);
    // sols des pièces (apparaissent en 3D)
    const floors = rooms.map(([x, y, w, h], i) => mk(iso, 'a', '', `left:${x}px;top:${y}px;width:${w}px;height:${h}px;background:${['#C9A27A', '#E8E4DC', '#B98D63', '#DCE6EE'][i % 4]};opacity:0`));
    // plan SVG (traits qui se dessinent)
    let d = '';
    walls.forEach(([x1, y1, x2, y2]) => { d += `<path d="M${x1} ${y1}L${x2} ${y2}" pathLength="1" stroke-dasharray="1 1" stroke-dashoffset="1" class="w"/>`; });
    const doors = [[190, 300, 90, 0], [300, 210, 90, 1], [480, 300, 80, 0]];
    doors.forEach(([x, y, r, v]) => { d += v ? `<path class="dr" d="M${x} ${y}A${r} ${r} 0 0 1 ${x - r} ${y + r}" pathLength="1" stroke-dasharray="1 1" stroke-dashoffset="1"/>` : `<path class="dr" d="M${x} ${y}A${r} ${r} 0 0 0 ${x + r} ${y - r}" pathLength="1" stroke-dasharray="1 1" stroke-dashoffset="1"/>`; });
    [[80, 0, 160, 0], [420, 0, 560, 0], [700, 90, 700, 220], [0, 360, 0, 460], [560, 520, 650, 520]].forEach(([x1, y1, x2, y2]) => { d += `<path class="wi" d="M${x1} ${y1}L${x2} ${y2}"/>`; });
    const svg = mk(iso, 'a', `<svg width="${PW + 40}" height="${PH + 40}" viewBox="-20 -20 ${PW + 40} ${PH + 40}" style="overflow:visible"><g fill="none" stroke-linecap="square">${d}</g>` +
      rooms.map(([x, y, w, h, n]) => `<text class="rn" x="${x + w / 2}" y="${y + h / 2 + 10}" text-anchor="middle" font-family="Poppins" font-weight="700" font-size="26" letter-spacing="3" fill="${line}" opacity="0">${esc(n)}</text>`).join('') +
      `<line class="dim" x1="0" y1="-14" x2="700" y2="-14" stroke="${C.accent}" stroke-width="2" opacity="0"/></svg>`, 'left:-20px;top:-20px');
    svg.querySelectorAll('.w').forEach((e) => { e.setAttribute('stroke', line); e.setAttribute('stroke-width', '12'); });
    svg.querySelectorAll('.dr').forEach((e) => { e.setAttribute('stroke', C.accent); e.setAttribute('stroke-width', '4'); });
    svg.querySelectorAll('.wi').forEach((e) => { e.setAttribute('stroke', C.accent); e.setAttribute('stroke-width', '16'); e.setAttribute('opacity', '0'); });
    const pw = [...svg.querySelectorAll('.w')], pd = [...svg.querySelectorAll('.dr')], pwi = [...svg.querySelectorAll('.wi')], rn = [...svg.querySelectorAll('.rn')];
    // murs 3D
    const w3 = walls.map(([x1, y1, x2, y2], i) => {
      const len = Math.hypot(x2 - x1, y2 - y1), ang = Math.atan2(y2 - y1, x2 - x1) * 180 / Math.PI;
      const shade = Math.abs(Math.cos(ang * Math.PI / 180)) > 0.5 ? ['#FFFFFF', '#E7E1D6'] : ['#E4DDD0', '#C9C0B0'];
      const el = mk(iso, 'a', '', `left:0;top:0;width:${len}px;height:${WH}px;transform-origin:0 0;background:linear-gradient(180deg,${shade[0]},${shade[1]});border-top:6px solid ${C.accent};box-sizing:border-box;backface-visibility:visible;opacity:0`);
      el._base = `translate3d(${x1}px,${y1}px,0) rotateZ(${ang}deg) rotateX(-90deg)`;
      return el;
    });
    // mobilier (volumes simples) + ombre portée: la maquette prend du corps
    const shadow = mk(iso, 'a', '', `left:-10px;top:-10px;width:${PW + 20}px;height:${PH + 20}px;background:rgba(0,0,0,.45);filter:blur(22px);transform:translateZ(-2px);opacity:0`);
    iso.insertBefore(shadow, iso.firstChild);
    const FUR = [[40, 60, 190, 80, 45, '#3D4A66'], [380, 90, 140, 140, 70, '#8C6A4A'], [60, 360, 200, 150, 40, '#F2F2F2'], [520, 340, 150, 90, 45, '#DDE8F2'], [590, 30, 90, 200, 85, '#6B7280']];
    const furn = FUR.map(([x, y, w, h, z, col]) => {
      const g = mk(iso, 'a', '', `left:${x}px;top:${y}px;width:${w}px;height:${h}px;transform-style:preserve-3d;opacity:0`);
      const face = (st) => mk(g, 'a', '', st + ';backface-visibility:visible;box-sizing:border-box');
      face(`left:0;top:0;width:${w}px;height:${h}px;background:${col};border:3px solid rgba(255,255,255,.35);transform:translateZ(${z}px)`);
      face(`left:0;top:${h}px;width:${w}px;height:${z}px;background:${col};filter:brightness(.72);transform-origin:0 0;transform:rotateX(90deg)`);
      face(`left:${w}px;top:0;width:${z}px;height:${h}px;background:${col};filter:brightness(.55);transform-origin:0 0;transform:rotateY(-90deg)`);
      face(`left:0;top:0;width:${w}px;height:${z}px;background:${col};filter:brightness(.8);transform-origin:0 0;transform:rotateX(90deg)`);
      face(`left:0;top:0;width:${z}px;height:${h}px;background:${col};filter:brightness(.62);transform-origin:0 0;transform:rotateY(-90deg)`);
      return g;
    });
    // barre de scan IA
    const scan = mk(iso, 'a', '', `left:-30px;top:0;width:${PW + 60}px;height:10px;background:${C.accent};box-shadow:0 0 40px 14px rgba(${C.accentRGB},.55);opacity:0`);
    const ai = mk(root, 'a', `<span class="pill" style="display:inline-flex;align-items:center;gap:14px;background:rgba(0,0,0,.55);border:2px solid ${C.accent};font-weight:800;font-size:40px;color:#fff">${icon('sparkle', 44, C.accent, 2)}${esc(p.ai_label || 'IA')}</span>`, 'left:0;width:1080px;text-align:center;top:1500px');
    const tD = wordTime(shot, p.at, 0.02) + 0.05, t3 = wordTime(shot, p.to3d_at || '3d', 0.55), tS = t3 - 0.95;
    dropEvents(t1, wordTime(shot, p.title_at, 0) );
    walls.forEach((_, i) => ev(tD + i * 0.12, 'tick', 0.7)); ev(tD + 1.0, 'pop_low', 0.5);
    ev(tS, 'riser', 0.8); ev(tS + 0.05, 'blip', 0.6); ev(t3, 'whoosh_deep', 0.9); ev(t3 + 0.35, 'impact_big', 1); ev(t3 + 0.4, 'shimmer', 0.9);
    walls.forEach((_, i) => ev(t3 + 0.3 + i * 0.05, 'thud', 0.25));
    FUR.forEach((_, i) => ev(t3 + 0.75 + i * 0.09, 'pop_low', 0.5));
    IMPACTS.push(t3 + 0.35); FLASHES.push(t3 + 0.35);
    return (t) => {
      drop(t1, t, wordTime(shot, p.title_at, 0));
      vis(grid, clamp((t - shot.start) / 0.4) * (1 - 0.5 * clamp((t - t3) / 0.6)));
      pw.forEach((e, i) => e.setAttribute('stroke-dashoffset', (1 - eo((t - tD - i * 0.12) / 0.35)).toFixed(3)));
      pd.forEach((e, i) => e.setAttribute('stroke-dashoffset', (1 - eo((t - tD - 0.9 - i * 0.1) / 0.3)).toFixed(3)));
      pwi.forEach((e, i) => e.setAttribute('opacity', clamp((t - tD - 1.0 - i * 0.06) / 0.2).toFixed(2)));
      const u = eio((t - t3) / 0.75); // bascule 2D → 3D
      rn.forEach((e, i) => e.setAttribute('opacity', (clamp((t - tD - 1.1 - i * 0.08) / 0.25) * (1 - u)).toFixed(2)));
      svg.querySelector('.dim').setAttribute('opacity', (clamp((t - tD - 1.3) / 0.3) * (1 - u)).toFixed(2));
      const spin = t > t3 ? (t - t3) * 5 : 0;
      tf(iso, `translate(${(u * 30).toFixed(1)}px,${(u * 20).toFixed(1)}px) rotateX(${(56 * u).toFixed(2)}deg) rotateZ(${(-38 * u - spin).toFixed(2)}deg) scale(${(1.25 - 0.12 * u).toFixed(3)})`);
      const draw = clamp((t - tD) / 0.3);
      vis(wrap, draw);
      floors.forEach((f, i) => { f.style.opacity = (0.95 * clamp((t - t3 - 0.2 - i * 0.05) / 0.3)).toFixed(2); });
      shadow.style.opacity = (0.9 * u).toFixed(2);
      furn.forEach((g, i) => { const r = pop(t, t3 + 0.75 + i * 0.09, 15, 0.55); g.style.opacity = t > t3 + 0.72 + i * 0.09 ? '1' : '0'; g.style.transform = `translateZ(${((1 - r) * 260).toFixed(1)}px)`; });
      w3.forEach((e, i) => {
        const r = pop(t, t3 + 0.3 + i * 0.05, 13, 0.6);
        e.style.opacity = t > t3 + 0.25 + i * 0.05 ? '1' : '0';
        e.style.transform = `${e._base} scaleY(${Math.max(0.001, r).toFixed(3)})`;
      });
      const sc = clamp((t - tS) / 0.9); vis(scan, sc > 0 && sc < 1 ? 1 : 0); scan.style.top = (sc * PH - 5).toFixed(0) + 'px';
      vis(ai, clamp((t - tS) * 5) * (1 - clamp((t - t3 - 0.6) * 3)));
      const q = pop(t, tD, 14, 0.55); vis(tag, clamp((t - tD) * 5)); tf(tag, `scale(${((0.5 + 0.5 * q) * (1 + 0.12 * Math.max(0, 1 - Math.abs(t - t3 - 0.35) / 0.2))).toFixed(3)})`);
      l2.style.display = t < t3 + 0.35 ? '' : 'none'; l3.style.display = t < t3 + 0.35 ? 'none' : '';
    };
  };

  // Scène par défaut si le type est inconnu.
  SC.default = SC.title_slam;

  // ================================================================== RUNTIME
  const FLASHES = [];
  const stage = $('stage'), cam = $('cam');
  // Mode incrustation (face caméra): fond transparent, chaque plan entre ET sort
  // par-dessus la vidéo de la personne.
  const OVERLAY = !!STORY.overlay;
  if (OVERLAY) { document.documentElement.style.background = 'transparent'; document.body.style.background = 'transparent'; stage.style.background = 'transparent'; }
  const shots = STORY.shots;
  const T = STORY.duration;
  const built = [];
  // Extension « Studio » (face caméra): ADN de style, scènes flottantes, sous-titres,
  // logo, transitions. Chargée AVANT ce script; absente pour la pub explicative.
  const EXT = typeof window.CF_STUDIO_INIT === 'function' ? window.CF_STUDIO_INIT({
    SC, mk, vis, tf, clamp, lerp, eo, eio, S, pop, rnd, esc, norm, up, ev, IMPACTS, FLASHES, icon, IC, emblem,
    prepDrop, drop, dropEvents, fit, wordTime, itemTimes, inkFor, subFor, rays, chevrons, person, HAND, CURSOR,
    C, TPL, STORY, stage, cam, $,
  }) : null;
  function bgFor(tone) {
    if (tone === 'light') return `radial-gradient(ellipse at 50% 40%,${C.light1} 0%,${C.light2} 55%,${C.light3} 100%)`;
    if (tone === 'alarm') return `radial-gradient(ellipse at 50% 55%,${C.alarm1} 0%,${C.alarm2} 60%,#080204 100%)`;
    if (tone === 'split') return '#000';
    return `radial-gradient(ellipse at 50% 42%,${C.dark2} 0%,${C.dark1} 55%,${C.dark0} 100%)`;
  }
  function build() {
    shots.forEach((shot, i) => {
      const el = mk(cam, 'sc', '', `background:${EXT && EXT.bgFor ? EXT.bgFor(shot) : bgFor(shot.tone)}`);
      const fn = SC[shot.scene.type] || SC.default;
      let upd;
      // visible pendant la construction: fit() a besoin des vraies mesures de mise en page
      el.style.display = 'block';
      try { upd = fn(el, shot, shot.scene); } catch (e) { console.error('scene', shot.scene.type, e); el.innerHTML = ''; upd = SC.title_slam(el, shot, { title: shot.text }); }
      if (EXT && EXT.decorate) EXT.decorate(el, shot, i);
      el.style.display = 'none';
      built.push({ el, shot, upd });
      if (EXT) return; // l'extension pose ses propres sons de transition
      if (i > 0 || OVERLAY) ev(shot.start - 0.28, TPL.transition === 'zoom' ? 'whoosh_deep' : 'whoosh', 0.7);
      if (OVERLAY) ev(shot.end - 0.2, 'whoosh', 0.45);
    });
    if (EXT && EXT.build) EXT.build();
    // grain animé déterministe
    const g = $('grain'); const x = g.getContext('2d'); const im = x.createImageData(600, 1040);
    for (let i = 0; i < im.data.length; i += 4) { const v = Math.floor(rnd(i * 0.37) * 255); im.data[i] = im.data[i + 1] = im.data[i + 2] = v; im.data[i + 3] = 255; }
    x.putImageData(im, 0, 0); g.style.opacity = String(TPL.grain == null ? 0.07 : TPL.grain);
    EVENTS.sort((a, b) => a.t - b.t);
  }
  function transition(el, t, a, b, last, shot) {
    if (EXT && EXT.transition) { EXT.transition(el, t, a, b, shot); return; }
    const D = 0.3; let tr = '', bl = 0; const sc = 1 + (TPL.pushIn == null ? 0.04 : TPL.pushIn) * clamp((t - a) / Math.max(0.1, b - a));
    const kind = TPL.transition || 'whip';
    if ((a > 0 || OVERLAY) && t < a + D / 2) {
      const u = eo((t - (a - D / 2)) / D);
      if (kind === 'zoom') { tr = `scale(${(0.7 + 0.3 * u).toFixed(4)})`; bl = (1 - u) * 20; el.style.opacity = u.toFixed(3); }
      else if (kind === 'slide') { tr = `translateX(${((1 - u) * 1080).toFixed(1)}px)`; bl = (1 - u) * 18; }
      else { tr = `translateY(${((1 - u) * 700).toFixed(1)}px)`; bl = (1 - u) * 26; }
    } else if (!last && t > b - D / 2) {
      const u = eio((t - (b - D / 2)) / D);
      if (kind === 'zoom') { tr = `scale(${(1 + 0.6 * u).toFixed(4)})`; bl = u * 20; el.style.opacity = (1 - u).toFixed(3); }
      else if (kind === 'slide') { tr = `translateX(${(-u * 1080).toFixed(1)}px)`; bl = u * 18; }
      else { tr = `translateY(${(-u * 700).toFixed(1)}px)`; bl = u * 26; }
    } else el.style.opacity = '1';
    el.style.transform = `${tr} scale(${sc.toFixed(4)})`; el.style.filter = bl > 0.3 ? `blur(${bl.toFixed(1)}px)` : 'none';
  }
  function seek(t) {
    let sx = 0, sy = 0;
    IMPACTS.forEach((k, i) => { const d = t - k; if (d > 0 && d < 0.35) { const a = (1 - d / 0.35) * 13 * (TPL.shake == null ? 1 : TPL.shake); sx += a * Math.sin(d * 90 + i); sy += a * Math.cos(d * 77 + i * 2); } });
    // en incrustation, un léger zoom pendant la secousse évite de découvrir le visage sur les bords
    tf(cam, `translate(${sx.toFixed(1)}px,${sy.toFixed(1)}px)${OVERLAY && (sx || sy) ? ' scale(1.03)' : ''}`);
    const g = $('grain'); tf(g, `translate(${-Math.floor(rnd(Math.floor(t * 12)) * 60)}px,${-Math.floor(rnd(Math.floor(t * 12) + 5) * 60)}px)`);
    if (EXT && EXT.grainOn) g.style.display = EXT.grainOn(t) ? '' : 'none';
    else if (OVERLAY) g.style.display = built.some(({ shot }) => t >= shot.start + 0.15 && t <= shot.end - 0.15) ? '' : 'none';
    let fl = 0; FLASHES.forEach((k) => { if (t > k) fl = Math.max(fl, Math.max(0, 1 - (t - k) / 0.25) * 0.55); });
    $('flash').style.opacity = fl.toFixed(3);
    built.forEach(({ el, shot, upd }, i) => {
      const a = shot.start, b = shot.end, D = EXT ? 0.5 : 0.3, last = !OVERLAY && i === built.length - 1;
      const kept = EXT && EXT.keep && EXT.keep(shot); // étapes d'un voyage: toujours présentes sur la carte
      if (!kept && (t < a - D / 2 || (!last && t > b + D / 2))) { el.style.display = 'none'; return; }
      el.style.display = 'block'; transition(el, t, a, b, last, shot);
      try { upd(t); } catch (e) { console.error(e); }
    });
    if (EXT && EXT.update) EXT.update(t);
  }
  window.seek = seek; window.DURATION = T; window.EVENTS = EVENTS;
  // Studio: le visage est une suite d'images; on attend leur décodage avant la capture.
  window.seekAsync = (t) => { seek(t); return EXT && EXT.ready ? EXT.ready() : Promise.resolve(); };
  // Les polices ne se chargent qu'au premier usage: on force leur chargement AVANT
  // de construire (sinon fit() mesure une police de repli et réduit trop le texte).
  const FONT_LOADS = ['100px Anton', '100px Bebas', '100px DMSerif', '500 40px Poppins', '700 40px Poppins', '800 40px Poppins'];
  window.READY = Promise.all(FONT_LOADS.map((f) => document.fonts.load(f).catch(() => null)).concat(EXT && EXT.preload ? [EXT.preload()] : []))
    .then(() => document.fonts.ready).then(() => { build(); seek(0); return true; });
  if (!/render/.test(location.search)) {
    window.READY.then(() => { const t0 = performance.now(); (function loop() { seek(((performance.now() - t0) / 1000) % T); requestAnimationFrame(loop); })(); });
  }
})();
