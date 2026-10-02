/*
 * Mode « App 3D » — inspiré des pubs d'applications (budget, assurance en ligne, CV).
 * Fond blanc lumineux avec halo de la couleur de marque, téléphone 3D qui pivote et flotte,
 * pilules 3D qui basculent (« L'assurance », « Santé »…), texte cinétique « petite ligne + grande ligne »,
 * étapes numérotées à côté du téléphone, trio de téléphones en perspective, puces en verre,
 * numéro qui se tape avec l'icône téléphone, logo final. Idéal applis, fintech, assurance, SaaS, services en ligne.
 */
(function () {
  const K = window.KIT;
  const { Z, mk, esc, P, eo, back, lerp, cl, pop, slide, fade, fit, fitBox, letters, typeIn, ev, kick, LIB, ACC, ACC2, PRODUCT, W, H, O } = K;
  const u = Math.min(W, H) / 1080;
  const SIDE = O === 'landscape' || O === 'square';
  const NAVY = '#14163a';
  const SCR = K.S.screens || [];
  const ttl = Z('title');
  // zones : texte (TX) et téléphone (PZ)
  const TX = SIDE ? { x: 70 * u, y: H * .16, w: W * .46, h: H * .68 } : { x: ttl.x, y: ttl.y - 30 * u, w: ttl.w, h: ttl.h + 10 * u };
  const PZ = SIDE ? { x: W * .52, y: 30 * u, w: W * .46, h: H - 60 * u } : { x: 0, y: TX.y + TX.h + 20 * u, w: W, h: (O === 'portrait' ? 1420 : H - 40 * u) - (TX.y + TX.h + 20 * u) };
  const PW = Math.min(PZ.w * .7, PZ.h / 2.1);
  const screen = (i, kind, d = {}) => (SCR.length ? `<img src="${SCR[i % SCR.length]}" style="width:100%;height:100%;object-fit:cover;object-position:top">` : LIB.appScreen(kind, { fs: PW / 18, ...d }));
  const phone3d = (el, i, kind, d, x = null, y = null, w = PW) => {
    const e = mk(el, `<div class="a" style="left:${x ?? PZ.x + (PZ.w - w) / 2}px;top:${y ?? PZ.y + (PZ.h - w * 2.05) / 2}px;perspective:${2400 * u}px"><div class="ph3" style="transform-style:preserve-3d">${LIB.phone(w, screen(i, kind, d))}</div></div>`);
    e.__in = e.firstElementChild; return e;
  };
  const spin = (ph, t, t0, from = -70, rest = -14) => {
    const q = P(t, t0, t0 + .7);
    ph.style.opacity = cl(q * 4);
    ph.__in.style.transform = `rotateY(${lerp(from, rest, eo(q)) + Math.sin(t * 1.3) * 4}deg) rotateX(${5 + Math.sin(t * .9) * 2}deg) translateY(${(1 - eo(q)) * 260 * u + Math.sin(t * 1.7) * 10 * u}px)`;
  };
  // texte cinétique : petite ligne + grande ligne (couleur de marque)
  const kin = (el, small, big, z = TX, align = SIDE ? 'left' : 'center') => {
    const e = mk(el, `<div class="a" style="left:${z.x}px;top:${z.y}px;width:${z.w}px;height:${z.h}px;display:flex;flex-direction:column;justify-content:center;text-align:${align};line-height:1.05">
      ${small ? `<div class="sm" style="font:600 ${58 * u}px Poppins;color:${NAVY};margin-bottom:${10 * u}px">${letters(small)}</div>` : ''}
      <div class="bg" style="font:800 ${120 * u}px Poppins;color:${ACC};letter-spacing:-.02em">${letters(big || '')}</div></div>`);
    const sm = e.querySelector('.sm'), bg = e.querySelector('.bg');
    if (sm) fitBox(sm, z.w, z.h * .32, 24);
    fitBox(bg, z.w, z.h * (sm ? .62 : .95), 30);
    return { e, sm, bg };
  };
  const pill = (text, bg = ACC, fs = 80, maxW = W - 160 * u) => { const n = String(text || '').length || 1; const f = Math.min(fs * u, maxW / (n * .56 + 1.15)); return LIB.pill3d(text, bg, '#fff', f); };
  const tumble = (el, t, t0, dur = .5, rot = -6) => { const q = P(t, t0, t0 + dur); el.style.opacity = cl(q * 4); el.style.transform = `perspective(${1400 * u}px) rotateX(${(1 - back(q)) * 95}deg) rotate(${rot}deg) scale(${lerp(.6, 1, eo(q))})`; return q; };
  const SC = {};

  // Accroche : pilule 3D géante qui bascule + phrase
  SC.ap_hook = {
    build(el, p, T, sh, i) {
      const TALL = O === 'tall';
      const pl = mk(el, `<div class="a" style="left:0;right:0;top:${SIDE ? H * .26 : TALL ? H * .07 : H * .17}px;text-align:center">${pill(p.pill || 'STOP', ACC, SIDE ? 120 : 140)}</div>`);
      const ln = mk(el, `<div class="a" style="left:${80 * u}px;top:${SIDE ? H * .55 : TALL ? H * .285 : H * .31}px;width:${W - 160 * u}px;text-align:center;font:700 ${76 * u}px Poppins;color:${NAVY};line-height:1.12">${letters(p.line || sh.text)}</div>`); fitBox(ln, W - 160 * u, SIDE ? H * .3 : TALL ? H * .19 : H * .28, 26);
      const ph = SIDE ? null : phone3d(el, i, 'dashboard', { title: PRODUCT.name }, (W - PW * (TALL ? .62 : .8)) / 2, TALL ? H * .52 : H * .62, PW * (TALL ? .62 : .8));
      const tp = Math.min(T.at(p.at, 0, .1), sh.start + .6); ev(tp, 'whoosh', .6); ev(tp + .25, 'pop_high', .8);
      return { pl, ln, tp, ph };
    },
    update(t, c, p, T, sh) { tumble(c.pl, t, c.tp, .55, -5); c.pl.style.transform += ` translateY(${Math.sin(t * 2) * 6 * u}px)`; typeIn(c.ln, t, c.tp + .3, .9); if (c.ph) spin(c.ph, t, sh.start + .5, -60, -12); },
  };

  // Téléphone 3D + texte cinétique (plan à tout faire)
  SC.ap_kin = {
    build(el, p, T, sh, i) {
      const k = kin(el, p.small || '', p.big || sh.text);
      const ph = phone3d(el, i, p.screen || 'dashboard', { rows: p.rows, title: p.title });
      const tb = T.at(p.at, 0, .3); ev(sh.start + .1, 'whoosh', .5); ev(tb, 'pop', .7);
      return { k, ph, tb };
    },
    update(t, c, p, T, sh) { spin(c.ph, t, sh.start, -70, SIDE ? -16 : -10); if (c.k.sm) typeIn(c.k.sm, t, sh.start + .1, .5); typeIn(c.k.bg, t, Math.max(sh.start + .3, c.tb - .2), .55, 'drop'); },
  };

  // Pilules empilées (symptômes, catégories)
  SC.ap_pills = {
    build(el, p, T, sh) {
      const items = (p.items || []).slice(0, 4);
      const cols = [ACC, NAVY, '#E11D48', '#0EA5E9'];
      const tt = p.title ? mk(el, `<div class="a" style="left:${80 * u}px;top:${SIDE ? 70 * u : ttl.y}px;width:${W - 160 * u}px;text-align:center;font:800 ${76 * u}px Poppins;color:${NAVY}">${letters(p.title)}</div>`) : null; if (tt) fitBox(tt, W - 160 * u, 200 * u, 26);
      const top0 = SIDE ? H * .26 : H * .25, gap = SIDE ? (H * .64) / Math.max(1, items.length) : 270 * u;
      const ps = items.map((it, i) => { const e = mk(el, `<div class="a" style="left:0;right:0;top:${top0 + i * gap}px;text-align:center"><span style="display:inline-block">${(it.emoji ? `<span class="emo" style="font-size:${90 * u}px;vertical-align:middle;margin-right:${20 * u}px">${esc(it.emoji)}</span>` : '')}</span>${pill(it.text || it, cols[i % cols.length], SIDE ? 64 : 76, W - (it.emoji ? 300 : 180) * u)}</div>`); return e; });
      const ts = T.seq(items, 'at', .05, .8); if (ts.length) ts[0] = Math.min(ts[0], sh.start + .35); ts.forEach((x) => { ev(x, 'whoosh', .45); ev(x + .2, 'pop', .7); });
      return { tt, ps, ts };
    },
    update(t, c, p, T, sh) { if (c.tt) typeIn(c.tt, t, sh.start, .5); c.ps.forEach((e, i) => tumble(e, t, c.ts[i], .5, i % 2 ? 4 : -4)); },
  };

  // Personne (photo importée, sinon avatar) + bulle « Génial, n'est-ce pas ? »
  SC.ap_person = {
    caps: true, build(el, p, T, sh, i) {
      const pw = SIDE ? H * .78 : W * .78, phh = SIDE ? H * .86 : H * .52;
      const ph = LIB.photo(i, SIDE ? W * .42 : pw, phh, 40 * u);
      const x = SIDE ? W * .52 : (W - pw) / 2, y = SIDE ? H * .07 : H * .2;
      const pic = mk(el, `<div class="a" style="left:${x}px;top:${y}px">${ph || `<div style="width:${SIDE ? W * .42 : pw}px;height:${phh}px;border-radius:${40 * u}px;background:radial-gradient(circle at 50% 40%,${ACC}33,${ACC}11);display:flex;align-items:center;justify-content:center"><span class="emo" style="font-size:${Math.min(phh, SIDE ? W * .42 : pw) * .6}px">${esc(p.emoji || '😃')}</span></div>`}</div>`);
      const bb = mk(el, `<div class="a" style="left:${SIDE ? 80 * u : 60 * u}px;top:${SIDE ? H * .38 : y + phh * .62}px">${pill(p.bubble || 'Génial, non ?', NAVY, SIDE ? 70 : 76)}</div>`); fit(bb.firstElementChild, SIDE ? W * .44 : W - 120 * u, 24);
      const tb = T.at(p.at, 0, .45); ev(sh.start + .1, 'whoosh', .5); ev(tb, 'pop_high', .8);
      return { pic, bb, tb };
    },
    update(t, c, p, T, sh) { pop(c.pic, t, sh.start, .55, 120 * u, .85); tumble(c.bb, t, c.tb, .45, -6); },
  };

  // Révélation : icône d'appli / logo qui tourne, nom, accroche
  SC.ap_reveal = {
    build(el, p, T, sh) {
      const s = (SIDE ? 300 : 340) * u;
      const logo = K.S.logo;
      const ic = mk(el, `<div class="a" style="left:${(W - s) / 2}px;top:${SIDE ? H * .14 : H * .26}px;width:${s}px;height:${s}px;border-radius:${s * .24}px;background:${logo ? '#fff' : `linear-gradient(135deg,${ACC},${NAVY})`};box-shadow:0 ${30 * u}px ${60 * u}px ${ACC}55,inset 0 -${10 * u}px 0 rgba(0,0,0,.18);display:flex;align-items:center;justify-content:center;overflow:hidden">${logo ? `<img src="${logo}" style="width:80%;height:80%;object-fit:contain">` : `<span style="font:800 ${s * .5}px Poppins;color:#fff">${esc((p.name || 'A').trim()[0].toUpperCase())}</span>`}</div>`);
      const nm = mk(el, `<div class="a" style="left:${60 * u}px;top:${(SIDE ? H * .14 : H * .26) + s + 50 * u}px;width:${W - 120 * u}px;text-align:center;font:800 ${110 * u}px Poppins;color:${NAVY};line-height:1.02">${letters(p.name || '')}</div>`); fitBox(nm, W - 120 * u, 240 * u, 30);
      const tg = p.tagline ? mk(el, `<div class="a" style="left:0;right:0;top:${(SIDE ? H * .14 : H * .26) + s + (SIDE ? 220 : 300) * u}px;text-align:center">${pill(p.tagline, ACC, 56)}</div>`) : null; if (tg) fit(tg.firstElementChild, W - 160 * u, 22);
      const tr = T.at(p.at, 0, .15); ev(tr - .15, 'whoosh_deep', .7); ev(tr + .1, 'impact', .8); ev(tr + .25, 'shimmer', .7);
      return { ic, nm, tg, tr };
    },
    update(t, c, p, T, sh) {
      const q = P(t, c.tr - .2, c.tr + .4); c.ic.style.opacity = cl(q * 4); c.ic.style.transform = `perspective(${1200 * u}px) rotateY(${(1 - eo(q)) * 360}deg) scale(${lerp(.3, 1, back(q))})`;
      typeIn(c.nm, t, c.tr + .15, .5, 'drop'); if (c.tg) tumble(c.tg, t, c.tr + .7, .45, -4); kick(t, c.tr + .1, 10);
    },
  };

  // Étapes numérotées à côté du téléphone (« Comment ça marche ? »)
  SC.ap_steps = {
    build(el, p, T, sh, i) {
      const steps = (p.steps || []).slice(0, 3);
      const hd = mk(el, `<div class="a" style="left:0;right:0;top:${SIDE ? 40 * u : ttl.y - 30 * u}px;text-align:center">${pill(p.title || 'Comment ça marche ?', NAVY, SIDE ? 62 : 70)}</div>`); fit(hd.firstElementChild, W - 160 * u, 22);
      const pw = SIDE ? PW * .9 : PW * .95;
      const px = SIDE ? W * .58 : 50 * u, py = SIDE ? H * .16 : H * .2;
      const kinds = ['form', 'dashboard', 'success'];
      const phs = steps.map((s, k) => phone3d(el, i + k, kinds[k % 3], { title: PRODUCT.name, text: s.text, button: 'Valider' }, px, py, pw));
      const lz = SIDE ? { x: 70 * u, y: H * .2, w: W * .48, h: H * .66 } : { x: px + pw + 40 * u, y: py + 40 * u, w: W - (px + pw + 40 * u) - 50 * u, h: pw * 2.05 - 80 * u };
      const rows = steps.map((s, k) => { const e = mk(el, `<div class="a" style="left:${lz.x}px;top:${lz.y + k * lz.h / Math.max(1, steps.length)}px;width:${lz.w}px;display:flex;gap:${20 * u}px;align-items:flex-start"><div style="flex:none;width:${84 * u}px;height:${84 * u}px;border-radius:50%;background:${ACC};color:#fff;font:800 ${48 * u}px Poppins;display:flex;align-items:center;justify-content:center">${k + 1}</div><div class="tx" style="font:700 ${54 * u}px Poppins;color:${NAVY};line-height:1.1">${letters(s.text || s)}</div></div>`); fitBox(e.querySelector('.tx'), lz.w - 100 * u, lz.h / Math.max(1, steps.length) - 20 * u, 22); return e; });
      const hand = mk(el, `<div class="a emo" style="left:${px + pw * .5}px;top:${py + pw * 1.5}px;font-size:${120 * u}px">👆</div>`);
      const ts = T.seq(steps, 'at', .12, .78); ts.forEach((x) => { ev(x, 'whoosh', .4); ev(x + .25, 'click', .8); });
      return { hd, phs, rows, hand, ts };
    },
    update(t, c, p, T, sh) {
      tumble(c.hd, t, sh.start, .45, -3);
      c.phs.forEach((ph, k) => { const a = c.ts[k] - .25, b = (c.ts[k + 1] ?? 1e9) - .25; const on = t >= a && t < b + .3; ph.style.display = on ? '' : 'none'; if (on) { spin(ph, t, a, k ? 70 : -70, -10); if (t > b) ph.style.opacity = 1 - P(t, b, b + .3); } });
      c.rows.forEach((r, k) => slide(r, t, c.ts[k], 260 * u, 0, .45));
      const k = c.ts.findIndex((x, j) => t >= x && t < (c.ts[j + 1] ?? 1e9)); const tap = k >= 0 ? c.ts[k] + .25 : -1;
      c.hand.style.opacity = k >= 0 ? 1 : 0; c.hand.style.transform = `scale(${t > tap && t < tap + .15 ? .82 : 1}) translateY(${Math.sin(t * 3) * 8 * u}px)`;
    },
  };

  // Trio de téléphones en perspective (« en un coup d'œil »)
  SC.ap_trio = {
    caps: true, build(el, p, T, sh, i) {
      const pw = SIDE ? PW * .78 : PW * .92;
      const kinds = ['list', 'dashboard', 'success'];
      const cx = W / 2, cy = SIDE ? H * .5 : H * .5;
      const phs = [0, 1, 2].map((k) => phone3d(el, i + k, kinds[k], { title: PRODUCT.name, text: p.title || '' }, cx - pw / 2 + (k - 1) * pw * (SIDE ? 1.25 : 1.05), cy - pw * 1.02 + (k === 1 ? -40 * u : 30 * u), pw));
      const tt = p.title ? mk(el, `<div class="a" style="left:${80 * u}px;top:${SIDE ? 30 * u : ttl.y - 20 * u}px;width:${W - 160 * u}px;text-align:center;font:800 ${(SIDE ? 90 : 120) * u}px Poppins;color:${ACC};line-height:1.02">${letters(p.title)}</div>`) : null; if (tt) fitBox(tt, W - 160 * u, (SIDE ? 120 : 260) * u, 26);
      ev(sh.start + .1, 'whoosh_deep', .6); [0, 1, 2].forEach((k) => ev(sh.start + .25 + k * .18, 'pop', .5));
      return { phs, tt };
    },
    update(t, c, p, T, sh) {
      if (c.tt) typeIn(c.tt, t, sh.start, .5);
      c.phs.forEach((ph, k) => { const q = P(t, sh.start + .1 + k * .18, sh.start + .7 + k * .18); ph.style.opacity = cl(q * 4); ph.__in.style.transform = `rotateY(${(k - 1) * -24 + (1 - eo(q)) * 60}deg) rotateX(8deg) translateY(${(1 - eo(q)) * 400 * u + Math.sin(t * 1.4 + k) * 10 * u}px)`; });
    },
  };

  // Puces en verre qui flottent autour du téléphone (bénéfices)
  SC.ap_chips = {
    build(el, p, T, sh, i) {
      const items = (p.items || []).slice(0, 4);
      const ph = phone3d(el, i, 'dashboard', { title: PRODUCT.name });
      const phx = PZ.x + (PZ.w - PW) / 2, phy = PZ.y + (PZ.h - PW * 2.05) / 2;
      const tt = p.title ? mk(el, `<div class="a" style="left:${TX.x}px;top:${SIDE ? H * .1 : ttl.y}px;width:${TX.w}px;text-align:${SIDE ? 'left' : 'center'};font:800 ${92 * u}px Poppins;color:${NAVY};line-height:1.05">${letters(p.title)}</div>`) : null; if (tt) fitBox(tt, TX.w, SIDE ? H * .3 : TX.h * .9, 26);
      const chips = items.map((it, k) => {
        const side = k % 2 ? 1 : -1;
        const cw = SIDE ? W * .46 : W - 120 * u;
        const x = SIDE ? 70 * u : 60 * u + side * 10 * u, y = SIDE ? H * .36 + k * 150 * u : phy + 160 * u + k * 190 * u;
        const e = mk(el, `<div class="a" style="left:${x}px;top:${y}px;width:${cw}px;box-sizing:border-box;padding:${18 * u}px ${30 * u}px;border-radius:${26 * u}px;background:rgba(255,255,255,.72);backdrop-filter:blur(10px);border:${2 * u}px solid rgba(255,255,255,.9);box-shadow:0 ${16 * u}px ${40 * u}px rgba(20,22,58,.18);display:flex;gap:${16 * u}px;align-items:center;font:700 ${54 * u}px Poppins;color:${NAVY};line-height:1.1"><span class="emo" style="font-size:${66 * u}px">${esc(it.emoji || '✅')}</span><span class="tx">${esc(it.text || it)}</span></div>`);
        fitBox(e.querySelector('.tx'), cw - 150 * u, 130 * u, 22); return e;
      });
      const ts = T.seq(items, 'at', .1, .8); ts.forEach((x) => ev(x, 'pop_high', .7));
      return { ph, tt, chips, ts, phx };
    },
    update(t, c, p, T, sh) {
      spin(c.ph, t, sh.start, 60, SIDE ? -16 : 12); if (c.tt) typeIn(c.tt, t, sh.start, .5);
      c.chips.forEach((e, k) => { const q = P(t, c.ts[k] - .1, c.ts[k] + .35); e.style.opacity = cl(q * 3); e.style.transform = `translate(${(1 - back(q)) * (k % 2 ? 200 : -200) * u}px,${Math.sin(t * 1.6 + k) * 8 * u}px) scale(${lerp(.7, 1, eo(q))}) rotate(${k % 2 ? 1.5 : -1.5}deg)`; });
    },
  };

  // Prix : téléphone + grand prix 3D
  SC.ap_price = {
    build(el, p, T, sh, i) {
      const ph = phone3d(el, i, 'success', { title: PRODUCT.name, text: p.label || '' }, SIDE ? null : W * .5, SIDE ? null : H * .36, SIDE ? PW : PW * .8);
      const lab = mk(el, `<div class="a" style="left:${SIDE ? TX.x : 60 * u}px;top:${SIDE ? H * .26 : ttl.y}px;width:${SIDE ? TX.w : W - 120 * u}px;text-align:${SIDE ? 'left' : 'center'};font:700 ${64 * u}px Poppins;color:${NAVY}">${letters(p.label || 'Seulement')}</div>`); fit(lab, SIDE ? TX.w : W - 120 * u, 24);
      const pr = mk(el, `<div class="a" style="left:${SIDE ? TX.x : 60 * u}px;top:${SIDE ? H * .38 : ttl.y + 110 * u}px;width:${SIDE ? TX.w : W - 120 * u}px;text-align:${SIDE ? 'left' : 'center'}">${LIB.price3d(p.big || '', 170 * u, ACC, NAVY)}</div>`); fit(pr.firstElementChild, SIDE ? TX.w : W - 120 * u, 40);
      const tp = T.at(p.at, 0, .3); ev(tp, 'impact', .9); ev(tp + .1, 'coin', .8);
      return { ph, lab, pr, tp };
    },
    update(t, c, p, T, sh) { spin(c.ph, t, sh.start, -60, -14); typeIn(c.lab, t, sh.start + .1, .4); const q = P(t, c.tp - .15, c.tp + .35); c.pr.style.opacity = q > 0 ? 1 : 0; c.pr.style.transform = `perspective(${1200 * u}px) rotateX(${(1 - eo(q)) * 90}deg) scale(${lerp(1.3, 1, eo(q))})`; kick(t, c.tp + .1, 12); },
  };

  // Appel à l'action : téléphone, bouton, numéro qui se tape, logo
  SC.ap_cta = {
    build(el, p, T, sh, i) {
      const ph = phone3d(el, i, 'success', { title: PRODUCT.name, text: p.tagline || 'C\'est parti !' }, SIDE ? null : (W - PW * .8) / 2, SIDE ? null : ttl.y + 190 * u, SIDE ? PW : PW * .8);
      const z = SIDE ? { x: TX.x, w: TX.w } : { x: 90 * u, w: W - 180 * u };
      const top = SIDE ? H * .2 : ttl.y + 190 * u + PW * .8 * 2.05 - 60 * u;
      const tg = mk(el, `<div class="a" style="left:${SIDE ? TX.x : 60 * u}px;top:${SIDE ? top : ttl.y - 10 * u}px;width:${SIDE ? TX.w : W - 120 * u}px;text-align:${SIDE ? 'left' : 'center'};font:800 ${78 * u}px Poppins;color:${NAVY};line-height:1.05">${letters(p.tagline || PRODUCT.name || '')}</div>`); fitBox(tg, SIDE ? TX.w : W - 120 * u, 220 * u, 24);
      const btn = mk(el, `<div class="a" style="left:${z.x}px;top:${SIDE ? top + 260 * u : top + 40 * u}px;width:${z.w}px;padding:${26 * u}px ${20 * u}px;border-radius:${60 * u}px;background:${ACC};color:#fff;font:800 ${(SIDE ? 50 : 62) * u}px Poppins;text-align:center;box-shadow:0 ${12 * u}px 0 ${NAVY}55">${esc(p.button || 'Cliquez sur le lien')}</div>`); fitBox(btn, z.w, 200 * u, 22);
      const pn = p.phone ? mk(el, `<div class="a" style="left:${z.x}px;top:${SIDE ? top + 480 * u : top + 190 * u}px;width:${z.w}px;display:flex;gap:${16 * u}px;align-items:center;justify-content:${SIDE ? 'flex-start' : 'center'}">${LIB.icon('phone', 70 * u, ACC)}<span class="tx" style="font:800 ${(SIDE ? 62 : 76) * u}px Poppins;color:${NAVY};white-space:nowrap">${letters(p.phone)}</span></div>`) : null;
      if (pn) fit(pn.querySelector('.tx'), z.w - 90 * u, 22);
      const tc = T.at(p.click_at, 0, .25), tp = T.at(p.call_at, 0, .55);
      ev(tc, 'click', .9); if (pn) { ev(tp, 'ping', .7); ev(tp + .2, 'tick', .4); }
      return { ph, tg, btn, pn, tc, tp };
    },
    update(t, c, p, T, sh) {
      spin(c.ph, t, sh.start, 70, 14); typeIn(c.tg, t, sh.start + .05, .5); pop(c.btn, t, sh.start + .25, .45, 60 * u, .7);
      c.btn.style.transform += ` scale(${t > c.tc && t < c.tc + .16 ? .93 : 1})`;
      if (c.pn) { fade(c.pn, t, c.tp - .2, .2); typeIn(c.pn, t, c.tp, 1.3, 'drop'); }
    },
  };

  // Repli : texte cinétique seul
  SC.ap_text = {
    build(el, p, T, sh) {
      const lines = (p.lines && p.lines.length ? p.lines : [sh.text]).slice(0, 3);
      const z = SIDE ? { x: 120 * u, y: H * .15, w: W - 240 * u, h: H * .7 } : { x: 70 * u, y: H * .22, w: W - 140 * u, h: H * .5 };
      const k = kin(el, lines.length > 1 ? lines.slice(0, -1).join(' ') : '', lines[lines.length - 1], z, 'center');
      const ts = T.lineStarts(lines); ev(ts[ts.length - 1], 'pop', .6);
      return { k, ts };
    },
    update(t, c, p, T, sh) { if (c.k.sm) typeIn(c.k.sm, t, c.ts[0] - .05, .5); typeIn(c.k.bg, t, c.ts[c.ts.length - 1] - .05, .5, 'drop'); },
  };

  document.getElementById('bg').innerHTML = `<div style="position:absolute;inset:0;background:radial-gradient(ellipse 110% 55% at 50% 112%,${ACC}55 0,${ACC}18 45%,transparent 70%),radial-gradient(ellipse 80% 60% at 50% 40%,#fff 0,#f5f6fb 60%,#e7e9f3 100%)"></div>`;
  K.register({
    name: 'app', SCENES: SC, fallback: 'ap_text', grain: 0, trDur: .38,
    transition(i, b, nx) { if (nx.type === 'ap_reveal') return 'zoom'; if (nx.type === 'ap_cta') return 'slideUp'; return ['whip', 'slide', 'zoomOut', 'slideUp'][i % 4]; },
    trSfx: { whip: 'whoosh', slide: 'whoosh', zoom: 'whoosh_deep', zoomOut: 'whoosh_rev', slideUp: 'whoosh' },
  });
})();
