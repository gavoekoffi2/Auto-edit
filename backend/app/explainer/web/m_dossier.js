/*
 * Mode « Dossier résultat » — inspiré de la pub « Maîtriser le TCF Canada ».
 * Deux mondes : le blanc de la galère (compte à rebours, écrans, documents, enveloppe « REFUSÉ »)
 * puis le rouge de la solution (coffret qui tombe, dossiers colorés, livre ouvert, bonus, « imaginez »),
 * et l'enveloppe finale « ADMIS ». Idéal examens, concours, formations certifiantes, projets à enjeu.
 */
(function () {
  const K = window.KIT;
  const { Z, mk, place, esc, P, eo, back, lerp, cl, pop, slam, slide, fade, fit, fitBox, letters, words, typeIn, wordsIn, ev, kick, flash, LIB, ACC, ACC2, W, H, O } = K;
  const LAND = O === 'landscape';
  const u = Math.min(W, H) / 1080;
  const RED = '#C8102E';
  const ttl = Z('title'), hero = Z('hero'), sub = Z('sub');
  const center = (w, h, z = hero) => ({ x: z.x + (z.w - w) / 2, y: z.y + (z.h - h) / 2 });
  const redBg = (el) => { el.style.background = `radial-gradient(ellipse 80% 70% at 50% 45%,#E2203B 0,${RED} 45%,#7E0A1D 100%)`; };
  const head = (el, text, y, color = '#0b0b0e', fs = 92, x = null, w = null) => { const e = mk(el, `<div class="a" style="left:${x ?? 60 * u}px;top:${y}px;width:${w ?? W - 120 * u}px;text-align:${LAND && x != null ? 'left' : 'center'};font:800 ${fs * u}px Poppins;color:${color};line-height:1.1">${letters(text)}</div>`); fitBox(e, w ?? W - 120 * u, 260 * u, 26); return e; };
  const SC = {};

  // Accroche : « Chaque année… » + foule de pictogrammes qui se multiplie
  SC.ds_count = {
    tint: 'none', build(el, p, T) {
      const ln = head(el, p.line || '', LAND ? 140 : ttl.y + 40 * u, '#0b0b0e', 104, LAND ? 90 : null, LAND ? 860 : null);
      const n = 24, cols = 6, s = (LAND ? 110 : 130) * u;
      const grid = mk(el, `<div class="a" style="left:${LAND ? 1020 : (W - cols * s * 1.25) / 2}px;top:${LAND ? 200 : H * .36}px;display:grid;grid-template-columns:repeat(${cols},${s * 1.25}px);row-gap:${s * .3}px">${[...Array(n)].map(() => `<div class="pp">${LIB.icon('star', 0, '#000').replace(/<svg[^>]*>.*<\/svg>/, '')}<svg width="${s}" height="${s}" viewBox="0 0 64 64"><circle cx="32" cy="18" r="12" fill="#111"/><path d="M10 62c0-14 10-24 22-24s22 10 22 24z" fill="#111"/></svg></div>`).join('')}</div>`);
      const tl = T.at(p.at, 0, .2); ev(sh0(T), 'blip', .6); ev(tl, 'pop', .6);
      return { ln, grid, tl, pp: [...grid.querySelectorAll('.pp')] };
    },
    update(t, c, p, T, sh) {
      typeIn(c.ln, t, sh.start, .6);
      c.pp.forEach((x, i) => { const q = P(t, c.tl + i * .035, c.tl + i * .035 + .3); x.style.opacity = q; x.style.transform = `scale(${back(q)})`; if (p.fail && i % 3 === 0 && t > c.tl + 1.2) x.style.opacity = .2; });
    },
  };

  // Symptômes : compte à rebours + écran/documents qui changent à chaque symptôme
  SC.ds_timer = {
    tint: 'none', build(el, p, T, sh) {
      const items = (p.items && p.items.length ? p.items : [{ text: p.line || sh.text, emoji: p.emoji }]).slice(0, 4);
      const brand = mk(el, `<div class="a" style="left:0;right:0;top:${LAND ? 50 : ttl.y - 40 * u}px;text-align:center;font:900 ${110 * u}px Poppins;font-style:italic;color:#0b0b0e;letter-spacing:-.02em">${esc(p.brand || '')}</div>`); fit(brand, W - 120, 30);
      const dg = mk(el, `<div class="a" style="left:0;right:0;top:${LAND ? 180 : ttl.y + 100 * u}px;text-align:center"><span class="dg" style="display:inline-block;padding:${6 * u}px ${18 * u}px;background:#1c1c22;border-radius:${10 * u}px;color:#fff;font:700 ${92 * u}px Poppins;letter-spacing:.06em">00:09</span></div>`);
      const iw = LAND ? 760 : Math.min(W - 160 * u, 860 * u);
      const pos = center(iw, iw * .75, LAND ? { x: 1000, y: 330, w: 840, h: 700 } : { x: 0, y: H * .3, w: W, h: H * .42 });
      const cards = items.map((it) => mk(el, `<div class="a" style="left:${pos.x}px;top:${pos.y}px;width:${iw}px;height:${iw * .75}px;border-radius:${30 * u}px;background:linear-gradient(135deg,#1d4ed8,#0b1b4a);display:flex;align-items:center;justify-content:center;box-shadow:0 30px 60px rgba(0,0,0,.25)"><span class="emo" style="font-size:${iw * .38}px">${esc(it.emoji || '📄')}</span></div>`));
      const caps = items.map((it) => mk(el, `<div class="a" style="left:${LAND ? 90 : 60 * u}px;top:${LAND ? 420 : pos.y + iw * .75 + 50 * u}px;width:${LAND ? 860 : W - 120 * u}px;text-align:${LAND ? 'left' : 'center'};font:800 ${70 * u}px Poppins;color:#0b0b0e">${letters(it.text || '')}</div>`));
      caps.forEach((c_) => fitBox(c_, LAND ? 860 : W - 120 * u, 240 * u, 26));
      const ts = T.seq(items, 'at', 0, .75); ts[0] = Math.min(ts[0], sh.start + .15);
      ts.forEach((x) => { ev(x, 'whoosh', .4); ev(x + .1, 'tick', .5); });
      return { brand, dg: dg.querySelector('.dg'), cards, caps, ts };
    },
    update(t, c, p, T, sh) {
      fade(c.brand, t, sh.start, .3);
      const left = Math.max(0, 9 - Math.floor((t - sh.start) * 1.6)); c.dg.textContent = `00:${String(left).padStart(2, '0')}`; c.dg.style.color = left <= 3 ? '#ff4d5e' : '#fff';
      c.cards.forEach((cd, i) => { const a = c.ts[i] - .15, b_ = (c.ts[i + 1] ?? 1e9) - .15; const on = t >= a && t < b_ + .2; cd.style.display = on ? '' : 'none'; if (on) { const q = P(t, a, a + .35), o = P(t, b_, b_ + .2); cd.style.transform = `translateX(${(1 - back(q)) * 600 - eo(o) * 600}px) rotate(${(1 - q) * 8}deg)`; cd.style.opacity = 1 - o; } });
      c.caps.forEach((cp, i) => { const a = c.ts[i] - .05, b_ = (c.ts[i + 1] ?? 1e9) - .1; cp.style.display = t >= a && t < b_ ? '' : 'none'; typeIn(cp, t, a, .5); });
    },
  };

  // L'échec : l'enveloppe, le résultat qui sort, le tampon
  SC.ds_envelope = {
    tint: 'none', build(el, p, T) {
      const ew = LAND ? 640 : Math.min(W - 240 * u, 760 * u);
      const pos = center(ew, ew * .75, LAND ? { x: 1000, y: 200, w: 840, h: 760 } : { x: 0, y: H * .38, w: W, h: H * .4 });
      const env = mk(el, `<div class="a" style="left:${pos.x}px;top:${pos.y}px">${LIB.envelope(ew, p.stamp || 'REFUSÉ', p.ok ? '#16a34a' : '#E11D2E', p.paper || 'Résultat')}</div>`);
      const ln = p.line ? head(el, p.line, LAND ? 200 : ttl.y + 30 * u, p.ok ? '#0f7a3a' : '#0b0b0e', 96, LAND ? 90 : null, LAND ? 860 : null) : null;
      if (p.red) redBg(el); if (p.red && ln) ln.style.color = '#fff';
      const ts = T.at(p.at, 0, .55); ev(ts - .5, 'paper', .7); ev(ts, 'stamp', 1);
      return { env, ln, ts, ew };
    },
    update(t, c, p, T, sh) {
      const q = P(t, sh.start, sh.start + .5); c.env.style.transform = `translateY(${(1 - back(q)) * 500}px) rotate(${-6 + (1 - q) * 20}deg)`; c.env.style.opacity = cl(q * 3);
      const pp = c.env.querySelector('.paper'); pp.style.transform = `translateY(${-eo(P(t, c.ts - .6, c.ts - .2)) * c.ew * .25}px)`;
      const st = c.env.querySelector('.stamp'); if (st) { const qs = P(t, c.ts, c.ts + .22); st.style.opacity = qs > 0 ? 1 : 0; st.style.transform = `rotate(-12deg) scale(${lerp(2.4, 1, eo(qs))})`; }
      kick(t, c.ts + .1, 22); if (c.ln) typeIn(c.ln, t, sh.start + .1, .5);
    },
  };

  // Bascule dans le monde rouge : le coffret / livre tombe, trait lumineux
  SC.ds_reveal = {
    tint: 'none', build(el, p, T) {
      redBg(el);
      const bw = LAND ? 560 : Math.min(W * .62, 640 * u);
      const pos = center(bw, bw * 1.1, LAND ? { x: 1000, y: 60, w: 840, h: 960 } : hero);
      const line = mk(el, `<div class="a" style="left:${pos.x + bw / 2}px;top:0;width:${3 * u}px;height:${H}px;background:linear-gradient(transparent,#fff,transparent);transform-origin:50% 0"></div>`);
      const box = mk(el, `<div class="a" style="left:${pos.x}px;top:${pos.y}px;filter:drop-shadow(0 40px 50px rgba(0,0,0,.45))">${LIB.product(bw)}</div>`);
      const pre = p.pre ? mk(el, `<div class="a" style="left:${LAND ? 90 : 60 * u}px;top:${LAND ? 140 : ttl.y - 50 * u}px;width:${LAND ? 860 : W - 120 * u}px;text-align:${LAND ? 'left' : 'center'};font:700 ${60 * u}px Poppins;color:rgba(255,255,255,.85);line-height:1.15">${letters(p.pre)}</div>`) : null; if (pre) fitBox(pre, LAND ? 860 : W - 120 * u, 150 * u, 24);
      const nm = mk(el, `<div class="a" style="left:${LAND ? 90 : 60 * u}px;top:${LAND ? 340 : ttl.y + 120 * u}px;width:${LAND ? 860 : W - 120 * u}px;text-align:${LAND ? 'left' : 'center'};font:900 ${120 * u}px Poppins;color:#fff;text-transform:uppercase;line-height:1">${letters(p.name || '')}</div>`); fitBox(nm, LAND ? 860 : W - 120 * u, 260 * u, 30);
      const tr = T.at(p.at, 0, .1); ev(tr - .2, 'whoosh_deep', .7); ev(tr + .15, 'impact_big', .9); ev(tr + .3, 'shimmer', .7);
      return { line, box, pre, nm, tr };
    },
    update(t, c, p, T, sh) {
      c.line.style.transform = `scaleY(${eo(P(t, sh.start, sh.start + .4))})`; c.line.style.opacity = 1 - P(t, c.tr + .2, c.tr + .6);
      const q = P(t, c.tr - .15, c.tr + .25); c.box.style.opacity = q > 0 ? 1 : 0; c.box.style.transform = `translateY(${(1 - eo(q)) * -900}px) rotate(${(1 - q) * -12 + Math.sin(t * 1.5) * 2}deg)`;
      kick(t, c.tr + .15, 24); if (c.pre) typeIn(c.pre, t, sh.start, .4); typeIn(c.nm, t, c.tr + .2, .5);
    },
  };

  // Dossiers colorés (modules, épreuves, catégories)
  SC.ds_folders = {
    tint: 'none', build(el, p, T) {
      redBg(el);
      const items = (p.items || []).slice(0, 5);
      const cols = ['#ec4899', '#8b5cf6', '#2563eb', '#16a34a', '#f59e0b'];
      const fw = (LAND ? 160 : 210) * u;
      const tt = p.title ? mk(el, `<div class="a" style="left:60px;right:60px;top:${LAND ? 60 : ttl.y}px;text-align:center;font:400 ${110 * u}px Anton;color:#fff;text-transform:uppercase">${letters(p.title)}</div>`) : null; if (tt) fit(tt, W - 120, 24);
      const fs = items.map((it, i) => mk(el, `<div class="a" style="left:${LAND ? 140 + (i % 2) * 860 : 100 * u}px;top:${LAND ? 260 + Math.floor(i / 2) * 260 : H * .27 + i * (fw * .8 + 70 * u)}px;width:${LAND ? 800 : W - 160 * u}px">${LIB.folder(fw, cols[i % cols.length], it.text || it)}</div>`));
      const ts = T.seq(items, 'at', .05, .85); ts.forEach((x) => ev(x, 'pop', .8));
      return { tt, fs, ts };
    },
    update(t, c, p, T, sh) { if (c.tt) typeIn(c.tt, t, sh.start, .5); c.fs.forEach((f, i) => slide(f, t, c.ts[i] - .2, -500, 0, .4)); },
  };

  // Livre ouvert : méthodes / ce qu'on y découvre
  SC.ds_book = {
    tint: 'none', build(el, p, T) {
      redBg(el);
      const bw = LAND ? 1200 : W - 80 * u;
      const pos = center(bw, bw * .7, LAND ? { x: 0, y: 100, w: W, h: 900 } : { x: 0, y: H * .2, w: W, h: H * .6 });
      const bk = mk(el, `<div class="a" style="left:${pos.x}px;top:${pos.y}px">${LIB.book(bw, true)}</div>`);
      const items = (p.items || []).slice(0, 4);
      const txt = mk(el, `<div class="a" style="left:${pos.x + bw * .08}px;top:${pos.y + bw * .08}px;width:${bw * .84}px;height:${bw * .56}px;display:grid;grid-template-columns:1fr 1fr;column-gap:${bw * .1}px;align-content:start">${items.map((it) => `<div class="it" style="margin:${14 * u}px 0;font:800 ${(LAND ? 52 : 54) * u}px Poppins;color:#3b2a14;text-transform:uppercase;line-height:1.12">${letters(it.text || it)}</div>`).join('')}</div>`);
      const its = [...txt.querySelectorAll('.it')]; its.forEach((x) => fitBox(x, bw * .37, bw * .25, 18));
      const ts = T.seq(items, 'at', .1, .85); ts.forEach((x) => ev(x, 'pencil', .6)); ev(sh0(T), 'paper', .7);
      return { bk, its, ts };
    },
    update(t, c, p, T, sh) {
      const q = P(t, sh.start, sh.start + .6); c.bk.style.transform = `perspective(1600px) rotateX(${(1 - eo(q)) * 70}deg) rotate(${Math.sin(t * .8) * 1}deg)`; c.bk.style.opacity = cl(q * 3);
      c.its.forEach((it, i) => typeIn(it, t, c.ts[i], .6));
    },
  };
  const sh0 = (T) => T.span[0];

  // Bonus
  SC.ds_bonus = {
    tint: 'none', build(el, p, T) {
      redBg(el);
      const tt = mk(el, `<div class="a" style="left:0;right:0;top:${LAND ? 70 : ttl.y}px;text-align:center;font:400 ${100 * u}px Anton;color:#fff;text-transform:uppercase">${letters(p.title || 'Recevez en bonus')}</div>`); fit(tt, W - 120, 26);
      const items = (p.items || [{ text: 'Bonus' }]).slice(0, 3);
      const bw = (LAND ? 380 : 440) * u;
      const bx = items.map((it, i) => mk(el, `<div class="a" style="left:${LAND ? 200 + i * 520 : (W - bw) / 2 + (i - (items.length - 1) / 2) * 60 * u}px;top:${LAND ? 260 : H * .3 + i * 60 * u}px;filter:drop-shadow(0 30px 40px rgba(0,0,0,.4))">${LIB.box(bw, it.text || it)}</div>`));
      const ts = T.seq(items, 'at', .15, .8); ts.forEach((x) => { ev(x, 'whoosh', .5); ev(x + .2, 'shimmer', .5); });
      return { tt, bx, ts };
    },
    update(t, c, p, T, sh) { typeIn(c.tt, t, sh.start, .5); c.bx.forEach((b, i) => { const q = P(t, c.ts[i] - .2, c.ts[i] + .3); b.style.opacity = cl(q * 3); b.style.transform = `translateY(${(1 - back(q)) * 600}px) rotate(${(i - 1) * 6}deg)`; }); },
  };

  // « Imaginez… » : photo ou emoji qui saute de joie + confettis
  SC.ds_imagine = {
    tint: 'none', caps: false, build(el, p, T) {
      redBg(el);
      const ln = mk(el, `<div class="a" style="left:${LAND ? 90 : 60 * u}px;top:${LAND ? 120 : ttl.y}px;width:${LAND ? 860 : W - 120 * u}px;text-align:${LAND ? 'left' : 'center'};font:800 ${60 * u}px Poppins;color:#fff">${letters(p.line || '')}</div>`); fitBox(ln, LAND ? 860 : W - 120 * u, 260 * u, 24);
      const ph = LIB.photo(0, LAND ? 760 : W - 160 * u, LAND ? 820 : H * .5, 30 * u);
      const pic = mk(el, `<div class="a" style="left:${LAND ? 1060 : 80 * u}px;top:${LAND ? 130 : H * .3}px">${ph || `<div class="emo" style="font-size:${LAND ? 520 : 600 * u}px;width:${LAND ? 760 : W - 160 * u}px;text-align:center">${esc(p.emoji || '🥳')}</div>`}</div>`);
      const cf = mk(el, LIB.confetti(46, ['#fff', '#ffd60a', '#ff8fa3']));
      const tp = T.at(p.at, 0, .3); ev(tp, 'shimmer', .9);
      return { ln, pic, cf, tp };
    },
    update(t, c, p, T, sh) {
      typeIn(c.ln, t, sh.start, .7);
      const q = P(t, c.tp - .2, c.tp + .4); c.pic.style.opacity = cl(q * 3); c.pic.style.transform = `translateY(${(1 - back(q)) * 400 - Math.abs(Math.sin(t * 3)) * 30}px)`;
      [...c.cf.children].forEach((d, i) => { const y = ((t - sh.start) * (120 + (i % 5) * 40)) % H; d.style.transform = `translateY(${y}px) rotate(${t * 200 + i * 30}deg)`; d.style.opacity = P(t, c.tp, c.tp + .3); });
    },
  };

  // Preuve : captures (témoignages) en éventail
  SC.ds_proof = {
    tint: 'none', caps: true, build(el, p, T) {
      redBg(el);
      const scr = K.S.screens || [];
      const items = (p.items || []).slice(0, 3);
      const cw = (LAND ? 420 : 520) * u;
      const cards = (scr.length ? scr.slice(0, 3) : items).map((it, i) => mk(el, `<div class="a" style="left:${LAND ? 300 + i * 450 : (W - cw) / 2 + (i - 1) * 90 * u}px;top:${LAND ? 140 : H * .22 + i * 80 * u}px;width:${cw}px;border-radius:${24 * u}px;overflow:hidden;background:#fff;box-shadow:0 30px 60px rgba(0,0,0,.35);padding:${scr.length ? 0 : 36 * u}px">${scr.length ? `<img src="${it}" style="width:100%;display:block">` : `<div style="font:700 ${40 * u}px Poppins;color:#111">⭐⭐⭐⭐⭐</div><div style="margin-top:${16 * u}px;font:600 ${38 * u}px Poppins;color:#333">${esc(it.text || it)}</div>`}</div>`));
      const ts = T.seq(cards.map(() => ({})), 'at', .05, .6); ts.forEach((x) => ev(x, 'pop', .7));
      return { cards, ts };
    },
    update(t, c, p, T, sh) { c.cards.forEach((cd, i) => { const q = P(t, c.ts[i] - .15, c.ts[i] + .3); cd.style.opacity = cl(q * 3); cd.style.transform = `translateY(${(1 - back(q)) * 500}px) rotate(${(i - 1) * 5}deg)`; }); },
  };

  // Prix / offre
  SC.ds_offer = {
    tint: 'none', caps: false, build(el, p, T) {
      redBg(el);
      const lab = mk(el, `<div class="a" style="left:0;right:0;top:${LAND ? 200 : H * .26}px;text-align:center;font:800 ${64 * u}px Poppins;color:#fff">${letters(p.label || 'Seulement')}</div>`);
      const pr = mk(el, `<div class="a" style="left:0;right:0;top:${LAND ? 330 : H * .34}px;text-align:center">${LIB.price3d(p.big || '', 200 * u, '#fff', '#8a0b1f')}</div>`); fit(pr.firstElementChild, W - 120, 40);
      const tp = T.at(p.at, 0, .3); ev(tp, 'impact_big', 1); ev(tp + .1, 'coin', .8);
      return { lab, pr, tp };
    },
    update(t, c, p, T, sh) { typeIn(c.lab, t, sh.start, .4); const q = P(t, c.tp - .15, c.tp + .35); c.pr.style.opacity = q > 0 ? 1 : 0; c.pr.style.transform = `perspective(1200px) rotateX(${(1 - eo(q)) * 90}deg) scale(${lerp(1.4, 1, eo(q))})`; kick(t, c.tp + .1, 20); },
  };

  // Appel à l'action : coffret + bouton blanc + main + barre de chargement + enveloppe « ADMIS »
  SC.ds_cta = {
    tint: 'none', build(el, p, T) {
      redBg(el);
      const bw = LAND ? 420 : 520 * u;
      const box = mk(el, `<div class="a" style="left:${LAND ? 200 : (W - bw) / 2}px;top:${LAND ? 120 : H * .12}px;filter:drop-shadow(0 30px 40px rgba(0,0,0,.4))">${LIB.product(bw)}</div>`);
      const btn = mk(el, `<div class="a" style="left:${LAND ? 120 : (W - 760 * u) / 2}px;top:${LAND ? 720 : H * .52}px;width:${LAND ? 600 : 760 * u}px;padding:${24 * u}px;border-radius:${50 * u}px;background:#fff;color:${RED};font:800 ${54 * u}px Poppins;text-align:center;white-space:nowrap">${esc(p.button || 'Cliquez sur le bouton')}</div>`); fit(btn, LAND ? 560 : 700 * u, 24);
      const hand = mk(el, `<div class="a emo" style="left:${LAND ? 520 : W * .55}px;top:${LAND ? 800 : H * .57}px;font-size:${150 * u}px">👆</div>`);
      const bar = mk(el, `<div class="a" style="left:${LAND ? 120 : W * .2}px;top:${LAND ? 880 : H * .66}px;width:${LAND ? 600 : W * .6}px;height:${18 * u}px;border-radius:${10 * u}px;background:rgba(255,255,255,.25)"><div style="height:100%;width:0;border-radius:${10 * u}px;background:#fff"></div></div>`);
      const ew = LAND ? 520 : 560 * u;
      const env = mk(el, `<div class="a" style="left:${LAND ? 1180 : (W - ew) / 2}px;top:${LAND ? 300 : H * .7}px">${LIB.envelope(ew, p.stamp || 'VALIDÉ', '#16a34a', 'Résultat')}</div>`);
      const phone = p.phone ? mk(el, `<div class="a" style="left:0;right:0;top:${LAND ? 980 : H * .44}px;text-align:center;font:900 ${70 * u}px Poppins;color:#fff">${letters(p.phone)}</div>`) : null;
      if (phone) { fit(phone, W - 120, 26); if (LAND) { phone.style.left = '120px'; phone.style.right = 'auto'; phone.style.top = '600px'; } }
      const tc = T.at(p.click_at, 0, .35), te = T.span[1] - .4;
      ev(tc, 'click', 1); ev(te, 'stamp', .9); ev(te + .2, 'shimmer', .8); if (phone) ev(T.at(p.call_at, 0, .6), 'ping', .7);
      return { box, btn, hand, bar, env, phone, tc, te, tp: T.at(p.call_at, 0, .6) };
    },
    update(t, c, p, T, sh) {
      pop(c.box, t, sh.start, .5, 200, .7); pop(c.btn, t, sh.start + .2, .4, 40, .7);
      const qh = P(t, c.tc - .4, c.tc); c.hand.style.opacity = cl(qh * 3); c.hand.style.transform = `translate(${(1 - eo(qh)) * 200}px,${(1 - eo(qh)) * 200}px) scale(${t > c.tc && t < c.tc + .15 ? .85 : 1})`;
      c.btn.style.transform += ` scale(${t > c.tc && t < c.tc + .15 ? .94 : 1})`;
      c.bar.firstElementChild.style.width = eo(P(t, c.tc + .1, c.te)) * 100 + '%'; c.bar.style.opacity = P(t, c.tc, c.tc + .2);
      const qe = P(t, c.te - .6, c.te - .2); c.env.style.opacity = cl(qe * 3); c.env.style.transform = `translateY(${(1 - back(qe)) * 300}px) rotate(-5deg)`;
      const st = c.env.querySelector('.stamp'); const qs = P(t, c.te, c.te + .22); st.style.opacity = qs > 0 ? 1 : 0; st.style.transform = `rotate(-12deg) scale(${lerp(2.4, 1, eo(qs))})`;
      if (c.phone) typeIn(c.phone, t, c.tp, 1.4);
    },
  };

  // Repli : carte de texte
  SC.ds_title = {
    tint: 'none', build(el, p, T, sh) {
      if (p.red) redBg(el);
      const lines = (p.lines && p.lines.length ? p.lines : [sh.text]).slice(0, 4);
      const z = LAND ? { x: 160, y: 160, w: W - 320, h: H - 320 } : { x: 70 * u, y: H * .2, w: W - 140 * u, h: H * .6 };
      const box = mk(el, `<div class="a" style="left:${z.x}px;top:${z.y}px;width:${z.w}px;height:${z.h}px;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:${16 * u}px;text-align:center">${lines.map((l, i) => `<div class="ln" style="line-height:1.08;font:${i === lines.length - 1 && lines.length > 1 ? 900 : 800} ${(i === lines.length - 1 && lines.length > 1 ? 130 : 96) * u}px Poppins;line-height:1.08;color:${p.red ? '#fff' : (i === lines.length - 1 && lines.length > 1 ? RED : '#0b0b0e')};text-transform:${i === lines.length - 1 && lines.length > 1 ? 'uppercase' : 'none'}">${letters(l)}</div>`).join('')}</div>`);
      [...box.children].forEach((l) => fitBox(l, z.w, z.h / lines.length, 26));
      const ts = T.lineStarts(lines); ts.forEach((x, i) => ev(x, i === lines.length - 1 ? 'impact' : 'blip', .6));
      return { box, ts };
    },
    update(t, c, p, T, sh) { [...c.box.children].forEach((l, i) => typeIn(l, t, c.ts[i] - .05, .45, i === c.ts.length - 1 ? 'drop' : 'blur')); },
  };

  document.getElementById('bg').innerHTML = '<div style="position:absolute;inset:0;background:radial-gradient(ellipse 75% 65% at 50% 45%,#fff 0,#f3f3f5 55%,#d6d6dc 100%)"></div>';
  K.register({
    name: 'dossier', SCENES: SC, fallback: 'ds_title', grain: .04, trDur: .4,
    transition(i, b, nx) { if (nx.type === 'ds_reveal') return 'bars'; if (/ds_(folders|book|bonus|imagine|proof|offer|cta)/.test(nx.type)) return ['slideUp', 'zoom', 'slide'][i % 3]; return ['slide', 'zoom', 'flip'][i % 3]; },
    trSfx: { slide: 'whoosh', slideUp: 'whoosh', zoom: 'whoosh_deep', flip: 'whoosh', bars: 'whoosh_deep' },
  });
})();
