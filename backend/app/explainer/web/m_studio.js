/*
 * Mode « Studio blanc » — inspiré des pubs d'infoproduits (Slide IA, Motion Mastery, WhatsApp Closer).
 * Fond blanc vignetté, objets détourés (ordinateur, silhouettes, pièce d'échecs, coffret produit),
 * titres tapés lettre par lettre, sous-titres serif italiques qui rebondissent, étiquettes inclinées,
 * ruptures plein écran (noir « ça fait mal », rouge à motif), coffret + bouclier « accès exclusif ».
 */
(function () {
  const K = window.KIT;
  const { Z, mk, place, esc, P, eo, back, lerp, cl, pop, slam, slide, fade, fit, fitBox, letters, words, typeIn, wordsIn, ev, kick, flash, LIB, ACC, ACC2, W, H, O } = K;
  const LAND = O === 'landscape';
  const u = Math.min(W, H) / 1080;
  const plusRow = (y, color = '#9a9aa3') => `<div class="a" style="left:0;right:0;top:${y}px;text-align:center;font:500 ${46 * u}px Poppins;letter-spacing:${38 * u}px;color:${color}">+ + + + + + + + + + + + + + +</div>`;
  const title = (el, z, text, fs = 120, extra = '') => { const e = mk(el, `<div class="a ttl" style="font:400 ${fs * u}px Anton;text-transform:uppercase;color:#0b0b0e;text-align:center;line-height:1.02;${extra}">${letters(text)}</div>`); place(e, { x: z.x, y: z.y, w: z.w, h: z.h }); fitBox(e, z.w, z.h, 30); return e; };
  const serif = (el, x, y, w, text, fs = 64, color = ACC) => { const e = mk(el, `<div class="a" style="left:${x}px;top:${y}px;width:${w}px;text-align:center;font:italic 400 ${fs * u}px DMSerif;color:${color}">${letters(text)}</div>`); fit(e, w, 26); return e; };
  const tag = (el, x, y, text, bg = ACC, fg = '#fff', rot = -8, fs = 46) => mk(el, `<div class="a tag" style="left:${x}px;top:${y}px;padding:${12 * u}px ${30 * u}px;background:${bg};color:${fg};font:800 ${fs * u}px Poppins;white-space:nowrap;transform-origin:0 50%;--r:${rot}deg">${esc(text)}</div>`);
  const hero = Z('hero'), ttl = Z('title'), sub = Z('sub');
  const center = (w, h, z = hero) => ({ x: z.x + (z.w - w) / 2, y: z.y + (z.h - h) / 2 });

  const SC = {};

  // Accroche « statistique / constat » : mot géant + silhouettes + phrase
  SC.st_stat = {
    tint: 'none', build(el, p, T) {
      const big = mk(el, `<div class="a" style="left:0;right:0;top:${(LAND ? 120 : ttl.y + 40 * u)}px;text-align:center;font:900 ${(LAND ? 300 : 340) * u}px Poppins;color:#E11D2E;letter-spacing:-.04em;line-height:1">${esc(p.big || '')}</div>`); fit(big, W - 80, 60);
      const fig = mk(el, `<div class="a" style="left:0;right:0;bottom:${LAND ? 0 : H * .14}px;display:flex;justify-content:center;gap:${4 * u}px;align-items:flex-end">${[0, 1, 2, 3, 4].map((i) => LIB.figure((LAND ? 520 : 560) * u * (i === 2 ? 1.05 : .9 + (i % 2) * .05), ['stand', 'stand', 'stand', 'stand', 'stand'][i], '#111')).join('')}</div>`);
      const line = mk(el, `<div class="a" style="left:${sub.x}px;top:${LAND ? H - 200 : sub.y + 60 * u}px;width:${sub.w}px;text-align:center;font:800 ${62 * u}px Poppins;color:#111">${words(p.line || '')}</div>`); fitBox(line, sub.w, 200 * u, 30);
      const tb = T.at(p.big_at, 0, 0); ev(tb, 'impact_big', 1);
      return { big, fig, line, tb, lt: T.wordTimes(p.line || '') };
    },
    update(t, c, p, T, sh) {
      const q = P(t, c.tb - .1, c.tb + .35); c.big.style.opacity = sh.start === 0 ? 1 : cl(q * 3); c.big.style.transform = `scale(${lerp(1.5, 1, eo(q))})`;
      c.fig.style.transform = `translateY(${(1 - eo(P(t, sh.start, sh.start + .6))) * 300}px)`;
      wordsIn(c.line, t, c.lt); kick(t, c.tb + .1, 10);
    },
  };

  // Démonstration sur ordinateur : titre tapé, écran, sous-titre italique, étiquette
  SC.st_laptop = {
    tint: 'none', caps: false, build(el, p, T) {
      const lw = LAND ? 860 : Math.min(W - 60, 980 * u);
      const pos = center(lw, lw * .66);
      const scr = p.screen === 'product' ? `<div style="height:100%;display:flex;align-items:center;justify-content:center;background:#fff">${LIB.product(lw * .45, false)}</div>` : (K.S.screens && K.S.screens[0]) ? `<img src="${K.S.screens[0]}" style="width:100%;height:100%;object-fit:cover">` : LIB.appScreen(p.screen || 'list', { title: p.screen_title, rows: p.rows, fs: 30 * u });
      mk(el, plusRow(pos.y + lw * .62 * .5));
      const lap = mk(el, `<div class="a" style="left:${pos.x}px;top:${pos.y}px">${LIB.laptop(lw, scr)}</div>`);
      const tl = title(el, LAND ? Z('title') : { x: ttl.x, y: ttl.y + 20 * u, w: ttl.w, h: 300 * u }, p.title || '', LAND ? 110 : 140);
      const sb = p.sub ? serif(el, sub.x, LAND ? 620 : pos.y + lw * .66 + 50 * u, sub.w, p.sub, 70) : null;
      const tg = p.tag ? tag(el, LAND ? 1100 : pos.x + lw * .45, LAND ? 820 : pos.y + lw * .58, p.tag) : null;
      const tt = T.at(p.title_at, 0, 0), ts = T.at(p.sub_at, 0, .45), tgT = T.at(p.tag_at, 0, .75);
      ev(tt, 'blip', .6); if (sb) ev(ts, 'pop', .5); if (tg) ev(tgT, 'stamp', .6);
      return { lap, tl, sb, tg, tt, ts, tgT };
    },
    update(t, c, p, T, sh) {
      const q = P(t, sh.start, sh.start + .55); c.lap.style.transform = `translateY(${(1 - back(q)) * 260}px) scale(${1 + .03 * P(t, sh.start, sh.end)})`; c.lap.style.opacity = cl(q * 3);
      typeIn(c.tl, t, c.tt - .05, .55);
      if (c.sb) typeIn(c.sb, t, c.ts, .7, 'bounce');
      if (c.tg) { const qq = P(t, c.tgT, c.tgT + .3); c.tg.style.opacity = qq > 0 ? 1 : 0; c.tg.style.transform = `rotate(-8deg) scaleX(${eo(qq)})`; kick(t, c.tgT + .2, 8); }
    },
  };

  // Grille de 4 cartes sombres (résultats, modules) + étiquette tamponnée
  SC.st_grid = {
    tint: 'none', build(el, p, T) {
      const items = (p.items || []).slice(0, 4);
      const gw = LAND ? 760 : Math.min(W - 140, 860 * u), cw = (gw - 30 * u) / 2, ch = cw * 1.08;
      const pos = center(gw, ch * 2 + 30 * u);
      const lab = mk(el, `<div class="a" style="left:${W / 2}px;top:${pos.y - 120 * u}px;transform:translateX(-50%);padding:${12 * u}px ${30 * u}px;background:${p.label_bg || '#111'};color:#fff;font:800 ${50 * u}px Poppins;white-space:nowrap">${esc(p.label || '')}</div>`);
      if (!p.label) lab.style.display = 'none';
      const cards = items.map((it, i) => mk(el, `<div class="a" style="left:${pos.x + (i % 2) * (cw + 30 * u)}px;top:${pos.y + Math.floor(i / 2) * (ch + 30 * u)}px;width:${cw}px;height:${ch}px;border-radius:${18 * u}px;background:linear-gradient(160deg,#1c1c22,#0b0b0e);padding:${26 * u}px;box-shadow:0 20px 40px rgba(0,0,0,.25);overflow:hidden">
          <div class="emo" style="font-size:${70 * u}px">${esc(it.emoji || '✨')}</div>
          <div class="tx" style="margin-top:${16 * u}px;font:800 ${46 * u}px Poppins;color:#fff;line-height:1.1">${esc(it.text || it)}</div>
          <div style="position:absolute;right:${20 * u}px;bottom:${20 * u}px;width:${60 * u}px;height:${60 * u}px;border-radius:${14 * u}px;background:${ACC}"></div></div>`));
      cards.forEach((cd) => fitBox(cd.querySelector('.tx'), cw - 52 * u, ch * .55, 20));
      const st = p.stamp ? tag(el, pos.x - 10 * u, pos.y + ch * 2 - 20 * u, p.stamp, p.stamp_bad ? '#111' : ACC, '#fff', -14, 52) : null;
      const ts = T.seq(items, 'at', .1, .7), tst = T.at(p.stamp_at, 0, .85);
      ts.forEach((x) => ev(x, 'pop', .6)); if (st) ev(tst, 'stamp', .8);
      return { lab, cards, st, ts, tst };
    },
    update(t, c, p, T, sh) {
      pop(c.lab, t, sh.start, .35, 20, .8);
      c.cards.forEach((cd, i) => pop(cd, t, c.ts[i] - .15, .4, 60, .7));
      if (c.st) { const q = P(t, c.tst, c.tst + .25); c.st.style.opacity = q > 0 ? 1 : 0; c.st.style.transform = `rotate(-14deg) scale(${lerp(2, 1, eo(q))})`; kick(t, c.tst + .15, 14); }
    },
  };

  // Silhouette expressive + mot qui apparaît dans sa main
  SC.st_figure = {
    tint: 'none', caps: true, build(el, p, T) {
      const fh = LAND ? 900 : 1100 * u;
      const fig = mk(el, `<div class="a" style="left:${LAND ? 1050 : W * .05}px;bottom:${LAND ? 0 : H * .12}px">${LIB.figure(fh, p.pose || 'shrug', '#0f0f12')}</div>`);
      const wd = mk(el, `<div class="a" style="left:${LAND ? 90 : W * .38}px;top:${LAND ? 300 : H * .26}px;width:${LAND ? 860 : W * .58}px;text-align:center"><div class="emo" style="font-size:${120 * u}px">${esc(p.emoji || '💡')}</div><div class="bw" style="font:400 ${130 * u}px Anton;text-transform:uppercase;color:#0b0b0e;line-height:1">${letters(p.word || '')}</div></div>`);
      fit(wd.querySelector('.bw'), LAND ? 860 : W * .58, 30);
      const tw = T.at(p.word_at, 0, .3); ev(tw, 'shimmer', .6);
      return { fig, wd, tw };
    },
    update(t, c, p, T, sh) {
      const q = P(t, sh.start, sh.start + .5); c.fig.style.transform = `translateX(${(1 - eo(q)) * -400}px)`; c.fig.style.opacity = cl(q * 2);
      pop(c.wd.querySelector('.emo'), t, c.tw - .1, .4, 40, .3); typeIn(c.wd.querySelector('.bw'), t, c.tw, .5, 'drop');
    },
  };

  // Rupture noire : « ça fait mal »
  SC.st_dark = {
    tint: 'none', build(el, p, T) {
      el.style.background = '#050506';
      const fig = mk(el, `<div class="a" style="left:${LAND ? 1100 : W * .2}px;bottom:${LAND ? 0 : H * .18}px;transform-origin:50% 100%">${LIB.figure(LAND ? 820 : 900 * u, 'stand', '#1d1d22')}</div>`);
      const box = mk(el, `<div class="a" style="left:${LAND ? 120 : 70 * u}px;top:${LAND ? 360 : H * .28}px;padding:${18 * u}px ${44 * u}px;background:#C8102E;color:#fff;font:400 ${130 * u}px Anton;text-transform:uppercase;white-space:nowrap">${esc(p.text || 'Ça fait mal')}</div>`); fit(box, LAND ? 900 : W - 140 * u, 40);
      const tb = T.at(p.at, 0, .2); ev(tb, 'impact_big', 1.1); ev(tb + .02, 'heartbeat', .7);
      return { fig, box, tb };
    },
    update(t, c, p, T, sh) {
      const q = P(t, c.tb - .1, c.tb + .2); c.box.style.opacity = q > 0 ? 1 : 0; c.box.style.transform = `scaleX(${eo(q)})`; c.box.style.transformOrigin = '0 50%';
      c.fig.style.transform = `rotate(${-8 * eo(P(t, c.tb, c.tb + .8))}deg) translateY(${eo(P(t, c.tb, c.tb + .8)) * 60}px)`;
      kick(t, c.tb + .05, 26); flash(t, c.tb, .2);
    },
  };

  // Fond rouge à motif typographique + phrases qui claquent dans des cartouches blancs
  SC.st_pattern = {
    tint: 'none', build(el, p, T) {
      el.style.background = '#B3122B';
      const pat = String(p.pattern || K.PRODUCT.name || 'OFFRE').toUpperCase();
      const rows = [...Array(LAND ? 6 : 9)].map((_, i) => `<div style="white-space:nowrap;font:400 ${180 * u}px Anton;color:transparent;-webkit-text-stroke:${3 * u}px rgba(255,190,120,.35);transform:translateX(${(i % 2) * -300}px)">${esc((pat + ' ').repeat(6))}</div>`).join('');
      const bgt = mk(el, `<div class="a" style="left:-200px;top:-40px;line-height:1">${rows}</div>`);
      const items = (p.items || []).slice(0, 4);
      const lines = items.map((it, i) => mk(el, `<div class="a" style="left:${LAND ? 140 : 80 * u}px;top:${(LAND ? 260 : H * .34) + i * 170 * u}px;padding:${14 * u}px ${30 * u}px;background:#fff;color:#C8102E;font:800 ${64 * u}px Poppins;white-space:nowrap;box-shadow:0 10px 30px rgba(0,0,0,.3)">${esc(it.text || it)}</div>`));
      lines.forEach((l) => fit(l, LAND ? 900 : W - 160 * u, 26));
      const ic = p.emoji ? mk(el, `<div class="a emo" style="right:${LAND ? 160 : 70 * u}px;top:${LAND ? 300 : H * .62}px;font-size:${LAND ? 360 : 300 * u}px">${esc(p.emoji)}</div>`) : null;
      const ts = T.seq(items, 'at', .1, .8); ts.forEach((x) => ev(x, 'thud', .8));
      return { bgt, lines, ic, ts };
    },
    update(t, c, p, T, sh) {
      c.bgt.style.transform = `translateX(${-(t - sh.start) * 60}px)`;
      c.lines.forEach((l, i) => { slide(l, t, c.ts[i] - .15, -800, 0, .35); kick(t, c.ts[i] + .05, 8); });
      if (c.ic) { pop(c.ic, t, sh.start + .1, .5, 80, .4); c.ic.style.transform += ` rotate(${Math.sin(t * 3) * 6}deg)`; }
    },
  };

  // Révélation du coffret produit (trait courbe dessiné, rotation douce)
  SC.st_product = {
    tint: 'none', build(el, p, T) {
      const bw = LAND ? 620 : Math.min(W * .62, 640 * u);
      const pos = center(bw, bw * 1.1);
      const curve = mk(el, `<svg class="a" style="left:0;top:0" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><path d="M${-50} ${H * .9} C ${W * .3} ${H * .55}, ${W * .2} ${H * .25}, ${W + 50} ${H * .12}" fill="none" stroke="#c9a464" stroke-width="${5 * u}" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/></svg>`);
      const box = mk(el, `<div class="a" style="left:${pos.x}px;top:${pos.y}px;filter:drop-shadow(0 40px 50px rgba(0,0,0,.35))">${LIB.product(bw)}</div>`);
      const nm = p.name ? mk(el, `<div class="a" style="left:${ttl.x}px;top:${LAND ? 120 : ttl.y}px;width:${LAND ? 860 : ttl.w}px;text-align:center;font:400 ${110 * u}px Anton;text-transform:uppercase;color:#0b0b0e">${letters(p.name)}</div>`) : null; if (nm) fit(nm, LAND ? 860 : ttl.w, 30);
      const sb = p.sub ? serif(el, sub.x, LAND ? 700 : pos.y + bw * 1.1 + 40 * u, sub.w, p.sub, 62) : null;
      const tr = T.at(p.at, 0, .05); ev(tr - .2, 'whoosh', .7); ev(tr + .1, 'shimmer', .9);
      return { curve, box, nm, sb, tr };
    },
    update(t, c, p, T, sh) {
      c.curve.querySelector('path').setAttribute('stroke-dashoffset', String(1 - eo(P(t, sh.start, sh.start + 1.2))));
      const q = P(t, c.tr - .25, c.tr + .4); c.box.style.opacity = cl(q * 3);
      c.box.style.transform = `perspective(1400px) rotateY(${(1 - eo(q)) * 70 + Math.sin(t * 1.2) * 8}deg) translateY(${Math.sin(t * 2) * 8}px)`;
      if (c.nm) typeIn(c.nm, t, c.tr + .1, .5); if (c.sb) typeIn(c.sb, t, c.tr + .5, .6, 'bounce');
    },
  };

  // Positionnement « n°1 » : pièce d'échecs + grand titre
  SC.st_chess = {
    tint: 'none', build(el, p, T) {
      const ch = mk(el, `<div class="a" style="left:${LAND ? 1150 : W * .02}px;bottom:${LAND ? 40 : H * .1}px">${LIB.chess(LAND ? 820 : 900 * u)}</div>`);
      const big = mk(el, `<div class="a" style="left:${LAND ? 90 : 60 * u}px;top:${LAND ? 220 : ttl.y}px;width:${LAND ? 980 : W - 120 * u}px;text-align:${LAND ? 'left' : 'center'};font:400 ${170 * u}px Anton;text-transform:uppercase;color:#E11D2E;line-height:1">${letters(p.big || '')}</div>`); fitBox(big, LAND ? 980 : W - 120 * u, 380 * u, 40);
      const sb = p.sub ? mk(el, `<div class="a" style="left:${LAND ? 90 : W * .48}px;top:${LAND ? 640 : H * .5}px;width:${LAND ? 860 : W * .47}px;text-align:${LAND ? 'left' : 'left'};font:800 ${64 * u}px Poppins;color:#111;line-height:1.15">${words(p.sub)}</div>`) : null; if (sb) fitBox(sb, LAND ? 860 : W * .47, 520 * u, 26);
      const tb = T.at(p.at, 0, .05); ev(tb, 'impact', .8);
      return { ch, big, sb, tb, st: T.wordTimes(p.sub || '') };
    },
    update(t, c, p, T, sh) {
      const q = P(t, sh.start, sh.start + .6); c.ch.style.transform = `translateY(${(1 - back(q)) * 400}px)`; c.ch.style.opacity = cl(q * 3);
      typeIn(c.big, t, Math.min(c.tb, sh.start + .3), .5, 'drop'); if (c.sb) wordsIn(c.sb, t, c.st);
    },
  };

  // Scène « expert devant son public » : écran géant derrière, silhouettes
  SC.st_stage = {
    tint: 'none', caps: true, build(el, p, T) {
      const sw = LAND ? 1100 : W - 120 * u, sh_ = sw * .52;
      const scr = mk(el, `<div class="a" style="left:${(W - sw) / 2}px;top:${LAND ? 80 : H * .2}px;width:${sw}px;height:${sh_}px;background:#111;border-radius:${10 * u}px;box-shadow:0 0 60px rgba(0,0,0,.25);display:flex;align-items:center;justify-content:center;padding:${40 * u}px;text-align:center;font:400 ${96 * u}px Anton;text-transform:uppercase;color:${ACC2}">${letters(p.screen || '')}</div>`); fitBox(scr, sw - 80 * u, sh_ - 80 * u, 30);
      const pr = mk(el, `<div class="a" style="left:${W * .58}px;bottom:${LAND ? 120 : H * .2}px">${LIB.presenter(LAND ? 560 : 640 * u)}</div>`);
      const cr = mk(el, `<div class="a" style="left:0;right:0;bottom:0;height:${LAND ? 260 : H * .22}px;background:#0d0d10;display:flex;align-items:flex-start;overflow:hidden">${LIB.crowd(W * 1.1)}</div>`);
      cr.firstElementChild.style.marginTop = `-${LAND ? 150 : 170 * u}px`;
      const tt = p.title ? mk(el, `<div class="a" style="left:0;right:0;top:${LAND ? 30 : H * .1}px;text-align:center;font:800 ${58 * u}px Poppins;color:#111">${words(p.title)}</div>`) : null;
      const ts = T.at(p.screen_at, 0, .3); ev(ts, 'blip', .6);
      return { scr, pr, cr, tt, ts, wt: T.wordTimes(p.title || '') };
    },
    update(t, c, p, T, sh) {
      fade(c.scr, t, sh.start, .3); typeIn(c.scr, t, c.ts, .6);
      slide(c.pr, t, sh.start + .1, 300, 0, .5); c.cr.style.transform = `translateY(${(1 - eo(P(t, sh.start, sh.start + .5))) * 300}px)`;
      if (c.tt) wordsIn(c.tt, t, c.wt);
    },
  };

  // Feuille de papier : la liste de ce qu'on apprend / reçoit
  SC.st_checklist = {
    tint: 'none', build(el, p, T) {
      const pw = LAND ? 760 : Math.min(W - 160 * u, 820 * u), ph = pw * 1.25;
      const pos = center(pw, ph, LAND ? { x: 980, y: 60, w: 860, h: 960 } : hero);
      const sheet = mk(el, `<div class="a" style="left:${pos.x}px;top:${pos.y}px;width:${pw}px;height:${ph}px;background:#fff;box-shadow:0 30px 60px rgba(0,0,0,.18);padding:${60 * u}px ${50 * u}px;transform-origin:50% 0">
          ${p.badge ? `<div style="display:inline-block;padding:${8 * u}px ${20 * u}px;border-radius:${30 * u}px;background:${ACC};color:#fff;font:800 ${30 * u}px Poppins;margin-bottom:${30 * u}px">${esc(p.badge)}</div>` : ''}
          ${(p.items || []).slice(0, 5).map((it) => `<div class="it" style="display:flex;gap:${18 * u}px;align-items:flex-start;margin:${26 * u}px 0;font:700 ${58 * u}px Poppins;color:#111;line-height:1.2"><span style="flex:none">•</span><span class="tx">${letters(it.text || it)}</span></div>`).join('')}</div>`);
      const its = [...sheet.querySelectorAll('.it')];
      its.forEach((i_) => fitBox(i_, pw - 100 * u, 200 * u, 22));
      const tt = LAND && p.title ? mk(el, `<div class="a" style="left:90px;top:200px;width:820px;font:400 ${110 * u}px Anton;text-transform:uppercase;color:#0b0b0e">${letters(p.title)}</div>`) : null;
      const ts = T.seq(p.items || [], 'at', .05, .85); ts.forEach((x) => ev(x, 'pencil', .6));
      return { sheet, its, ts, tt };
    },
    update(t, c, p, T, sh) {
      const q = P(t, sh.start, sh.start + .5); c.sheet.style.transform = `perspective(1500px) rotateX(${(1 - eo(q)) * 60}deg) rotate(${-2 + Math.sin(t) * .4}deg)`; c.sheet.style.opacity = cl(q * 3);
      c.its.forEach((it, i) => typeIn(it.querySelector('.tx'), t, c.ts[i], .5));
      if (c.tt) typeIn(c.tt, t, sh.start + .1, .5);
    },
  };

  // Bouclier « accès exclusif » + bonus qui défilent
  SC.st_shield = {
    tint: 'none', caps: true, build(el, p, T) {
      const lab = mk(el, `<div class="a" style="left:0;right:0;top:${LAND ? 70 : ttl.y}px;text-align:center;font:400 ${120 * u}px Anton;text-transform:uppercase;color:#0b0b0e">${letters(p.label || 'Accès exclusif')}</div>`); fit(lab, W - 120, 30);
      const sz = LAND ? 360 : 420 * u;
      const sh_ = mk(el, `<div class="a" style="left:${(W - sz) / 2}px;top:${LAND ? 260 : H * .24}px;filter:drop-shadow(0 30px 40px rgba(37,99,235,.35))">${LIB.icon('shield', sz, '#3B82F6')}</div>`);
      const items = (p.items || []).slice(0, 4);
      const cards = items.map((it, i) => mk(el, `<div class="a" style="left:${LAND ? 200 + i * 400 : 90 * u}px;top:${LAND ? 700 : H * .52 + i * 150 * u}px;width:${LAND ? 360 : W - 180 * u}px;padding:${22 * u}px ${30 * u}px;border-radius:${22 * u}px;background:#111;color:#fff;display:flex;gap:${20 * u}px;align-items:center;font:800 ${42 * u}px Poppins"><span class="emo" style="font-size:${56 * u}px">${esc(it.emoji || '🎁')}</span><span class="tx">${esc(it.text || it)}</span></div>`));
      cards.forEach((cd) => fit(cd.querySelector('.tx'), (LAND ? 360 : W - 180 * u) - 140 * u, 20));
      const tl = T.at(p.at, 0, 0), ts = T.seq(items, 'at', .3, .9);
      ev(tl, 'shimmer', .8); ts.forEach((x) => ev(x, 'ding', .6));
      return { lab, sh: sh_, cards, tl, ts };
    },
    update(t, c, p, T, sh) {
      typeIn(c.lab, t, c.tl - .05, .45);
      const q = P(t, c.tl, c.tl + .5); c.sh.style.opacity = cl(q * 3); c.sh.style.transform = `scale(${back(q)}) rotate(${Math.sin(t * 2) * 4}deg)`;
      c.cards.forEach((cd, i) => slide(cd, t, c.ts[i] - .2, LAND ? 0 : 700, LAND ? 300 : 0, .4));
    },
  };

  // Bonus : cadeau + « en plus, tu reçois » + coffrets qui s'empilent
  SC.st_bonus = {
    tint: 'none', caps: true, build(el, p, T) {
      const tt = mk(el, `<div class="a" style="left:0;right:0;top:${LAND ? 80 : ttl.y + 30 * u}px;text-align:center;font:800 ${70 * u}px Poppins;color:#111">${letters(p.title || 'En plus, tu reçois')}</div>`); fit(tt, W - 120, 26);
      const gift = mk(el, `<div class="a emo" style="left:${(W - 300 * u) / 2}px;top:${LAND ? 220 : H * .2}px;font-size:${300 * u}px">🎁</div>`);
      const items = (p.items || []).slice(0, 4);
      const bw = LAND ? 300 : 300 * u;
      const boxes = items.map((it, i) => mk(el, `<div class="a" style="left:${LAND ? 120 + i * 440 : (i % 2 ? W * .5 : W * .06)}px;top:${LAND ? 560 : H * .42 + Math.floor(i / 2) * 470 * u}px;width:${LAND ? 400 : W * .44}px;text-align:center">${LIB.box(bw, it.text || it)}<div style="font:800 ${36 * u}px Poppins;color:#111;margin-top:${8 * u}px">${esc(it.text || it)}</div></div>`));
      const ts = T.seq(items, 'at', .25, .9), tg = T.at(p.at, 0, 0);
      ev(tg, 'pop_high', .8); ts.forEach((x) => ev(x, 'whoosh', .4));
      return { tt, gift, boxes, ts, tg };
    },
    update(t, c, p, T, sh) {
      typeIn(c.tt, t, sh.start, .5);
      const q = P(t, c.tg, c.tg + .5); c.gift.style.opacity = cl(q * 3) * (1 - P(t, c.ts[0] - .3, c.ts[0])); c.gift.style.transform = `scale(${back(q)}) rotate(${Math.sin(t * 8) * 6 * (1 - q)}deg)`;
      c.boxes.forEach((b, i) => pop(b, t, c.ts[i] - .2, .45, 80, .4));
    },
  };

  // Rareté (uniquement si fournie par le client) : « 20 places » + tampon
  SC.st_scarcity = {
    tint: 'none', caps: true, build(el, p, T) {
      const big = mk(el, `<div class="a" style="left:0;right:0;top:${LAND ? 120 : H * .2}px;text-align:center;font:400 ${220 * u}px Anton;text-transform:uppercase;color:#E11D2E">${esc(p.big || '')}</div>`); fit(big, W - 120, 40);
      const st = p.stamp ? mk(el, `<div class="a" style="left:0;right:0;top:${LAND ? 420 : H * .38}px;text-align:center"><span style="display:inline-block;padding:${10 * u}px ${30 * u}px;border:${8 * u}px solid #111;font:400 ${90 * u}px Anton;text-transform:uppercase;color:#111;transform:rotate(-6deg)">${esc(p.stamp)}</span></div>`) : null;
      const cr = mk(el, `<div class="a" style="left:0;right:0;bottom:0;height:${LAND ? 260 : H * .3}px;background:#0d0d10;overflow:hidden">${LIB.crowd(W * 1.1)}</div>`); cr.firstElementChild.style.marginTop = `-${LAND ? 150 : 200 * u}px`;
      const tb = T.at(p.at, 0, .05), ts = T.at(p.stamp_at, 0, .6);
      ev(tb, 'impact_big', 1); if (st) ev(ts, 'stamp', 1);
      return { big, st, cr, tb, ts };
    },
    update(t, c, p, T, sh) {
      slam(c.big, t, c.tb - .1, 1.8); kick(t, c.tb + .1, 18);
      if (c.st) { const q = P(t, c.ts, c.ts + .25); c.st.style.opacity = q > 0 ? 1 : 0; c.st.style.transform = `scale(${lerp(2.2, 1, eo(q))})`; kick(t, c.ts + .1, 20); }
      c.cr.style.transform = `translateY(${(1 - eo(P(t, sh.start, sh.start + .5))) * 300}px)`;
    },
  };

  // Offre / remise (uniquement si fournie)
  SC.st_offer = {
    tint: 'none', caps: true, build(el, p, T) {
      const face = mk(el, `<div class="a emo" style="left:${LAND ? 1200 : W * .1}px;top:${LAND ? 300 : H * .45}px;font-size:${(LAND ? 480 : 560) * u}px">${esc(p.emoji || '😎')}</div>`);
      const big = mk(el, `<div class="a" style="left:0;right:0;top:${LAND ? 120 : H * .14}px;text-align:center;font:900 ${260 * u}px Poppins;color:#E11D2E;text-shadow:0 0 ${40 * u}px rgba(225,29,46,.4)">${esc(p.big || '')}</div>`); fit(big, LAND ? 1000 : W - 100, 50);
      const lab = mk(el, `<div class="a" style="left:0;right:0;top:${LAND ? 460 : H * .32}px;text-align:center;font:400 ${90 * u}px Anton;text-transform:uppercase;color:#111">${letters(p.label || '')}</div>`); fit(lab, W - 120, 26);
      const tb = T.at(p.at, 0, .2); ev(tb, 'impact_big', 1); ev(tb + .1, 'coin', .8);
      return { face, big, lab, tb };
    },
    update(t, c, p, T, sh) {
      const q = P(t, sh.start, sh.start + .5); c.face.style.transform = `translateY(${(1 - back(q)) * 500}px) rotate(${Math.sin(t * 2) * 5}deg)`; c.face.style.opacity = cl(q * 3);
      slam(c.big, t, c.tb - .1, 2.2); typeIn(c.lab, t, c.tb + .3, .5); kick(t, c.tb + .1, 22);
    },
  };

  // Appel à l'action : texte tapé + tampon « Profitez de l'offre » + coffret + numéro
  SC.st_cta = {
    tint: 'none', build(el, p, T) {
      const tt = mk(el, `<div class="a" style="left:${LAND ? 90 : 60 * u}px;top:${LAND ? 220 : ttl.y + 40 * u}px;width:${LAND ? 860 : W - 120 * u}px;text-align:${LAND ? 'left' : 'center'};font:800 ${78 * u}px Poppins;color:#111">${letters(p.button || 'Clique sur le bouton')}</div>`); fitBox(tt, LAND ? 860 : W - 120 * u, 220 * u, 30);
      const st = mk(el, `<div class="a" style="left:${LAND ? 90 : W * .12}px;top:${LAND ? 420 : ttl.y + 260 * u}px;padding:${14 * u}px ${34 * u}px;background:#111;color:#fff;font:800 ${56 * u}px Poppins;white-space:nowrap">${esc(p.stamp || 'Profitez de l\'offre')}</div>`);
      const bw = LAND ? 520 : 560 * u;
      const box = mk(el, `<div class="a" style="left:${LAND ? 1150 : (W - bw) / 2}px;top:${LAND ? 150 : H * .38}px;filter:drop-shadow(0 40px 50px rgba(0,0,0,.35))">${LIB.product(bw)}</div>`);
      const phone = p.phone ? mk(el, `<div class="a" style="left:${LAND ? 90 : 0}px;right:${LAND ? 'auto' : 0}px;top:${LAND ? 640 : H * .76}px;text-align:center;font:900 ${86 * u}px Poppins;color:#111;white-space:nowrap">${LIB.icon('phone', 70 * u, ACC)} ${letters(p.phone)}</div>`) : null;
      if (phone) fit(phone, LAND ? 860 : W - 80, 30);
      const tg = p.tagline ? mk(el, `<div class="a" style="left:0;right:0;top:${LAND ? 800 : H * .85}px;text-align:center;font:italic 400 ${56 * u}px DMSerif;color:${ACC}">${letters(p.tagline)}</div>`) : null; if (tg) fit(tg, W - 120, 24);
      const ts = T.at(p.stamp_at, 0, .35), tp = T.at(p.call_at, 0, .55);
      ev(sh0(T), 'blip', .6); ev(ts, 'stamp', .9); if (phone) ev(tp, 'ping', .7);
      return { tt, st, box, phone, tg, ts, tp };
    },
    update(t, c, p, T, sh) {
      typeIn(c.tt, t, sh.start, .6);
      const q = P(t, c.ts, c.ts + .25); c.st.style.opacity = q > 0 ? 1 : 0; c.st.style.transform = `rotate(-10deg) scale(${lerp(2, 1, eo(q))})`; kick(t, c.ts + .1, 14);
      const qb = P(t, sh.start + .2, sh.start + .8); c.box.style.opacity = cl(qb * 3); c.box.style.transform = `perspective(1400px) rotateY(${(1 - eo(qb)) * -60 + Math.sin(t * 1.3) * 6}deg) scale(${1 + .02 * Math.sin(t * 3)})`;
      if (c.phone) typeIn(c.phone, t, c.tp, 1.6);
      if (c.tg) typeIn(c.tg, t, T.span[1] + .2, .6, 'bounce');
    },
  };
  const sh0 = (T) => T.span[0];

  // Repli : mots tapés au centre
  SC.st_words = {
    tint: 'none', build(el, p, T, sh) {
      const lines = (p.lines && p.lines.length ? p.lines : [sh.text]).slice(0, 4);
      const z = LAND ? { x: 160, y: 200, w: W - 320, h: H - 400 } : { x: 70 * u, y: H * .3, w: W - 140 * u, h: H * .4 };
      const box = mk(el, `<div class="a" style="left:${z.x}px;top:${z.y}px;width:${z.w}px;height:${z.h}px;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:${10 * u}px;text-align:center">${lines.map((l, i) => `<div class="ln" style="font:${i % 2 ? `italic 400 ${118 * u}px DMSerif;color:${ACC}` : `800 ${120 * u}px Poppins;color:#111`}">${letters(l)}</div>`).join('')}</div>`);
      [...box.children].forEach((l) => fit(l, z.w, 26));
      const ts = T.lineStarts(lines); ts.forEach((x) => ev(x, 'blip', .5));
      return { box, ts };
    },
    update(t, c, p, T, sh) { [...c.box.children].forEach((l, i) => typeIn(l, t, c.ts[i] - .05, .5, i % 2 ? 'bounce' : 'blur')); },
  };

  const BG = document.getElementById('bg');
  BG.innerHTML = `<div style="position:absolute;inset:0;background:radial-gradient(ellipse 70% 60% at 50% 45%,#ffffff 0,#f4f4f6 45%,#c4c4cb 100%)"></div>`;
  K.register({
    name: 'studio', SCENES: SC, fallback: 'st_words', grain: .05, trDur: .35,
    transition(i, b, nx) { if (nx.type === 'st_dark' || b.type === 'st_dark') return 'cut'; if (nx.type === 'st_pattern') return 'wipe'; return ['slide', 'zoom', 'slideUp', 'zoomOut', 'flip'][i % 5]; },
    trSfx: { slide: 'whoosh', zoom: 'whoosh_deep', slideUp: 'whoosh', zoomOut: 'whoosh_rev', flip: 'whoosh', wipe: 'whoosh_deep' },
    background() {},
  });
})();
