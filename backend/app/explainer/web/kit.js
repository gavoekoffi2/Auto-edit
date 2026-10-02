/*
 * KIT — socle commun des modes de montage « nouvelle génération » (multi-format).
 *
 * window.STORY = { duration, format:{w,h}, shots:[{start,end,speechEnd,words,text,scene}],
 *                  accent, accent2, product:{img,cut,name}, logo, photos:[dataURL], screens:[dataURL], brand, keywords }
 * Un mode de montage s'enregistre avec KIT.register({ name, SCENES, background(t, tint), transition(i, b, nx), caps, grain })
 * puis KIT.start() construit tous les plans et expose window.seek / EVENTS / READY / DURATION.
 *
 * Mise en page par ZONES : chaque scène place ses éléments dans des zones (titre, héros, liste, sous-titre…)
 * calculées selon le format (9:16, 4:5, 1:1, 16:9) — le même montage s'adapte à chaque réseau.
 */
(function () {
  const S = window.STORY || {};
  const W = (S.format && S.format.w) || 1080, H = (S.format && S.format.h) || 1920;
  const R = H / W;
  const O = R > 1.5 ? 'portrait' : R > 1.15 ? 'tall' : R > 0.85 ? 'square' : 'landscape';
  const DUR = S.duration || 10;
  const $ = (s) => document.getElementById(s);
  const cl = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  const P = (t, a, b) => cl((t - a) / Math.max(1e-6, b - a));
  const eo = (x) => 1 - Math.pow(1 - x, 3), ei = (x) => x * x * x, eio = (x) => (x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
  const back = (x) => { const c1 = 1.7, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
  const elastic = (x) => (x <= 0 ? 0 : x >= 1 ? 1 : Math.pow(2, -10 * x) * Math.sin((x * 10 - .75) * (2 * Math.PI) / 3) + 1);
  const lerp = (a, b, x) => a + (b - a) * x;
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const norm = (s) => String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]/g, '');

  // ---------------------------------------------------------------- zones par format
  const ZONES = {
    portrait: { title: [60, 150, W - 120, 430], hero: [60, 620, W - 120, 800], list: [70, 560, W - 140, 860], sub: [60, 1430, W - 120, 170], caps: [60, 1440, W - 120, 200], full: [0, 0, W, H], top: [60, 90, W - 120, 160], footer: [60, H - 420, W - 120, 260], center: [60, 560, W - 120, 800] },
    tall: { title: [60, 70, W - 120, 300], hero: [60, 390, W - 120, 690], list: [70, 380, W - 140, 760], sub: [60, 1100, W - 120, 130], caps: [60, H - 230, W - 120, 150], full: [0, 0, W, H], top: [60, 40, W - 120, 110], footer: [60, H - 260, W - 120, 200], center: [60, 330, W - 120, 690] },
    square: { title: [60, 50, W - 120, 240], hero: [80, 300, W - 160, 560], list: [70, 290, W - 140, 620], sub: [60, 880, W - 120, 110], caps: [60, H - 175, W - 120, 130], full: [0, 0, W, H], top: [60, 30, W - 120, 90], footer: [60, H - 210, W - 120, 170], center: [60, 260, W - 120, 560] },
    landscape: { title: [90, 170, 860, 360], hero: [1000, 80, 840, 920], list: [90, 360, 860, 620], sub: [90, 560, 860, 220], caps: [260, H - 175, W - 520, 130], full: [0, 0, W, H], top: [90, 60, 860, 110], footer: [90, H - 300, 860, 220], center: [460, 140, 1000, 800] },
  };
  const Z = (name) => { const z = (ZONES[O] || ZONES.portrait)[name] || ZONES.portrait.full; return { x: z[0], y: z[1], w: z[2], h: z[3] }; };
  const place = (el, z, extra = '') => { el.style.cssText += `;position:absolute;left:${z.x}px;top:${z.y}px;width:${z.w}px;height:${z.h}px;${extra}`; return el; };

  const EVENTS = [];
  const ev = (t, sfx, gain = 1) => { if (isFinite(t) && t >= 0 && t < DUR) EVENTS.push({ t: +t.toFixed(3), sfx, gain }); };
  let SHAKE = 0, FLASH = 0;
  const kick = (t, t0, amp = 18, dur = .3) => { if (t >= t0 && t < t0 + dur) SHAKE = Math.max(SHAKE, amp * (1 - (t - t0) / dur)); };
  const flash = (t, t0, a = .5, dur = .2) => { if (t >= t0 && t < t0 + dur) FLASH = Math.max(FLASH, a * (1 - (t - t0) / dur)); };
  const mk = (parent, html) => { const d = document.createElement('div'); d.innerHTML = html.trim(); const e = d.firstElementChild; parent.appendChild(e); return e; };
  const pop = (el, t, t0, dur = .45, dy = 50, sc = .6) => { const q = P(t, t0, t0 + dur), b = back(q); el.style.opacity = cl(q * 3); el.style.transform = `translateY(${(1 - b) * dy}px) scale(${lerp(sc, 1, b)})`; return q; };
  const slam = (el, t, t0, from = 2, dur = .28, extra = '') => { const q = P(t, t0, t0 + dur); el.style.opacity = t >= t0 ? 1 : 0; el.style.transform = `scale(${lerp(from, 1, eo(q))}) ${extra}`; return q; };
  const slide = (el, t, t0, dx, dy = 0, dur = .5) => { const q = P(t, t0, t0 + dur), b = back(q); el.style.opacity = cl(q * 3); el.style.transform = `translate(${(1 - b) * dx}px,${(1 - b) * dy}px)`; return q; };
  const fade = (el, t, t0, dur = .35) => { const q = P(t, t0, t0 + dur); el.style.opacity = q; return q; };

  function textW(el) { const r = document.createRange(); r.selectNodeContents(el); return r.getBoundingClientRect().width; }
  function fit(el, maxW, minPx = 22) {
    if (!el.style.whiteSpace) el.style.whiteSpace = 'nowrap';
    let fs = parseFloat(getComputedStyle(el).fontSize), g = 80;
    while (textW(el) > maxW && fs > minPx && g--) { fs *= .95; el.style.fontSize = fs + 'px'; }
    return fs;
  }
  // texte multi-lignes qui tient dans une boîte (largeur et hauteur)
  function fitBox(el, maxW, maxH, minPx = 22) {
    el.style.whiteSpace = 'normal';
    let fs = parseFloat(getComputedStyle(el).fontSize), g = 90;
    const over = () => el.scrollHeight > maxH + 2 || [...el.querySelectorAll('.ln,.w,.wd')].some((x) => x.getBoundingClientRect().width > maxW + 2) || el.scrollWidth > maxW + 2;
    while (over() && fs > minPx && g--) { fs *= .95; el.style.fontSize = fs + 'px'; }
    return fs;
  }
  // mots et lettres animables
  function words(text, cls = 'w') { return String(text).split(/\s+/).filter(Boolean).map((w) => `<span class="${cls}" style="display:inline-block;white-space:pre">${esc(w)} </span>`).join(''); }
  // lettres animables, regroupées par mot (un mot ne se coupe jamais en fin de ligne)
  function letters(text) { return String(text).split(/(\s+)/).filter((x) => x !== '').map((wd) => (/^\s+$/.test(wd) ? ' ' : `<span class="wd" style="display:inline-block;white-space:nowrap">${[...wd].map((c) => `<span class="lt" style="display:inline-block">${esc(c)}</span>`).join('')}</span>`)).join(''); }
  // révélation lettre par lettre (flou + saut), style « frappe »
  function typeIn(el, t, t0, dur = .6, mode = 'blur') {
    const ls = el.__lt || (el.__lt = [...el.querySelectorAll('.lt')]);
    const n = ls.length || 1;
    ls.forEach((s, i) => {
      const a = t0 + dur * i / n, q = P(t, a, a + .18);
      s.style.opacity = q;
      if (mode === 'bounce') s.style.transform = `translateY(${(1 - eo(q)) * 30 * (i % 2 ? 1 : -1)}px)`;
      else if (mode === 'drop') s.style.transform = `translateY(${(1 - back(q)) * -40}px)`;
      else s.style.filter = q < 1 ? `blur(${(1 - q) * 8}px)` : 'none';
    });
  }
  function wordsIn(el, t, times, mode = 'rise') {
    const ws = el.__w || (el.__w = [...el.querySelectorAll('.w')]);
    ws.forEach((s, i) => { const t0 = times[Math.min(i, times.length - 1)] + (i >= times.length ? (i - times.length + 1) * .12 : 0); const q = P(t, t0 - .05, t0 + .25); s.style.opacity = q; s.style.transform = mode === 'rise' ? `translateY(${(1 - eo(q)) * 26}px)` : `scale(${lerp(1.6, 1, eo(q))})`; });
  }

  // ---------------------------------------------------------------- minutage par plan
  function timer(sh) {
    const ws = sh.words || [];
    const span = [sh.start + .05, Math.max(sh.start + .4, sh.speechEnd || sh.end)];
    const T = {
      span, words: ws,
      at(q, n = 0, frac = null) {
        if (q != null && q !== '') {
          const k = norm(q); let c = 0;
          for (const w of ws) { const nw = norm(w.w); if (nw && (nw === k || (k.length > 2 && nw.includes(k)) || (nw.length > 3 && k.startsWith(nw)))) { if (c === n) return w.s; c++; } }
        }
        return lerp(span[0], span[1], frac == null ? 0 : frac);
      },
      frac: (f) => lerp(span[0], span[1], f),
      seq(list, key = 'at', a = .05, b = .85) { // instants croissants pour une liste d'éléments {at}
        const out = list.map((it, i) => T.at(it && typeof it === 'object' ? it[key] : null, 0, lerp(a, b, list.length > 1 ? i / (list.length - 1) : 0)));
        for (let i = 1; i < out.length; i++) if (out[i] <= out[i - 1] + .2) out[i] = out[i - 1] + .3;
        return out;
      },
      lineStarts(lines) {
        const out = []; let from = 0;
        lines.forEach((ln, i) => {
          const first = norm(String(ln).split(/\s+/)[0]); let tt = null;
          for (let j = from; j < ws.length; j++) if (norm(ws[j].w) === first || (first.length > 3 && norm(ws[j].w).startsWith(first))) { tt = ws[j].s; from = j + 1; break; }
          out.push(tt == null ? lerp(span[0], span[1], i / Math.max(1, lines.length)) : tt);
        });
        for (let i = 1; i < out.length; i++) if (out[i] < out[i - 1]) out[i] = out[i - 1] + .25;
        return out;
      },
      wordTimes(text) { // instants de chaque mot d'un texte affiché, appariés à la voix
        const tw = String(text).split(/\s+/).filter(Boolean); const out = []; let j = 0;
        tw.forEach((w, i) => { const k = norm(w); let hit = null; for (let m = j; m < Math.min(ws.length, j + 6); m++) if (k && norm(ws[m].w) === k) { hit = m; break; } if (hit != null) { out.push(ws[hit].s); j = hit + 1; } else out.push(out.length ? out[out.length - 1] + .14 : span[0] + i * .14); });
        return out;
      },
    };
    return T;
  }

  // ---------------------------------------------------------------- bibliothèque graphique
  const ACC = S.accent || '#7C3AED', ACC2 = S.accent2 || '#FFD60A';
  const PRODUCT = S.product || {};
  const LIB = {
    box(w, label) {
      const words_ = String(label || PRODUCT.name || 'VOTRE PRODUIT').toUpperCase().split(/\s+/).slice(0, 4);
      const half = Math.ceil(words_.length / 2), l1 = words_.slice(0, half).join(' '), l2 = words_.slice(half).join(' ');
      return `<svg width="${w}" height="${w * 1.1}" viewBox="0 0 400 440"><defs><linearGradient id="bx${w}" x1="0" x2="1"><stop offset="0" stop-color="${ACC}"/><stop offset="1" stop-color="#1b1036"/></linearGradient></defs>
        <polygon points="70,40 330,40 330,400 70,400" fill="url(#bx${w})"/><polygon points="330,40 375,70 375,425 330,400" fill="#120a26"/><polygon points="70,400 330,400 375,425 115,425" fill="#0c0718"/>
        <rect x="95" y="80" width="210" height="6" rx="3" fill="rgba(255,255,255,.5)"/>
        <text x="200" y="${l2 ? 205 : 230}" font-family="Anton,Poppins" font-weight="800" font-size="${l1.length > 10 ? 34 : 46}" fill="#fff" text-anchor="middle">${esc(l1)}</text>
        ${l2 ? `<text x="200" y="258" font-family="Anton,Poppins" font-weight="800" font-size="${l2.length > 10 ? 34 : 46}" fill="${ACC2}" text-anchor="middle">${esc(l2)}</text>` : ''}
        <rect x="95" y="330" width="120" height="14" rx="7" fill="rgba(255,255,255,.35)"/><rect x="95" y="352" width="80" height="10" rx="5" fill="rgba(255,255,255,.2)"/></svg>`;
    },
    product(w, framed = true) {
      if (PRODUCT.img) {
        if (PRODUCT.cut) return `<img src="${PRODUCT.img}" style="width:${w}px;height:${w}px;object-fit:contain;filter:drop-shadow(0 30px 40px rgba(0,0,0,.35))">`;
        return `<div style="width:${w}px;height:${w}px;border-radius:${w * .08}px;overflow:hidden;${framed ? 'box-shadow:0 30px 70px rgba(0,0,0,.35);border:6px solid #fff' : ''}"><img src="${PRODUCT.img}" style="width:100%;height:100%;object-fit:cover"></div>`;
      }
      return LIB.box(w);
    },
    photo(i, w, h, radius = 30) {
      const ph = (S.photos || [])[i % Math.max(1, (S.photos || []).length)];
      if (!ph) return null;
      return `<div style="width:${w}px;height:${h}px;border-radius:${radius}px;overflow:hidden"><img src="${ph}" style="width:100%;height:100%;object-fit:cover"></div>`;
    },
    phone(w, inner, dark = true) {
      const h = w * 2.05;
      return `<div class="kphone" style="position:relative;width:${w}px;height:${h}px;border-radius:${w * .14}px;background:${dark ? '#0c0c12' : '#e9e9ef'};padding:${w * .035}px;box-shadow:0 ${w * .1}px ${w * .25}px rgba(0,0,0,.35),inset 0 0 0 ${w * .012}px #3a3a46">
        <div style="position:absolute;left:50%;top:${w * .05}px;width:${w * .28}px;height:${w * .07}px;margin-left:-${w * .14}px;border-radius:${w * .04}px;background:#000;z-index:3"></div>
        <div class="kscr" style="position:relative;width:100%;height:100%;border-radius:${w * .11}px;overflow:hidden;background:#fff">${inner || ''}</div></div>`;
    },
    laptop(w, inner) {
      const h = w * .62;
      return `<div style="position:relative;width:${w}px"><div style="margin:0 auto;width:${w * .82}px;height:${h * .86}px;border-radius:${w * .02}px ${w * .02}px 0 0;background:#1a1a1f;padding:${w * .018}px;box-shadow:0 20px 50px rgba(0,0,0,.25)">
        <div class="kscr" style="width:100%;height:100%;overflow:hidden;background:#0f0f14;border-radius:4px">${inner || ''}</div></div>
        <div style="width:${w}px;height:${w * .035}px;background:linear-gradient(#d9d9de,#a9a9b2);border-radius:0 0 ${w * .03}px ${w * .03}px"></div></div>`;
    },
    // écran d'application généré (tableau de bord, formulaire, liste, succès)
    appScreen(kind, d = {}) {
      const c = d.color || ACC, title = esc(d.title || PRODUCT.name || 'Mon app');
      const head = `<div style="padding:9% 7% 4%;font:800 1.15em Poppins;color:#111">${title}</div>`;
      const rows = (d.rows || ['Logement', 'Alimentation', 'Transport', 'Loisirs']).slice(0, 5);
      if (kind === 'dashboard') return `<div style="font-size:${d.fs || 22}px;height:100%;background:#0f1424;color:#fff">${head.replace('#111', '#fff')}
        <div style="margin:0 auto;width:52%;aspect-ratio:1;border-radius:50%;background:conic-gradient(${c} 0 ${d.pct || 65}%,rgba(255,255,255,.12) 0);display:flex;align-items:center;justify-content:center"><div style="width:78%;aspect-ratio:1;border-radius:50%;background:#0f1424;display:flex;align-items:center;justify-content:center;font:800 1.6em Poppins">${d.pct || 65}%</div></div>
        ${rows.map((r, i) => `<div style="margin:5% 7% 0;display:flex;align-items:center;gap:6%;font:600 .8em Poppins"><div style="width:12%;aspect-ratio:1;border-radius:30%;background:rgba(255,255,255,.12)"></div><div style="flex:1">${esc(r)}<div style="height:.4em;margin-top:.4em;border-radius:1em;background:rgba(255,255,255,.12)"><div style="height:100%;width:${[78, 52, 34, 61, 25][i]}%;border-radius:1em;background:${c}"></div></div></div></div>`).join('')}</div>`;
      if (kind === 'form') return `<div style="font-size:${d.fs || 22}px;height:100%;background:#fff">${head}
        ${rows.slice(0, 4).map((r) => `<div style="margin:3% 7%;font:600 .7em Poppins;color:#666">${esc(r)}<div style="margin-top:.4em;height:2.2em;border-radius:.6em;border:2px solid #e3e3ea"></div></div>`).join('')}
        <div style="margin:8% 7%;height:2.6em;border-radius:1.3em;background:${c};color:#fff;font:700 .85em Poppins;display:flex;align-items:center;justify-content:center">${esc(d.button || 'Continuer')}</div></div>`;
      if (kind === 'success') return `<div style="font-size:${d.fs || 22}px;height:100%;background:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6%">
        <div style="width:38%;aspect-ratio:1;border-radius:50%;background:${c};display:flex;align-items:center;justify-content:center">${LIB.icon('check', '55%', '#fff')}</div><div style="font:800 1.1em Poppins;color:#111;text-align:center;padding:0 8%">${esc(d.text || 'C\'est fait !')}</div></div>`;
      return `<div style="font-size:${d.fs || 22}px;height:100%;background:#f4f5f9">${head}${rows.map((r) => `<div style="margin:3% 6%;padding:5%;border-radius:.8em;background:#fff;box-shadow:0 4px 14px rgba(0,0,0,.06);display:flex;gap:6%;align-items:center;font:600 .78em Poppins;color:#222"><div style="width:16%;aspect-ratio:1;border-radius:30%;background:${c}22"></div>${esc(r)}</div>`).join('')}</div>`;
    },
    icon(name, size = 80, color = '#111') {
      const s = typeof size === 'number' ? size + 'px' : size;
      const P_ = {
        check: '<path d="M14 33l12 12 24-26" fill="none" stroke="{c}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>',
        x: '<path d="M18 18l28 28M46 18L18 46" stroke="{c}" stroke-width="8" stroke-linecap="round"/>',
        shield: '<path d="M32 4l24 9v17c0 15-10 26-24 31C18 56 8 45 8 30V13z" fill="{c}"/><path d="M21 32l8 8 15-16" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>',
        lock: '<rect x="12" y="28" width="40" height="30" rx="6" fill="{c}"/><path d="M20 28v-8a12 12 0 0124 0v8" fill="none" stroke="{c}" stroke-width="6"/>',
        unlock: '<rect x="12" y="28" width="40" height="30" rx="6" fill="{c}"/><path d="M20 28v-8a12 12 0 0123-4" fill="none" stroke="{c}" stroke-width="6"/>',
        gift: '<rect x="8" y="26" width="48" height="32" rx="4" fill="{c}"/><rect x="5" y="18" width="54" height="12" rx="3" fill="{c}"/><rect x="29" y="18" width="6" height="40" fill="#fff" opacity=".8"/><path d="M32 18c-6-12-20-10-14 0M32 18c6-12 20-10 14 0" fill="none" stroke="{c}" stroke-width="4"/>',
        target: '<circle cx="32" cy="32" r="26" fill="none" stroke="{c}" stroke-width="6"/><circle cx="32" cy="32" r="15" fill="none" stroke="{c}" stroke-width="6"/><circle cx="32" cy="32" r="5" fill="{c}"/>',
        trophy: '<path d="M18 8h28v12a14 14 0 01-28 0z" fill="{c}"/><path d="M18 12H8c0 10 6 14 12 14M46 12h10c0 10-6 14-12 14" fill="none" stroke="{c}" stroke-width="4"/><rect x="28" y="34" width="8" height="12" fill="{c}"/><rect x="18" y="46" width="28" height="8" rx="2" fill="{c}"/>',
        phone: '<path d="M18 6l10 2 4 14-7 5c3 7 8 12 15 15l5-7 14 4 2 10c-1 5-6 9-11 8C27 55 9 37 7 14c-1-5 4-9 11-8z" fill="{c}"/>',
        clock: '<circle cx="32" cy="32" r="26" fill="none" stroke="{c}" stroke-width="6"/><path d="M32 16v17l11 7" fill="none" stroke="{c}" stroke-width="6" stroke-linecap="round"/>',
        star: '<path d="M32 4l8 18 20 2-15 13 5 20-18-11-18 11 5-20L4 24l20-2z" fill="{c}"/>',
        bolt: '<path d="M36 4L12 36h16l-4 24 24-34H32z" fill="{c}"/>',
        cart: '<path d="M6 10h8l7 30h28l6-20H18" fill="none" stroke="{c}" stroke-width="5" stroke-linejoin="round"/><circle cx="24" cy="50" r="5" fill="{c}"/><circle cx="46" cy="50" r="5" fill="{c}"/>',
        download: '<path d="M32 8v32M18 28l14 14 14-14" fill="none" stroke="{c}" stroke-width="6" stroke-linecap="round"/><path d="M10 52h44" stroke="{c}" stroke-width="6" stroke-linecap="round"/>',
        mail: '<rect x="6" y="14" width="52" height="36" rx="5" fill="{c}"/><path d="M8 18l24 18 24-18" fill="none" stroke="#fff" stroke-width="4"/>',
        calendar: '<rect x="8" y="12" width="48" height="44" rx="6" fill="{c}"/><rect x="8" y="12" width="48" height="12" fill="#000" opacity=".2"/><path d="M20 6v12M44 6v12" stroke="{c}" stroke-width="5" stroke-linecap="round"/>',
        pin: '<path d="M32 4a18 18 0 0118 18c0 14-18 36-18 36S14 36 14 22A18 18 0 0132 4z" fill="{c}"/><circle cx="32" cy="22" r="7" fill="#fff"/>',
        play: '<circle cx="32" cy="32" r="28" fill="{c}"/><path d="M26 20l18 12-18 12z" fill="#fff"/>',
        chat: '<path d="M8 12h48v30H26l-12 10V42H8z" fill="{c}"/>',
      };
      return `<svg viewBox="0 0 64 64" width="${s}" height="${s}">${(P_[name] || P_.star).replace(/\{c\}/g, color)}</svg>`;
    },
    // silhouettes plates (aucune photo nécessaire)
    crowd(w, color = '#0d0d10') {
      let heads = ''; for (let i = 0; i < 14; i++) { const x = 20 + i * 70 + (i % 2) * 18, y = 70 + (i % 3) * 14; heads += `<circle cx="${x}" cy="${y}" r="26"/><path d="M${x - 44} 200 Q${x - 40} ${y + 26} ${x} ${y + 30} Q${x + 40} ${y + 26} ${x + 44} 200z"/>`; }
      return `<svg width="${w}" height="${w * .2}" viewBox="0 0 1000 200" preserveAspectRatio="xMidYMax slice"><g fill="${color}">${heads}</g></svg>`;
    },
    presenter(h, color = '#0d0d10') {
      return `<svg height="${h}" viewBox="0 0 200 400"><g fill="${color}"><circle cx="90" cy="46" r="30"/><path d="M50 90h80l20 140h-30l-6 160H86l-6-160H58L40 160 20 230 6 224 30 120z"/><path d="M128 100l60-40 6 8-58 46z"/></g></svg>`;
    },
    figure(h, pose = 'shrug', color = '#0d0d10') {
      const arms = pose === 'shrug' ? '<path d="M60 110 L10 140 L16 150 L64 130z M140 110 L190 140 L184 150 L136 130z"/>' : pose === 'win' ? '<path d="M62 104 L30 30 L42 24 L76 98z M138 104 L170 30 L158 24 L124 98z"/>' : '<path d="M60 110 L48 220 L62 222 L72 120z M140 110 L152 220 L138 222 L128 120z"/>';
      return `<svg height="${h}" viewBox="0 0 200 420"><g fill="${color}"><circle cx="100" cy="52" r="34"/><path d="M58 96h84l10 150h-22l-8 170H110l-10-150-10 150H78l-8-170H48z"/>${arms}</g></svg>`;
    },
    chess(h, color = '#111') {
      return `<svg height="${h}" viewBox="0 0 200 420"><g fill="${color}"><rect x="92" y="6" width="16" height="44"/><rect x="78" y="20" width="44" height="14"/><path d="M60 70h80l-14 40H74z"/><path d="M74 110h52l18 190H56z"/><path d="M40 300h120l10 40H30z"/><rect x="20" y="340" width="160" height="40" rx="8"/></g></svg>`;
    },
    envelope(w, stamp = '', stampColor = '#E11D2E', paper = '') {
      return `<div style="position:relative;width:${w}px;height:${w * .75}px">
        <div class="paper" style="position:absolute;left:12%;right:12%;top:-30%;height:80%;background:#fff;border-radius:6px;box-shadow:0 6px 20px rgba(0,0,0,.15);padding:6%;font:700 ${w * .05}px Poppins;color:#333">${esc(paper)}</div>
        <div style="position:absolute;inset:0;background:linear-gradient(#d9b47a,#c49a5c);border-radius:10px;box-shadow:0 20px 40px rgba(0,0,0,.25)"></div>
        <div style="position:absolute;left:0;right:0;top:0;height:45%;background:linear-gradient(#e2c08a,#cfa766);clip-path:polygon(0 0,100% 0,50% 100%)"></div>
        ${stamp ? `<div class="stamp" style="position:absolute;left:14%;top:38%;padding:2% 6%;border:${w * .012}px solid ${stampColor};color:${stampColor};font:800 ${w * .1}px Poppins;transform:rotate(-12deg);border-radius:8px;background:rgba(255,255,255,.7);opacity:0">${esc(stamp)}</div>` : ''}</div>`;
    },
    book(w, open = false) {
      if (open) return `<div style="width:${w}px;height:${w * .7}px;position:relative;filter:drop-shadow(0 20px 30px rgba(0,0,0,.3))"><div style="position:absolute;left:0;width:50%;height:100%;background:linear-gradient(90deg,#efe3c8,#fbf4e3);border-radius:10px 0 0 10px"></div><div style="position:absolute;right:0;width:50%;height:100%;background:linear-gradient(90deg,#fbf4e3,#efe3c8);border-radius:0 10px 10px 0"></div><div style="position:absolute;left:50%;top:0;bottom:0;width:2px;background:#cdbb95"></div></div>`;
      return LIB.box(w);
    },
    folder(w, color, label) {
      return `<div style="display:flex;align-items:center;gap:${w * .18}px"><svg width="${w}" height="${w * .8}" viewBox="0 0 100 80"><path d="M4 12h34l8 8h50v52H4z" fill="${color}"/><path d="M4 26h92v46H4z" fill="${color}" opacity=".8"/><rect x="38" y="40" width="24" height="18" rx="4" fill="#fff" opacity=".5"/></svg><div style="font:800 ${w * .32}px Poppins;color:#fff;text-transform:uppercase;line-height:1.05">${esc(label)}</div></div>`;
    },
    pill3d(text, bg = ACC, fg = '#fff', fs = 64) {
      return `<div style="display:inline-block;padding:${fs * .28}px ${fs * .55}px;border-radius:${fs * .4}px;background:${bg};color:${fg};font:800 ${fs}px Poppins;white-space:nowrap;box-shadow:0 ${fs * .14}px 0 rgba(0,0,0,.35),0 ${fs * .3}px ${fs * .5}px rgba(0,0,0,.3);text-shadow:0 3px 0 rgba(0,0,0,.2)">${esc(text)}</div>`;
    },
    price3d(text, fs = 220, color = '#fff', depth = '#9aa0ad') {
      let sh = ''; for (let i = 1; i <= 10; i++) sh += `${i * .7}px ${i * 1}px 0 ${depth},`;
      return `<div style="font:900 ${fs}px Poppins;letter-spacing:-.03em;color:${color};white-space:nowrap;text-shadow:${sh}0 ${fs * .12}px ${fs * .25}px rgba(0,0,0,.4)">${esc(text)}</div>`;
    },
    confetti(n = 40, colors = ['#fff', ACC2, ACC]) {
      let s = ''; for (let i = 0; i < n; i++) { const x = (i * 37) % 100, y = (i * 53) % 100, r = (i * 47) % 360; s += `<div class="cf" style="position:absolute;left:${x}%;top:${y}%;width:${10 + (i % 3) * 6}px;height:${6 + (i % 2) * 8}px;background:${colors[i % colors.length]};transform:rotate(${r}deg);border-radius:${i % 4 ? 2 : 50}%"></div>`; }
      return `<div style="position:absolute;inset:0;pointer-events:none">${s}</div>`;
    },
  };

  // ---------------------------------------------------------------- moteur générique
  let MONTAGE = null;
  function register(m) { MONTAGE = m; if (window.KIT) window.KIT.M = m; }

  function start() {
    const stage = $('stage');
    stage.style.width = W + 'px'; stage.style.height = H + 'px';
    document.documentElement.style.setProperty('--acc', ACC); document.documentElement.style.setProperty('--acc2', ACC2);
    const SC = $('scenes');
    const shots = S.shots || [];
    const built = shots.map((sh, i) => {
      const type = MONTAGE.SCENES[(sh.scene || {}).type] ? sh.scene.type : MONTAGE.fallback || Object.keys(MONTAGE.SCENES)[0];
      const def = MONTAGE.SCENES[type];
      const el = mk(SC, '<div class="sc" style="display:block;visibility:hidden"></div>');
      const T = timer(sh);
      let ctx;
      try { ctx = def.build(el, sh.scene || {}, T, sh, i) || {}; } catch (e) { console.error('scène', type, e); el.innerHTML = ''; const fb = MONTAGE.SCENES[MONTAGE.fallback]; ctx = fb.build(el, { lines: [sh.text] }, T, sh, i) || {}; return { sh, el, def: fb, T, ctx, type: MONTAGE.fallback }; }
      return { sh, el, def, T, ctx, type };
    });
    built.forEach((b) => { b.el.style.visibility = ''; b.el.style.display = 'none'; });
    built.forEach((b, i) => { const nx = built[i + 1]; b.tr = nx ? MONTAGE.transition(i, b, nx) : 'none'; if (nx && b.tr !== 'cut') ev(nx.sh.start - .08, (MONTAGE.trSfx || {})[b.tr] || 'whoosh', .5); });
    const TRD = MONTAGE.trDur || .4;
    // sous-titres
    const CAP = [];
    built.forEach((b) => {
      if (!(b.def.caps || (b.sh.scene || {}).caps)) return;
      const ws = b.sh.words || []; let cur = [];
      ws.forEach((w, i) => { cur.push(w); const nx = ws[i + 1]; if (!nx || cur.length >= (O === 'landscape' ? 6 : 4) || /[.,?!…:]$/.test(w.w) || nx.s - w.e > .3) { CAP.push({ ws: cur, s: cur[0].s, e: cur[cur.length - 1].e }); cur = []; } });
    });
    CAP.forEach((c, i) => { const n = CAP[i + 1]; c.end = n && n.s - c.e < .6 ? n.s : c.e + .35; });
    const cz = Z('caps'); const C = $('caps'); place(C, cz);
    const KEYW = new Set(((S.keywords || []).concat([PRODUCT.name || ''])).map(norm).filter((x) => x.length > 2));
    // grain
    const gr = $('grain'); const g = gr ? gr.getContext('2d') : null; const GR = [];
    if (g && MONTAGE.grain) { let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647; for (let k = 0; k < 4; k++) { const id = g.createImageData(gr.width, gr.height); for (let i = 0; i < id.data.length; i += 4) { const v = rnd() * 255; id.data[i] = id.data[i + 1] = id.data[i + 2] = v; id.data[i + 3] = 255; } GR.push(id); } gr.style.opacity = MONTAGE.grain; } else if (gr) gr.style.display = 'none';

    function trans(type, p, out) {
      const e = eio(p);
      switch (type) {
        case 'slide': return { tf: `translateX(${out ? -e * W : (1 - e) * W}px)` };
        case 'slideUp': return { tf: `translateY(${out ? -e * H : (1 - e) * H}px)` };
        case 'whip': return { tf: `translateX(${out ? -e * W * 1.05 : (1 - e) * W * 1.05}px)`, f: `blur(${Math.sin(p * Math.PI) * 22}px)` };
        case 'zoom': return out ? { tf: `scale(${1 + e * 1.5})`, op: 1 - e } : { tf: `scale(${.75 + .25 * eo(p)})`, op: eo(p) };
        case 'zoomOut': return out ? { tf: `scale(${1 - e * .3})`, op: 1 - e } : { tf: `scale(${1.4 - .4 * eo(p)})`, op: eo(p) };
        case 'fade': return { op: out ? 1 - e : e };
        case 'flip': return out ? { tf: `perspective(1600px) rotateY(${e * 90}deg)`, op: p < .5 ? 1 : 0 } : { tf: `perspective(1600px) rotateY(${(1 - e) * -90}deg)`, op: p < .5 ? 0 : 1 };
        case 'spin': return out ? { tf: `rotate(${e * 25}deg) scale(${1 - e * .5})`, op: 1 - e } : { tf: `rotate(${(1 - e) * -25}deg) scale(${.5 + .5 * eo(p)})`, op: eo(p) };
        case 'wipe': case 'circle': case 'bars': return { op: out ? (p < .5 ? 1 : 0) : (p < .5 ? 0 : 1) };
      }
      return { op: out ? 0 : 1 };
    }

    function seek(t) {
      SHAKE = 0; FLASH = 0;
      let tint = 'none', wipeP = -1, wipeType = '';
      const ctx = { t, W, H, O };
      built.forEach((b, i) => {
        const nx = built[i + 1], pv = built[i - 1];
        const from = i === 0 ? 0 : b.sh.start, to = nx ? nx.sh.start : DUR + 1;
        const on = t >= from - (pv && pv.tr === 'cut' ? 0 : 0) && t < to + (nx && b.tr !== 'cut' ? TRD : 0);
        b.el.style.display = on ? 'block' : 'none'; if (!on) return;
        const tt = (i === 0 && t < 0.034) ? Math.max(t, Math.min(b.sh.speechEnd || to, to - .3)) : t;  // image 0 = vignette composée
        try { b.def.update(tt, b.ctx, b.sh.scene || {}, b.T, b.sh); } catch (e) { /* jamais bloquant */ }
        let st = {};
        if (nx && t >= to) { st = trans(b.tr, P(t, to, to + TRD), true); wipeP = P(t, to, to + TRD); wipeType = b.tr; }
        else if (pv && t < from + TRD && pv.tr !== 'cut') st = trans(pv.tr, P(t, from, from + TRD), false);
        b.el.style.transform = st.tf || 'none'; b.el.style.opacity = st.op == null ? 1 : st.op; b.el.style.filter = st.f || 'none';
        if (t >= from && t < to) { tint = b.def.tint || 'none'; ctx.scene = b.type; ctx.local = t - from; ctx.index = i; }
      });
      const Wp = $('wipe');
      if (Wp) {
        if (wipeP >= 0 && (wipeType === 'wipe' || wipeType === 'circle' || wipeType === 'bars')) {
          Wp.style.display = 'block'; const e = Math.sin(wipeP * Math.PI);
          if (wipeType === 'circle') Wp.style.clipPath = `circle(${e * Math.hypot(W, H) * .6}px at 50% 50%)`;
          else if (wipeType === 'bars') Wp.style.clipPath = `polygon(${[0, 1, 2, 3, 4].map((k) => { const x0 = k * W / 5, h = cl(e * 1.3 - (k % 2) * .15) * H; return `${x0}px 0,${x0 + W / 5}px 0,${x0 + W / 5}px ${h}px,${x0}px ${h}px,${x0}px 0`; }).join(',')})`;
          else Wp.style.clipPath = `polygon(0 0,${e * 140}% 0,${e * 140 - 40}% 100%,0 100%)`;
        } else Wp.style.display = 'none';
      }
      if (MONTAGE.background) MONTAGE.background(t, tint, ctx);
      const sx = SHAKE ? Math.sin(t * 97) * SHAKE : 0, sy = SHAKE ? Math.cos(t * 83) * SHAKE : 0;
      $('cam').style.transform = `translate(${sx}px,${sy}px)`;
      $('flash').style.opacity = FLASH;
      const cur = CAP.find((c) => t >= c.s - .05 && t < c.end);
      if (!cur) { if (C.dataset.k) { C.innerHTML = ''; C.dataset.k = ''; } } else {
        if (C.dataset.k !== String(cur.s)) { C.dataset.k = String(cur.s); C.innerHTML = cur.ws.map((w) => `<span>${esc(w.w)} </span>`).join(''); }
        [...C.children].forEach((sp, j) => { const w = cur.ws[j]; const q = P(t, w.s - .06, w.s + .12); sp.style.opacity = q; sp.style.transform = `translateY(${(1 - eo(q)) * 14}px)`; sp.classList.toggle('kw', KEYW.has(norm(w.w))); });
      }
      if (g && GR.length) g.putImageData(GR[Math.floor(t * 24) % GR.length], 0, 0);
    }
    EVENTS.sort((a, b) => a.t - b.t);
    window.seek = seek; window.EVENTS = EVENTS;
    window.seekAsync = (t) => { seek(t); return new Promise((r) => requestAnimationFrame(() => r())); };
    const first = built.find((b) => ['hook', 'reveal', 'title'].some((k) => b.type.includes(k)));
    window.TURN = (built.find((b) => /reveal|pivot|product/.test(b.type)) || {}).sh?.start ?? DUR * .35;
    seek(0);
    return first;
  }

  window.KIT = { S, W, H, O, DUR, Z, place, $, cl, P, eo, ei, eio, back, elastic, lerp, esc, norm, mk, pop, slam, slide, fade, fit, fitBox, words, letters, typeIn, wordsIn, ev, kick, flash, LIB, ACC, ACC2, PRODUCT, register, start, timer };
  window.DURATION = DUR;
  const fontLoads = ['400 100px Anton', '500 40px Poppins', '700 40px Poppins', '800 40px Poppins', 'italic 400 40px DMSerif', '40px "Noto Color Emoji"'].map((f) => document.fonts.load(f, 'Aé😀').catch(() => null));
  window.KIT_READY = Promise.all(fontLoads).then(() => document.fonts.ready);
})();
