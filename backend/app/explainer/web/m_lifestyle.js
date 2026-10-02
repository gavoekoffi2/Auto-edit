/*
 * Mode « Lifestyle offre » — inspiré des pubs d'abonnements (musique, films) et de promos.
 * Monde plein écran à la couleur de marque, personne heureuse (photo importée ou grand avatar),
 * téléphone couché qui sort du cadre, gros titres condensés, lignes italiques, et surtout :
 * le fond CHANGE DE COULEUR à chaque offre / avantage. Prix 3D « par mois ». Idéal abonnements,
 * e-commerce, promotions, offres groupées, mode, restauration.
 */
(function () {
  const K = window.KIT;
  const { Z, mk, esc, P, eo, back, lerp, cl, pop, slide, fade, fit, fitBox, letters, typeIn, ev, kick, flash, LIB, ACC, ACC2, PRODUCT, W, H, O } = K;
  const u = Math.min(W, H) / 1080;
  const SIDE = O === 'landscape' || O === 'square';
  const hex = (c) => { const m = String(c).replace('#', ''); const v = m.length === 3 ? m.split('').map((x) => x + x).join('') : m; return [0, 2, 4].map((i) => parseInt(v.slice(i, i + 2), 16) || 0); };
  const light = (c) => { const [r, g, b] = hex(c); return (r * 299 + g * 587 + b * 114) / 1000 > 165; };
  const shade = (c, f) => { const [r, g, b] = hex(c); const s = (x) => Math.round(cl(x * f, 0, 255)).toString(16).padStart(2, '0'); return `#${s(r)}${s(g)}${s(b)}`; };
  const PAL = [ACC, '#E50914', '#1DB954', '#2563EB', '#F97316', '#111827'];
  const world = (el, c) => { el.style.background = `radial-gradient(ellipse 85% 70% at 40% 40%,${shade(c, 1.15)} 0,${c} 45%,${shade(c, .55)} 100%)`; el.__c = c; return light(c) ? '#111' : '#fff'; };
  const SC = {};
  const person = (el, i, x, y, w, h, emoji = '😄') => {
    const ph = LIB.photo(i, w, h, 0);
    return mk(el, `<div class="a" style="left:${x}px;top:${y}px;width:${w}px;height:${h}px">${ph ? ph.replace('border-radius:0px', `border-radius:${30 * u}px`) : `<div style="width:100%;height:100%;display:flex;align-items:flex-end;justify-content:center"><span class="emo" style="font-size:${Math.min(w, h) * .82}px;line-height:1;filter:drop-shadow(0 ${30 * u}px ${40 * u}px rgba(0,0,0,.3))">${esc(emoji)}</span></div>`}</div>`);
  };
  const big = (el, text, z, color, fs = 170, align = 'left') => { const e = mk(el, `<div class="a" style="left:${z.x}px;top:${z.y}px;width:${z.w}px;font:400 ${fs * u}px Anton;color:${color};text-transform:uppercase;line-height:.98;text-align:${align};text-shadow:0 ${6 * u}px ${20 * u}px rgba(0,0,0,.25)">${letters(text)}</div>`); fitBox(e, z.w, z.h, 30); return e; };
  const ital = (el, text, z, color, fs = 58, align = 'left') => { const e = mk(el, `<div class="a" style="left:${z.x}px;top:${z.y}px;width:${z.w}px;font:italic 700 ${fs * u}px Poppins;color:${color};line-height:1.15;text-align:${align}">${letters(text)}</div>`); fitBox(e, z.w, z.h, 22); return e; };

  // Accroche : couleur de marque, personne heureuse, grand titre
  SC.ls_hero = {
    build(el, p, T, sh, i) {
      const fg = world(el, PAL[0]);
      const pz = SIDE ? { x: W * .5, y: H * .06, w: W * .46, h: H * .94 } : { x: W * .12, y: H * .4, w: W * .88, h: H * .6 };
      const pr = person(el, i, pz.x, pz.y, pz.w, pz.h, p.emoji || '😄');
      const tz = SIDE ? { x: 80 * u, y: H * .2, w: W * .46, h: H * .45 } : { x: 70 * u, y: Z('title').y, w: W - 140 * u, h: H * .2 };
      const tt = big(el, p.big || sh.text, tz, fg, SIDE ? 150 : 170, SIDE ? 'left' : 'center');
      const ln = p.line ? ital(el, p.line, SIDE ? { x: 80 * u, y: H * .68, w: W * .44, h: H * .22 } : { x: 70 * u, y: tz.y + tz.h + 20 * u, w: W - 140 * u, h: 180 * u }, fg, 54, SIDE ? 'left' : 'center') : null;
      const tb = T.at(p.at, 0, .1); ev(sh.start + .05, 'whoosh', .5); ev(tb, 'impact', .8);
      return { pr, tt, ln, tb };
    },
    update(t, c, p, T, sh) { pop(c.pr, t, sh.start, .6, 200 * u, .9); c.pr.style.transform += ` translateY(${Math.sin(t * 1.4) * 8 * u}px)`; typeIn(c.tt, t, c.tb - .1, .45, 'drop'); if (c.ln) typeIn(c.ln, t, c.tb + .3, .7); },
  };

  // Téléphone couché qui sort du cadre, titre condensé sur l'écran, ligne italique
  SC.ls_device = {
    build(el, p, T, sh, i) {
      const fg = world(el, PAL[(i + 3) % PAL.length]);
      const pw = SIDE ? W * .34 : W * .6;
      const scr = (K.S.screens || [])[i % Math.max(1, (K.S.screens || []).length)];
      const inner = scr ? `<img src="${scr}" style="width:100%;height:100%;object-fit:cover">` : `<div style="width:100%;height:100%;background:linear-gradient(135deg,#111,#2b2b33);display:flex;align-items:center;justify-content:center;padding:8%;box-sizing:border-box"><div class="ttx" style="font:400 ${pw * .22}px Anton;color:#fff;text-transform:uppercase;line-height:.95;transform:rotate(90deg);text-align:center;width:${pw * 1.6}px">${esc(p.screen || PRODUCT.name || '')}</div></div>`;
      const ph = mk(el, `<div class="a" style="left:${SIDE ? W * .6 : W * .3}px;top:${SIDE ? H * .1 : H * .12}px;transform-origin:50% 50%">${LIB.phone(pw, inner)}</div>`);
      const ln = ital(el, p.line || sh.text, SIDE ? { x: 80 * u, y: H * .3, w: W * .4, h: H * .4 } : { x: 70 * u, y: H * .74, w: W - 140 * u, h: H * .16 }, fg, SIDE ? 60 : 64, SIDE ? 'left' : 'center');
      ev(sh.start + .05, 'whoosh_deep', .6);
      return { ph, ln };
    },
    update(t, c, p, T, sh) {
      const q = P(t, sh.start, sh.start + .7);
      c.ph.style.transform = `perspective(${2000 * u}px) rotate(${lerp(-60, -78, eo(q))}deg) rotateY(${(1 - eo(q)) * 40 + Math.sin(t) * 3}deg) translate(${(1 - eo(q)) * 600 * u}px,0)`;
      typeIn(c.ln, t, sh.start + .3, .8);
    },
  };

  // Liste à changements de couleur : un avantage / une offre = un monde
  SC.ls_switch = {
    caps: false, build(el, p, T, sh) {
      const items = (p.items || [{ text: sh.text }]).slice(0, 4);
      const layers = items.map((it, k) => {
        const L = mk(el, `<div class="a" style="left:0;top:0;width:${W}px;height:${H}px;overflow:hidden"></div>`);
        const fg = world(L, PAL[(k + 1) % PAL.length]);
        const em = mk(L, `<div class="a emo" style="left:0;right:0;top:${SIDE ? H * .12 : H * .2}px;text-align:center;font-size:${(SIDE ? 300 : 360) * u}px;line-height:1">${esc(it.emoji || '✨')}</div>`);
        const tx = big(L, it.text || it, SIDE ? { x: 100 * u, y: H * .6, w: W - 200 * u, h: H * .3 } : { x: 70 * u, y: H * .48, w: W - 140 * u, h: H * .3 }, fg, SIDE ? 120 : 150, 'center');
        const no = mk(L, `<div class="a" style="left:${50 * u}px;top:${40 * u}px;font:400 ${110 * u}px Anton;color:${fg};opacity:.35">${String(k + 1).padStart(2, '0')}</div>`);
        return { L, em, tx, no };
      });
      const ts = T.seq(items, 'at', 0, .82); ts[0] = Math.min(ts[0], sh.start + .1); ts.forEach((x) => { ev(x - .05, 'whoosh', .5); ev(x + .1, 'pop', .6); });
      return { layers, ts };
    },
    update(t, c, p, T, sh) {
      c.layers.forEach((ly, k) => {
        const a = c.ts[k] - .12, on = t >= a;
        ly.L.style.display = on ? '' : 'none'; if (!on) return;
        const q = P(t, a, a + .3); ly.L.style.clipPath = k ? `circle(${eo(q) * 150}% at ${k % 2 ? 90 : 10}% ${k % 2 ? 10 : 90}%)` : 'none';
        const qe = P(t, a + .05, a + .45); ly.em.style.transform = `scale(${back(qe)}) rotate(${(1 - qe) * -30}deg)`;
        typeIn(ly.tx, t, a + .12, .4, 'drop');
      });
    },
  };

  // Coup de poing : un mot plein écran
  SC.ls_punch = {
    build(el, p, T, sh, i) {
      const fg = world(el, '#111827');
      const tt = big(el, p.text || sh.text, SIDE ? { x: 120 * u, y: H * .3, w: W - 240 * u, h: H * .4 } : { x: 70 * u, y: H * .36, w: W - 140 * u, h: H * .3 }, fg, 220, 'center');
      const tb = Math.min(T.at(p.at, 0, .2), sh.start + .45); ev(tb, 'impact_big', 1);
      return { tt, tb };
    },
    update(t, c, p, T, sh) { const q = P(t, c.tb - .1, c.tb + .25); c.tt.style.transform = `scale(${lerp(2, 1, eo(q))})`; c.tt.style.opacity = cl(q * 3); kick(t, c.tb + .05, 20); flash(t, c.tb, .25); },
  };

  // Révélation : produit / logo au centre du monde de marque
  SC.ls_reveal = {
    build(el, p, T, sh) {
      const fg = world(el, PAL[0]);
      const s = SIDE ? H * .5 : W * .62;
      const logo = K.S.logo;
      const hero = mk(el, `<div class="a" style="left:${SIDE ? W * .55 : (W - s) / 2}px;top:${SIDE ? H * .22 : H * .3}px;width:${s}px;height:${s}px;display:flex;align-items:center;justify-content:center">${PRODUCT.img ? LIB.product(s) : logo ? `<img src="${logo}" style="max-width:100%;max-height:100%;filter:drop-shadow(0 20px 30px rgba(0,0,0,.3))">` : LIB.box(s * .8)}</div>`);
      const nm = big(el, p.name || PRODUCT.name || '', SIDE ? { x: 80 * u, y: H * .3, w: W * .45, h: H * .3 } : { x: 70 * u, y: Z('title').y, w: W - 140 * u, h: H * .14 }, fg, 150, SIDE ? 'left' : 'center');
      const tg = p.tagline ? ital(el, p.tagline, SIDE ? { x: 80 * u, y: H * .64, w: W * .45, h: H * .2 } : { x: 70 * u, y: H * .72, w: W - 140 * u, h: H * .12 }, fg, 60, SIDE ? 'left' : 'center') : null;
      const tr = T.at(p.at, 0, .15); ev(tr - .1, 'whoosh_deep', .7); ev(tr + .1, 'impact', .9); ev(tr + .3, 'shimmer', .7);
      return { hero, nm, tg, tr };
    },
    update(t, c, p, T, sh) { const q = P(t, c.tr - .15, c.tr + .4); c.hero.style.opacity = cl(q * 3); c.hero.style.transform = `scale(${lerp(.4, 1, back(q))}) rotate(${(1 - q) * -20 + Math.sin(t * 1.3) * 2}deg)`; typeIn(c.nm, t, c.tr, .45, 'drop'); if (c.tg) typeIn(c.tg, t, c.tr + .5, .7); kick(t, c.tr + .1, 12); },
  };

  // Liste de bénéfices : lignes condensées avec coches, personne à côté
  SC.ls_benefits = {
    build(el, p, T, sh, i) {
      const fg = world(el, PAL[(i + 1) % PAL.length]);
      const items = (p.items || []).slice(0, 4);
      const pr = person(el, i + 1, SIDE ? W * .58 : W * .45, SIDE ? H * .08 : H * .55, SIDE ? W * .4 : W * .55, SIDE ? H * .92 : H * .45, p.emoji || '😍');
      const tz = SIDE ? { x: 80 * u, y: H * .14, w: W * .5, h: H * .72 } : { x: 70 * u, y: Z('title').y, w: W - 140 * u, h: H * .4 };
      const rows = items.map((it, k) => { const e = mk(el, `<div class="a" style="left:${tz.x}px;top:${tz.y + k * tz.h / Math.max(1, items.length)}px;width:${tz.w}px;display:flex;align-items:center;gap:${22 * u}px"><div style="flex:none;width:${80 * u}px;height:${80 * u}px;border-radius:50%;background:${fg};display:flex;align-items:center;justify-content:center">${LIB.icon('check', 54 * u, fg === '#fff' ? PAL[(i + 1) % PAL.length] : '#fff')}</div><div class="tx" style="font:400 ${84 * u}px Anton;color:${fg};text-transform:uppercase;line-height:1">${letters(it.text || it)}</div></div>`); fitBox(e.querySelector('.tx'), tz.w - 110 * u, tz.h / Math.max(1, items.length) - 16 * u, 26); return e; });
      const ts = T.seq(items, 'at', .05, .82); ts.forEach((x) => ev(x, 'pop', .7));
      return { pr, rows, ts };
    },
    update(t, c, p, T, sh) { slide(c.pr, t, sh.start, 300 * u, 0, .6); c.rows.forEach((r, k) => { slide(r, t, c.ts[k] - .1, -300 * u, 0, .4); typeIn(r.querySelector('.tx'), t, c.ts[k], .4, 'drop'); }); },
  };

  // Prix 3D (« par mois », « seulement »)
  SC.ls_price = {
    build(el, p, T, sh, i) {
      const fg = world(el, PAL[(i + 2) % PAL.length]);
      const lab = mk(el, `<div class="a" style="left:0;right:0;top:${SIDE ? H * .2 : H * .3}px;text-align:center;font:italic 700 ${66 * u}px Poppins;color:${fg}">${letters(p.label || 'Seulement')}</div>`);
      const pr = mk(el, `<div class="a" style="left:0;right:0;top:${SIDE ? H * .34 : H * .38}px;text-align:center">${LIB.price3d(p.big || '', 220 * u, fg, shade(PAL[(i + 2) % PAL.length], .45))}</div>`); fit(pr.firstElementChild, W - 120 * u, 40);
      const sub = p.sub ? mk(el, `<div class="a" style="left:0;right:0;top:${SIDE ? H * .66 : H * .55}px;text-align:center;font:italic 700 ${60 * u}px Poppins;color:${fg}">${letters(p.sub)}</div>`) : null;
      const tp = T.at(p.at, 0, .3); ev(tp, 'impact_big', 1); ev(tp + .1, 'coin', .8);
      return { lab, pr, sub, tp };
    },
    update(t, c, p, T, sh) { typeIn(c.lab, t, sh.start + .05, .4); const q = P(t, c.tp - .15, c.tp + .35); c.pr.style.opacity = q > 0 ? 1 : 0; c.pr.style.transform = `perspective(${1200 * u}px) rotateX(${(1 - eo(q)) * 90}deg) scale(${lerp(1.5, 1, eo(q))})`; if (c.sub) typeIn(c.sub, t, c.tp + .4, .5); kick(t, c.tp + .1, 18); },
  };

  // Appel à l'action
  SC.ls_cta = {
    build(el, p, T, sh, i) {
      const fg = world(el, PAL[0]);
      const pr = person(el, i + 2, SIDE ? W * .6 : W * .2, SIDE ? H * .1 : H * .56, SIDE ? W * .36 : W * .8, SIDE ? H * .9 : H * .44, p.emoji || '🤩');
      const tz = SIDE ? { x: 80 * u, w: W * .5 } : { x: 80 * u, w: W - 160 * u };
      const tg = big(el, p.tagline || PRODUCT.name || '', { x: tz.x, y: SIDE ? H * .12 : Z('title').y - 20 * u, w: tz.w, h: SIDE ? H * .3 : H * .16 }, fg, 130, SIDE ? 'left' : 'center');
      const bc = fg === '#fff' ? '#fff' : '#111', btx = fg === '#fff' ? PAL[0] : '#fff';
      const btn = mk(el, `<div class="a" style="left:${tz.x}px;top:${SIDE ? H * .5 : H * .3}px;width:${tz.w}px;box-sizing:border-box;padding:${26 * u}px;border-radius:${60 * u}px;background:${bc};color:${btx};font:800 ${58 * u}px Poppins;text-align:center;box-shadow:0 ${14 * u}px ${30 * u}px rgba(0,0,0,.3)">${esc(p.button || 'Cliquez sur le lien')}</div>`); fitBox(btn, tz.w, 200 * u, 22);
      const pn = p.phone ? mk(el, `<div class="a" style="left:${tz.x}px;top:${SIDE ? H * .7 : H * .42}px;width:${tz.w}px;display:flex;gap:${16 * u}px;align-items:center;justify-content:${SIDE ? 'flex-start' : 'center'}">${LIB.icon('phone', 74 * u, fg)}<span class="tx" style="font:400 ${96 * u}px Anton;color:${fg};white-space:nowrap">${letters(p.phone)}</span></div>`) : null;
      if (pn) fit(pn.querySelector('.tx'), tz.w - 100 * u, 24);
      const tc = T.at(p.click_at, 0, .25), tp = T.at(p.call_at, 0, .55);
      ev(tc, 'click', .9); if (pn) ev(tp, 'ping', .7);
      return { pr, tg, btn, pn, tc, tp };
    },
    update(t, c, p, T, sh) { pop(c.pr, t, sh.start, .6, 200 * u, .9); typeIn(c.tg, t, sh.start + .05, .45, 'drop'); pop(c.btn, t, sh.start + .3, .45, 60 * u, .7); c.btn.style.transform += ` scale(${t > c.tc && t < c.tc + .16 ? .93 : 1})`; if (c.pn) { fade(c.pn, t, c.tp - .2, .2); typeIn(c.pn, t, c.tp, 1.3, 'drop'); } },
  };

  // Repli : titres condensés
  SC.ls_text = {
    build(el, p, T, sh, i) {
      const fg = world(el, PAL[i % PAL.length]);
      const lines = (p.lines && p.lines.length ? p.lines : [sh.text]).slice(0, 3);
      const z = SIDE ? { x: 140 * u, y: H * .2, w: W - 280 * u, h: H * .6 } : { x: 70 * u, y: H * .26, w: W - 140 * u, h: H * .46 };
      const box = mk(el, `<div class="a" style="left:${z.x}px;top:${z.y}px;width:${z.w}px;height:${z.h}px;display:flex;flex-direction:column;justify-content:center;gap:${12 * u}px;text-align:center">${lines.map((l, k) => `<div class="ln" style="font:${k === lines.length - 1 ? `400 ${150 * u}px Anton;text-transform:uppercase` : `italic 700 ${64 * u}px Poppins`};color:${fg};line-height:1">${letters(l)}</div>`).join('')}</div>`);
      [...box.children].forEach((l) => fitBox(l, z.w, z.h / lines.length, 24));
      const ts = T.lineStarts(lines); ts.forEach((x, k) => ev(x, k === lines.length - 1 ? 'impact' : 'blip', .6));
      return { box, ts };
    },
    update(t, c, p, T, sh) { [...c.box.children].forEach((l, k) => typeIn(l, t, c.ts[k] - .05, .45, k === c.ts.length - 1 ? 'drop' : 'blur')); },
  };

  document.getElementById('bg').innerHTML = `<div style="position:absolute;inset:0;background:${ACC}"></div>`;
  K.register({
    name: 'lifestyle', SCENES: SC, fallback: 'ls_text', grain: .03, trDur: .36,
    transition(i, b, nx) { if (nx.type === 'ls_punch') return 'cut'; if (nx.type === 'ls_reveal') return 'circle'; return ['whip', 'zoom', 'slideUp', 'spin'][i % 4]; },
    trSfx: { whip: 'whoosh', zoom: 'whoosh_deep', slideUp: 'whoosh', spin: 'whoosh_rev', circle: 'whoosh_deep' },
  });
})();
