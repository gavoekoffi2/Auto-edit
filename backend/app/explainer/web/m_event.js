/*
 * Mode « Événement » — inspiré de la pub d'un concours de talents (« EYA Vacances »).
 * Dégradé orange vif avec structures de scène (truss) et projecteurs, photos assombries derrière le texte,
 * texte cinétique blanc avec MOTS ENCADRÉS (boîte marine ou orange), pilule « À la clé ? » + montant géant,
 * pilule de date, chiffres qui défilent, affiche finale. Idéal événements, concours, inscriptions, soirées,
 * formations en présentiel, ouvertures de boutique.
 */
(function () {
  const K = window.KIT;
  const { Z, mk, esc, P, eo, back, lerp, cl, pop, slide, fade, fit, fitBox, letters, typeIn, ev, kick, flash, LIB, ACC, ACC2, PRODUCT, W, H, O } = K;
  const u = Math.min(W, H) / 1080;
  const SIDE = O === 'landscape' || O === 'square';
  const OR1 = '#FF7A00', OR2 = '#FF4D00', NAVY = '#1F2547';
  const SC = {};
  const truss = (x, w) => `<svg class="a" style="left:${x}px;top:0;opacity:.18" width="${w}" height="${H}" viewBox="0 0 60 600" preserveAspectRatio="none"><g fill="none" stroke="#fff" stroke-width="2.5"><path d="M5 0V600M55 0V600"/>${[...Array(20)].map((_, k) => `<path d="M5 ${k * 30}L55 ${k * 30 + 30}M55 ${k * 30}L5 ${k * 30 + 30}"/>`).join('')}</g></svg>`;
  const orange = (el) => { el.style.background = `radial-gradient(ellipse 70% 60% at 50% 45%,#FFB347 0,${OR1} 40%,${OR2} 80%,#C93A00 100%)`; el.insertAdjacentHTML('afterbegin', truss(-10 * u, 90 * u) + truss(W - 80 * u, 90 * u) + `<div class="a" style="left:0;right:0;top:0;height:${H * .4}px;background:radial-gradient(ellipse 30% 100% at 30% 0,rgba(255,255,255,.35),transparent),radial-gradient(ellipse 30% 100% at 70% 0,rgba(255,255,255,.3),transparent)"></div>`); };
  const dark = (el, i) => {
    const ph = LIB.photo(i, W, H, 0);
    el.insertAdjacentHTML('afterbegin', ph ? `<div class="a bgph" style="left:0;top:0">${ph}</div><div class="a" style="inset:0;background:linear-gradient(180deg,rgba(10,10,20,.55),rgba(10,10,20,.7))"></div>` : '');
    if (!ph) orange(el);
    return !!ph;
  };
  // texte avec mots encadrés : « Alors ! c'est le moment de montrer [ton talent] »
  const boxed = (el, text, hi, z, fs = 96) => {
    const H_ = String(hi || '').toLowerCase();
    let parts = [String(text)], b = '';
    const k = H_ ? String(text).toLowerCase().lastIndexOf(H_) : -1;
    if (k >= 0) { parts = [text.slice(0, k).trim(), text.slice(k + H_.length).trim()]; b = text.slice(k, k + H_.length); }
    const e = mk(el, `<div class="a" style="left:${z.x}px;top:${z.y}px;width:${z.w}px;height:${z.h}px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;font:800 ${fs * u}px Poppins;color:#fff;line-height:1.08;text-shadow:0 ${4 * u}px ${14 * u}px rgba(0,0,0,.25)">
      ${parts[0] ? `<div class="p0">${letters(parts[0])}</div>` : ''}
      ${b ? `<div class="bx" style="display:inline-block;margin:${14 * u}px 0;padding:${10 * u}px ${34 * u}px;border-radius:${22 * u}px;background:${NAVY};font-size:1.12em;transform:rotate(-2deg);box-shadow:0 ${10 * u}px 0 rgba(0,0,0,.25)">${letters(b)}</div>` : ''}
      ${parts[1] ? `<div class="p1">${letters(parts[1])}</div>` : ''}</div>`);
    fitBox(e, z.w, z.h, 26);
    return { e, p0: e.querySelector('.p0'), bx: e.querySelector('.bx'), p1: e.querySelector('.p1') };
  };
  const boxedIn = (c, t, t0, tb) => { if (c.p0) typeIn(c.p0, t, t0, .5); if (c.bx) { const q = P(t, tb - .1, tb + .3); c.bx.style.opacity = q > 0 ? 1 : 0; c.bx.style.transform = `rotate(-2deg) scale(${lerp(.3, 1, back(q))})`; } if (c.p1) typeIn(c.p1, t, (c.bx ? tb + .2 : t0 + .4), .5); };
  const TZ = SIDE ? { x: 160 * u, y: H * .18, w: W - 320 * u, h: H * .64 } : { x: 80 * u, y: H * .22, w: W - 160 * u, h: H * .5 };

  // Texte encadré sur fond orange (accroche, bascule, repli)
  SC.ev_title = {
    build(el, p, T, sh) {
      orange(el);
      const c = boxed(el, p.line || sh.text, p.hi, TZ, SIDE ? 100 : 104);
      const tb = T.at(p.hi ? String(p.hi).split(/\s+/)[0] : null, 0, .5); ev(sh.start + .05, 'blip', .5); ev(tb, 'pop_high', .8);
      return { c, tb };
    },
    update(t, c, p, T, sh) { boxedIn(c.c, t, sh.start + .05, c.tb); },
  };

  // Photo assombrie + texte encadré orange (symptômes, preuve, ambiance)
  SC.ev_photo = {
    build(el, p, T, sh, i) {
      const has = dark(el, i);
      const items = (p.items || []).slice(0, 3);
      const text = p.line || (items.length ? items.map((x) => x.text || x).join(' · ') : sh.text);
      const c = boxed(el, text, p.hi || (items[0] && (items[0].text || items[0])), TZ, SIDE ? 92 : 96);
      if (c.bx) c.bx.style.background = OR1;
      const tb = T.at(p.at || (items[0] && items[0].at), 0, .4); ev(sh.start + .05, 'whoosh', .5); ev(tb, 'impact', .7);
      return { c, tb, ph: el.querySelector('.bgph'), has };
    },
    update(t, c, p, T, sh) { boxedIn(c.c, t, sh.start + .1, c.tb); if (c.ph) c.ph.style.transform = `scale(${1.05 + (t - sh.start) * .02})`; },
  };

  // Liste : étiquettes encadrées qui s'empilent (programme, catégories, avantages)
  SC.ev_list = {
    build(el, p, T, sh) {
      orange(el);
      const items = (p.items || []).slice(0, 4);
      const tt = p.title ? mk(el, `<div class="a" style="left:${80 * u}px;top:${SIDE ? 60 * u : Z('title').y}px;width:${W - 160 * u}px;text-align:center;font:800 ${84 * u}px Poppins;color:#fff">${letters(p.title)}</div>`) : null; if (tt) fitBox(tt, W - 160 * u, 200 * u, 26);
      const top0 = SIDE ? H * .26 : H * .28, gap = SIDE ? H * .6 / Math.max(1, items.length) : 260 * u;
      const rows = items.map((it, k) => { const e = mk(el, `<div class="a" style="left:0;right:0;top:${top0 + k * gap}px;text-align:center"><span class="bx" style="display:inline-block;max-width:${W - 200 * u}px;padding:${16 * u}px ${36 * u}px;border-radius:${24 * u}px;background:${k % 2 ? '#fff' : NAVY};color:${k % 2 ? OR2 : '#fff'};font:800 ${70 * u}px Poppins;line-height:1.1;transform:rotate(${k % 2 ? 2 : -2}deg);box-shadow:0 ${10 * u}px 0 rgba(0,0,0,.2)">${it.emoji ? `<span class="emo">${esc(it.emoji)}</span> ` : ''}${esc(it.text || it)}</span></div>`); fitBox(e.querySelector('.bx'), W - 200 * u, gap - 30 * u, 24); return e; });
      const ts = T.seq(items, 'at', .05, .8); ts.forEach((x) => { ev(x, 'whoosh', .4); ev(x + .15, 'pop', .7); });
      return { tt, rows, ts };
    },
    update(t, c, p, T, sh) { if (c.tt) typeIn(c.tt, t, sh.start, .5); c.rows.forEach((r, k) => slide(r, t, c.ts[k] - .1, (k % 2 ? 1 : -1) * W * .8, 0, .45)); },
  };

  // Coup de poing : mot géant blanc, flash
  SC.ev_punch = {
    build(el, p, T, sh, i) {
      dark(el, i + 1);
      const tt = mk(el, `<div class="a" style="left:${80 * u}px;top:${SIDE ? H * .3 : H * .36}px;width:${W - 160 * u}px;text-align:center;font:400 ${220 * u}px Anton;color:#fff;text-transform:uppercase;line-height:.95">${letters(p.text || sh.text)}</div>`); fitBox(tt, W - 160 * u, SIDE ? H * .4 : H * .3, 40);
      const tb = T.at(p.at, 0, .2); ev(tb, 'impact_big', 1);
      return { tt, tb };
    },
    update(t, c, p, T, sh) { const q = P(t, c.tb - .1, c.tb + .25); c.tt.style.opacity = cl(q * 3); c.tt.style.transform = `scale(${lerp(2.2, 1, eo(q))})`; kick(t, c.tb + .05, 22); flash(t, c.tb, .35); },
  };

  // Révélation : « Et cette année » + nom dans une boîte marine + logo
  SC.ev_reveal = {
    build(el, p, T, sh) {
      orange(el);
      const pre = mk(el, `<div class="a" style="left:${80 * u}px;top:${SIDE ? H * .2 : H * .28}px;width:${W - 160 * u}px;text-align:center;font:800 ${92 * u}px Poppins;color:#fff">${letters(p.pre || 'Voici')}</div>`); fit(pre, W - 160 * u, 26);
      const logo = K.S.logo;
      const nm = mk(el, `<div class="a" style="left:0;right:0;top:${SIDE ? H * .36 : H * .38}px;text-align:center"><div class="bx" style="display:inline-block;max-width:${W - 160 * u}px;padding:${26 * u}px ${50 * u}px;border-radius:${30 * u}px;background:${NAVY};color:#fff;font:800 ${120 * u}px Poppins;line-height:1;transform:rotate(-3deg);box-shadow:0 ${14 * u}px 0 rgba(0,0,0,.25)">${letters(p.name || PRODUCT.name || '')}</div></div>`); fitBox(nm.querySelector('.bx'), W - 160 * u, SIDE ? H * .3 : H * .2, 30);
      const lg = logo ? mk(el, `<div class="a" style="left:${(W - 320 * u) / 2}px;top:${SIDE ? H * .7 : H * .62}px;width:${320 * u}px;height:${220 * u}px;display:flex;align-items:center;justify-content:center"><img src="${logo}" style="max-width:100%;max-height:100%;filter:drop-shadow(0 10px 20px rgba(0,0,0,.3))"></div>`) : null;
      const tg = !logo && p.tagline ? mk(el, `<div class="a" style="left:${80 * u}px;top:${SIDE ? H * .72 : H * .62}px;width:${W - 160 * u}px;text-align:center;font:italic 700 ${64 * u}px Poppins;color:#fff">${letters(p.tagline)}</div>`) : null; if (tg) fitBox(tg, W - 160 * u, 200 * u, 24);
      const tr = T.at(p.at, 0, .2); ev(tr - .1, 'whoosh_deep', .7); ev(tr + .1, 'impact_big', .9); ev(tr + .3, 'shimmer', .7);
      return { pre, nm, lg, tg, tr };
    },
    update(t, c, p, T, sh) { typeIn(c.pre, t, sh.start + .05, .4); const q = P(t, c.tr - .1, c.tr + .35); c.nm.style.opacity = q > 0 ? 1 : 0; c.nm.style.transform = `scale(${lerp(.2, 1, back(q))})`; if (c.lg) pop(c.lg, t, c.tr + .4, .45, 80 * u, .5); if (c.tg) typeIn(c.tg, t, c.tr + .5, .6); kick(t, c.tr + .1, 16); },
  };

  // « À la clé ? » + montant géant (prix, gain, remise)
  SC.ev_amount = {
    build(el, p, T, sh) {
      orange(el);
      const pl = mk(el, `<div class="a" style="left:0;right:0;top:${SIDE ? H * .18 : H * .28}px;text-align:center"><span style="display:inline-block;padding:${14 * u}px ${40 * u}px;border-radius:${50 * u}px;background:#fff;color:${OR2};font:800 ${60 * u}px Poppins;box-shadow:0 ${8 * u}px 0 rgba(0,0,0,.18)">${esc(p.label || 'À la clé ?')}</span></div>`);
      const am = mk(el, `<div class="a" style="left:${60 * u}px;top:${SIDE ? H * .36 : H * .37}px;width:${W - 120 * u}px;text-align:center;font:800 ${210 * u}px Poppins;color:#fff;letter-spacing:-.03em;line-height:1;text-shadow:0 ${8 * u}px 0 rgba(0,0,0,.15)">${esc(p.big || '')}</div>`); fit(am, W - 120 * u, 50);
      const sub = p.sub ? mk(el, `<div class="a" style="left:0;right:0;top:${SIDE ? H * .64 : H * .52}px;text-align:center;font:800 ${90 * u}px Poppins;color:#fff">${letters(p.sub)}</div>`) : null;
      const cf = mk(el, LIB.confetti(40, ['#fff', NAVY, '#FFD60A']));
      const tp = T.at(p.at, 0, .35); ev(sh.start + .05, 'pop', .6); ev(tp, 'impact_big', 1); ev(tp + .1, 'coin', .9);
      return { pl, am, sub, cf, tp, num: String(p.big || '') };
    },
    update(t, c, p, T, sh) {
      pop(c.pl, t, sh.start + .05, .4, 40 * u, .6);
      const q = P(t, c.tp - .35, c.tp); // chiffres qui défilent jusqu'au montant
      const m = c.num.match(/[\d\s.,]+/);
      if (m && q < 1) { const target = parseInt(m[0].replace(/\D/g, ''), 10) || 0; const v = Math.round(target * eo(q)); c.am.textContent = c.num.replace(m[0].trim(), v.toLocaleString('fr-FR').replace(/ | /g, ' ')); } else c.am.textContent = c.num;
      c.am.style.opacity = t >= c.tp - .35 ? 1 : 0; c.am.style.transform = `scale(${lerp(1.3, 1, eo(P(t, c.tp, c.tp + .25)))})`;
      if (c.sub) typeIn(c.sub, t, c.tp + .25, .4); kick(t, c.tp + .05, 20);
      [...c.cf.children].forEach((d, k) => { const y = ((t - c.tp) * (160 + (k % 5) * 50)) % H; d.style.transform = `translateY(${y}px) rotate(${t * 220 + k * 30}deg)`; d.style.opacity = t > c.tp ? 1 : 0; });
    },
  };

  // Date / urgence : pilule calendrier + texte
  SC.ev_date = {
    build(el, p, T, sh) {
      orange(el);
      const cal = mk(el, `<div class="a" style="left:${(W - 300 * u) / 2}px;top:${SIDE ? H * .14 : H * .24}px">${LIB.icon('calendar', 300 * u, '#fff')}</div>`);
      const big = mk(el, `<div class="a" style="left:0;right:0;top:${SIDE ? H * .5 : H * .44}px;text-align:center"><span class="bx" style="display:inline-block;padding:${16 * u}px ${44 * u}px;border-radius:${26 * u}px;background:${NAVY};color:#fff;font:800 ${110 * u}px Poppins">${esc(p.big || '')}</span></div>`); fit(big.querySelector('.bx'), W - 160 * u, 30);
      const st = p.stamp ? mk(el, `<div class="a" style="left:${80 * u}px;top:${SIDE ? H * .72 : H * .56}px;width:${W - 160 * u}px;text-align:center;font:800 ${70 * u}px Poppins;color:#fff">${letters(p.stamp)}</div>`) : null; if (st) fitBox(st, W - 160 * u, 200 * u, 24);
      const tb = T.at(p.at, 0, .3); ev(sh.start + .1, 'pop', .6); ev(tb, 'stamp', .9); ev(tb + .3, 'tick', .5);
      return { cal, big, st, tb };
    },
    update(t, c, p, T, sh) { pop(c.cal, t, sh.start + .05, .45, 80 * u, .5); c.cal.style.transform += ` rotate(${Math.sin(t * 3) * 4}deg)`; slide(c.big, t, c.tb - .15, 0, 200 * u, .4); if (c.st) typeIn(c.st, t, c.tb + .2, .5); },
  };

  // Affiche finale : nom, bouton, numéro qui se tape
  SC.ev_poster = {
    build(el, p, T, sh, i) {
      orange(el);
      const ph = LIB.photo(i + 2, SIDE ? W * .32 : W * .7, SIDE ? H * .7 : H * .3, 30 * u);
      const pic = ph ? mk(el, `<div class="a" style="left:${SIDE ? W * .62 : W * .15}px;top:${SIDE ? H * .15 : H * .1}px;box-shadow:0 ${20 * u}px ${40 * u}px rgba(0,0,0,.3);border-radius:${30 * u}px;transform:rotate(3deg)">${ph}</div>`) : null;
      const zx = SIDE ? 100 * u : 80 * u, zw = SIDE ? W * .5 : W - 160 * u, y0 = SIDE ? H * .12 : (ph ? H * .44 : H * .2);
      const nm = mk(el, `<div class="a" style="left:${zx}px;top:${y0}px;width:${zw}px;text-align:${SIDE ? 'left' : 'center'}"><span class="bx" style="display:inline-block;max-width:${zw}px;padding:${16 * u}px ${36 * u}px;border-radius:${26 * u}px;background:${NAVY};color:#fff;font:800 ${96 * u}px Poppins;line-height:1.02">${letters(p.tagline || PRODUCT.name || '')}</span></div>`); fitBox(nm.querySelector('.bx'), zw, SIDE ? H * .3 : H * .17, 26);
      const btn = mk(el, `<div class="a" style="left:${zx}px;top:${y0 + (SIDE ? H * .36 : H * .2)}px;width:${zw}px;box-sizing:border-box;padding:${26 * u}px;border-radius:${60 * u}px;background:#fff;color:${OR2};font:800 ${60 * u}px Poppins;text-align:center;box-shadow:0 ${10 * u}px 0 rgba(0,0,0,.2)">${esc(p.button || 'Inscris-toi via le lien')}</div>`); fitBox(btn, zw, 200 * u, 22);
      const pn = p.phone ? mk(el, `<div class="a" style="left:${zx}px;top:${y0 + (SIDE ? H * .56 : H * .32)}px;width:${zw}px;display:flex;gap:${18 * u}px;align-items:center;justify-content:${SIDE ? 'flex-start' : 'center'}">${LIB.icon('phone', 80 * u, '#fff')}<span class="tx" style="font:800 ${88 * u}px Poppins;color:#fff;white-space:nowrap">${letters(p.phone)}</span></div>`) : null;
      if (pn) fit(pn.querySelector('.tx'), zw - 110 * u, 24);
      const tc = T.at(p.click_at, 0, .25), tp = T.at(p.call_at, 0, .55);
      ev(tc, 'click', .9); if (pn) ev(tp, 'ping', .7);
      return { pic, nm, btn, pn, tc, tp };
    },
    update(t, c, p, T, sh) {
      if (c.pic) pop(c.pic, t, sh.start, .55, 120 * u, .8);
      const q = P(t, sh.start + .1, sh.start + .45); c.nm.style.opacity = cl(q * 3); c.nm.style.transform = `scale(${lerp(.4, 1, back(q))})`;
      pop(c.btn, t, sh.start + .35, .45, 60 * u, .7); c.btn.style.transform += ` scale(${t > c.tc && t < c.tc + .16 ? .93 : 1})`;
      if (c.pn) { fade(c.pn, t, c.tp - .2, .2); typeIn(c.pn, t, c.tp, 1.3, 'drop'); }
    },
  };

  K.register({
    name: 'event', SCENES: SC, fallback: 'ev_title', grain: .04, trDur: .34,
    transition(i, b, nx) { if (nx.type === 'ev_punch') return 'cut'; if (nx.type === 'ev_amount' || nx.type === 'ev_reveal') return 'zoom'; return ['wipe', 'slide', 'zoomOut', 'whip'][i % 4]; },
    trSfx: { wipe: 'whoosh', slide: 'whoosh', zoom: 'whoosh_deep', zoomOut: 'whoosh_rev', whip: 'whoosh' },
  });
  document.getElementById('bg').innerHTML = `<div style="position:absolute;inset:0;background:${OR1}"></div>`;
})();
