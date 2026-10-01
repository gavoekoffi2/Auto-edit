/*
 * Montage « Impact » — pub produit rythmée (problème → agitation → solution → appel à l'action).
 *
 * Entrée : window.STORY = { duration, shots:[{start,end,speechEnd,words,text,scene}], product:{img,cut,name}, logo, brand }
 * Sortie : window.seek(t), window.seekAsync(t), window.DURATION, window.EVENTS (repères SFX), window.READY
 *
 * Chaque plan porte une scène (scene.type) construite une fois puis animée de façon
 * déterministe par seek(t). Les déclencheurs « at » sont des mots prononcés dans
 * la phrase du plan : l'animation tombe exactement sur la voix.
 */
(function () {
  const STORY = window.STORY;
  const $ = (s) => document.getElementById(s);
  const cl = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  const P = (t, a, b) => cl((t - a) / Math.max(1e-6, b - a));
  const eo = (x) => 1 - Math.pow(1 - x, 3), eio = (x) => (x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
  const back = (x) => { const c1 = 1.9, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
  const lerp = (a, b, x) => a + (b - a) * x;
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const norm = (s) => String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]/g, '');
  const DUR = STORY.duration;
  const EVENTS = [];
  const ev = (t, sfx, gain = 1) => { if (isFinite(t) && t >= 0 && t < DUR) EVENTS.push({ t: +t.toFixed(3), sfx, gain }); };
  let SHAKE = 0, FLASH = 0;
  const kick = (t, t0, amp = 22, dur = .35) => { if (t >= t0 && t < t0 + dur) SHAKE = Math.max(SHAKE, amp * (1 - (t - t0) / dur)); };
  const flash = (t, t0, a = .6, dur = .22) => { if (t >= t0 && t < t0 + dur) FLASH = Math.max(FLASH, a * (1 - (t - t0) / dur)); };
  const mk = (parent, html) => { const d = document.createElement('div'); d.innerHTML = html.trim(); const e = d.firstElementChild; parent.appendChild(e); return e; };
  const pop = (el, t, t0, dur = .45, dy = 60, sc = .6) => { const q = P(t, t0, t0 + dur), b = back(q); el.style.opacity = cl(q * 3); el.style.transform = `translateY(${(1 - b) * dy}px) scale(${lerp(sc, 1, b)})`; return q; };
  const slam = (el, t, t0, from = 2.2, dur = .28, extra = '') => { const q = P(t, t0, t0 + dur); el.style.opacity = t >= t0 ? 1 : 0; el.style.transform = `scale(${lerp(from, 1, eo(q))}) ${extra}`; return q; };
  const slide = (el, t, t0, dx, dur = .45) => { const q = P(t, t0, t0 + dur); el.style.opacity = cl(q * 3); el.style.transform = `translateX(${(1 - back(q)) * dx}px)`; return q; };

  // texte qui tient sur la largeur disponible (réduit la taille, jamais coupé)
  function textW(el) { const r = document.createRange(); r.selectNodeContents(el); return r.getBoundingClientRect().width; }
  function fit(el, maxW, minPx = 30) {
    if (!el.style.whiteSpace) el.style.whiteSpace = 'nowrap';
    let fs = parseFloat(getComputedStyle(el).fontSize), guard = 80;
    while (textW(el) > maxW && fs > minPx && guard--) { fs *= .95; el.style.fontSize = fs + 'px'; }
    return fs;
  }
  // mots-clés surlignés dans une ligne
  function hl(text, words) {
    const keys = (words || []).map(norm).filter(Boolean);
    return String(text).split(/(\s+)/).map((tok) => (keys.length && keys.some((k) => norm(tok) && (norm(tok) === k || (k.length > 3 && norm(tok).includes(k)))) ? `<span class="acc">${esc(tok)}</span>` : esc(tok))).join('');
  }

  // ---------------------------------------------------------------- minutage
  function timer(sh) {
    const ws = sh.words || [];
    const span = [sh.start + .05, Math.max(sh.start + .4, sh.speechEnd || sh.end)];
    return {
      at(q, n = 0, frac = null) {
        if (q != null && q !== '') {
          const k = norm(q); let c = 0;
          for (const w of ws) { const nw = norm(w.w); if (nw && (nw === k || (k.length > 2 && nw.includes(k)) || (nw.length > 3 && k.startsWith(nw)))) { if (c === n) return w.s; c++; } }
        }
        return lerp(span[0], span[1], frac == null ? 0 : frac);
      },
      frac: (f) => lerp(span[0], span[1], f),
      lineStarts(lines) { // instant du premier mot de chaque ligne, dans l'ordre
        const out = []; let from = 0;
        lines.forEach((ln, i) => {
          const first = norm(String(ln).split(/\s+/)[0]);
          let tt = null;
          for (let j = from; j < ws.length; j++) if (norm(ws[j].w) === first || (first.length > 3 && norm(ws[j].w).startsWith(first))) { tt = ws[j].s; from = j + 1; break; }
          out.push(tt == null ? lerp(span[0], span[1], i / Math.max(1, lines.length)) : tt);
        });
        for (let i = 1; i < out.length; i++) if (out[i] < out[i - 1]) out[i] = out[i - 1] + .25;
        return out;
      },
      spread(n, a = 0, b = .85) { return [...Array(n)].map((_, i) => lerp(span[0], span[1], lerp(a, b, n > 1 ? i / (n - 1) : 0))); },
      span,
    };
  }

  // ---------------------------------------------------------------- produit
  const PRODUCT = STORY.product || {};
  function boxSVG(w, label) {
    const words = String(label || 'VOTRE PRODUIT').toUpperCase().split(/\s+/).slice(0, 3);
    const l1 = words.slice(0, Math.ceil(words.length / 2)).join(' '), l2 = words.slice(Math.ceil(words.length / 2)).join(' ');
    return `<svg width="${w}" height="${w * 1.05}" viewBox="0 0 400 420">
      <polygon points="200,20 370,95 200,170 30,95" fill="rgba(255,255,255,.55)"/><polygon points="200,20 370,95 200,170 30,95" fill="var(--acc)" opacity=".75"/>
      <polygon points="30,95 200,170 200,400 30,325" fill="var(--acc)"/>
      <polygon points="370,95 200,170 200,400 370,325" fill="var(--acc)"/><polygon points="370,95 200,170 200,400 370,325" fill="rgba(0,0,0,.22)"/>
      <polygon points="115,57 285,132 285,170 115,95" fill="rgba(0,0,0,.12)"/>
      <g transform="translate(115,230) skewY(24)"><text x="0" y="0" font-family="Anton" font-size="${l1.length > 9 ? 26 : 34}" fill="#09090D" text-anchor="middle">${esc(l1)}</text>
      <text x="0" y="42" font-family="Anton" font-size="${l2.length > 9 ? 26 : 34}" fill="#09090D" text-anchor="middle">${esc(l2)}</text></g></svg>`;
  }
  function productHTML(w) {
    if (PRODUCT.img) {
      if (PRODUCT.cut) return `<img src="${PRODUCT.img}" style="width:${w}px;height:${w}px;object-fit:contain;filter:drop-shadow(0 30px 40px rgba(0,0,0,.6))">`;
      return `<div style="width:${w}px;height:${w}px;border-radius:40px;overflow:hidden;border:6px solid var(--acc);box-shadow:0 30px 80px rgba(0,0,0,.6)"><img src="${PRODUCT.img}" style="width:100%;height:100%;object-fit:cover"></div>`;
    }
    return boxSVG(w, PRODUCT.name);
  }
  const pedestal = '<svg width="620" height="260" viewBox="0 0 620 260"><ellipse cx="310" cy="60" rx="300" ry="56" fill="#2a2a34"/><rect x="10" y="60" width="600" height="150" fill="#1a1a21"/><ellipse cx="310" cy="210" rx="300" ry="50" fill="#121218"/><ellipse cx="310" cy="60" rx="300" ry="56" fill="none" stroke="var(--acc)" stroke-opacity=".5" stroke-width="3"/></svg>';
  const IC = {
    x: '<svg viewBox="0 0 64 64" width="64" height="64"><path d="M18 18l28 28M46 18L18 46" stroke="#fff" stroke-width="9" stroke-linecap="round"/></svg>',
    check: '<svg viewBox="0 0 64 64" width="56" height="56"><path d="M14 33l12 12 24-26" fill="none" stroke="#fff" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    phone: '<svg viewBox="0 0 64 64" width="110" height="110"><path d="M18 6l10 2 4 14-7 5c3 7 8 12 15 15l5-7 14 4 2 10c-1 5-6 9-11 8C27 55 9 37 7 14c-1-5 4-9 11-8z" fill="#fff"/></svg>',
  };

  // ---------------------------------------------------------------- scènes
  // build(el, p, T, sh) -> ctx ; update(t, c, p, T, sh) ; caps: sous-titres ; tint: lumière d'ambiance
  const SCENES = {};

  // Accroche : lignes qui claquent + produit sur socle ou grand emoji, étiquette qui tombe
  SCENES.hook_question = {
    tint: 'red', build(el, p, T) {
      const lines = (p.lines && p.lines.length ? p.lines : [p.title || '']).slice(0, 4);
      const n = lines.length, fs = n <= 2 ? 150 : n === 3 ? 124 : 108;
      const ls = lines.map((ln, i) => mk(el, `<div class="a c anton" style="top:${120 + i * fs * 1.08}px;font-size:${fs}px">${hl(ln, p.highlight)}</div>`));
      ls.forEach((l) => fit(l, 960));
      const base = 120 + n * fs * 1.08 + 30;
      let hero;
      if (p.product) {
        const top = Math.max(base + 60, 760);
        mk(el, `<div class="a" style="left:-100px;top:${top - 500}px;width:1280px;height:1500px;background:radial-gradient(ellipse 34% 40% at 50% 62%,rgba(var(--accRGB),.28),rgba(0,0,0,0) 70%)"></div>`);
        mk(el, `<div class="a" style="left:230px;top:${top + 380}px">${pedestal}</div>`);
        hero = mk(el, `<div class="a" style="left:340px;top:${top}px">${productHTML(400)}</div>`);
      } else hero = mk(el, `<div class="a c emo" style="top:${Math.max(base + 80, 820)}px;font-size:300px">${esc(p.emoji || '🤔')}</div>`);
      const tag = p.stamp ? mk(el, `<div class="a" style="left:640px;top:${Math.max(base + 120, 880)}px;transform-origin:20px 0"><div style="width:4px;height:90px;background:#888;margin-left:18px"></div><div style="padding:16px 26px;background:#FF3B30;border-radius:16px;font:400 64px Anton;white-space:nowrap">${esc(p.stamp)}</div></div>`) : null;
      const ts = T.lineStarts(lines);
      ts.forEach((tt, i) => ev(tt, i === 0 ? 'impact_big' : 'impact', i === 0 ? 1 : .8));
      const tg = T.at(p.stamp_at, 0, .8); if (tag) { ev(tg, 'whoosh_rev', .6); ev(tg + .3, 'stamp', .9); }
      return { ls, hero, tag, ts, tg };
    },
    update(t, c, p, T, sh) {
      c.ls.forEach((l, i) => {
        if (sh.start === 0) { const q = P(t, c.ts[i] - .05, c.ts[i] + .25); l.style.opacity = 1; l.style.transform = `scale(${1 + .16 * Math.sin(q * Math.PI)})`; }
        else { const t0 = i === 0 ? sh.start + .02 : c.ts[i] - .1; slam(l, t, t0, i === 0 ? 1.6 : 2.0); }
        kick(t, c.ts[i] + .1, i === 0 ? 14 : 22);
      });
      c.hero.style.transform = `translateY(${Math.sin(t * 2.2) * 10}px) scale(${1 + .04 * Math.sin(t * 1.3)})`;
      if (c.tag) { const q = P(t, c.tg, c.tg + .35); c.tag.style.opacity = t > c.tg ? 1 : 0; c.tag.style.transform = `translateY(${(1 - eo(q)) * -500}px) rotate(${Math.sin((t - c.tg) * 6) * 14 * Math.exp(-(t - c.tg) * 1.4)}deg)`; }
    },
  };

  // Liste de douleurs barrées en rouge sur un fil d'actualité flou
  SCENES.pain_stack = {
    tint: 'red', build(el, p, T) {
      const feed = mk(el, '<div class="a" style="left:0;top:0;width:1080px;height:1920px;opacity:.26;filter:blur(10px)"></div>');
      const cols = ['#5b3df5', '#ff7a18', '#12c2e9', '#f64f59', '#11998e', '#8e2de2'];
      for (let i = 0; i < 16; i++) mk(feed, `<div class="a" style="left:${i % 2 ? 560 : 60}px;top:${Math.floor(i / 2) * 520 - 200}px;width:460px;height:480px;border-radius:30px;background:linear-gradient(135deg,${cols[i % 6]},#222)"></div>`);
      const items = (p.items || []).slice(0, 4);
      const h = p.lead ? mk(el, `<div class="a c" style="top:200px;font:800 54px Poppins">${esc(p.lead)}</div>`) : null;
      const top0 = items.length > 3 ? 360 : 420;
      const negs = items.map((it, i) => mk(el, `<div class="neg" style="top:${top0 + i * 230}px"><div class="ic emo">${esc(it.emoji || '✖️')}</div><div class="t">${esc(it.text)}</div><div class="bar"></div></div>`));
      negs.forEach((n) => fit(n.querySelector('.t'), 760, 34));
      const tin = items.map((it, i) => T.at(it.at, 0, .1 + .8 * i / Math.max(1, items.length)));
      for (let i = 1; i < tin.length; i++) if (tin[i] <= tin[i - 1]) tin[i] = tin[i - 1] + .35;
      tin.forEach((tt) => { ev(tt - .3, 'whoosh', .4); ev(tt + .45, 'buzz', .8); });
      return { feed, h, negs, tin };
    },
    update(t, c, p, T, sh) {
      c.feed.style.transform = `translateY(${-((t - sh.start) * 1500) % 1040}px)`;
      if (c.h) pop(c.h, t, sh.start - .05, .35, 20, .9);
      c.negs.forEach((n, i) => {
        const t0 = c.tin[i] - .3; slide(n, t, t0, i % 2 ? 900 : -900, .4);
        const tb = c.tin[i] + .45; n.querySelector('.bar').style.transform = `scaleX(${eo(P(t, tb, tb + .3))})`;
        n.style.background = t > tb && t < tb + .2 ? '#3a1210' : '#16161d'; kick(t, tb + .1, i === c.negs.length - 1 ? 28 : 12);
      });
    },
  };

  // Compteurs : ce qui monte… et ce qui reste à zéro
  SCENES.counter_rows = {
    tint: 'red', caps: true, build(el, p, T) {
      const h = mk(el, `<div class="a c anton" style="top:120px;font-size:140px">${esc(p.title || 'Résultat ?')}</div>`); fit(h, 960);
      const rows = (p.rows || []).slice(0, 4);
      const bubs = (p.bubbles || []).slice(0, 3);
      const R = rows.map((r, i) => {
        const bad = r.bad || r.value === 0 || r.value === '0';
        const e = mk(el, `<div class="row" style="top:${330 + i * 175}px;${bad ? 'border:4px solid #FF3B30;background:#200b0a' : ''}"><div class="lab"><span class="emo">${esc(r.emoji || '')}</span> ${esc(r.label)}</div><div class="val ${bad ? 'red' : 'grn'}">0</div></div>`);
        fit(e.querySelector('.lab'), 560, 30);
        return { e, bad, v: typeof r.value === 'number' ? r.value : parseFloat(String(r.value).replace(/\s/g, '').replace(',', '.')) || 0, raw: r.value };
      });
      const top = 330 + rows.length * 175 + 10;
      const B = bubs.map((b, i) => mk(el, `<div class="bub" style="left:${[90, 380, 170][i]}px;top:${top + i * 118}px">${esc(b)}</div>`));
      const tr = rows.map((r, i) => T.at(r.at, 0, .08 + .75 * i / Math.max(1, rows.length)));
      for (let i = 1; i < tr.length; i++) if (tr[i] <= tr[i - 1]) tr[i] = tr[i - 1] + .4;
      const tb = T.at(p.bubbles_at, 0, .55);
      R.forEach((r, i) => { if (r.bad) { ev(tr[i], 'impact_big', 1); ev(tr[i] + .05, 'buzz', .7); } else { for (let k = 0; k < 18; k++) ev(tr[i] + k * .06, 'tick', .5); } });
      B.forEach((b, i) => ev(tb + i * .32, 'ding', .7));
      return { h, R, B, tr, tb };
    },
    update(t, c, p, T, sh) {
      slam(c.h, t, sh.start - .05, 1.7);
      c.R.forEach((r, i) => {
        const t0 = c.tr[i] - .3;
        if (r.bad) { slam(r.e, t, t0 + .2, 1.5); kick(t, t0 + .35, 34); flash(t, t0 + .32, .22); r.e.querySelector('.val').textContent = r.raw; }
        else { pop(r.e, t, t0, .4, 60, .9); const v = Math.round(eo(P(t, t0, t0 + 1.3)) * r.v); r.e.querySelector('.val').textContent = isFinite(r.v) && r.v ? v.toLocaleString('fr-FR').replace(/ /g, ' ') : r.raw; }
      });
      c.B.forEach((b, i) => pop(b, t, c.tb + i * .32, .35, 30, .5));
    },
  };

  // Deux panneaux : ce qui va bien (vert) / ce qui ne va pas (rouge)
  SCENES.versus = {
    tint: 'none', caps: true, build(el, p, T) {
      const h = p.title ? mk(el, `<div class="a c anton" style="top:120px;font-size:96px">${esc(p.title)}</div>`) : null; if (h) fit(h, 960);
      const panel = (x, side, ok) => mk(el, `<div class="a" style="left:${x}px;top:300px;width:450px;height:900px;border-radius:40px;background:#13131a;border:3px solid ${ok ? '#25D366' : '#FF3B30'}">
          <div class="a" style="left:0;right:0;top:40px;text-align:center;font:800 38px Poppins;color:${ok ? '#25D366' : '#FF3B30'};letter-spacing:.12em;padding:0 20px">${esc((side.label || '').toUpperCase())}</div>
          <div class="a" style="left:0;right:0;top:${side.product ? 150 : 200}px;text-align:center;${side.product ? '' : 'font-size:200px'}" class="emo">${side.product ? `<div style="display:inline-block;${ok ? '' : 'filter:blur(8px) grayscale(.8) brightness(.6)'}">${productHTML(300)}</div>` : `<span class="emo">${esc(side.emoji || (ok ? '✅' : '❌'))}</span>`}</div>
          <div class="a" style="left:30px;right:30px;top:560px;text-align:center;font:700 40px Poppins;line-height:1.2">${esc(side.text || '')}</div>
          <div class="a" style="left:165px;top:720px;width:120px;height:120px;border-radius:50%;background:${ok ? '#25D366' : '#FF3B30'};display:flex;align-items:center;justify-content:center">${ok ? IC.check : IC.x}</div></div>`);
      const A = panel(60, p.a || {}, true), B = panel(570, p.b || {}, false);
      const ta = T.at(p.a && p.a.at, 0, 0), tb = T.at(p.b && p.b.at, 0, .5);
      ev(ta, 'whoosh', .6); ev(ta + .4, 'ding', .7); ev(tb - .3, 'whoosh', .6); ev(tb + .2, 'buzz', .8);
      return { h, A, B, ta, tb };
    },
    update(t, c, p, T, sh) {
      if (c.h) pop(c.h, t, sh.start - .05, .4, 30, .8);
      slide(c.A, t, Math.min(c.ta, sh.start + .1), -700); slide(c.B, t, c.tb - .35, 700); kick(t, c.tb + .1, 18);
      c.B.style.boxShadow = t > c.tb ? `0 0 ${50 + 20 * Math.sin(t * 10)}px rgba(255,59,48,.45)` : 'none';
    },
  };

  // Vous (silence) / eux (les messages pleuvent)
  SCENES.rival_split = {
    tint: 'green', caps: true, build(el, p, T) {
      const tp = p.top || {}, bt = p.bottom || {};
      const top = mk(el, `<div class="a" style="left:0;right:0;top:0;height:900px;background:#0c0c10">
          <div class="a" style="left:70px;top:150px;font:800 42px Poppins;color:#8a8a96;letter-spacing:.2em">${esc((tp.label || 'VOUS').toUpperCase())}</div>
          <div class="a anton" style="left:70px;top:230px;font-size:120px;color:#4a4a55;white-space:nowrap">${esc(tp.value || '0 client')}</div>
          <div class="a" style="left:70px;top:390px;font:600 40px Poppins;color:#5d5d68">${esc(tp.sub || 'silence…')}</div>
          <div class="a" style="left:660px;top:170px;filter:grayscale(.5) brightness(.8)">${productHTML(280)}</div></div>`);
      fit(top.querySelector('.anton'), 560);
      const line = mk(el, '<div class="a" style="left:0;top:896px;height:8px;width:1080px;background:var(--acc)"></div>');
      const bot = mk(el, `<div class="a" style="left:0;right:0;top:904px;bottom:0;background:linear-gradient(180deg,#0f2418,#09090D)">
          <div class="a" style="left:70px;top:60px;font:800 42px Poppins;color:#25D366;letter-spacing:.2em">${esc((bt.label || 'VOTRE CONCURRENT').toUpperCase())}</div></div>`);
      const msgs = (bt.bubbles || ['Je commande ! 🛍️', 'Vous livrez aujourd\'hui ?', 'J\'en veux 2 🔥']).slice(0, 4);
      const bubs = msgs.map((m, i) => mk(bot, `<div class="bub me" style="left:${70 + (i % 2) * 200}px;top:${170 + i * 135}px">${esc(m)}</div>`));
      bubs.forEach((b) => fit(b, 900, 26));
      const tb = T.at(bt.at, 0, .35), tm = T.at(p.bubbles_at, 0, .6);
      ev(tb - .2, 'whoosh', .6); bubs.forEach((_, i) => ev(tm + i * .26, 'ding', .9));
      return { top, line, bot, bubs, tb, tm };
    },
    update(t, c, p, T, sh) {
      c.line.style.transform = `scaleX(${eo(P(t, sh.start, sh.start + .5))})`; c.top.style.opacity = P(t, sh.start, sh.start + .3);
      c.bot.style.opacity = P(t, c.tb - .25, c.tb + .05); c.bot.style.transform = `translateY(${(1 - eo(P(t, c.tb - .25, c.tb + .15))) * 200}px)`;
      c.bubs.forEach((b, i) => pop(b, t, c.tm - .1 + i * .26, .35, 40, .6));
    },
  };

  // Coup de poing : « et ça, ça fait mal »
  SCENES.punch = {
    tint: 'none', build(el, p, T) {
      el.style.background = 'radial-gradient(ellipse at 50% 45%,#4a0b08,#120303 70%)';
      const crack = mk(el, '<svg class="a" style="left:0;top:0" width="1080" height="1920" viewBox="0 0 1080 1920"><g fill="none" stroke="rgba(255,255,255,.85)" stroke-width="5" stroke-linecap="round">' +
        ['M540 900 L470 780 L500 640 L420 480', 'M540 900 L660 820 L720 700 L860 640', 'M540 900 L610 1030 L580 1180 L650 1360', 'M540 900 L400 980 L300 960 L180 1080', 'M540 900 L560 760 L640 600', 'M540 900 L470 1060 L380 1150']
          .map((d) => `<path d="${d}" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/>`).join('') + '</g></svg>');
      const a = p.pre ? mk(el, `<div class="a c anton" style="top:590px;font-size:150px">${esc(p.pre)}</div>`) : null; if (a) fit(a, 960);
      const b = mk(el, `<div class="a c anton red" style="top:${p.pre ? 790 : 700}px;font-size:250px;white-space:normal;text-shadow:0 0 60px rgba(255,59,48,.6)">${esc(p.punch || '')}</div>`);
      const tb = T.at(p.at, 0, .45);
      ev(sh0(T), 'heartbeat', .8); ev(tb, 'impact_big', 1.2); ev(tb + .02, 'glitch', .7);
      return { crack, a, b, tb };
    },
    update(t, c, p, T, sh) {
      if (c.a) pop(c.a, t, sh.start - .05, .3, 20, .8);
      slam(c.b, t, c.tb - .2, 2.6); kick(t, c.tb + .05, 46, .5); flash(t, c.tb + .02, .35);
      c.crack.querySelectorAll('path').forEach((pp, i) => pp.setAttribute('stroke-dashoffset', String(1 - eo(P(t, c.tb + i * .03, c.tb + .3 + i * .03)))));
    },
  };
  const sh0 = (T) => T.span[0];

  // Bascule : fond plein accent, « c'est pour ça qu'on est là »
  SCENES.pivot = {
    tint: 'none', build(el, p, T) {
      el.style.background = 'var(--acc)';
      const shapes = [];
      for (let i = 0; i < 8; i++) shapes.push(mk(el, `<div class="a" style="left:${[80, 860, 140, 900, 470, 60, 820, 300][i]}px;top:${[220, 300, 1330, 1250, 140, 860, 820, 1520][i]}px;width:${[90, 70, 120, 60, 50, 70, 100, 60][i]}px;height:${[90, 70, 120, 60, 50, 70, 100, 60][i]}px;border-radius:${i % 3 ? '50%' : '14px'};border:12px solid #09090D;${i % 2 ? 'background:#09090D' : ''}"></div>`));
      const lines = (p.lines || []).slice(0, 3);
      const ls = lines.map((ln, i) => mk(el, `<div class="a c anton" style="top:${560 + i * 140}px;font-size:130px;color:#09090D">${esc(ln)}</div>`));
      ls.forEach((l) => fit(l, 960));
      const pill = p.pill ? mk(el, `<div class="a" style="left:110px;right:110px;top:${560 + lines.length * 140 + 40}px;height:220px;border-radius:120px;background:#09090D;color:var(--acc);font:400 116px Anton;text-transform:uppercase;display:flex;align-items:center;justify-content:center;white-space:nowrap;padding:0 40px">${esc(p.pill)}</div>`) : null;
      if (pill) fit(pill, 860);
      const ts = T.lineStarts(lines); const tp = T.at(p.pill_at, 0, .75);
      ts.forEach((x) => ev(x, 'impact', .7)); if (pill) ev(tp, 'impact_big', 1);
      return { shapes, ls, pill, ts, tp };
    },
    update(t, c, p, T, sh) {
      c.ls.forEach((l, i) => { const t0 = i === 0 ? Math.min(c.ts[0], sh.start + .02) : c.ts[i] - .1; slam(l, t, t0, 2.2); kick(t, t0 + .2, 10); });
      if (c.pill) { slam(c.pill, t, c.tp - .15, 1.8); kick(t, c.tp + .05, 26); }
      c.shapes.forEach((s, i) => { const q = P(t, sh.start + i * .06, sh.start + i * .06 + .5); s.style.transform = `scale(${back(q)}) rotate(${t * (i % 2 ? 60 : -45)}deg)`; s.style.opacity = q > 0 ? 1 : 0; });
    },
  };

  // Révélation du produit : socle, rayons, nom, accroche
  SCENES.product_reveal = {
    tint: 'gold', caps: true, build(el, p, T) {
      const rays = mk(el, '<div class="a" style="left:-460px;top:-160px;width:2000px;height:2000px;background:repeating-conic-gradient(from 0deg,rgba(var(--accRGB),.17) 0 6deg,transparent 6deg 18deg);border-radius:50%"></div>');
      const kick_ = p.kicker ? mk(el, `<div class="a c" style="top:150px;font:800 44px Poppins;letter-spacing:.22em;color:var(--acc)">${esc(p.kicker.toUpperCase())}</div>`) : null;
      const name = mk(el, `<div class="a c anton" style="top:220px;font-size:150px">${esc(p.name || PRODUCT.name || '')}</div>`); fit(name, 960);
      const tag = p.tagline ? mk(el, `<div class="a c anton acc" style="top:400px;font-size:84px">${esc(p.tagline)}</div>`) : null; if (tag) fit(tag, 960);
      const ped = mk(el, `<div class="a" style="left:230px;top:1180px">${pedestal}</div>`);
      const box = mk(el, `<div class="a" style="left:330px;top:770px">${productHTML(420)}</div>`);
      const stars = p.stars === false ? null : mk(el, '<div class="a c" style="top:640px;font-size:76px;letter-spacing:8px;color:var(--acc)">★★★★★</div>');
      const badge = p.badge ? mk(el, `<div class="a" style="left:720px;top:760px;padding:14px 26px;border-radius:16px;background:#FF3B30;font:400 58px Anton;transform:rotate(8deg);white-space:nowrap">${esc(p.badge)}</div>`) : null;
      const tr = T.at(p.at, 0, .05);
      ev(tr - .3, 'riser_short', .6); ev(tr, 'impact_big', 1); ev(tr + .1, 'shimmer', .8); if (badge) ev(tr + .8, 'pop', 1);
      return { rays, kick_, name, tag, ped, box, stars, badge, tr };
    },
    update(t, c, p, T, sh) {
      const g = eo(P(t, c.tr - .2, c.tr + .6));
      c.rays.style.opacity = g; c.rays.style.transform = `rotate(${t * 14}deg) scale(${.6 + .5 * g})`;
      if (c.kick_) pop(c.kick_, t, sh.start - .05, .35, 20, .9);
      slam(c.name, t, c.tr - .1, 1.8); kick(t, c.tr + .1, 20);
      if (c.tag) pop(c.tag, t, c.tr + .35, .4, 30, .85);
      const q = P(t, c.tr - .3, c.tr + .3);
      c.box.style.opacity = cl(q * 3); c.box.style.transform = `translateY(${(1 - back(q)) * 300 + Math.sin(t * 2.2) * 10}px) scale(${1 + .06 * g})`;
      c.box.style.filter = `drop-shadow(0 0 ${g * 50}px rgba(var(--accRGB),.7))`;
      c.ped.style.opacity = P(t, sh.start, sh.start + .3);
      if (c.stars) pop(c.stars, t, c.tr + .5, .4, 20, .6);
      if (c.badge) { pop(c.badge, t, c.tr + .8, .35, 0, .3); if (t > c.tr + 1.2) c.badge.style.transform += ` rotate(${8 + Math.sin(t * 6) * 3}deg)`; }
    },
  };

  // Grille de cartes emoji (catalogue de produits, de cibles, de catégories)
  SCENES.tiles = {
    tint: 'gold', build(el, p, T) {
      const items = (p.items || []).slice(0, 8);
      const h = p.kicker ? mk(el, `<div class="a c" style="top:150px;font:800 44px Poppins;letter-spacing:.22em;color:var(--acc)">${esc(p.kicker.toUpperCase())}</div>`) : null;
      const n = p.title ? mk(el, `<div class="a c anton" style="top:215px;font-size:116px;white-space:normal">${hl(p.title, p.highlight)}</div>`) : null;
      const big = items.length <= 4;
      const tiles = items.map((it, i) => {
        const x = big ? 120 : (i % 2 ? 560 : 80), y = (big ? 560 : 520) + (big ? i * 230 : Math.floor(i / 2) * 225);
        const odd = !big && items.length % 2 && i === items.length - 1;
        const e = mk(el, `<div class="tile" style="left:${odd ? 320 : x}px;top:${y}px;${big ? 'width:840px;height:200px' : ''}"><div class="e emo">${esc(it.emoji || '✨')}</div><div class="n" style="${big ? 'font-size:50px' : ''}">${esc(it.label)}</div></div>`);
        fit(e.querySelector('.n'), big ? 640 : 280, 24); return e;
      });
      const ts = items.map((it, i) => T.at(it.at, 0, .05 + .85 * i / Math.max(1, items.length)));
      for (let i = 1; i < ts.length; i++) if (ts[i] <= ts[i - 1]) ts[i] = ts[i - 1] + .25;
      ts.forEach((x) => ev(x - .2, 'pop', .9));
      return { h, n, tiles, ts };
    },
    update(t, c, p, T, sh) {
      if (c.h) pop(c.h, t, sh.start - .1, .35, 20, .9); if (c.n) pop(c.n, t, sh.start - .05, .4, 30, .85);
      c.tiles.forEach((tl, i) => {
        const t0 = c.ts[i] - .22, q = P(t, t0, t0 + .4);
        tl.style.opacity = cl(q * 3); tl.style.transform = `scale(${back(q)}) rotate(${(1 - eo(q)) * (i % 2 ? 12 : -12)}deg)`;
        const act = t >= t0 + .1 && t < t0 + .6; tl.style.borderColor = act ? 'var(--acc)' : '#2b2b35'; tl.style.background = act ? 'rgba(var(--accRGB),.14)' : '#15151c';
      });
    },
  };

  // Téléphone : la pub qui marche + 3 coches vertes
  SCENES.phone_checks = {
    tint: 'gold', build(el, p, T) {
      const lines = (p.title || '').split('\n').slice(0, 2);
      const ls = lines.map((ln, i) => mk(el, `<div class="a c anton ${i ? 'acc' : ''}" style="top:${110 + i * 122}px;font-size:110px">${esc(ln)}</div>`)); ls.forEach((l) => fit(l, 960));
      const ph = mk(el, `<div class="phone" style="left:270px;top:400px;width:540px;height:760px"><div class="notch"></div>
         <div class="a" style="inset:0;background:linear-gradient(160deg,#1d1d27,#0b0b10)">
           <div class="rays a" style="left:-230px;top:-150px;width:1000px;height:1000px;border-radius:50%;background:repeating-conic-gradient(from 0deg,rgba(var(--accRGB),.18) 0 8deg,transparent 8deg 20deg)"></div>
           <div class="pb a" style="left:120px;top:140px">${productHTML(290)}</div>
           ${p.badge ? `<div class="promo a" style="left:30px;top:80px;padding:10px 22px;border-radius:14px;background:#FF3B30;font:400 52px Anton;white-space:nowrap">${esc(p.badge)}</div>` : ''}
           <div class="a" style="left:0;right:0;top:470px;text-align:center;font-size:56px;color:var(--acc)">★★★★★</div>
           <div class="btn a" style="left:50px;right:50px;top:580px;height:100px;border-radius:50px;background:#25D366;font:800 40px Poppins;display:flex;align-items:center;justify-content:center;white-space:nowrap">${esc(p.button || 'COMMANDER')}</div>
         </div></div>`);
      const checks = (p.checks || []).slice(0, 3);
      const oks = checks.map((ck, i) => mk(el, `<div class="a" style="left:100px;right:60px;top:${1215 + i * 108}px;display:flex;align-items:center;gap:26px"><div class="chk">${IC.check}</div><div class="tx" style="font:400 62px Anton;text-transform:uppercase;white-space:nowrap">${esc(ck.text || ck)}</div></div>`));
      oks.forEach((o) => fit(o.querySelector('.tx'), 800, 30));
      const ts = lines.length ? T.lineStarts(lines) : [];
      const tp = T.at(p.at, 0, .2);
      const tc = checks.map((ck, i) => T.at(ck.at, 0, .45 + .45 * i / Math.max(1, checks.length)));
      for (let i = 1; i < tc.length; i++) if (tc[i] <= tc[i - 1]) tc[i] = tc[i - 1] + .35;
      ts.forEach((x) => ev(x, 'impact', .6)); ev(tp - .2, 'whoosh', .7); tc.forEach((x) => ev(x, 'ding', .8));
      return { ls, ts, ph, oks, tp, tc };
    },
    update(t, c, p, T, sh) {
      c.ls.forEach((l, i) => slam(l, t, i ? c.ts[i] - .25 : sh.start - .05, 1.7));
      const q = P(t, c.tp - .3, c.tp + .2);
      c.ph.style.opacity = cl(q * 3); c.ph.style.transform = `translateY(${(1 - back(q)) * 500}px) rotate(${(1 - eo(q)) * -10}deg)`;
      c.ph.querySelector('.rays').style.transform = `rotate(${t * 20}deg)`;
      c.ph.querySelector('.pb').style.transform = `translateY(${Math.abs(Math.sin(t * 4)) * -26}px) rotate(${Math.sin(t * 4) * 3}deg)`;
      const pr = c.ph.querySelector('.promo'); if (pr) pr.style.transform = `scale(${1 + .08 * Math.sin(t * 10)}) rotate(-6deg)`;
      c.ph.querySelector('.btn').style.transform = `scale(${1 + .04 * Math.sin(t * 8)})`;
      c.oks.forEach((o, i) => { slide(o, t, c.tc[i] - .15, -900, .4); kick(t, c.tc[i] + .05, 10); });
    },
  };

  // Trois piliers (accroche / message / offre, ou 3 bénéfices)
  SCENES.pillars = {
    tint: 'gold', build(el, p, T) {
      const h = p.kicker ? mk(el, `<div class="a c" style="top:200px;font:800 46px Poppins;letter-spacing:.22em;color:var(--acc)">${esc(p.kicker.toUpperCase())}</div>`) : null;
      const items = (p.items || []).slice(0, 3);
      const pils = items.map((it, i) => mk(el, `<div class="pil" style="top:${360 + i * 290}px"><div class="e emo">${esc(it.emoji || '✨')}</div><div class="t">${esc(it.text)}</div></div>`));
      pils.forEach((pp) => { const tx = pp.querySelector('.t'); tx.style.whiteSpace = 'normal'; let fs = 72, g = 30; while (tx.scrollHeight > 170 && fs > 36 && g--) { fs *= .93; tx.style.fontSize = fs + 'px'; } });
      const ts = items.map((it, i) => T.at(it.at, 0, .05 + .8 * i / Math.max(1, items.length)));
      for (let i = 1; i < ts.length; i++) if (ts[i] <= ts[i - 1]) ts[i] = ts[i - 1] + .4;
      ts.forEach((x) => { ev(x - .35, 'whoosh', .5); ev(x - .05, 'impact', .5); });
      return { h, pils, ts };
    },
    update(t, c, p, T, sh) {
      if (c.h) pop(c.h, t, sh.start - .1, .35, 20, .9);
      c.pils.forEach((pp, i) => { slide(pp, t, c.ts[i] - .3, i % 2 ? 1000 : -1000, .4); kick(t, c.ts[i], 12); pp.querySelector('.e').style.transform = `scale(${1 + .1 * Math.sin(t * 8 + i)})`; });
    },
  };

  // Le téléphone sonne, les commandes tombent, le compteur grimpe
  SCENES.phone_ring = {
    tint: 'green', caps: true, build(el, p, T) {
      const h = mk(el, `<div class="a c anton" style="top:140px;font-size:110px;white-space:normal">${esc(p.title || '')}</div>`);
      const ph = mk(el, `<div class="a" style="left:440px;top:500px;width:200px;height:200px;border-radius:50%;background:#25D366;display:flex;align-items:center;justify-content:center">${IC.phone}</div>`);
      const waves = [0, 1, 2].map(() => mk(el, '<div class="a" style="left:440px;top:500px;width:200px;height:200px;border-radius:50%;border:6px solid #25D366"></div>'));
      const N = (p.notes && p.notes.length ? p.notes : ['🛍️ Nouvelle commande', '💬 « C\'est disponible ? »', '🛍️ Nouvelle commande', '📞 Appel manqué (2)']).slice(0, 4);
      const notes = N.map((n, i) => mk(el, `<div class="a" style="left:110px;right:110px;top:${790 + i * 118}px;height:100px;border-radius:26px;background:rgba(255,255,255,.08);border:2px solid rgba(255,255,255,.12);font:700 40px Poppins;display:flex;align-items:center;padding:0 30px;white-space:nowrap;overflow:hidden">${esc(n)}</div>`));
      const cnt = p.counter_label ? mk(el, `<div class="a c anton grn" style="top:1290px;font-size:110px"></div>`) : null;
      const tr = T.at(p.at, 0, .45);
      ev(tr - .3, 'ping', .8); for (let k = 0; k < 4; k++) ev(tr + k * .5, 'ping', .45);
      notes.forEach((_, i) => ev(tr + .1 + i * .3, 'ding', .8)); if (cnt) ev(T.span[1] + .2, 'coin', 1);
      return { h, ph, waves, notes, cnt, tr };
    },
    update(t, c, p, T, sh) {
      pop(c.h, t, sh.start - .05, .4, 30, .85);
      pop(c.ph, t, c.tr - .7, .4, 0, .3); if (t > c.tr - .3) c.ph.style.transform = `rotate(${Math.sin(t * 50) * 9 * (Math.sin(t * 4) > 0 ? 1 : .25)}deg)`;
      c.waves.forEach((w, i) => { const u = ((t - c.tr - i * .45) % 1.35 + 1.35) % 1.35 / 1.35; w.style.opacity = t > c.tr - .3 ? (1 - u) * .8 : 0; w.style.transform = `scale(${1 + u * 1.3})`; });
      c.notes.forEach((n, i) => pop(n, t, c.tr + .1 + i * .3, .3, -40, .8));
      if (c.cnt) { const v = Math.round(eo(P(t, c.tr, T.span[1] + .5)) * (p.counter_to || 27)); c.cnt.textContent = `${p.counter_label} : ${v}`; c.cnt.style.opacity = P(t, c.tr, c.tr + .3); }
    },
  };

  // Prix / offre : étiquette qui claque, ancien prix barré
  SCENES.price_offer = {
    tint: 'gold', caps: true, build(el, p, T) {
      const k = p.kicker ? mk(el, `<div class="a c anton" style="top:240px;font-size:110px">${esc(p.kicker)}</div>`) : null; if (k) fit(k, 960);
      const old = p.old_price ? mk(el, `<div class="a c anton" style="top:560px;font-size:110px;color:#8a8a96">${esc(p.old_price)}<div class="st" style="position:absolute;left:30%;right:30%;top:62px;height:12px;background:#FF3B30;transform-origin:left"></div></div>`) : null;
      const pr = mk(el, `<div class="a" style="left:120px;right:120px;top:720px;height:300px;border-radius:50px;background:var(--acc);color:var(--onAcc);font:400 190px Anton;display:flex;align-items:center;justify-content:center;white-space:nowrap;box-shadow:0 20px 80px rgba(var(--accRGB),.4)">${esc(p.price || '')}</div>`); fit(pr, 840);
      const note = p.note ? mk(el, `<div class="a c" style="top:1080px;font:700 50px Poppins">${esc(p.note)}</div>`) : null; if (note) fit(note, 960);
      const tp = T.at(p.at, 0, .3);
      ev(tp, 'impact_big', 1); ev(tp + .05, 'coin', .9); if (old) ev(tp - .6, 'tear', .6);
      return { k, old, pr, note, tp };
    },
    update(t, c, p, T, sh) {
      if (c.k) pop(c.k, t, sh.start - .05, .4, 30, .85);
      if (c.old) { pop(c.old, t, c.tp - 1.0, .35, 20, .9); c.old.querySelector('.st').style.transform = `scaleX(${eo(P(t, c.tp - .6, c.tp - .3))})`; }
      slam(c.pr, t, c.tp - .1, 2.0); kick(t, c.tp + .1, 30); if (t > c.tp + .4) c.pr.style.transform = `scale(${1 + .025 * Math.sin(t * 7)})`;
      if (c.note) pop(c.note, t, c.tp + .5, .4, 20, .9);
    },
  };

  // Appel à l'action : bouton, flèche, téléphone qui sonne, numéro chiffre par chiffre
  SCENES.cta = {
    tint: 'gold', build(el, p, T) {
      const btn = mk(el, `<div class="a" style="left:100px;right:100px;top:200px;height:190px;border-radius:100px;background:var(--acc);color:var(--onAcc);font:400 92px Anton;text-transform:uppercase;display:flex;align-items:center;justify-content:center;white-space:nowrap;padding:0 40px;box-shadow:0 20px 80px rgba(var(--accRGB),.35)">${esc(p.button || 'Cliquez sur le lien')}</div>`); fit(btn, 860);
      const arr = mk(el, `<div class="a c anton acc" style="top:410px;font-size:64px">${esc(p.sub || 'sous cette vidéo')}<br><span style="font-size:120px;display:inline-block">↓</span></div>`);
      const groups = String(p.phone || '').trim() ? String(p.phone).trim().split(/\s+/) : [];
      let or = null, ph = null, waves = [], num = null;
      if (groups.length) {
        or = mk(el, `<div class="a c" style="top:650px;font:700 44px Poppins;color:#8a8a96;letter-spacing:.3em">— ${esc((p.or || 'OU APPELEZ').toUpperCase())} —</div>`);
        ph = mk(el, `<div class="a" style="left:440px;top:790px;width:200px;height:200px;border-radius:50%;background:#25D366;display:flex;align-items:center;justify-content:center">${IC.phone}</div>`);
        waves = [0, 1, 2].map(() => mk(el, '<div class="a" style="left:440px;top:790px;width:200px;height:200px;border-radius:50%;border:6px solid #25D366"></div>'));
        num = mk(el, `<div class="a c anton" style="top:1030px;font-size:140px;white-space:nowrap">${groups.map((g) => `<span style="display:inline-block">${esc(g)}</span>`).join(' ')}</div>`); fit(num, 980);
      }
      const e1 = p.tagline ? mk(el, `<div class="a c anton acc" style="top:${groups.length ? 1230 : 900}px;font-size:96px;white-space:normal">${esc(p.tagline)}</div>`) : null;
      const logo = STORY.logo ? mk(el, `<img class="a" src="${STORY.logo}" style="left:390px;top:${groups.length ? 1400 : 1150}px;width:300px;height:200px;object-fit:contain">`) : null;
      const ta = T.at(p.call_at, 0, .35);
      const span = [ta + .5, T.span[1]];
      const tg = groups.map((g, i) => { const w = T.at(g.replace(/^\+/, ''), 0, null); return w > ta ? w : lerp(span[0], span[1], i / Math.max(1, groups.length)); });
      for (let i = 1; i < tg.length; i++) if (tg[i] <= tg[i - 1]) tg[i] = tg[i - 1] + .5;
      ev(T.span[0], 'impact', .8); if (groups.length) { ev(ta, 'ping', .7); for (let k = 0; k < 3; k++) ev(ta + .5 + k * .55, 'ping', .4); tg.forEach((x) => ev(x - .1, 'pop', 1)); }
      if (e1) ev(T.span[1] + .3, 'shimmer', .8);
      return { btn, arr, or, ph, waves, num, e1, logo, ta, tg };
    },
    update(t, c, p, T, sh) {
      const q = pop(c.btn, t, sh.start - .05, .45, 0, .5); if (q >= 1) c.btn.style.transform = `scale(${1 + .03 * Math.sin(t * 7)})`;
      pop(c.arr, t, sh.start + .4, .35, -20, .9); c.arr.querySelector('span').style.transform = `translateY(${Math.abs(Math.sin(t * 5)) * 26}px)`;
      if (c.ph) {
        pop(c.or, t, c.ta - .3, .3, 10, .9); pop(c.ph, t, c.ta - .2, .4, 0, .3);
        if (t > c.ta + .2) c.ph.style.transform = `rotate(${Math.sin(t * 50) * 8 * (Math.sin(t * 4) > 0 ? 1 : .2)}deg)`;
        c.waves.forEach((w, i) => { const u = ((t - c.ta - i * .45) % 1.35 + 1.35) % 1.35 / 1.35; w.style.opacity = t > c.ta + .1 ? (1 - u) * .8 : 0; w.style.transform = `scale(${1 + u * .55})`; });
        c.num.querySelectorAll('span').forEach((s, i) => { const t0 = c.tg[i] - .12, qq = P(t, t0, t0 + .25); s.style.opacity = qq > 0 ? 1 : 0; s.style.transform = `translateY(${(1 - back(qq)) * 50}px)`; s.style.color = t > t0 && t < t0 + .5 ? 'var(--acc)' : '#fff'; kick(t, t0 + .1, 7); });
      }
      if (c.e1) pop(c.e1, t, T.span[1] + .3, .45, 40, .8);
      if (c.logo) pop(c.logo, t, T.span[1] + .5, .45, 30, .8);
    },
  };

  // Titre générique (repli) : lignes qui claquent
  SCENES.title = {
    tint: 'gold', build(el, p, T, sh) {
      const lines = (p.lines && p.lines.length ? p.lines : [p.title || sh.text]).slice(0, 4);
      const fs = lines.length <= 2 ? 130 : 104;
      const top0 = 960 - lines.length * fs * .6;
      const ls = lines.map((ln, i) => mk(el, `<div class="a c anton" style="top:${top0 + i * fs * 1.1}px;font-size:${fs}px">${hl(ln, p.highlight)}</div>`));
      ls.forEach((l) => fit(l, 960));
      const ts = T.lineStarts(lines); ts.forEach((x, i) => ev(x, i ? 'impact' : 'impact_big', .7));
      return { ls, ts };
    },
    update(t, c, p, T, sh) { c.ls.forEach((l, i) => { slam(l, t, i ? c.ts[i] - .1 : sh.start - .02, 1.8); kick(t, c.ts[i] + .1, 12); }); },
  };

  // ---------------------------------------------------------------- transitions
  const TRD = .4;
  const TR_CYCLE = ['whip', 'zoom', 'glitch', 'split', 'circle', 'whip', 'bars', 'zoom'];
  function trans(type, p, out) {
    const e = eio(p);
    switch (type) {
      case 'whip': return { tf: `translateX(${out ? -e * 1150 : (1 - e) * 1150}px)`, f: `blur(${Math.sin(p * Math.PI) * 24}px)` };
      case 'zoom': return out ? { tf: `scale(${1 + e * 1.6})`, op: 1 - e } : { tf: `scale(${.7 + .3 * eo(p)})`, op: eo(p) };
      case 'glitch': return { tf: `translate(${Math.sin(p * 90) * 40 * (1 - p)}px,0) skewX(${Math.sin(p * 70) * 8 * (1 - p)}deg)`, op: out ? (p < .5 ? 1 : 0) : (p < .5 ? 0 : 1), f: `hue-rotate(${(1 - p) * 90}deg) saturate(${1 + (1 - p) * 2})` };
      case 'split': return { tf: `translateY(${out ? -e * 1920 : (1 - e) * 1920}px)` };
      case 'flash': return { op: out ? 1 - e : e };
      case 'bars': case 'circle': return { op: out ? (p < .5 ? 1 : 0) : (p < .5 ? 0 : 1) };
    }
    return {};
  }
  const TR_SFX = { whip: 'whoosh', zoom: 'whoosh_deep', glitch: 'glitch', split: 'whoosh', circle: 'whoosh', bars: 'whoosh_deep', flash: 'impact_big' };

  // ---------------------------------------------------------------- construction
  function init() {
  const SC = $('scenes');
  const shots = STORY.shots || [];
  const built = shots.map((sh, i) => {
    const type = SCENES[(sh.scene || {}).type] ? sh.scene.type : 'title';
    const def = SCENES[type];
    const el = mk(SC, '<div class="sc" style="display:block;visibility:hidden"></div>');
    const T = timer(sh);
    let ctx;
    try { ctx = def.build(el, sh.scene || {}, T, sh) || {}; } catch (e) { console.error('scène', type, e); el.innerHTML = ''; ctx = SCENES.title.build(el, { title: sh.text }, T, sh); return { sh, el, def: SCENES.title, T, ctx, type: 'title' }; }
    return { sh, el, def, T, ctx, type };
  });
  built.forEach((b) => { b.el.style.visibility = ''; b.el.style.display = 'none'; });
  // transition à la sortie de chaque plan (la bascule sort en flash)
  built.forEach((b, i) => {
    const nx = built[i + 1];
    b.tr = !nx ? 'none' : (b.type === 'punch' || nx.type === 'pivot') ? 'flash' : (nx.type === 'cta' ? 'circle' : TR_CYCLE[i % TR_CYCLE.length]);
    if (nx) ev(nx.sh.start - .1, TR_SFX[b.tr] || 'whoosh', b.tr === 'flash' ? .9 : .55);
  });
  const pivotAt = (built.find((b) => b.type === 'pivot') || built.find((b) => b.type === 'product_reveal') || {}).sh;
  window.TURN = pivotAt ? pivotAt.start : DUR * .4;

  // sous-titres (scènes qui ne montrent pas déjà le texte)
  const CAP = [];
  built.forEach((b) => {
    if (!(b.def.caps || (b.sh.scene || {}).caps)) return;
    const ws = b.sh.words || []; let cur = [];
    ws.forEach((w, i) => { cur.push(w); const nx = ws[i + 1]; if (!nx || cur.length >= 4 || /[.,?!…:]$/.test(w.w) || nx.s - w.e > .3) { CAP.push({ ws: cur, s: cur[0].s, e: cur[cur.length - 1].e }); cur = []; } });
  });
  CAP.forEach((c, i) => { const n = CAP[i + 1]; c.end = n && n.s - c.e < .6 ? n.s : c.e + .35; });
  const KEYW = new Set(((STORY.keywords || []).concat([PRODUCT.name || ''])).map(norm).filter((x) => x.length > 2));

  // grain
  const g = $('grain').getContext('2d'); const GR = [];
  let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  for (let k = 0; k < 6; k++) { const id = g.createImageData(540, 960); for (let i = 0; i < id.data.length; i += 4) { const v = rnd() * 255; id.data[i] = id.data[i + 1] = id.data[i + 2] = v; id.data[i + 3] = 255; } GR.push(id); }
  const TINT = { red: 'rgba(255,40,30,.24)', green: 'rgba(37,211,102,.18)', gold: 'rgba(var(--accRGB),.15)', none: 'rgba(0,0,0,0)' };

  function seek(t) {
    SHAKE = 0; FLASH = 0;
    let tint = 'none', wipeP = -1, wipeType = '';
    built.forEach((b, i) => {
      const nx = built[i + 1], pv = built[i - 1];
      const from = i === 0 ? 0 : b.sh.start, to = nx ? nx.sh.start : DUR + 1;
      const on = t >= from && t < to + (nx ? TRD : 0);
      b.el.style.display = on ? 'block' : 'none'; if (!on) return;
      try { b.def.update(t, b.ctx, b.sh.scene || {}, b.T, b.sh); } catch (e) { /* une scène ne casse jamais le rendu */ }
      let st = {};
      if (nx && t >= to) { st = trans(b.tr, P(t, to, to + TRD), true); wipeP = P(t, to, to + TRD); wipeType = b.tr; }
      else if (pv && t < from + TRD) st = trans(pv.tr, P(t, from, from + TRD), false);
      b.el.style.transform = st.tf || 'none'; b.el.style.opacity = st.op == null ? 1 : st.op; b.el.style.filter = st.f || 'none';
      if (t >= from && t < to) tint = b.def.tint || 'none';
      if (b.tr === 'flash') flash(t, to + TRD * .45, .9, .35);
      if (b.tr === 'glitch') flash(t, to + TRD * .5, .18, .1);
    });
    const Wp = $('wipe');
    if (wipeP >= 0 && (wipeType === 'bars' || wipeType === 'circle')) {
      Wp.style.display = 'block'; const e = Math.sin(wipeP * Math.PI);
      if (wipeType === 'bars') Wp.style.clipPath = `polygon(${[0, 1, 2, 3, 4].map((k) => { const x0 = k * 216, h = cl(e * 1.3 - (k % 2) * .15) * 1920; return `${x0}px 0,${x0 + 216}px 0,${x0 + 216}px ${h}px,${x0}px ${h}px,${x0}px 0`; }).join(',')})`;
      else Wp.style.clipPath = `circle(${e * 1500}px at 540px 960px)`;
    } else Wp.style.display = 'none';
    $('glow').style.background = `radial-gradient(ellipse 60% 45% at 50% 42%, ${TINT[tint]}, rgba(0,0,0,0) 70%)`;
    $('grid').style.transform = `translate(${(t * 18) % 90}px,${(t * 30) % 90}px)`;
    const sx = SHAKE ? Math.sin(t * 97) * SHAKE : 0, sy = SHAKE ? Math.cos(t * 83) * SHAKE : 0;
    $('cam').style.transform = `translate(${sx}px,${sy}px) scale(${1 + .012 * Math.sin(t * .7)})`;
    $('flash').style.opacity = FLASH;
    const C = $('caps'); const cur = CAP.find((c) => t >= c.s - .05 && t < c.end);
    if (!cur) { if (C.dataset.k) { C.innerHTML = ''; C.dataset.k = ''; } } else {
      if (C.dataset.k !== String(cur.s)) { C.dataset.k = String(cur.s); C.innerHTML = cur.ws.map((w) => `<span>${esc(w.w)} </span>`).join(''); }
      [...C.children].forEach((sp, j) => { const w = cur.ws[j]; const q = P(t, w.s - .06, w.s + .12); sp.style.opacity = q; sp.style.transform = `translateY(${(1 - eo(q)) * 16}px) scale(${1 + .12 * (1 - eo(q))})`; sp.style.color = KEYW.has(norm(w.w)) ? 'var(--acc)' : '#fff'; });
    }
    g.putImageData(GR[Math.floor(t * 30) % 6], 0, 0);
  }

  EVENTS.sort((a, b) => a.t - b.t);
  window.seek = seek; window.EVENTS = EVENTS;
  window.seekAsync = (t) => { seek(t); return new Promise((r) => requestAnimationFrame(() => r())); };
  seek(0);
  }
  window.DURATION = DUR;
  const fontLoads = ['400 100px Anton', '500 40px Poppins', '700 40px Poppins', '800 40px Poppins', '40px "Noto Color Emoji"'].map((f) => document.fonts.load(f, 'A😀').catch(() => null));
  window.READY = Promise.all(fontLoads).then(() => document.fonts.ready).then(() => {
    init();
    const imgs = [...document.images];
    return Promise.all(imgs.map((im) => (im.decode ? im.decode().catch(() => null) : null)));
  }).then(() => { window.seek(0); return true; });
  if (!/render/.test(location.search)) window.READY.then(() => { const t0 = performance.now(); (function loop() { window.seek(((performance.now() - t0) / 1000) % DUR); requestAnimationFrame(loop); })(); });
})();
