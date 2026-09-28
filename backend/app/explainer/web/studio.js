/* CutForge — extension « Studio » du moteur web (montage face caméra).
 *
 * Chargée AVANT engine.js. Le moteur l'appelle avec ses utilitaires; elle lui
 * rend des crochets (fond, décor, transition, mise à jour, préchargement).
 *
 * Tout est piloté par l'ADN de style (STORY.style): palette, typo, texture des
 * panneaux, habillage des cartes flottantes (« chrome »), transition, style des
 * sous-titres, badge du logo, caractère du mouvement. Deux ADN différents
 * donnent deux vidéos qui ne se ressemblent pas, avec le même code.
 *
 * Image pure: chaque image est une fonction de t (aucun timer, aucun hasard
 * non déterministe — rnd(i) seulement).
 */
window.CF_STUDIO_INIT = function (A) {
  'use strict';
  const { SC, mk, vis, tf, clamp, lerp, eo, eio, pop, rnd, esc, norm, up, ev, IMPACTS, FLASHES, icon, IC,
    prepDrop, drop, dropEvents, fit, wordTime, C, STORY, stage, cam, $ } = A;
  cam.style.zIndex = '2';
  if ($('grain')) $('grain').style.zIndex = '2';
  if ($('flash')) $('flash').style.zIndex = '6';
  const ST = STORY.style || {};
  const P = ST.palette || {};
  const V = ST.variant || 0;
  const M = ST.motion || { stiff: 15, damp: 0.55, shake: 1, push: 0.04 };
  const SND = ST.sound || {};
  const LOGO = STORY.logo || '';
  const BRAND = STORY.brand || '';
  const WORDS = STORY.words || [];
  const T = STORY.duration;
  const CAP = ST.captions || { style: 'box', y: 0.78 };
  // ------------------------------------------------------------------ MODE DE MONTAGE (grammaire de l'image)
  //  face   : où vit le visage (plein cadre, fenêtre, téléphone, polaroid, écran scindé)
  //  skin   : comment s'écrivent les idées (cartes, gros titres, bulles, typo cinétique,
  //           notes collées, bandeaux TV, accroches de une, mots-clés géants)
  //  full   : comment on passe aux démonstrations (prise de plein écran, bulle du
  //           présentateur, zoom dans le téléphone, page de magazine tournée)
  //  cam    : amplitude des zooms/pivots de caméra sur le visage
  const MONTAGES = {
    plein_cadre: { face: 'full', skin: 'card', full: 'takeover', cam: 0.35 },
    presentateur: { face: 'full', skin: 'card', full: 'bubble', cam: 0.3 },
    fenetre: { face: 'window', skin: 'headline', full: 'takeover', cam: 0.15, capY: 1640 },
    telephone: { face: 'phone', skin: 'bubble', full: 'zoomin', cam: 0.1, capY: 1745 },
    kinetique: { face: 'full', skin: 'kinetic', full: 'takeover', cam: 0.6, capY: 1400 },
    ecran_scinde: { face: 'split', skin: 'band', full: 'takeover', cam: 0.25, capY: 1730 },
    zoom_rythme: { face: 'full', skin: 'keyword', full: 'takeover', cam: 1.0, capY: 1230 },
    mur_polaroid: { face: 'polaroid', skin: 'note', full: 'takeover', cam: 0.08, capY: 1560 },
    journal_tv: { face: 'full', skin: 'lower_third', full: 'takeover', cam: 0.25, capY: 1540, ticker: true },
    magazine: { face: 'full', skin: 'coverline', full: 'pageturn', cam: 0.15, capY: 1700, masthead: true },
    stories: { face: 'full', skin: 'sticker', full: 'takeover', cam: 0.2, capY: 1560, stories: true },
    jeu_video: { face: 'full', skin: 'dialog', full: 'takeover', cam: 0.3, capY: 1500, hud: true },
    podcast: { face: 'circle', skin: 'chapter', full: 'bubble', cam: 0.04, capY: 1560, wave: true },
    documentaire: { face: 'full', skin: 'doc', full: 'takeover', cam: 0.12, capY: 1580, letterbox: true },
    bento: { face: 'bento', skin: 'tile', full: 'takeover', cam: 0.08, capY: 1500, bento: true },
    voyage: { face: 'world', skin: 'card', full: 'travel', cam: 0.1, capY: 1560, world: true },
  };
  const MONT = MONTAGES[ST.montage] || MONTAGES.plein_cadre;
  const CAP_Y = MONT.capY || Math.round((CAP.y || 0.78) * 1920);
  const HEAD = ST.head_font === 'DMSerif' ? "'DMSerif'" : ST.head_font === 'Bebas' ? "'Bebas'" : "'Anton'";
  const SERIF = ST.head_font === 'DMSerif';
  const TU = STORY.tone === 'tu';
  const R = ST.radius == null ? 24 : ST.radius;
  const spring = (t, t0) => pop(t, t0, M.stiff || 15, M.damp || 0.55);
  const rv = (i) => rnd(V * 0.013 + i);                       // hasard seedé par la variante du style
  const rgba = (hex, a) => { const h = String(hex || '#000000').replace('#', ''); return `rgba(${parseInt(h.slice(0, 2), 16)},${parseInt(h.slice(2, 4), 16)},${parseInt(h.slice(4, 6), 16)},${a})`; };
  const lum = (hex) => { const h = String(hex || '#000000').replace('#', ''); const c = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255); return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; };
  const on = (bg) => (lum(bg) > 0.55 ? P.ink : '#FFFFFF');
  // première couleur lisible sur `bg` (contraste WCAG ≥ 3), sinon noir/blanc
  const contrast = (a, b) => { const x = lum(a) + 0.05, y = lum(b) + 0.05; return x > y ? x / y : y / x; };
  const pick = (bg, ...c) => c.find((x) => x && contrast(x, bg) >= 3) || (lum(bg) > 0.5 ? '#111111' : '#FFFFFF');
  const LAYOUT = Math.floor(rv(77) * 3);               // variante de mise en page de CE montage
  const W_ = (s) => String(s || '').replace(/ ([?!:;»%])/g, ' $1').replace(/(«) /g, '$1 ');

  // ------------------------------------------------------------------ motifs (SVG)
  const MAPLE = 'M12 1.8l1.7 3.3 2-.9-.5 4.1 3-2.4.7 2.2 2.6-.5-1.3 3.1 1.9 1-4.9 3.9.7 2.1-4.5-.8V22h-.8v-4.1l-4.5.8.7-2.1-4.9-3.9 1.9-1-1.3-3.1 2.6.5.7-2.2 3 2.4-.5-4.1 2 .9z';
  function motif(sz, col, sw) {
    if (ST.motif === 'maple') return `<svg width="${sz}" height="${sz}" viewBox="0 0 24 24"><path d="${MAPLE}" fill="${col}"/></svg>`;
    return icon(ST.motif || 'sparkle', sz, col, sw || 2);
  }

  // ------------------------------------------------------------------ textures des panneaux
  const NOISE = (a) => `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='320' height='320'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 ${a} 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>")`;
  function textureCSS(kind, dark) {
    const line = (a) => (dark ? `rgba(255,255,255,${a})` : rgba(P.ink, a));
    const acc = (a) => rgba(P.accent, a);
    switch (kind) {
      case 'paper': return `background-image:${NOISE(dark ? 0.10 : 0.07)};background-size:320px 320px`;
      case 'grid': return `background-image:linear-gradient(${line(0.07)} 2px,transparent 2px),linear-gradient(90deg,${line(0.07)} 2px,transparent 2px);background-size:90px 90px;background-position:-2px -2px`;
      case 'dots': return `background-image:radial-gradient(${line(0.13)} 2.5px,transparent 3px);background-size:38px 38px`;
      case 'lines': return `background-image:linear-gradient(90deg,transparent 118px,${rgba(P.bad, 0.35)} 118px,${rgba(P.bad, 0.35)} 121px,transparent 121px),repeating-linear-gradient(180deg,transparent 0 58px,${line(0.08)} 58px 60px)`;
      case 'halftone': return `background-image:radial-gradient(${acc(0.22)} 3px,transparent 3.5px),radial-gradient(${acc(0.12)} 2px,transparent 2.5px);background-size:28px 28px,28px 28px;background-position:0 0,14px 14px`;
      case 'blueprint': return `background-image:linear-gradient(${line(0.16)} 2px,transparent 2px),linear-gradient(90deg,${line(0.16)} 2px,transparent 2px),linear-gradient(${line(0.06)} 1px,transparent 1px),linear-gradient(90deg,${line(0.06)} 1px,transparent 1px);background-size:180px 180px,180px 180px,36px 36px,36px 36px`;
      case 'scan': return `background-image:repeating-linear-gradient(180deg,${line(0.05)} 0 2px,transparent 2px 7px)`;
      case 'stripes': return `background-image:repeating-linear-gradient(135deg,${line(0.06)} 0 34px,transparent 34px 68px)`;
      default: return '';
    }
  }
  function bgFor(shot) {
    if (shot.layout === 'float') return 'transparent';
    const tone = shot.tone;
    if (tone === 'light') return `radial-gradient(ellipse at 50% 38%,${P.light} 0%,${P.light} 45%,${P.light2} 100%)`;
    if (tone === 'alarm') return `radial-gradient(ellipse at 50% 55%,${C.alarm1} 0%,${C.alarm2} 62%,#050103 100%)`;
    if (tone === 'split') return '#000';
    return `radial-gradient(ellipse at 50% 40%,${P.dark2} 0%,${P.dark} 58%,${C.dark0} 100%)`;
  }

  // ------------------------------------------------------------------ apparition des textes (gène text_fx)
  function prepT(el, text, hl) {
    const fx = ST.text_fx || 'drop';
    el._fx = fx; el._txt = String(text);
    if (fx === 'drop') { prepDrop(el, text, hl); return; }
    const hls = (hl || []).map(norm);
    const words = W_(text).split(/ +/).filter(Boolean);
    if (fx === 'mask') {
      el.innerHTML = words.map((w) => (w === '|' ? '<br>' : `<span style="display:inline-block;overflow:hidden;vertical-align:top;padding-bottom:.08em"><span class="mw" style="display:inline-block${hls.some((h) => h && norm(w).startsWith(h)) ? `;color:${P.accent}` : ''}">${esc(w)}</span></span>`)).join(' ');
      el._w = [...el.querySelectorAll('.mw')];
    } else if (fx === 'type') {
      el.innerHTML = words.map((w) => (w === '|' ? '<br>' : `<span class="wd${hls.some((h) => h && norm(w).startsWith(h)) ? ' hl' : ''}">${[...w].map((c) => `<span class="ch">${esc(c)}</span>`).join('')}</span>`)).join(' ');
      el._ch = [...el.querySelectorAll('.ch')];
    } else {
      el.innerHTML = words.map((w) => (w === '|' ? '<br>' : `<span class="wd${hls.some((h) => h && norm(w).startsWith(h)) ? ' hl' : ''}">${esc(w)}</span>`)).join(' ');
    }
  }
  function showT(el, t, t0) {
    const fx = el._fx;
    if (fx === 'drop') { drop(el, t, t0); return; }
    if (fx === 'mask') { el._w.forEach((w, i) => { const u = eo((t - t0 - i * 0.07) / 0.38); w.style.transform = `translateY(${((1 - u) * 110).toFixed(1)}%)`; }); return; }
    if (fx === 'type') { const n = el._ch.length, st = Math.min(0.045, 0.9 / Math.max(1, n)); el._ch.forEach((c, i) => { c.style.opacity = t >= t0 + i * st ? '1' : '0'; }); return; }
    const q = spring(t, t0); el.style.opacity = clamp((t - t0) * 7).toFixed(3); el.style.transform = `scale(${(0.55 + 0.45 * q).toFixed(3)})`;
  }
  function sfxT(el, t0, gain) {
    const fx = el._fx;
    if (fx === 'drop') dropEvents(el, t0);
    else if (fx === 'type') { const n = el._ch.length, st = Math.min(0.045, 0.9 / Math.max(1, n)); for (let i = 0; i < n; i += 2) ev(t0 + i * st, 'tick', 0.55 * (gain || 1)); }
    else if (fx === 'mask') ev(t0, 'whoosh', 0.35 * (gain || 1));
    else ev(t0, 'pop', 0.6 * (gain || 1));
  }

  // ------------------------------------------------------------------ habillage des cartes (gène chrome)
  const LIGHT_BODY = { postcard: 1, dossier: 1, notification: 1, sticker: 1, ticket: 1, polaroid: 1, magazine: 1, clean: 1, tape: 1 };
  const CH = ST.chrome || 'clean';
  const cardInk = LIGHT_BODY[CH] ? P.ink : '#FFFFFF';
  const cardSoft = LIGHT_BODY[CH] ? rgba(P.ink, 0.62) : 'rgba(255,255,255,.72)';
  const KICK_COL = LIGHT_BODY[CH] ? (lum(P.accent2) > 0.7 ? P.accent : P.accent2) : P.accent;
  function chrome(root, x, w, kicker, k, compact) {
    // k: indice de la carte (varie les petites rotations/décors)
    const rot = (CH === 'sticker' ? -2.5 : CH === 'tape' || CH === 'polaroid' ? -1.6 : 0) * (rv(k) > 0.5 ? 1 : -1);
    const card = mk(root, 'a', '', `left:${x}px;top:0;width:${w}px;box-sizing:border-box;border-radius:${R}px`);
    card._rot = rot;
    const body = mk(card, '', '', 'position:relative;box-sizing:border-box');
    let css = '', pad = '44px 50px 46px';
    const kick = kicker ? esc(up(kicker)) : '';
    switch (CH) {
      case 'postcard': {
        css = `background:${P.light};border:9px solid #fff;box-shadow:0 26px 60px rgba(0,0,0,.45)`;
        pad = compact ? '36px 46px 40px' : '40px 250px 44px 46px';
        mk(card, 'a', '', `inset:14px;border:3px dashed ${rgba(P.accent2, 0.9)};border-radius:${Math.max(0, R - 8)}px;pointer-events:none`);
        if (!compact) mk(card, 'a', `<div style="width:150px;height:176px;border:5px solid ${P.accent};border-radius:6px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;background:${rgba(P.accent, 0.06)};outline:3px dotted ${rgba(P.accent, 0.35)};outline-offset:5px">${motif(84, P.accent)}<div style="font:800 17px Poppins;letter-spacing:.14em;color:${P.accent}">${esc(up(BRAND || 'POSTE')).slice(0, 12)}</div></div>`, 'right:40px;top:36px');
        if (!compact) card._post = mk(card, 'a', `<svg width="210" height="120" viewBox="0 0 210 120"><circle cx="60" cy="60" r="50" fill="none" stroke="${P.ink}" stroke-width="4" opacity=".75"/><circle cx="60" cy="60" r="38" fill="none" stroke="${P.ink}" stroke-width="2" opacity=".6"/>${[0, 1, 2, 3].map((i) => `<path d="M112 ${30 + i * 20} q12 -8 24 0 t24 0 t24 0" fill="none" stroke="${P.ink}" stroke-width="4" opacity=".7"/>`).join('')}</svg>`, 'right:60px;top:220px;transform-origin:30% 50%');
        if (kick) mk(body, '', kick, `font:800 26px Poppins;letter-spacing:.22em;color:${KICK_COL};margin-bottom:14px`);
        break;
      }
      case 'dossier': {
        css = `background:${P.light};box-shadow:0 26px 60px rgba(0,0,0,.45);background-image:repeating-linear-gradient(180deg,transparent 0 56px,${rgba(P.ink, 0.06)} 56px 58px)`;
        mk(card, 'a', `<span style="font:800 26px Poppins;letter-spacing:.2em;color:#fff">${kick || 'DOSSIER'}</span>`, `left:36px;top:-54px;height:58px;padding:0 30px;display:flex;align-items:center;background:${P.dark2};border-radius:14px 14px 0 0`);
        mk(card, 'a', `<svg width="54" height="120" viewBox="0 0 54 120"><path d="M16 110V22a11 11 0 0 1 22 0v76a6 6 0 0 1-12 0V30" fill="none" stroke="${rgba(P.ink, 0.55)}" stroke-width="6" stroke-linecap="round"/></svg>`, 'right:40px;top:-40px');
        pad = '46px 50px 46px';
        break;
      }
      case 'notification': {
        css = `background:rgba(255,255,255,.95);box-shadow:0 30px 70px rgba(0,0,0,.45)`;
        pad = '30px 40px 38px';
        mk(body, '', `<div style="display:flex;align-items:center;gap:18px;margin-bottom:18px"><div style="width:62px;height:62px;border-radius:16px;background:${P.accent};display:flex;align-items:center;justify-content:center">${motif(36, on(P.accent))}</div><div style="font:700 30px Poppins;color:${rgba(P.ink, 0.75)};flex:1;white-space:nowrap;overflow:hidden">${esc(kick ? kicker : (BRAND || 'Message'))}</div><div style="font:500 26px Poppins;color:${rgba(P.ink, 0.45)}">maintenant</div></div>`);
        break;
      }
      case 'glass': {
        css = `background:${rgba(P.dark, 0.78)};border:2px solid ${rgba(P.light, 0.22)};box-shadow:0 30px 70px rgba(0,0,0,.5),inset 0 2px 0 ${rgba(P.accent, 0.8)}`;
        if (kick) mk(body, '', kick, `font:800 26px Poppins;letter-spacing:.22em;color:${P.accent};margin-bottom:14px`);
        break;
      }
      case 'sticker': {
        css = `background:${P.light};border:12px solid #fff;box-shadow:0 10px 0 ${rgba(P.ink, 0.25)},0 30px 60px rgba(0,0,0,.4)`;
        if (kick) mk(card, 'a', `<span style="font:800 28px Poppins;letter-spacing:.14em;color:${on(P.accent)}">${kick}</span>`, `left:40px;top:-34px;padding:10px 26px;border-radius:999px;background:${P.accent};transform:rotate(-3deg);box-shadow:0 8px 20px rgba(0,0,0,.25)`);
        pad = '50px 50px 46px';
        break;
      }
      case 'ticket': {
        const z = []; for (let i = 0; i <= 24; i++) z.push(`${(i / 24 * 100).toFixed(2)}% ${i % 2 ? 0 : 18}px`);
        const zb = []; for (let i = 24; i >= 0; i--) zb.push(`${(i / 24 * 100).toFixed(2)}% calc(100% - ${i % 2 ? 0 : 18}px)`);
        css = `background:#fff;clip-path:polygon(${z.join(',')},${zb.join(',')});filter:drop-shadow(0 22px 30px rgba(0,0,0,.35))`;
        pad = compact ? '44px 50px 40px' : '50px 50px 74px';
        mk(body, '', `<div style="display:flex;justify-content:space-between;font:800 24px Poppins;letter-spacing:.18em;color:${rgba(P.ink, 0.6)};border-bottom:3px dashed ${rgba(P.ink, 0.3)};padding-bottom:14px;margin-bottom:18px"><span>${kick || esc(up(BRAND || 'REÇU'))}</span><span>N° ${String(1000 + Math.floor(rv(k + 3) * 8999))}</span></div>`);
        let bars = ''; for (let i = 0; i < 46; i++) { const bw = 2 + Math.floor(rv(i + k * 50) * 5); bars += `<rect x="${i * 8}" y="0" width="${bw}" height="40" fill="${P.ink}"/>`; }
        if (!compact) card._bar = mk(card, 'a', `<svg width="370" height="40">${bars}</svg>`, 'left:50%;bottom:26px;margin-left:-185px;opacity:.8');
        break;
      }
      case 'polaroid': {
        css = `background:#fff;box-shadow:0 30px 60px rgba(0,0,0,.45)`;
        pad = '26px 26px 40px';
        if (!compact) mk(body, '', `<div style="height:250px;border-radius:4px;background:linear-gradient(160deg,${P.accent2},${P.accent});display:flex;align-items:center;justify-content:center;margin-bottom:26px;position:relative;overflow:hidden"><div style="position:absolute;inset:0;background:${NOISE(0.25)};opacity:.6"></div>${motif(150, 'rgba(255,255,255,.92)')}</div>`);
        mk(card, 'a', '', `left:50%;top:-26px;width:230px;height:56px;margin-left:-115px;background:${rgba(P.accent2, 0.55)};transform:rotate(${(rv(k) - 0.5) * 8}deg);box-shadow:0 2px 6px rgba(0,0,0,.15)`);
        break;
      }
      case 'terminal': {
        css = `background:#0B0F0C;border:2px solid ${rgba(P.accent, 0.45)};box-shadow:0 30px 70px rgba(0,0,0,.55),0 0 40px ${rgba(P.accent, 0.18)}`;
        pad = '0 0 40px';
        mk(body, '', `<div style="height:62px;display:flex;align-items:center;gap:14px;padding:0 26px;background:#161B17;border-radius:${R}px ${R}px 0 0;margin-bottom:28px"><i style="width:18px;height:18px;border-radius:50%;background:#FF5F57"></i><i style="width:18px;height:18px;border-radius:50%;background:#FEBC2E"></i><i style="width:18px;height:18px;border-radius:50%;background:#28C840"></i><span style="margin-left:16px;font:600 24px Poppins;color:rgba(255,255,255,.55)">~/${esc(String(kicker || BRAND || 'studio').toLowerCase().replace(/\s+/g, '-')).slice(0, 28)}</span></div>`);
        break;
      }
      case 'magazine': {
        css = `background:${P.light};box-shadow:0 26px 60px rgba(0,0,0,.4);border-top:14px solid ${P.ink}`;
        if (kick) mk(body, '', `<span style="color:${P.accent}">■</span> ${kick}`, `font:800 26px Poppins;letter-spacing:.24em;color:${P.ink};margin-bottom:12px`);
        mk(card, 'a', `N°${String(1 + Math.floor(rv(k + 9) * 98)).padStart(2, '0')}`, `right:36px;top:22px;font:400 30px DMSerif;color:${rgba(P.ink, 0.5)}`);
        break;
      }
      case 'neon': {
        css = `background:${rgba(P.dark, 0.72)};border:4px solid ${P.accent};box-shadow:0 0 26px ${rgba(P.accent, 0.8)},inset 0 0 26px ${rgba(P.accent, 0.35)}`;
        if (kick) mk(body, '', kick, `font:800 26px Poppins;letter-spacing:.24em;color:${P.accent2};text-shadow:0 0 12px ${rgba(P.accent2, 0.9)};margin-bottom:14px`);
        break;
      }
      case 'tape': {
        css = `background:${P.light};box-shadow:0 22px 50px rgba(0,0,0,.4);background-image:${NOISE(0.06)}`;
        mk(card, 'a', '', `left:-24px;top:-16px;width:160px;height:48px;background:${rgba(P.accent2, 0.6)};transform:rotate(-24deg)`);
        mk(card, 'a', '', `right:-24px;top:-16px;width:160px;height:48px;background:${rgba(P.accent2, 0.6)};transform:rotate(22deg)`);
        if (kick) mk(body, '', kick, `font:800 26px Poppins;letter-spacing:.22em;color:${P.accent};margin-bottom:12px`);
        break;
      }
      default: { // clean
        css = `background:${P.light};box-shadow:0 26px 60px rgba(0,0,0,.4);border-left:16px solid ${P.accent}`;
        if (kick) mk(body, '', kick, `font:800 26px Poppins;letter-spacing:.22em;color:${P.accent};margin-bottom:12px`);
      }
    }
    card.style.cssText += ';' + css;
    body.style.padding = pad;
    return { card, body };
  }

  // Titre dans une carte selon le chrome (serif, condensé, prompt de terminal…)
  function cardTitle(body, text, hl, maxW, size) {
    const pre = CH === 'terminal' ? `<span style="color:${P.accent}">&gt;&nbsp;</span>` : '';
    const serif = SERIF || CH === 'postcard' || CH === 'magazine' || CH === 'polaroid';
    const holder = mk(body, '', pre, `display:inline-block;max-width:${maxW}px;color:${cardInk};${CH === 'terminal' ? 'margin:0 40px;' : ''}font-family:${serif ? "'DMSerif'" : HEAD};line-height:1.08;${serif ? 'font-style:italic;' : ''}${CH === 'neon' ? `text-shadow:0 0 18px ${rgba(P.accent, 0.8)};` : ''}`);
    const el = document.createElement('span');
    holder.appendChild(el);
    prepT(el, serif ? text : up(text), hl);
    fit(holder, maxW, size, Math.round(size * 0.5), size * 2.6);
    return el;
  }

  // Zone basse (au-dessus des sous-titres): bas de la carte ancré ici.
  const LOW_BOTTOM = CAP_Y - 70;

  // ------------------------------------------------------------------ SCÈNES FLOTTANTES (par-dessus le visage)
  let cardK = 0;
  // Carte habillée: sur-titre + titre révélé sur la voix + sous-texte, entrée/sortie élastiques.
  function cardSkin(root, shot, p) {
    const k = cardK++;
    const w = 940, x = 70;
    const { card, body } = chrome(root, x, w, p.kicker, k);
    const tTitle = wordTime(shot, p.at, 0.05);
    const title = cardTitle(body, p.title || shot.text, p.highlight, w - (CH === 'postcard' ? 300 : 110), p.size || 92);
    const sub = p.sub ? mk(body, '', esc(W_(p.sub)), `margin-top:18px;font:700 40px/1.3 Poppins;color:${cardSoft};${CH === 'terminal' ? 'padding:0 40px;' : ''}`) : null;
    const tSub = p.sub ? wordTime(shot, p.sub_at, 0.6) : 0;
    let badge = null, tBadge = 0;
    if (p.badge) {
      badge = mk(body, '', `<span style="display:inline-flex;align-items:center;gap:12px;padding:12px 30px;border-radius:999px;background:${P.good};color:#fff;font:800 34px Poppins;letter-spacing:.06em">${icon(p.badge_icon || 'check', 34, '#fff', 3)}${esc(up(p.badge))}</span>`, 'margin-top:22px');
      tBadge = wordTime(shot, p.badge_at || p.badge, 0.7);
    }
    const h = card.offsetHeight;
    const top = p.pos === 'top' ? 250 : p.pos === 'mid' ? Math.round(960 - h / 2) : Math.max(230, LOW_BOTTOM - h);
    card.style.top = top + 'px';
    const tIn = shot.start + 0.02, tOut = shot.end - 0.12;
    const kind = { postcard: 'rise', dossier: 'slide', notification: 'drop', glass: 'fade', sticker: 'slap', ticket: 'print', polaroid: 'toss', terminal: 'fade', magazine: 'slide', neon: 'flicker', clean: 'slide', tape: 'toss' }[CH] || 'rise';
    ev(tIn, { rise: 'paper', slide: 'whoosh', drop: 'blip', fade: 'whoosh', slap: 'pop_low', print: 'scan', toss: 'paper', flicker: 'buzz' }[kind], 0.55);
    sfxT(title, tTitle, 0.9);
    if (sub) ev(tSub, 'pop', 0.5);
    if (badge) { ev(tBadge, 'ding', 0.55); }
    if (card._post) ev(tTitle + 0.5, 'stamp', 0.5);
    ev(tOut, 'whoosh', 0.3);
    return (t) => {
      const q = spring(t, tIn), o = eio((t - tOut) / 0.3);
      let trn = '';
      if (kind === 'rise') trn = `translateY(${((1 - q) * 520).toFixed(0)}px) rotate(${((1 - q) * 7 + card._rot).toFixed(2)}deg)`;
      else if (kind === 'slide') trn = `translateX(${((1 - q) * 1100).toFixed(0)}px) rotate(${card._rot}deg)`;
      else if (kind === 'drop') trn = `translateY(${((1 - q) * -260).toFixed(0)}px) scale(${(0.9 + 0.1 * q).toFixed(3)})`;
      else if (kind === 'slap') trn = `scale(${(1.6 - 0.6 * q).toFixed(3)}) rotate(${(card._rot + (1 - q) * 10).toFixed(2)}deg)`;
      else if (kind === 'print') { trn = `rotate(${card._rot}deg)`; card.style.clipPath = `inset(0 0 ${((1 - eo((t - tIn) / 0.55)) * 100).toFixed(1)}% 0)`; }
      else if (kind === 'toss') trn = `translate(${((1 - q) * -700).toFixed(0)}px,${((1 - q) * 300).toFixed(0)}px) rotate(${(card._rot - (1 - q) * 25).toFixed(2)}deg)`;
      else trn = `scale(${(0.94 + 0.06 * q).toFixed(3)}) rotate(${card._rot}deg)`;
      trn += ` translateY(${(o * 60).toFixed(0)}px) scale(${(1 - 0.12 * o).toFixed(3)})`;
      card.style.transform = trn;
      let op = clamp((t - tIn) * 6) * (1 - o);
      if (kind === 'flicker' && t - tIn < 0.45) op *= (rv(Math.floor(t * 30)) > 0.35 ? 1 : 0.25);
      vis(card, op);
      showT(title, t, tTitle);
      if (sub) { const u = eo((t - tSub) / 0.35); vis(sub, u); sub.style.transform = `translateY(${((1 - u) * 24).toFixed(0)}px)`; }
      if (badge) { const b = spring(t, tBadge); vis(badge, clamp((t - tBadge) * 6)); badge.style.transform = `scale(${(0.4 + 0.6 * b).toFixed(3)})`; badge.style.transformOrigin = '0 50%'; }
      if (card._post) { const c = spring(t, tTitle + 0.5); vis(card._post, clamp((t - tTitle - 0.45) * 6)); card._post.style.transform = `rotate(-14deg) scale(${(1.5 - 0.5 * c).toFixed(3)})`; }
    };
  }

  // Entrée/sortie générique d'un bloc flottant (utilisée par les habillages de mode)
  const inOut = (t, shot) => ({ q: spring(t, shot.start + 0.02), o: eio((t - shot.end + 0.15) / 0.3), a: clamp((t - shot.start) * 6) });

  // GROS TITRE (fenêtre): typographie posée dans la zone libre au-dessus du cadre
  function headlineSkin(root, shot, p, zone) {
    const box = mk(root, 'a', '', `left:${zone.x}px;top:${zone.y}px;width:${zone.w}px;text-align:${zone.align || 'center'}`);
    const kick = p.kicker ? mk(box, '', esc(up(p.kicker)), `font:800 28px Poppins;letter-spacing:.24em;color:${pick(zone.bg, P.accent, P.accent2)};margin-bottom:10px`) : null;
    const ttl = mk(box, '', '', `display:inline-block;max-width:${zone.w}px;font-family:${HEAD};line-height:1.02;color:${zone.ink};${SERIF ? 'font-style:italic;' : ''}`);
    const sp = document.createElement('span'); ttl.appendChild(sp);
    prepT(sp, SERIF ? (p.title || '') : up(p.title || ''), p.highlight);
    fit(ttl, zone.w, zone.size || 104, 44, zone.h - (kick ? 50 : 0) - (p.sub ? 60 : 0));
    const sub = p.sub ? mk(box, '', esc(W_(p.sub)), `margin-top:12px;font:600 38px/1.25 Poppins;color:${rgba(zone.ink, 0.72)}`) : null;
    const tT = wordTime(shot, p.at, 0.05), tS = p.sub ? wordTime(shot, p.sub_at, 0.6) : 0;
    ev(shot.start, 'whoosh', 0.35); sfxT(sp, tT); if (sub) ev(tS, 'pop', 0.45);
    return (t) => {
      const { o, a } = inOut(t, shot); vis(box, a * (1 - o)); box.style.transform = `translateY(${(o * -30).toFixed(0)}px)`;
      if (kick) vis(kick, clamp((t - shot.start) * 4));
      showT(sp, t, tT);
      if (sub) { const u = eo((t - tS) / 0.35); vis(sub, u); }
    };
  }

  // BULLES (téléphone): les idées sortent du téléphone en bulles de discussion
  let bubK = 0;
  function bubbleSkin(root, shot, p) {
    const k = bubK++, left = k % 2 === 0;
    const mkB = (txt, big, y, me) => {
      const bg = me ? P.accent : '#FFFFFF';
      return mk(root, 'a', `<div style="font:${big ? `800 54px/1.12 ${SERIF ? 'DMSerif' : 'Poppins'}` : '600 38px/1.25 Poppins'};color:${pick(bg, me ? on(P.accent) : P.ink)}">${esc(W_(txt))}</div>`,
        `${left ? 'left:40px' : 'right:40px'};top:${y}px;max-width:720px;padding:${big ? '30px 40px' : '22px 32px'};background:${bg};border-radius:44px;${left ? 'border-bottom-left-radius:12px' : 'border-bottom-right-radius:12px'};box-shadow:0 20px 50px rgba(0,0,0,.35);transform-origin:${left ? '0% 100%' : '100% 100%'}`);
    };
    const y0 = 70 + (k % 3) * 40;
    const b1 = mkB(p.kicker ? `${p.kicker} · ${p.title}` : (p.title || ''), true, y0, !left);
    const b2 = p.sub ? mkB(p.sub, false, y0 + b1.offsetHeight + 18, left) : null;
    const tT = wordTime(shot, p.at, 0.05), tS = p.sub ? wordTime(shot, p.sub_at, 0.6) : 0;
    ev(tT, 'blip', 0.7); if (b2) ev(tS, 'pop', 0.6);
    return (t) => {
      const o = eio((t - shot.end + 0.15) / 0.3);
      const s1 = pop(t, tT - 0.05, 18, 0.55); vis(b1, clamp((t - tT + 0.05) * 7) * (1 - o)); b1.style.transform = `scale(${(0.4 + 0.6 * s1).toFixed(3)})`;
      if (b2) { const s2 = pop(t, tS, 18, 0.55); vis(b2, clamp((t - tS) * 7) * (1 - o)); b2.style.transform = `scale(${(0.4 + 0.6 * s2).toFixed(3)})`; }
    };
  }

  // TYPO CINÉTIQUE: la phrase clé tombe en lignes géantes de tailles différentes
  function kineticSkin(root, shot, p) {
    const words = String(p.title || '').replace(/\u00a0/g, ' ').split(/\s+/).filter(Boolean);
    const lines = []; let cur = [];
    words.forEach((w) => { cur.push(w); if (cur.join(' ').length >= 9 || cur.length >= 2) { lines.push(cur); cur = []; } });
    if (cur.length) lines.push(cur);
    const box = mk(root, 'a', '', 'left:50px;top:0;width:980px;text-align:center');
    const els = lines.slice(0, 5).map((ln, i) => {
      const hot = i === (lines.length > 1 ? 1 : 0);
      const e = mk(box, '', esc(up(ln.join(' '))), `display:block;white-space:nowrap;font-family:${i % 2 ? "'Poppins'" : HEAD};font-weight:800;line-height:.98;color:${hot ? P.accent : '#FFFFFF'};${i % 2 ? '' : `-webkit-text-stroke:${hot ? 0 : 3}px ${rgba(P.dark, 0.35)};`}text-shadow:0 10px 40px rgba(0,0,0,.55);transform-origin:50% 60%`);
      const holder = mk(box, '', '', 'display:inline-block'); holder.appendChild(e); box.appendChild(holder);
      e.style.fontSize = '100px';
      let sz = 260; e.style.fontSize = sz + 'px'; while (sz > 60 && e.scrollWidth > 980) { sz -= 6; e.style.fontSize = sz + 'px'; }
      return e;
    });
    const h = box.offsetHeight; box.style.top = Math.max(160, Math.round(880 - h / 2)) + 'px';
    const tT = wordTime(shot, p.at, 0.05);
    const ts = els.map((_, i) => tT + i * 0.22);
    ts.forEach((x) => { ev(x, 'impact', 0.35); ev(x - 0.06, 'whoosh', 0.25); });
    return (t) => {
      const o = eio((t - shot.end + 0.15) / 0.25);
      els.forEach((e, i) => { const q = pop(t, ts[i], 20, 0.5); vis(e, clamp((t - ts[i]) * 9) * (1 - o)); e.style.transform = `scale(${(1.8 - 0.8 * q).toFixed(3)}) translateY(${((1 - q) * -40).toFixed(0)}px)`; });
    };
  }

  // MOT-CLÉ GÉANT (zoom rythmé): 1 à 3 mots, énormes, au centre
  function keywordSkin(root, shot, p) {
    const ws = String(p.title || '').replace(/\u00a0/g, ' ').split(/\s+/).filter((w) => w.length > 2).slice(0, 3);
    const txt = (ws.length ? ws : [p.title || '']).join(' ');
    const el = mk(root, 'a ctr', '', `top:760px;left:40px;width:1000px;font-family:${HEAD};line-height:1;color:#FFFFFF;-webkit-text-stroke:12px ${P.dark};paint-order:stroke fill;text-shadow:0 18px 50px rgba(0,0,0,.5)`);
    el.textContent = up(txt); fit(el, 1000, 230, 90, 480);
    const bar = mk(root, 'a', '', `left:${540 - 220}px;top:${760 + el.scrollHeight + 10}px;width:440px;height:16px;background:${P.accent};transform-origin:0 50%`);
    const tT = wordTime(shot, p.at, 0.05);
    ev(tT, SND.impact || 'impact', 0.6); ev(tT - 0.08, 'whoosh_deep', 0.4); FLASHES.push(tT);
    return (t) => {
      const o = eio((t - shot.end + 0.15) / 0.25), q = pop(t, tT, 18, 0.45);
      vis(el, clamp((t - tT) * 9) * (1 - o)); el.style.transform = `scale(${(0.3 + 0.7 * q).toFixed(3)}) rotate(${((1 - q) * -8).toFixed(1)}deg)`;
      vis(bar, clamp((t - tT - 0.15) * 6) * (1 - o)); bar.style.transform = `scaleX(${eo((t - tT - 0.15) / 0.35).toFixed(3)})`;
    };
  }

  // NOTE COLLÉE (mur de polaroids): post-it épinglé autour de la photo
  let noteK = 0;
  function noteSkin(root, shot, p) {
    const k = noteK++;
    const spots = [[560, 80, 4], [60, 70, -5], [600, 1180, 3], [70, 1220, -4]];
    const [x, y, r] = spots[k % spots.length];
    const col = [P.accent2, '#FFF3A8', P.light2, '#FFD6E0'][k % 4];
    const note = mk(root, 'a', '', `left:${x}px;top:${y}px;width:450px;min-height:300px;box-sizing:border-box;padding:48px 38px 36px;background:${col};box-shadow:0 22px 40px rgba(0,0,0,.35);transform-origin:50% 0`);
    mk(note, 'a', '', `left:50%;top:-18px;margin-left:-22px;width:44px;height:44px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#fff,${P.bad} 45%,${P.dark} 100%);box-shadow:0 6px 10px rgba(0,0,0,.35)`);
    const ink = pick(col, P.ink, '#111111');
    const tt = mk(note, '', '', `display:inline-block;max-width:374px;font:italic 400 60px/1.08 DMSerif;color:${ink}`);
    const sp = document.createElement('span'); tt.appendChild(sp); prepT(sp, p.title || '', p.highlight); fit(tt, 374, 64, 34, 260);
    const sub = p.sub ? mk(note, '', esc(W_(p.sub)), `margin-top:14px;font:600 30px/1.25 Poppins;color:${rgba(ink, 0.7)}`) : null;
    const tT = wordTime(shot, p.at, 0.05);
    ev(shot.start, 'paper', 0.6); ev(shot.start + 0.2, 'click', 0.5); sfxT(sp, tT, 0.7);
    return (t) => {
      const { q, o, a } = inOut(t, shot);
      vis(note, a * (1 - o));
      note.style.transform = `rotate(${(r + (1 - q) * 18 + Math.sin(t * 1.3 + k) * 0.8).toFixed(2)}deg) translateY(${((1 - q) * -200 + o * 40).toFixed(0)}px)`;
      showT(sp, t, tT); if (sub) vis(sub, eo((t - (p.sub_at ? wordTime(shot, p.sub_at, 0.6) : tT + 0.8)) / 0.3));
    };
  }

  // BANDEAU TV (journal): titre qui glisse depuis la gauche, sur-titre en couleur
  function lowerThirdSkin(root, shot, p) {
    const y = CAP_Y - 250;
    const tag = mk(root, 'a', esc(up(p.kicker || BRAND || '')), `left:40px;top:${y}px;padding:10px 26px;background:${P.bad};font:800 30px Poppins;letter-spacing:.14em;color:#fff`);
    if (!p.kicker && !BRAND) tag.style.display = 'none';
    const bar = mk(root, 'a', '', `left:40px;top:${y + 56}px;width:1000px;box-sizing:border-box;padding:18px 30px;background:rgba(255,255,255,.96);border-left:18px solid ${P.accent};box-shadow:0 18px 40px rgba(0,0,0,.35)`);
    const tt = mk(bar, '', '', `display:inline-block;max-width:920px;font-family:${HEAD};color:${P.ink};line-height:1.05;white-space:nowrap`);
    tt.textContent = up(p.title || ''); fit(tt, 920, 72, 34);
    const sub = p.sub ? mk(root, 'a', esc(W_(p.sub)), `left:40px;top:${y + 56 + bar.offsetHeight}px;max-width:1000px;padding:10px 30px;background:${rgba(P.dark, 0.9)};font:600 32px Poppins;color:#fff`) : null;
    const tT = wordTime(shot, p.at, 0.05);
    ev(shot.start, 'whoosh', 0.5); ev(tT, 'blip', 0.5);
    return (t) => {
      const { o } = inOut(t, shot);
      const u = eo((t - shot.start) / 0.35), u2 = eo((t - shot.start - 0.12) / 0.4);
      tag.style.transform = `translateX(${((1 - u) * -700 - o * 1100).toFixed(0)}px)`;
      bar.style.transform = `translateX(${((1 - u2) * -1150 - o * 1150).toFixed(0)}px)`;
      bar.style.clipPath = `inset(0 ${((1 - eo((t - tT) / 0.5)) * 100).toFixed(1)}% 0 0)`;
      if (sub) sub.style.transform = `translateX(${((1 - eo((t - shot.start - 0.3) / 0.4)) * -1150 - o * 1150).toFixed(0)}px)`;
    };
  }

  // ACCROCHE DE UNE (magazine): bloc de texte aligné à gauche, filet, sur la photo
  let covK = 0;
  function coverlineSkin(root, shot, p) {
    const k = covK++;
    const right = k % 2 === 1;
    const box = mk(root, 'a', '', `${right ? 'right:60px;text-align:right' : 'left:60px'};top:${1140 + (k % 2) * 60}px;width:760px`);
    const kick = mk(box, '', esc(up(p.kicker || '')), `font:800 30px Poppins;letter-spacing:.2em;color:${P.accent};margin-bottom:10px;text-shadow:0 2px 10px rgba(0,0,0,.5)`);
    if (!p.kicker) kick.style.display = 'none';
    const tt = mk(box, '', '', `display:inline-block;max-width:760px;font:italic 400 92px/1.02 DMSerif;color:#fff;text-shadow:0 6px 30px rgba(0,0,0,.65)`);
    const sp = document.createElement('span'); tt.appendChild(sp); prepT(sp, p.title || '', p.highlight); fit(tt, 760, 96, 44, 300);
    const rule = mk(box, '', '', `height:6px;width:220px;background:${P.accent};margin:${right ? '16px 0 0 auto' : '16px 0 0'};transform-origin:${right ? '100%' : '0'} 50%`);
    const sub = p.sub ? mk(box, '', esc(W_(p.sub)), `margin-top:12px;font:700 34px/1.25 Poppins;color:#fff;text-shadow:0 2px 14px rgba(0,0,0,.7)`) : null;
    const tT = wordTime(shot, p.at, 0.05);
    ev(shot.start, 'paper', 0.4); sfxT(sp, tT, 0.8);
    return (t) => {
      const { o, a } = inOut(t, shot); vis(box, a * (1 - o));
      showT(sp, t, tT); rule.style.transform = `scaleX(${eo((t - tT - 0.2) / 0.4).toFixed(3)})`;
      if (sub) vis(sub, eo((t - tT - 0.5) / 0.35));
    };
  }

  // BANDE BASSE (écran scindé): titre écrit dans la bande sous l'image
  function bandSkin(root, shot, p) {
    return headlineSkin(root, shot, p, { x: 60, y: 1235, w: 960, h: 400, bg: BAND_BG, ink: BAND_INK, size: 132, align: 'left' });
  }

  SC.float_card = function (root, shot, p) {
    switch (MONT.skin) {
      case 'headline': return headlineSkin(root, shot, p, { x: 70, y: 185, w: 940, h: 245, bg: BACK_BG, ink: pick(BACK_BG, P.ink, P.light), size: 104 });
      case 'bubble': return bubbleSkin(root, shot, p);
      case 'kinetic': return kineticSkin(root, shot, p);
      case 'keyword': return keywordSkin(root, shot, p);
      case 'note': return noteSkin(root, shot, p);
      case 'lower_third': return lowerThirdSkin(root, shot, p);
      case 'coverline': return coverlineSkin(root, shot, p);
      case 'band': return bandSkin(root, shot, p);
      case 'sticker': return stickerSkin(root, shot, p);
      case 'dialog': return dialogSkin(root, shot, p);
      case 'chapter': return chapterSkin(root, shot, p);
      case 'doc': return docSkin(root, shot, p);
      case 'tile': return tileSkin(root, shot, p);
      default: return cardSkin(root, shot, p);
    }
  };


  // ================================================================== GRAMMAIRES DE SCÈNES
  // Chaque mode de montage a SA façon de construire les moments clés. Ce n'est pas
  // une couleur qui change: c'est la mise en page, l'objet qui porte l'idée, le
  // mouvement. q = question, c = appel à commenter, e = fin, s = tampon/alerte,
  // k = mot-clé.
  const GRAM = {
    plein_cadre: { q: 'dial', c: 'cards', e: 'classic', s: 'stamp', k: 'pill' },
    presentateur: { q: 'watermark', c: 'cards', e: 'classic', s: 'stamp', k: 'pill' },
    fenetre: { q: 'search', c: 'cards', e: 'window', s: 'stamp', k: 'pill' },
    telephone: { q: 'chat', c: 'thread', e: 'call_end', s: 'bubble', k: 'bubble' },
    kinetique: { q: 'kinetic', c: 'kinetic', e: 'kinetic', s: 'slam', k: 'kinetic' },
    ecran_scinde: { q: 'split', c: 'cards', e: 'classic', s: 'band', k: 'band' },
    zoom_rythme: { q: 'burst', c: 'kinetic', e: 'kinetic', s: 'slam', k: 'kinetic' },
    mur_polaroid: { q: 'note', c: 'notes', e: 'polaroid', s: 'marker', k: 'note' },
    journal_tv: { q: 'breaking', c: 'poll', e: 'slate', s: 'alert', k: 'tag' },
    magazine: { q: 'spread', c: 'coupon', e: 'backcover', s: 'sticker', k: 'coverline' },
  };
  let G = GRAM[ST.montage] || GRAM.plein_cadre;
  const NOTE_BG = lum(P.accent2) > 0.55 ? P.accent2 : '#FFE27A';
  const NOTE_BG2 = '#FFC6D0';
  const HAND = "italic 400 {s}px/1.08 'DMSerif'";
  const hand = (s) => HAND.replace('{s}', s);
  const sayUp = (s) => esc(up(W_(s || '')));
  const outlineCSS = (col, w) => `-webkit-text-stroke:${w}px ${col};paint-order:stroke fill`;
  const PIN = (c) => `<svg width="56" height="56" viewBox="0 0 56 56"><circle cx="28" cy="24" r="16" fill="${c}"/><circle cx="22" cy="18" r="5" fill="rgba(255,255,255,.55)"/><path d="M28 40 L28 54" stroke="rgba(0,0,0,.45)" stroke-width="4" stroke-linecap="round"/></svg>`;
  const scribble = (w, h, col, sw) => `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" style="overflow:visible"><path pathLength="1" stroke-dasharray="1 1" stroke-dashoffset="1" d="M${w * 0.06} ${h * 0.55} C ${w * 0.1} ${h * -0.05}, ${w * 0.92} ${h * -0.1}, ${w * 0.95} ${h * 0.45} S ${w * 0.35} ${h * 1.12}, ${w * 0.04} ${h * 0.6} S ${w * 0.5} ${h * 0.02}, ${w * 0.85} ${h * 0.12}" fill="none" stroke="${col}" stroke-width="${sw}" stroke-linecap="round"/></svg>`;
  const drawSvg = (el, u) => { const pth = el.querySelector('path[pathLength]'); if (pth) pth.setAttribute('stroke-dashoffset', (1 - clamp(u)).toFixed(3)); };
  const cork = (root) => mk(root, 'a', '', `left:0;top:0;width:1080px;height:1920px;background:radial-gradient(ellipse at 50% 35%,#D9B98C,#B98E5D);`
    + `background-image:${NOISE(0.22)},radial-gradient(ellipse at 50% 35%,#D9B98C,#B98E5D);background-size:320px 320px,100% 100%`);
  const typeText = (el, text, t, t0, cps = 0.04, caret = true) => {
    const n = Math.min(text.length, Math.max(0, Math.floor((t - t0) / cps)));
    el.textContent = t >= t0 ? text.slice(0, n) + (caret && n < text.length && Math.floor(t * 4) % 2 === 0 ? '▌' : '') : '';
  };
  const tickType = (t0, text, cps = 0.04) => { for (let c = 0; c < text.length; c += 2) ev(t0 + c * cps, 'tick', 0.32); };

  // ---------------------------------------------------------------- QUESTIONS
  const QV = {};
  // barre de recherche: la question se tape, des résultats apparaissent
  QV.search = function (root, shot, p) {
    const full = `${p.title || ''} ${String(p.sub || '').replace(/ /g, ' ')}`.trim().toLowerCase();
    const bgc = shot.tone === 'light' ? P.light : P.dark;
    const q = mk(root, 'a ctr', '?', `top:230px;font-family:${HEAD};font-size:300px;line-height:1;color:${pick(bgc, P.accent, P.accent2)}`);
    const bar = mk(root, 'a', `<div style="display:flex;align-items:center;gap:26px;height:150px;padding:0 44px">${icon('target', 60, P.accent, 2.6)}<div class="t" style="font:600 48px Poppins;color:#1a1a1a;white-space:nowrap;overflow:hidden;flex:1"></div></div>`, `left:60px;top:640px;width:960px;background:#fff;border-radius:999px;box-shadow:0 26px 70px rgba(0,0,0,.35),0 0 0 6px ${rgba(P.accent, 0.35)}`);
    const tx = bar.querySelector('.t');
    const res = [0, 1, 2].map((i) => mk(root, 'a', `<div style="height:34px;width:${[520, 610, 460][i]}px;border-radius:10px;background:${rgba(P.accent, 0.85)};margin-bottom:22px"></div><div style="height:22px;width:860px;border-radius:8px;background:${rgba(pick(bgc, P.ink, P.light), 0.22)};margin-bottom:14px"></div><div style="height:22px;width:${[700, 780, 620][i]}px;border-radius:8px;background:${rgba(pick(bgc, P.ink, P.light), 0.16)}"></div>`, `left:90px;top:${880 + i * 230}px`));
    const tT = wordTime(shot, p.at, 0.02) - 0.35;
    const cps = Math.min(0.05, Math.max(0.025, (shot.end - 0.6 - tT) / Math.max(1, full.length)));
    const tEnd = tT + full.length * cps;
    tickType(tT, full, cps); ev(tEnd + 0.05, 'click', 0.6); res.forEach((_, i) => ev(tEnd + 0.2 + i * 0.12, 'pop_low', 0.35));
    return (t) => {
      const s = spring(t, shot.start); vis(q, clamp((t - shot.start) * 4)); q.style.transform = `scale(${(0.5 + 0.5 * s).toFixed(3)}) rotate(${(Math.sin(t * 1.3) * 5).toFixed(2)}deg)`;
      const b = spring(t, shot.start + 0.1); vis(bar, clamp((t - shot.start) * 5)); bar.style.transform = `translateY(${((1 - b) * 120).toFixed(0)}px)`;
      typeText(tx, full, t, tT, cps);
      res.forEach((r, i) => { const u = eo((t - tEnd - 0.2 - i * 0.12) / 0.35); vis(r, u); r.style.transform = `translateY(${((1 - u) * 40).toFixed(0)}px)`; });
    };
  };
  // messagerie: « en train d'écrire… » puis la question arrive en bulles
  QV.chat = function (root, shot, p) {
    mk(root, 'a', `<div style="display:flex;align-items:center;gap:24px;height:170px;padding:0 50px"><div style="width:96px;height:96px;border-radius:50%;background:${P.accent};display:flex;align-items:center;justify-content:center">${motif(56, on(P.accent))}</div><div><div style="font:700 42px Poppins;color:#fff">${esc(BRAND || 'Message')}</div><div style="font:500 30px Poppins;color:rgba(255,255,255,.6)">en ligne</div></div></div>`, `left:0;top:0;width:1080px;background:${rgba('#000000', 0.35)}`);
    const t0 = shot.start + 0.15, tT = wordTime(shot, p.at, 0.1), tS = p.sub ? wordTime(shot, p.sub_at, 0.55) : 0;
    const dots = mk(root, 'a', `<div style="display:flex;gap:14px;padding:34px 40px">${[0, 1, 2].map(() => '<i style="width:22px;height:22px;border-radius:50%;background:#8a8f99;display:block"></i>').join('')}</div>`, 'left:60px;top:330px;background:#fff;border-radius:44px 44px 44px 10px');
    const b1 = mk(root, 'a', `<div style="font:800 140px/1.02 Poppins;color:#111">${esc(W_(p.title || ''))}…</div>`, 'left:60px;top:330px;max-width:880px;padding:34px 46px;background:#fff;border-radius:48px 48px 48px 12px;box-shadow:0 18px 40px rgba(0,0,0,.3);transform-origin:0 100%');
    const b2 = p.sub ? mk(root, 'a', `<div style="font:700 96px/1.1 Poppins;color:${on(P.accent)}">${esc(W_(p.sub))}</div>`, `left:60px;top:${360 + b1.offsetHeight}px;max-width:880px;padding:30px 44px;background:${P.accent};border-radius:48px 48px 48px 12px;box-shadow:0 18px 40px rgba(0,0,0,.3);transform-origin:0 100%`) : null;
    ev(t0, 'blip', 0.5); ev(tT, 'pop', 0.8); if (b2) ev(tS, 'pop', 0.8);
    return (t) => {
      const typing = t >= t0 && t < tT; vis(dots, typing ? 1 : 0);
      if (typing) [...dots.firstElementChild.children].forEach((d, i) => { d.style.transform = `translateY(${(Math.max(0, Math.sin(t * 9 - i * 0.9)) * -12).toFixed(1)}px)`; });
      const s1 = spring(t, tT); vis(b1, clamp((t - tT) * 8)); b1.style.transform = `scale(${(0.4 + 0.6 * s1).toFixed(3)})`;
      if (b2) { const s2 = spring(t, tS); vis(b2, clamp((t - tS) * 8)); b2.style.transform = `scale(${(0.4 + 0.6 * s2).toFixed(3)})`; }
    };
  };
  // typographie cinétique: chaque mot de la question claque sur sa propre ligne
  function kineticStack(root, shot, items, top0, bottom) {
    // items: [{text, t, big, col, outline}]
    const els = items.map((it) => {
      const e = mk(root, 'a ctr', sayUp(it.text), `left:40px;width:1000px;font-family:${HEAD};line-height:.95;color:${it.col};${it.outline ? outlineCSS(it.col, 6) + ';color:transparent' : ''}`);
      e.style.fontSize = (it.big || 180) + 'px'; fit(e, 1000, it.big || 180, 70, 9999);
      return e;
    });
    const tot = els.reduce((a, e) => a + e.offsetHeight + 8, 0);
    let y = Math.max(top0, Math.round((top0 + bottom) / 2 - tot / 2));
    els.forEach((e) => { e.style.top = y + 'px'; y += e.offsetHeight + 8; });
    items.forEach((it) => { ev(it.t, 'impact', 0.45); IMPACTS.push(it.t); });
    return (t) => els.forEach((e, i) => {
      const s = pop(t, items[i].t, 20, 0.45); vis(e, clamp((t - items[i].t) * 12));
      e.style.transform = `scale(${(1.9 - 0.9 * s).toFixed(3)}) rotate(${((1 - s) * (i % 2 ? 6 : -6)).toFixed(2)}deg)`;
    });
  }
  QV.kinetic = function (root, shot, p) {
    const tT = wordTime(shot, p.at, 0.05), tS = p.sub ? wordTime(shot, p.sub_at, 0.5) : tT + 0.5;
    const sub = String(p.sub || '').replace(/ /g, ' ').split(/\s+/).filter(Boolean);
    const items = [{ text: p.title, t: tT, big: 260, col: P.accent }];
    for (let i = 0; i < sub.length; i += 2) items.push({ text: sub.slice(i, i + 2).join(' '), t: tS + i * 0.1, big: i % 4 ? 170 : 210, col: i % 4 ? P.light : '#FFFFFF', outline: i % 4 === 2 });
    return kineticStack(root, shot, items, 200, 1650);
  };
  // écran scindé: bloc couleur « ? » en haut, question écrite en bas
  QV.split = function (root, shot, p) {
    const top = mk(root, 'a', '', `left:0;top:0;width:1080px;height:960px;background:${P.accent}`);
    const qm = mk(top, 'a ctr', '?', `top:40px;font-family:${HEAD};font-size:880px;line-height:1;color:${on(P.accent)}`);
    const ttl = mk(root, 'a', '', `left:70px;top:1030px;width:940px;font-family:${HEAD};color:${P.light};line-height:1`);
    prepT(ttl, SERIF ? p.title : up(p.title || '')); fit(ttl, 940, 230, 90, 300);
    const sub = p.sub ? mk(root, 'a', esc(W_(p.sub)), `left:70px;top:${1060 + ttl.scrollHeight}px;width:940px;font:700 66px/1.2 Poppins;color:${pick(P.dark, P.accent2, P.light)}`) : null;
    const tT = wordTime(shot, p.at, 0.05), tS = p.sub ? wordTime(shot, p.sub_at, 0.5) : 0;
    sfxT(ttl, tT); ev(shot.start, SND.impact || 'impact', 0.6); if (sub) ev(tS, 'pop', 0.5);
    return (t) => {
      const u = eio((t - shot.start + 0.1) / 0.5); top.style.transform = `translateY(${((1 - u) * -960).toFixed(0)}px)`;
      qm.style.transform = `rotate(${(Math.sin(t * 1.6) * 6).toFixed(2)}deg) scale(${(1 + 0.03 * Math.sin(t * 3)).toFixed(3)})`;
      showT(ttl, t, tT);
      if (sub) { const v = eo((t - tS) / 0.35); vis(sub, v); sub.style.transform = `translateX(${((1 - v) * -80).toFixed(0)}px)`; }
    };
  };
  // bande dessinée: lignes de vitesse qui tournent, titre énorme au contour
  QV.burst = function (root, shot, p) {
    let rays = ''; for (let i = 0; i < 36; i++) { const a = i / 36 * Math.PI * 2; rays += `<path d="M540 960 L${540 + 1500 * Math.cos(a - 0.035)} ${960 + 1500 * Math.sin(a - 0.035)} L${540 + 1500 * Math.cos(a + 0.035)} ${960 + 1500 * Math.sin(a + 0.035)}Z" fill="${i % 2 ? rgba(P.accent, 0.35) : rgba('#FFFFFF', 0.06)}"/>`; }
    const burst = mk(root, 'a', `<svg width="1080" height="1920"><g>${rays}</g></svg>`, 'left:0;top:0');
    const ttl = mk(root, 'a ctr', sayUp(p.title) + '<span style="color:' + P.bad + '"> ?</span>', `top:700px;left:30px;width:1020px;font-family:${HEAD};font-size:300px;line-height:.95;color:#FFFFFF;${outlineCSS(P.dark, 14)}`);
    fit(ttl, 1020, 300, 120, 700);
    const sub = p.sub ? mk(root, 'a ctr', `<span style="display:inline-block;background:${P.accent2};color:${on(P.accent2)};font:800 64px Poppins;padding:14px 40px;transform:rotate(-3deg)">${sayUp(p.sub)}</span>`, `top:${740 + ttl.offsetHeight}px`) : null;
    const tT = wordTime(shot, p.at, 0.05), tS = p.sub ? wordTime(shot, p.sub_at, 0.5) : 0;
    ev(tT, 'impact_big', 0.8); IMPACTS.push(tT); if (sub) { ev(tS, 'pop', 0.7); IMPACTS.push(tS); }
    return (t) => {
      burst.firstElementChild.firstElementChild.setAttribute('transform', `rotate(${(t * 20).toFixed(1)} 540 960)`);
      const s = pop(t, tT, 18, 0.4); vis(ttl, clamp((t - tT) * 10)); ttl.style.transform = `scale(${(2.2 - 1.2 * s).toFixed(3)})`;
      if (sub) { const q = pop(t, tS, 16, 0.5); vis(sub, clamp((t - tS) * 8)); sub.style.transform = `scale(${(0.3 + 0.7 * q).toFixed(3)})`; }
    };
  };
  // post-it épinglé sur un tableau de liège, soulignage au feutre
  QV.note = function (root, shot, p) {
    cork(root);
    const n = mk(root, 'a', '', `left:150px;top:420px;width:780px;height:780px;background:${NOTE_BG};box-shadow:0 30px 50px rgba(0,0,0,.35);transform-origin:50% 0`);
    mk(n, 'a', PIN(P.bad), 'left:362px;top:-24px');
    const ttl = mk(n, 'a', '', `left:60px;top:120px;width:660px;font:${hand(170)};color:#2b2118`);
    prepT(ttl, (p.title || '') + ' ?'); fit(ttl, 660, 170, 80, 400);
    const ul = mk(n, 'a', scribble(560, 70, P.bad, 9), `left:90px;top:${140 + ttl.scrollHeight}px`);
    const sub = p.sub ? mk(n, 'a', esc(W_(p.sub)), `left:60px;top:${230 + ttl.scrollHeight}px;width:660px;font:${hand(76)};color:#3b2f24`) : null;
    const tT = wordTime(shot, p.at, 0.05), tS = p.sub ? wordTime(shot, p.sub_at, 0.5) : 0;
    ev(shot.start, 'paper', 0.7); sfxT(ttl, tT); ev(tT + 0.5, 'pencil', 0.6); if (sub) ev(tS, 'pencil', 0.5);
    return (t) => {
      const s = spring(t, shot.start + 0.05); vis(n, clamp((t - shot.start) * 5)); n.style.transform = `rotate(${(-4 + (1 - s) * 18).toFixed(2)}deg) translateY(${((1 - s) * -300).toFixed(0)}px)`;
      showT(ttl, t, tT); drawSvg(ul, (t - tT - 0.5) / 0.45);
      if (sub) vis(sub, eo((t - tS) / 0.35));
    };
  };
  // flash info: bandeau rouge, titre dans un cartouche, fond rayé
  QV.breaking = function (root, shot, p) {
    mk(root, 'a', '', `left:0;top:0;width:1080px;height:1920px;background:repeating-linear-gradient(135deg,${rgba('#FFFFFF', 0.04)} 0 40px,transparent 40px 80px)`);
    const lab = mk(root, 'a', `<span style="display:inline-flex;align-items:center;gap:16px;background:${P.bad};color:#fff;font:800 50px Poppins;letter-spacing:.14em;padding:18px 38px">${icon('alert', 50, '#fff', 2.6)}LA QUESTION</span>`, 'left:0;top:520px');
    const box = mk(root, 'a', '', `left:0;top:640px;width:1000px;padding:40px 60px;box-sizing:border-box;background:#fff`);
    const ttl = mk(box, '', '', `font-family:${HEAD};color:#111;line-height:.98`); prepT(ttl, up(p.title || '') + ' ?'); fit(ttl, 880, 230, 90, 480);
    const sub = p.sub ? mk(root, 'a', sayUp(p.sub), `left:0;top:${680 + box.offsetHeight}px;max-width:1000px;padding:24px 60px;box-sizing:border-box;background:${P.dark};font:800 58px Poppins;color:#fff;border-left:16px solid ${P.accent}`) : null;
    const tT = wordTime(shot, p.at, 0.05), tS = p.sub ? wordTime(shot, p.sub_at, 0.5) : 0;
    ev(shot.start, 'whoosh', 0.6); ev(shot.start + 0.1, 'ping', 0.5); sfxT(ttl, tT); if (sub) ev(tS, 'whoosh', 0.4);
    return (t) => {
      const a = eo((t - shot.start) / 0.3); lab.style.transform = `translateX(${((1 - a) * -700).toFixed(0)}px)`;
      const b = eo((t - shot.start - 0.12) / 0.35); box.style.transform = `translateX(${((1 - b) * -1100).toFixed(0)}px)`;
      showT(ttl, t, tT);
      if (sub) { const c = eo((t - tS) / 0.3); sub.style.transform = `translateX(${((1 - c) * -1100).toFixed(0)}px)`; }
    };
  };
  // double page de magazine: grand titre serif, citation, colonnes
  QV.spread = function (root, shot, p) {
    mk(root, 'a', '', `left:0;top:0;width:1080px;height:1920px;background:${P.light}`);
    mk(root, 'a', '', `left:60px;top:150px;width:960px;height:10px;background:${P.ink}`);
    mk(root, 'a', 'LA QUESTION', `left:60px;top:185px;font:800 34px Poppins;letter-spacing:.3em;color:${P.accent}`);
    const ttl = mk(root, 'a', '', `left:60px;top:260px;width:960px;font:italic 400 250px/.95 'DMSerif';color:${P.ink}`);
    prepT(ttl, (p.title || '') + ' ?'); fit(ttl, 960, 250, 110, 560);
    const quote = p.sub ? mk(root, 'a', `<span style="font:400 190px/0 DMSerif;color:${P.accent};vertical-align:-70px">«</span> ${esc(W_(p.sub))} <span style="font:400 190px/0 DMSerif;color:${P.accent};vertical-align:-70px">»</span>`, `left:60px;top:${320 + ttl.scrollHeight}px;width:960px;font:italic 400 88px/1.15 'DMSerif';color:${P.ink};border-top:3px solid ${P.ink};border-bottom:3px solid ${P.ink};padding:40px 0`) : null;
    const colTop = 380 + ttl.scrollHeight + (quote ? quote.offsetHeight : 0) + 40;
    const cols = [0, 1].map((c) => mk(root, 'a', Array.from({ length: 9 }, (_, i) => `<div style="height:18px;margin-bottom:22px;border-radius:4px;background:${rgba(P.ink, 0.18)};width:${i === 8 ? 60 : 100 - rv(c * 20 + i) * 12}%"></div>`).join(''), `left:${60 + c * 500}px;top:${colTop}px;width:460px`));
    const tT = wordTime(shot, p.at, 0.05), tS = p.sub ? wordTime(shot, p.sub_at, 0.5) : 0;
    ev(shot.start, 'paper', 0.6); sfxT(ttl, tT); if (quote) ev(tS, 'pop_low', 0.5);
    return (t) => {
      showT(ttl, t, tT);
      if (quote) { const v = eo((t - tS) / 0.4); vis(quote, v); quote.style.clipPath = `inset(0 ${((1 - v) * 100).toFixed(1)}% 0 0)`; }
      cols.forEach((c, i) => vis(c, eo((t - shot.start - 0.3 - i * 0.15) / 0.4)));
    };
  };

  // ---------------------------------------------------------------- APPEL À COMMENTER
  const CV = {};
  const ctaTimes = (shot, opts) => opts.map((o, i) => wordTime(shot, o.at, 0.2 + 0.3 * i));
  // fil de commentaires d'un réseau social: les mots-clés se publient, cœurs, bouton RDV
  CV.thread = function (root, shot, p) {
    const opts = (p.options || []).slice(0, 2);
    mk(root, 'a', `<div style="display:flex;align-items:center;justify-content:space-between;height:150px;padding:0 50px;border-bottom:2px solid rgba(255,255,255,.12)"><span style="font:800 46px Poppins;color:#fff">Commentaires</span>${icon('message', 54, '#fff', 2.2)}</div>`, 'left:0;top:60px;width:1080px');
    const rows = opts.map((o, i) => {
      const r = mk(root, 'a', `<div style="display:flex;gap:26px;align-items:flex-start"><div style="width:100px;height:100px;border-radius:50%;background:${i ? P.accent2 : P.accent};flex:none;display:flex;align-items:center;justify-content:center">${icon('user', 56, '#fff', 2)}</div><div><div style="font:700 32px Poppins;color:rgba(255,255,255,.6)">${TU ? 'Toi' : 'Vous'} · à l'instant</div><div class="t" style="font:800 64px/1.1 Poppins;color:#fff;margin-top:6px"></div><div class="h" style="margin-top:14px;display:flex;gap:10px;align-items:center;font:700 32px Poppins;color:${P.bad}">${icon('heart', 40, P.bad, 2.6)}<span>J'aime</span></div></div></div>`, `left:50px;top:${280 + i * 300}px;width:980px`);
      r._t = r.querySelector('.t'); r._h = r.querySelector('.h'); r._text = up(o.text || ''); return r;
    });
    const input = mk(root, 'a', `<div style="display:flex;align-items:center;gap:22px;height:130px;padding:0 20px 0 44px;background:#fff;border-radius:999px"><div class="t" style="flex:1;font:600 46px Poppins;color:#222;white-space:nowrap;overflow:hidden"></div><div class="b" style="width:96px;height:96px;border-radius:50%;background:${P.accent};display:flex;align-items:center;justify-content:center">${icon('arrowRight', 54, on(P.accent), 3)}</div></div>`, `left:50px;top:${280 + opts.length * 300 + 40}px;width:980px`);
    const it = input.querySelector('.t'), btn = input.querySelector('.b');
    const ts = ctaTimes(shot, opts);
    ts.forEach((t0, i) => { tickType(t0 - 0.9, rows[i]._text, 0.04); ev(t0, 'click', 0.7); ev(t0 + 0.05, 'blip', 0.6); ev(t0 + 0.5, 'pop', 0.4); });
    let rdv = null, tR = 0;
    if (p.stamp) {
      tR = wordTime(shot, p.stamp_at || p.stamp, 0.85);
      rdv = mk(root, 'a ctr', `<span style="display:inline-flex;align-items:center;gap:22px;background:${P.good};color:#fff;font:800 64px Poppins;padding:30px 60px;border-radius:999px;box-shadow:0 20px 50px rgba(0,0,0,.35)">${icon('calendar', 64, '#fff', 2.6)}${sayUp(p.stamp)}</span>`, `top:${Math.min(1560, 280 + opts.length * 300 + 240)}px`);
      ev(tR, 'ding', 0.8); IMPACTS.push(tR);
    }
    return (t) => {
      const cur = ts.findIndex((t0) => t < t0);
      const k = cur === -1 ? -1 : cur;
      if (k >= 0) typeText(it, rows[k]._text, t, ts[k] - 0.9, 0.04, true); else it.textContent = '';
      btn.style.transform = `scale(${ts.some((t0) => t > t0 && t < t0 + 0.15) ? 0.86 : 1})`;
      rows.forEach((r, i) => {
        const s = spring(t, ts[i]); vis(r, clamp((t - ts[i]) * 8)); r.style.transform = `translateY(${((1 - s) * 60).toFixed(0)}px)`;
        r._t.textContent = r._text; const h = spring(t, ts[i] + 0.5); r._h.style.transform = `scale(${(t > ts[i] + 0.5 ? 0.6 + 0.4 * h : 0).toFixed(3)})`;
      });
      vis(input, clamp((t - shot.start) * 4));
      if (rdv) { const s = spring(t, tR); vis(rdv, clamp((t - tR) * 8)); rdv.style.transform = `scale(${(0.3 + 0.7 * s).toFixed(3)})`; }
    };
  };
  // typographie cinétique: ÉCRIS · mot 1 · OU · mot 2 · RENDEZ-VOUS
  CV.kinetic = function (root, shot, p) {
    const opts = (p.options || []).slice(0, 2), ts = ctaTimes(shot, opts);
    const items = [{ text: TU ? 'Écris' : 'Écrivez', t: shot.start + 0.1, big: 150, col: P.light, outline: true }];
    opts.forEach((o, i) => { if (i) items.push({ text: 'ou', t: ts[i] - 0.3, big: 110, col: P.light, outline: true }); items.push({ text: o.text, t: ts[i], big: 190, col: i ? '#FFFFFF' : P.accent }); });
    if (p.stamp) items.push({ text: p.stamp, t: wordTime(shot, p.stamp_at || p.stamp, 0.85), big: 200, col: P.bad });
    return kineticStack(root, shot, items, 160, 1760);
  };
  // post-it: « en commentaire » écrit au feutre, deux notes épinglées
  CV.notes = function (root, shot, p) {
    cork(root);
    const opts = (p.options || []).slice(0, 2), ts = ctaTimes(shot, opts);
    const head = mk(root, 'a', `${TU ? 'Écris' : 'Écrivez'} en commentaire :`, `left:80px;top:180px;width:920px;font:${hand(96)};color:#fff;text-shadow:0 4px 14px rgba(0,0,0,.35)`);
    const notes = opts.map((o, i) => {
      const n = mk(root, 'a', `${PIN(i ? P.accent : P.bad)}`, `left:${i ? 520 : 90}px;top:${i ? 700 : 450}px;width:470px;height:420px;background:${i ? NOTE_BG2 : NOTE_BG};box-shadow:0 26px 44px rgba(0,0,0,.35);transform-origin:50% 0`);
      n.firstElementChild.style.cssText = 'position:absolute;left:207px;top:-22px';
      const tx = mk(n, 'a', esc(W_(o.text)), `left:40px;top:110px;width:390px;font:${hand(84)};color:#2b2118`); fit(tx, 390, 84, 44, 280);
      return n;
    });
    ts.forEach((t0) => { ev(t0 - 0.1, 'paper', 0.6); ev(t0 + 0.2, 'pencil', 0.5); });
    let circ = null, tR = 0, word = null;
    if (p.stamp) {
      tR = wordTime(shot, p.stamp_at || p.stamp, 0.85);
      word = mk(root, 'a ctr', esc(W_(p.stamp)), `top:1330px;font:${hand(150)};color:#fff;text-shadow:0 6px 18px rgba(0,0,0,.4)`);
      circ = mk(root, 'a', scribble(900, 300, P.bad, 12), 'left:90px;top:1270px');
      ev(tR, 'pencil', 0.8); ev(tR + 0.3, 'pencil', 0.6);
    }
    return (t) => {
      vis(head, eo((t - shot.start) / 0.4));
      notes.forEach((n, i) => { const s = spring(t, ts[i] - 0.1); vis(n, clamp((t - ts[i] + 0.15) * 6)); n.style.transform = `rotate(${((i ? 5 : -5) + (1 - s) * (i ? 20 : -20)).toFixed(2)}deg) translateY(${((1 - s) * -400).toFixed(0)}px)`; });
      if (word) { vis(word, eo((t - tR) / 0.3)); drawSvg(circ, (t - tR - 0.1) / 0.6); }
    };
  };
  // sondage TV: deux réponses A / B dont les jauges se remplissent
  CV.poll = function (root, shot, p) {
    const opts = (p.options || []).slice(0, 2), ts = ctaTimes(shot, opts);
    const head = mk(root, 'a', `<span style="display:inline-block;background:${P.bad};color:#fff;font:800 50px Poppins;letter-spacing:.1em;padding:18px 40px">${TU ? 'RÉPONDS EN COMMENTAIRE' : 'RÉPONDEZ EN COMMENTAIRE'}</span>`, 'left:0;top:300px');
    fit(head.firstElementChild, 1000, 50, 30);
    const rows = opts.map((o, i) => {
      const r = mk(root, 'a', `<div style="display:flex;align-items:stretch;height:170px"><div style="width:170px;background:${i ? P.accent2 : P.accent};display:flex;align-items:center;justify-content:center;font-family:${HEAD};font-size:110px;color:${on(i ? P.accent2 : P.accent)}">${'AB'[i]}</div><div style="flex:1;position:relative;background:rgba(255,255,255,.1)"><div class="f" style="position:absolute;inset:0;background:#fff;transform-origin:0 50%"></div><div class="t" style="position:absolute;left:40px;top:0;height:170px;display:flex;align-items:center;font:800 60px Poppins;color:#111;white-space:nowrap"></div></div></div>`, `left:60px;top:${480 + i * 230}px;width:960px`);
      r._f = r.querySelector('.f'); r._t = r.querySelector('.t'); r._text = up(o.text || ''); r._t.textContent = r._text; fit(r._t, 740, 60, 32); r._t.textContent = ''; return r;
    });
    ts.forEach((t0) => { ev(t0 - 0.15, 'whoosh', 0.4); tickType(t0, 'x'.repeat(12), 0.05); });
    let rdv = null, tR = 0;
    if (p.stamp) {
      tR = wordTime(shot, p.stamp_at || p.stamp, 0.85);
      rdv = mk(root, 'a', `<span style="display:inline-block;background:#fff;color:#111;font-family:${HEAD};font-size:130px;padding:20px 60px;border-left:26px solid ${P.bad}">${sayUp(p.stamp)}</span>`, `left:0;top:${480 + opts.length * 230 + 120}px`);
      ev(tR, 'ping', 0.7); ev(tR, 'whoosh', 0.5);
    }
    return (t) => {
      const a = eo((t - shot.start) / 0.35); head.style.transform = `translateX(${((1 - a) * -900).toFixed(0)}px)`;
      rows.forEach((r, i) => { const u = eo((t - ts[i] + 0.2) / 0.35); r.style.transform = `translateX(${((1 - u) * 1100).toFixed(0)}px)`; r._f.style.transform = `scaleX(${eo((t - ts[i]) / 0.6).toFixed(3)})`; typeText(r._t, r._text, t, ts[i], 0.035, false); });
      if (rdv) { const u = eo((t - tR) / 0.3); rdv.style.transform = `translateX(${((1 - u) * -1100).toFixed(0)}px)`; }
    };
  };
  // coupon-réponse découpable: cases qui se cochent, tampon
  CV.coupon = function (root, shot, p) {
    mk(root, 'a', '', `left:0;top:0;width:1080px;height:1920px;background:${P.light}`);
    const opts = (p.options || []).slice(0, 2), ts = ctaTimes(shot, opts);
    const cp = mk(root, 'a', '', `left:70px;top:360px;width:940px;height:${360 + opts.length * 170}px;border:6px dashed ${P.ink};box-sizing:border-box`);
    mk(cp, 'a', icon('tool', 64, P.ink, 2), 'left:-36px;top:-36px;background:' + P.light);
    mk(cp, 'a', 'Coupon-réponse', `left:60px;top:50px;font:italic 400 90px 'DMSerif';color:${P.ink}`);
    mk(cp, 'a', `${TU ? 'À écrire' : 'À écrire'} en commentaire`, `left:60px;top:160px;font:800 32px Poppins;letter-spacing:.2em;color:${P.accent};text-transform:uppercase`);
    const rows = opts.map((o, i) => mk(cp, 'a', `<div style="display:flex;align-items:center;gap:34px"><div style="width:90px;height:90px;border:6px solid ${P.ink};flex:none;position:relative"><div class="k" style="position:absolute;left:-10px;top:-40px">${icon('check', 130, P.bad, 3.4)}</div></div><div style="font:800 62px Poppins;color:${P.ink}">${sayUp(o.text)}</div></div>`, `left:60px;top:${260 + i * 170}px;width:820px`));
    rows.forEach((r) => fit(r.firstElementChild.lastElementChild, 680, 62, 32));
    ts.forEach((t0) => { ev(t0 + 0.2, 'pencil', 0.7); });
    let stp = null, tR = 0;
    if (p.stamp) {
      tR = wordTime(shot, p.stamp_at || p.stamp, 0.85);
      stp = mk(root, 'a', `<div style="width:420px;height:420px;border-radius:50%;border:14px double ${P.bad};display:flex;align-items:center;justify-content:center;text-align:center;font-family:${HEAD};font-size:84px;line-height:1;color:${P.bad}">${sayUp(p.stamp).replace('-', '-<br>')}</div>`, `left:560px;top:${360 + opts.length * 170 + 250}px`);
      ev(tR, 'stamp', 0.9); IMPACTS.push(tR);
    }
    return (t) => {
      const s = spring(t, shot.start); vis(cp, clamp((t - shot.start) * 5)); cp.style.transform = `rotate(${((1 - s) * 8 - 1.5).toFixed(2)}deg)`;
      rows.forEach((r, i) => { vis(r, eo((t - ts[i] + 0.3) / 0.3)); const k = r.querySelector('.k'); k.style.clipPath = `inset(0 ${((1 - eo((t - ts[i] - 0.2) / 0.3)) * 100).toFixed(1)}% 0 0)`; });
      if (stp) { const q = pop(t, tR, 20, 0.45); vis(stp, clamp((t - tR) * 10)); stp.style.transform = `rotate(-14deg) scale(${(1.8 - 0.8 * q).toFixed(3)})`; }
    };
  };

  // ---------------------------------------------------------------- FINS
  const EV_ = {};
  const endTimes = (shot, p) => {
    const lines = (p.lines || []).slice(0, 2);
    return { lines, t1: lines[0] ? wordTime(shot, lines[0].at, 0.05) : shot.start, t2: lines[1] ? wordTime(shot, lines[1].at, 0.45) : shot.start, tB: p.bye ? wordTime(shot, p.bye.at, 0.9) : shot.end - 0.8 };
  };
  const logoHTML = (w, h) => (LOGO ? `<img src="${LOGO}" style="max-width:${w}px;max-height:${h}px;object-fit:contain;display:block;margin:0 auto">` : `<span style="font-family:${HEAD};font-size:${Math.round(h / 2)}px;color:${P.accent}">${esc(up(BRAND || ''))}</span>`);
  // le logo prend la place du visage dans la fenêtre
  EV_.window = function (root, shot, p) {
    const { lines, t1, t2, tB } = endTimes(shot, p);
    const h1 = mk(root, 'a ctr', lines[0] ? sayUp(lines[0].text) : '', `top:170px;left:60px;width:960px;font-family:${HEAD};font-size:110px;line-height:1;color:${pick(shot.tone === 'light' ? P.light : P.dark, P.accent2, P.accent, '#fff')}`); fit(h1, 960, 110, 60, 240);
    const win = mk(root, 'a', `<div style="padding:70px 40px">${logoHTML(760, 520)}</div>`, `left:80px;top:${230 + h1.offsetHeight}px;width:920px;background:#fff;border-radius:${Math.max(18, R)}px;box-shadow:0 40px 90px rgba(0,0,0,.45)`);
    const h2 = lines[1] ? mk(root, 'a ctr', sayUp(lines[1].text), `top:${280 + h1.offsetHeight + win.offsetHeight}px;left:60px;width:960px;font:800 50px Poppins;letter-spacing:.06em;color:${pick(shot.tone === 'light' ? P.light : P.dark, P.accent, '#fff')}`) : null;
    const bye = p.bye ? mk(root, 'a ctr', `<span style="display:inline-block;background:${P.accent};color:${on(P.accent)};font-family:${HEAD};font-size:110px;padding:14px 60px;border-radius:${Math.max(14, R)}px">${sayUp(p.bye.text)}</span>`, 'top:1560px') : null;
    ev(shot.start + 0.1, 'whoosh', 0.5); ev(shot.start + 0.3, 'shimmer', 0.6); ev(t1, 'pop', 0.4); if (bye) ev(tB, SND.impact || 'impact', 0.5);
    return (t) => {
      vis(h1, eo((t - t1) / 0.35)); const s = spring(t, shot.start + 0.1); vis(win, clamp((t - shot.start) * 4)); win.style.transform = `scale(${(0.7 + 0.3 * s).toFixed(3)})`;
      if (h2) vis(h2, eo((t - t2) / 0.35));
      if (bye) { const q = spring(t, tB - 0.1); vis(bye, clamp((t - tB + 0.1) * 6)); bye.style.transform = `scale(${(0.4 + 0.6 * q).toFixed(3)})`; }
    };
  };
  // fin d'appel vidéo: avatar-logo, « appel terminé », durée, au revoir
  EV_.call_end = function (root, shot, p) {
    const { lines, t1, tB } = endTimes(shot, p);
    const av = mk(root, 'a', `<div style="width:420px;height:420px;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;overflow:hidden;box-shadow:0 0 0 14px ${rgba(P.accent, 0.35)},0 30px 70px rgba(0,0,0,.5)"><div style="width:330px">${logoHTML(330, 330)}</div></div>`, 'left:330px;top:300px');
    const nm = mk(root, 'a ctr', esc(BRAND || ''), 'top:790px;font:800 70px Poppins;color:#fff');
    const mm = Math.floor(T / 60), ss = Math.round(T % 60);
    const st = mk(root, 'a ctr', `Appel terminé · ${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`, 'top:890px;font:500 42px Poppins;color:rgba(255,255,255,.65)');
    const l1 = lines[0] ? mk(root, 'a ctr', esc(W_(lines[0].text)), `top:1030px;left:80px;width:920px;font:italic 400 80px/1.15 'DMSerif';color:#fff`) : null;
    const bye = p.bye ? mk(root, 'a ctr', sayUp(p.bye.text), `top:1330px;font-family:${HEAD};font-size:150px;color:${P.accent}`) : null;
    const hang = mk(root, 'a', `<div style="width:170px;height:170px;border-radius:50%;background:#FF3B30;display:flex;align-items:center;justify-content:center">${icon('x', 80, '#fff', 3)}</div>`, 'left:455px;top:1600px');
    ev(shot.start, 'blip', 0.6); ev(shot.start + 0.25, 'pop_low', 0.6); if (bye) ev(tB, 'ding', 0.6);
    return (t) => {
      const s = spring(t, shot.start); vis(av, clamp((t - shot.start) * 5)); av.style.transform = `scale(${(0.5 + 0.5 * s).toFixed(3)})`;
      [nm, st].forEach((e, i) => vis(e, eo((t - shot.start - 0.3 - i * 0.15) / 0.35)));
      if (l1) vis(l1, eo((t - t1) / 0.4));
      if (bye) { const q = spring(t, tB - 0.1); vis(bye, clamp((t - tB + 0.1) * 6)); bye.style.transform = `scale(${(0.5 + 0.5 * q).toFixed(3)})`; }
      hang.style.transform = `scale(${(1 + 0.05 * Math.sin(t * 6)).toFixed(3)})`;
    };
  };
  // fin cinétique: la conclusion claque en mots, logo en pied
  EV_.kinetic = function (root, shot, p) {
    const { lines, t1, t2, tB } = endTimes(shot, p);
    const items = [];
    lines.forEach((l, i) => items.push({ text: l.text, t: i ? t2 : t1, big: i ? 130 : 170, col: i ? P.light : P.accent, outline: !!i }));
    if (p.bye) items.push({ text: p.bye.text, t: tB, big: 230, col: '#FFFFFF' });
    const upd = kineticStack(root, shot, items, 140, 1400);
    const lg = mk(root, 'a ctr', `<span style="display:inline-block;background:#fff;padding:30px 50px;border-radius:24px">${logoHTML(420, 180)}</span>`, 'top:1560px');
    ev(shot.start + 0.2, 'shimmer', 0.5);
    return (t) => { upd(t); const s = spring(t, shot.start + 0.1); vis(lg, clamp((t - shot.start) * 4)); lg.style.transform = `translateY(${((1 - s) * 200).toFixed(0)}px)`; };
  };
  // fin tableau de liège: logo dans un polaroid épinglé, mot écrit au feutre
  EV_.polaroid = function (root, shot, p) {
    cork(root);
    const { lines, t1, t2, tB } = endTimes(shot, p);
    const pol = mk(root, 'a', `<div style="height:560px;display:flex;align-items:center;justify-content:center;background:#f7f7f7">${logoHTML(560, 460)}</div><div style="height:130px;display:flex;align-items:center;justify-content:center;font:${hand(66)};color:#2b2118">${esc(BRAND || '')}</div>`, 'left:200px;top:230px;width:680px;padding:30px 30px 0;box-sizing:border-box;background:#fff;box-shadow:0 30px 60px rgba(0,0,0,.4)');
    mk(pol, 'a', '', `left:220px;top:-30px;width:240px;height:60px;background:${rgba(P.accent2, 0.6)};transform:rotate(-3deg)`);
    const n = lines.length ? mk(root, 'a', lines.map((l) => esc(W_(l.text))).join('<br>'), `left:120px;top:1060px;width:840px;padding:50px;box-sizing:border-box;background:${NOTE_BG};font:${hand(72)};color:#2b2118;box-shadow:0 20px 40px rgba(0,0,0,.3)`) : null;
    const bye = p.bye ? mk(root, 'a ctr', esc(W_(p.bye.text)), `top:1560px;font:${hand(150)};color:#fff;text-shadow:0 6px 18px rgba(0,0,0,.4)`) : null;
    ev(shot.start, 'paper', 0.7); ev(t1, 'pencil', 0.5); if (bye) ev(tB, 'pencil', 0.7);
    return (t) => {
      const s = spring(t, shot.start); vis(pol, clamp((t - shot.start) * 5)); pol.style.transform = `rotate(${(-3 + (1 - s) * 20).toFixed(2)}deg) translateY(${((1 - s) * -500).toFixed(0)}px)`;
      if (n) { const q = spring(t, t1 - 0.1); vis(n, clamp((t - t1 + 0.1) * 5)); n.style.transform = `rotate(${(2 + (1 - q) * -15).toFixed(2)}deg)`; }
      if (bye) vis(bye, eo((t - tB) / 0.4));
      void t2;
    };
  };
  // fin de journal: plateau, logo en incrustation, bandeau « à bientôt »
  EV_.slate = function (root, shot, p) {
    const { lines, t1, tB } = endTimes(shot, p);
    mk(root, 'a', '', `left:0;top:0;width:1080px;height:1920px;background:repeating-linear-gradient(135deg,${rgba('#FFFFFF', 0.04)} 0 40px,transparent 40px 80px)`);
    const lg = mk(root, 'a', `<div style="padding:60px 70px">${logoHTML(700, 360)}</div>`, 'left:90px;top:360px;width:900px;background:#fff;box-shadow:0 40px 90px rgba(0,0,0,.5)');
    const hl = lines[0] ? mk(root, 'a', `<span style="display:block;background:#fff;color:#111;font-family:${HEAD};font-size:96px;line-height:1;padding:30px 50px">${sayUp(lines[0].text)}</span>`, `left:0;top:${420 + lg.offsetHeight}px;width:1000px`) : null;
    if (hl) fit(hl.firstElementChild, 1000, 96, 50, 400);
    const bye = p.bye ? mk(root, 'a', `<span style="display:inline-block;background:${P.bad};color:#fff;font-family:${HEAD};font-size:120px;padding:18px 60px">${sayUp(p.bye.text)}</span>`, `left:0;top:${480 + lg.offsetHeight + (hl ? hl.offsetHeight : 0)}px`) : null;
    ev(shot.start, 'whoosh', 0.6); ev(shot.start + 0.2, 'ping', 0.6); if (bye) ev(tB, 'whoosh', 0.5);
    return (t) => {
      const s = spring(t, shot.start); vis(lg, clamp((t - shot.start) * 5)); lg.style.transform = `scale(${(0.8 + 0.2 * s).toFixed(3)})`;
      if (hl) { const u = eo((t - t1) / 0.3); hl.style.transform = `translateX(${((1 - u) * -1100).toFixed(0)}px)`; }
      if (bye) { const u = eo((t - tB) / 0.3); bye.style.transform = `translateX(${((1 - u) * -1100).toFixed(0)}px)`; }
    };
  };
  // quatrième de couverture: titre du magazine, accroches, logo encadré, code-barres
  EV_.backcover = function (root, shot, p) {
    const { lines, t1, t2, tB } = endTimes(shot, p);
    mk(root, 'a', '', `left:0;top:0;width:1080px;height:1920px;background:${P.light}`);
    const mast = mk(root, 'a ctr', esc(up(BRAND || '')), `top:80px;left:40px;width:1000px;font-family:${HEAD};font-size:250px;line-height:1;color:${P.ink}`); fit(mast, 1000, 250, 90, 280);
    mk(root, 'a', '', `left:60px;top:${100 + mast.offsetHeight}px;width:960px;height:8px;background:${P.accent}`);
    let cy = 150 + mast.offsetHeight;
    const cl = lines.map((l, i) => { const e = mk(root, 'a', esc(W_(l.text)), `left:60px;top:${cy}px;width:960px;font:italic 400 ${i ? 70 : 92}px/1.05 'DMSerif';color:${i ? P.accent : P.ink}`); cy += e.offsetHeight + 30; return e; });
    const box = mk(root, 'a', `<div style="padding:50px">${logoHTML(600, 360)}</div>`, `left:190px;top:${Math.max(760, cy + 60)}px;width:700px;border:6px solid ${P.ink};background:#fff`);
    let bars = ''; for (let i = 0; i < 40; i++) bars += `<rect x="${i * 7}" y="0" width="${2 + Math.floor(rv(i + 300) * 4)}" height="110" fill="${P.ink}"/>`;
    mk(root, 'a', `<svg width="280" height="110">${bars}</svg>`, 'right:60px;bottom:90px');
    const bye = p.bye ? mk(root, 'a', `<div style="width:340px;height:340px;border-radius:50%;background:${P.accent};display:flex;align-items:center;justify-content:center;text-align:center;font:italic 400 84px/1 'DMSerif';color:${on(P.accent)};transform:rotate(-12deg)">${esc(W_(p.bye.text))}</div>`, 'left:70px;top:1470px') : null;
    ev(shot.start, 'paper', 0.7); ev(t1, 'pop_low', 0.4); if (bye) { ev(tB, 'stamp', 0.6); IMPACTS.push(tB); }
    return (t) => {
      vis(mast, eo((t - shot.start) / 0.35));
      cl.forEach((c, i) => vis(c, eo((t - (i ? t2 : t1)) / 0.4)));
      const s = spring(t, shot.start + 0.2); vis(box, clamp((t - shot.start - 0.15) * 5)); box.style.transform = `scale(${(0.8 + 0.2 * s).toFixed(3)})`;
      if (bye) { const q = pop(t, tB, 18, 0.45); vis(bye, clamp((t - tB) * 8)); bye.style.transform = `scale(${(1.6 - 0.6 * q).toFixed(3)})`; }
    };
  };

  // ---------------------------------------------------------------- TAMPONS / ALERTES (flottants)
  const SV = {};
  const floatOut = (t, shot) => eio((t - shot.end + 0.2) / 0.25);
  SV.bubble = function (root, shot, p) {
    const b = mk(root, 'a', `<div style="display:flex;align-items:center;gap:24px"><div style="width:84px;height:84px;border-radius:22px;background:${P.bad};display:flex;align-items:center;justify-content:center;flex:none">${icon('alert', 50, '#fff', 2.6)}</div><div style="font:800 58px/1.1 Poppins;color:#111">${esc(W_(p.text || ''))}</div></div>`, 'left:60px;top:170px;width:960px;box-sizing:border-box;padding:30px 36px;background:rgba(255,255,255,.96);border-radius:40px;box-shadow:0 26px 60px rgba(0,0,0,.4)');
    const tS = wordTime(shot, p.at, 0.15); ev(tS, 'blip', 0.8); ev(tS + 0.05, 'pop', 0.5);
    return (t) => { const s = spring(t, tS), o = floatOut(t, shot); vis(b, clamp((t - tS) * 8) * (1 - o)); b.style.transform = `translateY(${((1 - s) * -300 - o * 200).toFixed(0)}px)`; };
  };
  SV.slam = function (root, shot, p) {
    const dim = mk(root, 'a', '', 'left:0;top:0;width:1080px;height:1920px;background:rgba(0,0,0,.55)');
    const w = mk(root, 'a ctr', sayUp(p.text), `top:640px;left:30px;width:1020px;font-family:${HEAD};font-size:230px;line-height:.95;color:${P.bad};${outlineCSS('#fff', 10)}`); fit(w, 1020, 230, 100, 640);
    const tS = wordTime(shot, p.at, 0.15); ev(tS, 'impact_big', 0.9); IMPACTS.push(tS); FLASHES.push(tS);
    return (t) => { const s = pop(t, tS, 20, 0.42), o = floatOut(t, shot); const a = clamp((t - tS + 0.05) * 10) * (1 - o); vis(dim, a); vis(w, a); w.style.transform = `scale(${(2.4 - 1.4 * s).toFixed(3)}) rotate(${((1 - s) * -8).toFixed(2)}deg)`; };
  };
  SV.marker = function (root, shot, p) {
    const mc = MONT.face === 'full' ? '#fff' : pick(BACK_BG, P.bad, P.ink);
    const w = mk(root, 'a ctr', esc(W_(p.text || '')), `top:250px;left:60px;width:960px;font:${hand(130)};color:${mc};${mc === '#fff' ? 'text-shadow:0 6px 20px rgba(0,0,0,.6)' : ''}`); fit(w, 960, 130, 60, 330);
    const c = mk(root, 'a', scribble(1000, w.offsetHeight + 120, P.bad, 14), 'left:40px;top:190px');
    const tS = wordTime(shot, p.at, 0.15); ev(tS, 'pencil', 0.8); ev(tS + 0.3, 'pencil', 0.6);
    return (t) => { const o = floatOut(t, shot); vis(w, eo((t - tS) / 0.25) * (1 - o)); vis(c, 1 - o); drawSvg(c, (t - tS - 0.15) / 0.55); };
  };
  SV.alert = function (root, shot, p) {
    const b = mk(root, 'a', `<div style="display:flex;align-items:stretch"><div style="background:${P.bad};padding:0 34px;display:flex;align-items:center;gap:14px;font:800 44px Poppins;color:#fff;letter-spacing:.1em">${icon('alert', 46, '#fff', 2.6)}ALERTE</div><div style="background:#fff;padding:22px 40px;font-family:${HEAD};font-size:84px;line-height:1;color:#111">${sayUp(p.text)}</div></div>`, 'left:0;top:1180px');
    const tS = wordTime(shot, p.at, 0.15); ev(tS - 0.1, 'whoosh', 0.6); ev(tS, 'ping', 0.6);
    return (t) => { const u = eo((t - tS + 0.1) / 0.3), o = floatOut(t, shot); b.style.transform = `translateX(${((1 - u) * -1100 - o * 1100).toFixed(0)}px)`; };
  };
  SV.sticker = function (root, shot, p) {
    let pts = ''; for (let i = 0; i < 32; i++) { const a = i / 32 * Math.PI * 2, r = i % 2 ? 250 : 290; pts += `${(300 + r * Math.cos(a)).toFixed(1)},${(300 + r * Math.sin(a)).toFixed(1)} `; }
    const st = mk(root, 'a', `<svg width="600" height="600" style="position:absolute;left:0;top:0"><polygon points="${pts}" fill="${P.bad}"/></svg><div style="position:absolute;left:90px;top:0;width:420px;height:600px;display:flex;align-items:center;justify-content:center;text-align:center;font-family:${HEAD};font-size:96px;line-height:1;color:#fff">${sayUp(p.text)}</div>`, 'left:470px;top:260px;width:600px;height:600px');
    fit(st.lastElementChild, 420, 96, 44, 420);
    const tS = wordTime(shot, p.at, 0.15); ev(tS, 'pop_low', 0.8); ev(tS + 0.05, 'impact', 0.5); IMPACTS.push(tS);
    return (t) => { const s = pop(t, tS, 18, 0.45), o = floatOut(t, shot); vis(st, clamp((t - tS) * 8) * (1 - o)); st.style.transform = `rotate(${(14 + (1 - s) * 60).toFixed(1)}deg) scale(${(0.2 + 0.8 * s).toFixed(3)})`; };
  };
  SV.band = function (root, shot, p) {
    const w = mk(root, 'a', `<span style="position:relative;display:inline-block">${sayUp(p.text)}<i style="position:absolute;left:-10px;right:-10px;top:48%;height:14px;background:${P.bad};transform-origin:0 50%" class="x"></i></span>`, `left:60px;top:1250px;width:960px;font-family:${HEAD};font-size:140px;line-height:1;color:${P.bad}`);
    fit(w, 960, 140, 60, 300); const x = w.querySelector('.x');
    const tS = wordTime(shot, p.at, 0.15); ev(tS, 'whoosh', 0.5); ev(tS + 0.45, 'tear', 0.4);
    return (t) => { const o = floatOut(t, shot); vis(w, eo((t - tS) / 0.25) * (1 - o)); x.style.transform = `scaleX(${eo((t - tS - 0.45) / 0.3).toFixed(3)})`; };
  };

  // ---------------------------------------------------------------- MOTS-CLÉS (flottants)
  const KV = {};
  KV.tag = function (root, shot, p) {
    const b = mk(root, 'a', `<div style="display:flex;align-items:stretch"><div style="background:${P.accent};padding:0 26px;display:flex;align-items:center">${motif(52, on(P.accent))}</div><div style="background:rgba(10,10,14,.85);padding:18px 34px;font:800 50px Poppins;color:#fff;letter-spacing:.06em">${sayUp(p.text)}</div></div>`, 'left:0;top:200px');
    const tK = wordTime(shot, p.at, 0.1); ev(tK, 'whoosh', 0.4); ev(tK + 0.05, 'blip', 0.4);
    return (t) => { const u = eo((t - tK) / 0.3), o = floatOut(t, shot); b.style.transform = `translateX(${((1 - u) * -900 - o * 900).toFixed(0)}px)`; };
  };
  KV.note = function (root, shot, p) {
    const n = mk(root, 'a', esc(W_(p.text || '')), `left:560px;top:170px;max-width:460px;padding:30px 36px;background:${NOTE_BG};font:${hand(66)};color:#2b2118;box-shadow:0 16px 30px rgba(0,0,0,.3)`);
    mk(n, 'a', '', `left:50%;top:-20px;width:170px;height:44px;margin-left:-85px;background:${rgba('#FFFFFF', 0.6)};transform:rotate(-4deg)`);
    const tK = wordTime(shot, p.at, 0.1); ev(tK, 'paper', 0.6);
    return (t) => { const s = spring(t, tK), o = floatOut(t, shot); vis(n, clamp((t - tK) * 6) * (1 - o)); n.style.transform = `rotate(${(4 + (1 - s) * 20).toFixed(2)}deg) scale(${(0.6 + 0.4 * s).toFixed(3)})`; };
  };
  KV.bubble = function (root, shot, p) {
    const b = mk(root, 'a', `<span style="font:800 56px Poppins;color:${on(P.accent)}">${esc(W_(p.text || ''))}</span>`, `right:60px;top:200px;padding:26px 44px;background:${P.accent};border-radius:46px 46px 12px 46px;box-shadow:0 18px 40px rgba(0,0,0,.35);transform-origin:100% 100%`);
    const tK = wordTime(shot, p.at, 0.1); ev(tK, 'pop', 0.7);
    return (t) => { const s = spring(t, tK), o = floatOut(t, shot); vis(b, clamp((t - tK) * 8) * (1 - o)); b.style.transform = `scale(${(0.3 + 0.7 * s).toFixed(3)})`; };
  };
  KV.kinetic = function (root, shot, p) {
    const w = mk(root, 'a ctr', sayUp(p.text), `top:260px;left:30px;width:1020px;font-family:${HEAD};font-size:170px;line-height:.95;color:transparent;${outlineCSS('#fff', 6)}`); fit(w, 1020, 170, 70, 400);
    const tK = wordTime(shot, p.at, 0.1); ev(tK, 'impact', 0.5); IMPACTS.push(tK);
    return (t) => { const s = pop(t, tK, 18, 0.45), o = floatOut(t, shot); vis(w, clamp((t - tK) * 10) * (1 - o)); w.style.transform = `scale(${(1.8 - 0.8 * s).toFixed(3)})`; };
  };
  KV.coverline = function (root, shot, p) {
    const w = mk(root, 'a', `<div style="font:800 30px Poppins;letter-spacing:.24em;color:${P.accent}">À LA UNE</div><div style="font:italic 400 84px/1.02 'DMSerif';color:#fff;text-shadow:0 4px 20px rgba(0,0,0,.5)">${esc(W_(p.text || ''))}</div>`, 'right:60px;top:380px;width:560px;text-align:right');
    const tK = wordTime(shot, p.at, 0.1); ev(tK, 'pop_low', 0.5);
    return (t) => { const u = eo((t - tK) / 0.35), o = floatOut(t, shot); vis(w, u * (1 - o)); w.style.transform = `translateX(${((1 - u) * 80).toFixed(0)}px)`; };
  };
  KV.band = function (root, shot, p) {
    const w = mk(root, 'a', `<span style="display:inline-flex;align-items:center;gap:18px">${motif(70, P.accent)}${sayUp(p.text)}</span>`, `left:60px;top:1250px;font-family:${HEAD};font-size:110px;line-height:1;color:${pick(P.dark, P.light, '#fff')}`);
    const tK = wordTime(shot, p.at, 0.1); ev(tK, 'whoosh', 0.4);
    return (t) => { const u = eo((t - tK) / 0.3), o = floatOut(t, shot); vis(w, u * (1 - o)); w.style.clipPath = `inset(0 ${((1 - u) * 100).toFixed(1)}% 0 0)`; };
  };


  // ================================================================== 5 NOUVELLES GRAMMAIRES DE MONTAGE
  // stories · jeu_video · podcast · documentaire · bento — chacune avec ses objets à elle.
  Object.assign(GRAM, {
    stories: { q: 'igquestion', c: 'igpoll', e: 'igprofile', s: 'igalert', k: 'hashtag' },
    jeu_video: { q: 'quest', c: 'rpgchoice', e: 'levelup', s: 'damage', k: 'achievement' },
    podcast: { q: 'episode', c: 'micmail', e: 'cover', s: 'soundbite', k: 'chaptertag' },
    documentaire: { q: 'chaptercard', c: 'letter', e: 'credits', s: 'doctitle', k: 'location' },
    bento: { q: 'bentoq', c: 'bentoc', e: 'bentoe', s: 'bentos', k: 'bentok' },
    voyage: { q: 'signpost', c: 'boarding', e: 'arrival', s: 'roadsign', k: 'pin' },
  });
  G = GRAM[ST.montage] || GRAM.plein_cadre;
  const VOICE = (t, i) => { const w = WORDS.find((x) => t >= x.s - 0.02 && t <= x.e + 0.05); if (!w) return 0.04 + 0.05 * rnd(i + Math.floor(t * 18)); return 0.25 + 0.75 * rnd(i * 1.7 + Math.floor(t * 15)) * (0.55 + 0.45 * Math.sin(i * 0.55 + t * 9) ** 2); };
  const IG = `linear-gradient(135deg,#FEDA75,#FA7E1E 30%,#D62976 60%,#962FBF 85%,#4F5BD5)`;
  const PIX = "'Bebas'";
  const mmss = (s) => `${String(Math.floor(s / 60)).padStart(1, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
  const ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII'];
  let chapN = 0;

  // ---------------------------------------------------------------- STORIES (Instagram)
  QV.igquestion = function (root, shot, p) {
    mk(root, 'a', '', `left:0;top:0;width:1080px;height:1920px;background:${IG};opacity:.92`);
    const st = mk(root, 'a', `<div style="padding:50px 50px 36px;background:${IG};border-radius:44px 44px 0 0;text-align:center"><div style="font:800 34px Poppins;letter-spacing:.06em;color:#fff;opacity:.9">UNE QUESTION</div><div class="t" style="margin-top:12px;font:800 110px/1.02 Poppins;color:#fff"></div></div><div style="padding:40px 50px 50px;text-align:center"><div class="s" style="display:inline-block;padding:26px 44px;border-radius:30px;background:#EFEFEF;font:700 56px Poppins;color:#262626">…</div></div>`, 'left:110px;top:560px;width:860px;background:#fff;border-radius:44px;box-shadow:0 40px 90px rgba(0,0,0,.35)');
    const tt = st.querySelector('.t'), ss = st.querySelector('.s');
    tt.textContent = (p.title || '') + ' ?';
    const tT = wordTime(shot, p.at, 0.05), tS = p.sub ? wordTime(shot, p.sub_at, 0.5) : 0;
    ev(shot.start, 'pop', 0.7); ev(tT, 'pop_high', 0.5); if (p.sub) tickType(tS, p.sub, 0.04);
    return (t) => {
      const s = spring(t, shot.start + 0.05); vis(st, clamp((t - shot.start) * 5)); st.style.transform = `scale(${(0.5 + 0.5 * s).toFixed(3)}) rotate(${((1 - s) * -8).toFixed(2)}deg)`;
      tt.style.opacity = clamp((t - tT) * 5).toFixed(2);
      if (p.sub) typeText(ss, W_(p.sub), t, tS, 0.04); else ss.textContent = '…';
    };
  };
  CV.igpoll = function (root, shot, p) {
    mk(root, 'a', '', `left:0;top:0;width:1080px;height:1920px;background:${IG};opacity:.9`);
    const opts = (p.options || []).slice(0, 2), ts = ctaTimes(shot, opts);
    const card = mk(root, 'a', `<div style="padding:46px 50px 20px;text-align:center;font:800 64px/1.1 Poppins;color:#262626">${TU ? 'Écris en commentaire' : 'Écrivez en commentaire'}</div>`, 'left:90px;top:420px;width:900px;background:#fff;border-radius:44px;box-shadow:0 40px 90px rgba(0,0,0,.35);padding-bottom:30px');
    const rows = opts.map((o) => {
      const r = mk(card, '', `<div style="position:relative;margin:18px 44px;height:130px;border-radius:26px;background:#EFEFEF;overflow:hidden"><div class="f" style="position:absolute;inset:0;background:${IG};transform-origin:0 50%;transform:scaleX(0)"></div><div class="t" style="position:absolute;left:36px;top:0;height:130px;display:flex;align-items:center;font:800 56px Poppins;color:#262626"></div><div class="k" style="position:absolute;right:26px;top:31px;width:68px;height:68px;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;opacity:0">${icon('check', 44, '#D62976', 3.4)}</div></div>`);
      r._t = r.querySelector('.t'); r._f = r.querySelector('.f'); r._k = r.querySelector('.k'); r._text = up(o.text || ''); return r;
    });
    ts.forEach((t0) => { ev(t0, 'pop', 0.6); ev(t0 + 0.5, 'ding', 0.4); });
    let heart = null, tR = 0;
    if (p.stamp || p.duo_at != null) {
      tR = p.stamp ? wordTime(shot, p.stamp_at || p.stamp, 0.85) : wordTime(shot, p.duo_at, 0.8);
      heart = mk(root, 'a ctr', `<span style="display:inline-flex;align-items:center;gap:20px;background:#fff;padding:26px 50px;border-radius:999px;font:800 60px Poppins;color:#262626;box-shadow:0 20px 50px rgba(0,0,0,.3)">${icon('calendar', 60, '#D62976', 2.6)}${sayUp(p.stamp || 'Rendez-vous')}</span>`, 'top:1300px');
      ev(tR, 'pop', 0.8);
    }
    return (t) => {
      const s = spring(t, shot.start + 0.05); vis(card, clamp((t - shot.start) * 5)); card.style.transform = `scale(${(0.6 + 0.4 * s).toFixed(3)})`;
      rows.forEach((r, i) => { typeText(r._t, r._text, t, ts[i] - 0.4, 0.03, false); if (t < ts[i] - 0.4) r._t.textContent = '·'.repeat(3); r._f.style.transform = `scaleX(${(eo((t - ts[i]) / 0.6) * 0.999).toFixed(3)})`; r._t.style.color = t > ts[i] + 0.3 ? '#fff' : '#262626'; r._k.style.opacity = clamp((t - ts[i] - 0.5) * 5).toFixed(2); });
      if (heart) { const q = spring(t, tR); vis(heart, clamp((t - tR) * 8)); heart.style.transform = `scale(${(0.3 + 0.7 * q).toFixed(3)})`; }
    };
  };
  EV_.igprofile = function (root, shot, p) {
    const { lines, t1, tB } = endTimes(shot, p);
    mk(root, 'a', '', `left:0;top:0;width:1080px;height:1920px;background:${IG};opacity:.95`);
    const card = mk(root, 'a', `<div style="width:300px;height:300px;margin:0 auto;border-radius:50%;padding:10px;background:${IG}"><div style="width:280px;height:280px;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;overflow:hidden"><div style="width:240px">${logoHTML(240, 240)}</div></div></div><div style="margin-top:26px;font:800 64px Poppins;color:#262626">${esc(BRAND || '')}</div><div class="l" style="margin-top:18px;font:500 44px/1.3 Poppins;color:#555;padding:0 40px">${lines.map((l) => esc(W_(l.text))).join('<br>')}</div><div class="b" style="margin:40px auto 0;width:600px;height:120px;border-radius:26px;background:#0095F6;display:flex;align-items:center;justify-content:center;font:800 52px Poppins;color:#fff">S'abonner</div>`, 'left:90px;top:380px;width:900px;padding:60px 0 60px;background:#fff;border-radius:48px;text-align:center;box-shadow:0 40px 90px rgba(0,0,0,.35)');
    const btn = card.querySelector('.b'), ln = card.querySelector('.l');
    const bye = p.bye ? mk(root, 'a ctr', sayUp(p.bye.text), `top:1560px;font:800 110px Poppins;color:#fff;text-shadow:0 8px 30px rgba(0,0,0,.3)`) : null;
    ev(shot.start, 'pop', 0.7); ev(t1 + 1.2, 'click', 0.7); if (bye) ev(tB, 'pop', 0.7);
    return (t) => {
      const s = spring(t, shot.start); vis(card, clamp((t - shot.start) * 5)); card.style.transform = `translateY(${((1 - s) * 400).toFixed(0)}px)`;
      vis(ln, eo((t - t1) / 0.4));
      const pressed = t > t1 + 1.2; btn.style.background = pressed ? '#EFEFEF' : '#0095F6'; btn.style.color = pressed ? '#262626' : '#fff'; btn.textContent = pressed ? 'Abonné ✓' : "S'abonner";
      btn.style.transform = `scale(${t > t1 + 1.2 && t < t1 + 1.35 ? 0.94 : 1})`;
      if (bye) { const q = spring(t, tB); vis(bye, clamp((t - tB) * 8)); bye.style.transform = `scale(${(0.4 + 0.6 * q).toFixed(3)})`; }
    };
  };
  SV.igalert = function (root, shot, p) {
    const b = mk(root, 'a ctr', `<span style="display:inline-block;padding:18px 40px;border-radius:22px;background:#fff;font:800 88px/1.05 Poppins;color:#262626;transform:rotate(-4deg);box-shadow:0 20px 50px rgba(0,0,0,.3)">${esc(W_(p.text || ''))}</span><div style="margin-top:34px;display:inline-flex;gap:18px">${[0, 1, 2].map(() => `<span style="width:110px;height:110px;border-radius:50%;background:#fff;display:inline-flex;align-items:center;justify-content:center;box-shadow:0 10px 26px rgba(0,0,0,.25)">${icon('alert', 64, '#D62976', 2.6)}</span>`).join('')}</div>`, 'top:300px');
    const tS = wordTime(shot, p.at, 0.15); ev(tS, 'pop', 0.8); ev(tS + 0.15, 'pop_high', 0.4);
    return (t) => { const s = spring(t, tS), o = floatOut(t, shot); vis(b, clamp((t - tS) * 8) * (1 - o)); b.style.transform = `scale(${(0.3 + 0.7 * s).toFixed(3)})`; };
  };
  KV.hashtag = function (root, shot, p) {
    const tag = '#' + String(p.text || '').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^A-Za-z0-9]/g, '').toUpperCase();
    const b = mk(root, 'a', `<span style="display:inline-block;padding:18px 36px;border-radius:18px;background:#fff;font:800 60px Poppins;background-clip:padding-box"><span style="background:${IG};-webkit-background-clip:text;color:transparent">${esc(tag)}</span></span>`, 'left:120px;top:300px;transform-origin:0 50%');
    const tK = wordTime(shot, p.at, 0.1); ev(tK, 'pop', 0.7);
    return (t) => { const s = spring(t, tK), o = floatOut(t, shot); vis(b, clamp((t - tK) * 8) * (1 - o)); b.style.transform = `rotate(${(-6 + (1 - s) * 20).toFixed(2)}deg) scale(${(0.4 + 0.6 * s).toFixed(3)})`; };
  };
  // idée = texte « avec fond » façon story, lignes surlignées une à une
  function stickerSkin(root, shot, p) {
    const col = [P.accent, '#FFFFFF', P.accent2][cardK++ % 3];
    const box = mk(root, 'a ctr', `<span class="l" style="font:800 84px/1.32 Poppins;color:${on(col)};background:${col};padding:6px 26px;border-radius:18px;-webkit-box-decoration-break:clone;box-decoration-break:clone">${esc(W_(p.title || ''))}</span>${p.sub ? `<div class="s" style="margin-top:26px"><span style="display:inline-block;padding:14px 30px;border-radius:999px;background:rgba(0,0,0,.55);font:700 44px Poppins;color:#fff">${esc(W_(p.sub))}</span></div>` : ''}`, 'top:1020px;left:70px;width:940px');
    const sub = box.querySelector('.s');
    const tT = wordTime(shot, p.at, 0.05), tS = p.sub ? wordTime(shot, p.sub_at, 0.6) : 0;
    ev(tT, 'pop', 0.7); if (sub) ev(tS, 'pop_high', 0.4);
    return (t) => { const s = spring(t, tT), o = floatOut(t, shot); vis(box, clamp((t - tT) * 8) * (1 - o)); box.style.transform = `rotate(${(-3 + (1 - s) * 12).toFixed(2)}deg) scale(${(0.5 + 0.5 * s).toFixed(3)})`; if (sub) vis(sub, eo((t - tS) / 0.3)); };
  }

  // ---------------------------------------------------------------- JEU VIDÉO (HUD + RPG)
  const dialogBox = (root, y, h) => mk(root, 'a', '', `left:40px;top:${y}px;width:1000px;height:${h}px;box-sizing:border-box;background:rgba(12,10,40,.93);border:8px solid #fff;outline:6px solid #0C0A28;border-radius:20px;box-shadow:0 20px 60px rgba(0,0,0,.5)`);
  function dialogSkin(root, shot, p) {
    const box = dialogBox(root, 1380, 400);
    const name = mk(box, 'a', esc(up(p.kicker || BRAND || 'Info')), `left:30px;top:-44px;padding:10px 28px;background:${P.accent};color:${on(P.accent)};font:400 52px/1 ${PIX};letter-spacing:.06em;border:6px solid #fff;border-radius:12px`);
    const tx = mk(box, 'a', '', 'left:44px;top:56px;width:900px;font:700 56px/1.3 Poppins;color:#fff');
    const full = W_(p.title || '') + (p.sub ? ' — ' + W_(p.sub) : '');
    const arrow = mk(box, 'a', '▼', `right:34px;bottom:22px;font:400 44px ${PIX};color:${P.accent}`);
    const tT = wordTime(shot, p.at, 0.05) - 0.1; const cps = Math.min(0.045, Math.max(0.02, (shot.end - tT - 0.8) / Math.max(1, full.length)));
    ev(shot.start, 'blip', 0.6); for (let c = 0; c < full.length; c += 2) ev(tT + c * cps, 'blip', 0.18);
    void name;
    return (t) => { const o = floatOut(t, shot), u = eo((t - shot.start) / 0.2); box.style.transform = `scaleY(${(u * (1 - o)).toFixed(3)})`; box.style.transformOrigin = '50% 100%'; typeText(tx, full, t, tT, cps, false); arrow.style.opacity = t > tT + full.length * cps && Math.floor(t * 3) % 2 ? '1' : '0'; };
  }
  QV.quest = function (root, shot, p) {
    mk(root, 'a', '', `left:0;top:0;width:1080px;height:1920px;background:repeating-linear-gradient(0deg,rgba(255,255,255,.035) 0 3px,transparent 3px 8px)`);
    const ban = mk(root, 'a ctr', `<span style="display:inline-block;padding:18px 60px;background:${P.accent};color:${on(P.accent)};font:400 90px/1 ${PIX};letter-spacing:.08em;border:8px solid #fff">NOUVELLE QUÊTE !</span>`, 'top:330px');
    const box = dialogBox(root, 560, 760);
    const ttl = mk(box, 'a', esc(up((p.title || '') + ' ?')), `left:50px;top:60px;width:880px;font:400 190px/.95 ${PIX};color:#fff`); fit(ttl, 880, 190, 90, 400);
    const obj = mk(box, 'a', `<div style="font:400 44px ${PIX};color:${P.accent2};letter-spacing:.1em">OBJECTIF</div><div style="display:flex;align-items:center;gap:26px;margin-top:10px"><span class="ck" style="width:74px;height:74px;border:6px solid #fff;display:inline-flex;align-items:center;justify-content:center"></span><span style="font:700 58px/1.2 Poppins;color:#fff">${esc(W_(p.sub || ''))}</span></div>`, `left:50px;top:${100 + ttl.offsetHeight}px;width:880px`);
    const ck = obj.querySelector('.ck');
    const tT = wordTime(shot, p.at, 0.05), tS = p.sub ? wordTime(shot, p.sub_at, 0.5) : tT + 0.6;
    ev(shot.start, 'riser_short', 0.6); ev(shot.start + 0.2, 'ding', 0.7); ev(tT, 'impact', 0.5); ev(tS, 'blip', 0.5);
    return (t) => {
      const s = pop(t, shot.start + 0.1, 16, 0.45); vis(ban, clamp((t - shot.start) * 8)); ban.style.transform = `scale(${(0.3 + 0.7 * s).toFixed(3)})`;
      box.style.transform = `scaleY(${eo((t - shot.start - 0.2) / 0.25).toFixed(3)})`;
      vis(ttl, clamp((t - tT) * 8)); vis(obj, eo((t - tS) / 0.3)); ck.style.background = Math.floor(t * 2) % 2 ? rgba(P.accent2, 0.4) : 'transparent';
    };
  };
  CV.rpgchoice = function (root, shot, p) {
    const opts = (p.options || []).slice(0, 2), ts = ctaTimes(shot, opts);
    const box = dialogBox(root, 520, 180 + opts.length * 150);
    mk(box, 'a', esc(up(TU ? 'Que réponds-tu en commentaire ?' : 'Que répondez-vous en commentaire ?')), `left:50px;top:40px;width:900px;font:400 64px/1 ${PIX};color:${P.accent2}`);
    const rows = opts.map((o, i) => mk(box, 'a', `<span class="cur" style="display:inline-block;width:70px;color:${P.accent}">►</span>${sayUp(o.text)}`, `left:50px;top:${150 + i * 150}px;font:400 96px/1 ${PIX};color:#fff`));
    let lv = null, tR = 0;
    if (p.stamp || p.duo_at != null) {
      tR = p.stamp ? wordTime(shot, p.stamp_at || p.stamp, 0.85) : wordTime(shot, p.duo_at, 0.8);
      lv = mk(root, 'a ctr', `<span style="display:inline-block;padding:24px 60px;background:#FFD23F;color:#1a1200;font:400 110px/1 ${PIX};border:8px solid #fff;box-shadow:0 0 0 8px #1a1200">${sayUp(p.stamp || 'Rendez-vous')} +100 XP</span>`, `top:${760 + opts.length * 150}px`);
      ev(tR, 'ding', 0.8); ev(tR + 0.05, 'shimmer', 0.6);
    }
    ts.forEach((t0) => ev(t0, 'blip', 0.7));
    return (t) => {
      box.style.transform = `scaleY(${eo((t - shot.start) / 0.25).toFixed(3)})`;
      const sel = ts.reduce((k, t0, i) => (t >= t0 ? i : k), -1);
      rows.forEach((r, i) => { vis(r, clamp((t - ts[i] + 0.4) * 5)); r.querySelector('.cur').style.visibility = sel === i && Math.floor(t * 4) % 2 === 0 ? 'visible' : sel === i ? 'visible' : 'hidden'; r.style.color = sel === i ? P.accent2 : '#fff'; });
      if (lv) { const s = pop(t, tR, 16, 0.45); vis(lv, clamp((t - tR) * 8)); lv.style.transform = `scale(${(0.3 + 0.7 * s).toFixed(3)})`; }
    };
  };
  EV_.levelup = function (root, shot, p) {
    const { lines, t1, tB } = endTimes(shot, p);
    const star = (c) => `<svg width="150" height="150" viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z" fill="${c}" stroke="#fff" stroke-width="1"/></svg>`;
    const head = mk(root, 'a ctr', 'NIVEAU TERMINÉ !', `top:220px;font:400 150px/1 ${PIX};color:#FFD23F;text-shadow:0 8px 0 #7a4b00`);
    const stars = [0, 1, 2].map((i) => mk(root, 'a', star('#FFD23F'), `left:${240 + i * 220}px;top:${420 - (i === 1 ? 40 : 0)}px`));
    const box = dialogBox(root, 700, 520);
    mk(box, 'a', `<div style="padding:60px 40px;background:#fff;border-radius:10px;margin:40px">${logoHTML(640, 280)}</div>`, 'left:0;top:0;width:984px');
    const l1 = lines[0] ? mk(root, 'a ctr', sayUp(lines[0].text), `top:1270px;left:60px;width:960px;font:400 90px/1 ${PIX};color:#fff`) : null;
    const bye = p.bye ? mk(root, 'a ctr', `<span style="display:inline-block;padding:20px 60px;background:${P.accent};color:${on(P.accent)};font:400 120px/1 ${PIX};border:8px solid #fff">${sayUp(p.bye.text)}</span>`, 'top:1480px') : null;
    ev(shot.start, 'riser_short', 0.6); [0, 1, 2].forEach((i) => ev(shot.start + 0.4 + i * 0.22, 'ding', 0.6)); if (bye) ev(tB, 'impact', 0.6);
    return (t) => {
      const s = pop(t, shot.start + 0.05, 14, 0.5); vis(head, clamp((t - shot.start) * 8)); head.style.transform = `scale(${(0.4 + 0.6 * s).toFixed(3)})`;
      stars.forEach((e, i) => { const q = pop(t, shot.start + 0.4 + i * 0.22, 18, 0.45); vis(e, clamp((t - shot.start - 0.4 - i * 0.22) * 8)); e.style.transform = `scale(${(0.2 + 0.8 * q).toFixed(3)}) rotate(${((1 - q) * 90).toFixed(0)}deg)`; });
      box.style.transform = `scaleY(${eo((t - shot.start - 0.3) / 0.25).toFixed(3)})`;
      if (l1) vis(l1, eo((t - t1) / 0.3));
      if (bye) { const q = spring(t, tB); vis(bye, clamp((t - tB) * 8)); bye.style.transform = `scale(${(0.4 + 0.6 * q).toFixed(3)})`; }
    };
  };
  SV.damage = function (root, shot, p) {
    const fl = mk(root, 'a', '', 'left:0;top:0;width:1080px;height:1920px;background:radial-gradient(ellipse at 50% 50%,rgba(255,0,0,0) 40%,rgba(255,0,40,.55) 100%)');
    const w = mk(root, 'a ctr', `<div style="font:400 70px/1 ${PIX};color:#FFD23F;letter-spacing:.1em">COUP CRITIQUE !</div><div style="font:400 190px/.95 ${PIX};color:#fff;text-shadow:0 10px 0 #7a0010,0 0 30px rgba(255,0,40,.8)">${sayUp(p.text)}</div>`, 'top:360px;left:30px;width:1020px');
    const tS = wordTime(shot, p.at, 0.15); ev(tS, 'impact_big', 0.9); ev(tS + 0.05, 'glitch', 0.5); IMPACTS.push(tS);
    return (t) => { const o = floatOut(t, shot), s = pop(t, tS, 22, 0.4); vis(fl, clamp((t - tS) * 10) * (1 - o) * (0.6 + 0.4 * Math.abs(Math.sin(t * 10)))); vis(w, clamp((t - tS) * 10) * (1 - o)); w.style.transform = `translateY(${((1 - s) * -200).toFixed(0)}px)`; };
  };
  KV.achievement = function (root, shot, p) {
    const b = mk(root, 'a', `<div style="display:flex;align-items:center;gap:26px"><div style="width:110px;height:110px;border-radius:50%;background:#FFD23F;display:flex;align-items:center;justify-content:center;flex:none">${icon('crown', 64, '#1a1200', 2.6)}</div><div><div style="font:400 40px/1 ${PIX};color:#FFD23F;letter-spacing:.12em">SUCCÈS DÉBLOQUÉ</div><div style="font:800 52px/1.1 Poppins;color:#fff">${esc(W_(p.text || ''))}</div></div></div>`, 'left:60px;top:250px;padding:26px 44px 26px 26px;background:rgba(12,10,40,.93);border:6px solid #FFD23F;border-radius:999px');
    const tK = wordTime(shot, p.at, 0.1); ev(tK, 'ding', 0.7); ev(tK + 0.05, 'shimmer', 0.5);
    return (t) => { const u = eo((t - tK) / 0.35), o = floatOut(t, shot); b.style.transform = `translateY(${((1 - u) * -400 - o * 400).toFixed(0)}px)`; };
  };

  // ---------------------------------------------------------------- PODCAST (cercle + onde)
  function chapterSkin(root, shot, p) {
    const n = ++chapN;
    const box = mk(root, 'a', `<div style="display:flex;align-items:center;gap:18px;font:800 30px Poppins;letter-spacing:.24em;color:${P.accent}">${icon('mic', 38, P.accent, 2.4)}CHAPITRE ${String(n).padStart(2, '0')}</div>`, 'left:70px;top:1090px;width:940px');
    const ttl = mk(box, '', '', `margin-top:14px;font-family:${HEAD};font-size:96px;line-height:1.02;color:${pick(BACK_BG, P.light, '#fff')};${SERIF ? 'font-style:italic' : ''}`);
    prepT(ttl, SERIF ? (p.title || '') : up(p.title || '')); fit(ttl, 940, 96, 48, 220);
    const sub = p.sub ? mk(box, '', esc(W_(p.sub)), `margin-top:10px;font:600 40px/1.25 Poppins;color:${rgba(pick(BACK_BG, P.light, '#fff'), 0.7)}`) : null;
    const tT = wordTime(shot, p.at, 0.05), tS = p.sub ? wordTime(shot, p.sub_at, 0.6) : 0;
    ev(shot.start, 'blip', 0.4); sfxT(ttl, tT); if (sub) ev(tS, 'pop_low', 0.4);
    return (t) => { const { o, a } = inOut(t, shot); vis(box, a * (1 - o)); showT(ttl, t, tT); if (sub) vis(sub, eo((t - tS) / 0.35)); };
  }
  QV.episode = function (root, shot, p) {
    const bars = mk(root, 'a', Array.from({ length: 48 }, (_, i) => `<i style="position:absolute;left:${i * 21}px;bottom:0;width:12px;border-radius:6px;background:${rgba(P.accent, 0.55)}"></i>`).join(''), 'left:36px;top:1350px;width:1008px;height:260px');
    const lab = mk(root, 'a ctr', 'LA QUESTION DE L’ÉPISODE', `top:300px;font:800 36px Poppins;letter-spacing:.24em;color:${P.accent}`);
    const q = mk(root, 'a', `<span style="font:400 360px/0 DMSerif;color:${P.accent};vertical-align:-150px">“</span>`, 'left:60px;top:470px');
    const ttl = mk(root, 'a ctr', '', `top:560px;left:80px;width:920px;font:italic 400 180px/1 'DMSerif';color:#fff`); prepT(ttl, (p.title || '') + ' ?'); fit(ttl, 920, 180, 80, 400);
    const sub = p.sub ? mk(root, 'a ctr', esc(W_(p.sub)), `top:${620 + ttl.offsetHeight}px;left:80px;width:920px;font:600 64px/1.2 Poppins;color:${rgba('#FFFFFF', 0.8)}`) : null;
    const tT = wordTime(shot, p.at, 0.05), tS = p.sub ? wordTime(shot, p.sub_at, 0.5) : 0;
    ev(shot.start, 'riser_short', 0.4); sfxT(ttl, tT); if (sub) ev(tS, 'pop_low', 0.5);
    const bs = [...bars.children];
    return (t) => { vis(lab, eo((t - shot.start) / 0.3)); vis(q, eo((t - tT + 0.2) / 0.3)); showT(ttl, t, tT); if (sub) vis(sub, eo((t - tS) / 0.35)); bs.forEach((b, i) => { b.style.height = (20 + 220 * VOICE(t, i)).toFixed(0) + 'px'; }); };
  };
  CV.micmail = function (root, shot, p) {
    const opts = (p.options || []).slice(0, 2), ts = ctaTimes(shot, opts);
    const mic = mk(root, 'a ctr', `<div style="display:inline-flex;width:260px;height:260px;border-radius:50%;background:${P.accent};align-items:center;justify-content:center;box-shadow:0 0 0 24px ${rgba(P.accent, 0.2)},0 0 0 48px ${rgba(P.accent, 0.08)}">${icon('mic', 140, on(P.accent), 2)}</div><div style="margin-top:50px;font:800 70px Poppins;color:#fff">${TU ? 'À toi le micro' : 'À vous le micro'}</div><div style="margin-top:8px;font:600 40px Poppins;color:rgba(255,255,255,.65)">${TU ? 'écris en commentaire' : 'écrivez en commentaire'}</div>`, 'top:220px');
    const msgs = opts.map((o, i) => mk(root, 'a', `<div style="display:flex;align-items:center;gap:22px">${icon('message', 52, P.accent2, 2.4)}<span style="font:800 60px Poppins;color:#111">${sayUp(o.text)}</span></div>`, `left:${i ? 170 : 90}px;top:${870 + i * 190}px;padding:30px 44px;background:#fff;border-radius:40px 40px 40px 10px;box-shadow:0 20px 44px rgba(0,0,0,.35)`));
    let rdv = null, tR = 0;
    if (p.stamp) { tR = wordTime(shot, p.stamp_at || p.stamp, 0.85); rdv = mk(root, 'a ctr', `<span style="display:inline-block;padding:22px 56px;border-radius:999px;border:6px solid ${P.accent};font:800 64px Poppins;color:#fff">${sayUp(p.stamp)}</span>`, `top:${900 + opts.length * 190 + 60}px`); ev(tR, 'ding', 0.7); }
    ts.forEach((t0) => ev(t0, 'pop', 0.7));
    return (t) => { const s = spring(t, shot.start); vis(mic, clamp((t - shot.start) * 5)); mic.style.transform = `scale(${(0.6 + 0.4 * s + 0.02 * Math.sin(t * 8)).toFixed(3)})`; msgs.forEach((m, i) => { const q = spring(t, ts[i]); vis(m, clamp((t - ts[i]) * 8)); m.style.transform = `scale(${(0.4 + 0.6 * q).toFixed(3)})`; m.style.transformOrigin = '0 100%'; }); if (rdv) vis(rdv, eo((t - tR) / 0.3)); };
  };
  EV_.cover = function (root, shot, p) {
    const { lines, t1, tB } = endTimes(shot, p);
    const cov = mk(root, 'a', `<div style="position:absolute;inset:0;background:${IG.replace('#FEDA75', P.accent).replace('#4F5BD5', P.dark2)};opacity:.9"></div><div style="position:absolute;left:60px;right:60px;top:70px;background:#fff;border-radius:30px;padding:50px 30px">${logoHTML(560, 280)}</div><div style="position:absolute;left:60px;bottom:60px;font:800 34px Poppins;letter-spacing:.24em;color:#fff">PODCAST · ${esc(up(BRAND || ''))}</div>`, 'left:170px;top:250px;width:740px;height:740px;border-radius:40px;overflow:hidden;box-shadow:0 40px 90px rgba(0,0,0,.5)');
    const l1 = lines.length ? mk(root, 'a ctr', lines.map((l) => esc(W_(l.text))).join('<br>'), `top:1060px;left:80px;width:920px;font:italic 400 76px/1.15 'DMSerif';color:#fff`) : null;
    const bar = mk(root, 'a', `<div style="height:14px;border-radius:7px;background:rgba(255,255,255,.2)"><div class="f" style="height:14px;border-radius:7px;background:${P.accent};transform-origin:0 50%"></div></div><div style="display:flex;justify-content:space-between;margin-top:14px;font:600 34px Poppins;color:rgba(255,255,255,.6)"><span>${mmss(T)}</span><span>${mmss(T)}</span></div>`, 'left:120px;top:1440px;width:840px');
    const bye = p.bye ? mk(root, 'a ctr', sayUp(p.bye.text), `top:1600px;font-family:${HEAD};font-size:120px;color:${P.accent}`) : null;
    ev(shot.start, 'whoosh', 0.5); if (bye) ev(tB, 'ding', 0.6);
    return (t) => { const s = spring(t, shot.start); vis(cov, clamp((t - shot.start) * 5)); cov.style.transform = `scale(${(0.7 + 0.3 * s).toFixed(3)})`; if (l1) vis(l1, eo((t - t1) / 0.4)); vis(bar, eo((t - shot.start - 0.3) / 0.3)); if (bye) vis(bye, eo((t - tB) / 0.3)); };
  };
  SV.soundbite = function (root, shot, p) {
    const b = mk(root, 'a ctr', `<div style="display:inline-block;padding:30px 50px;border-radius:30px;background:${P.bad}"><div style="font:800 30px Poppins;letter-spacing:.24em;color:#fff;opacity:.85">EXTRAIT</div><div style="font-family:${HEAD};font-size:110px;line-height:1;color:#fff">${sayUp(p.text)}</div></div>`, 'top:1060px');
    const tS = wordTime(shot, p.at, 0.15); ev(tS, 'impact', 0.6); IMPACTS.push(tS);
    return (t) => { const s = pop(t, tS, 18, 0.45), o = floatOut(t, shot); vis(b, clamp((t - tS) * 8) * (1 - o)); b.style.transform = `scale(${(0.3 + 0.7 * s).toFixed(3)})`; };
  };
  KV.chaptertag = function (root, shot, p) {
    const b = mk(root, 'a ctr', `<span style="display:inline-flex;align-items:center;gap:16px;padding:16px 36px;border-radius:999px;border:4px solid ${P.accent};font:800 46px Poppins;color:#fff">${motif(46, P.accent)}${sayUp(p.text)}</span>`, 'top:1080px');
    const tK = wordTime(shot, p.at, 0.1); ev(tK, 'pop_low', 0.6);
    return (t) => { const u = eo((t - tK) / 0.3), o = floatOut(t, shot); vis(b, u * (1 - o)); b.style.transform = `translateY(${((1 - u) * 40).toFixed(0)}px)`; };
  };

  // ---------------------------------------------------------------- DOCUMENTAIRE (cinéma)
  function docSkin(root, shot, p) {
    const box = mk(root, 'a', '', 'left:90px;top:1190px;width:900px');
    const kick = mk(box, '', esc(up(p.kicker || '')), `font:800 28px Poppins;letter-spacing:.34em;color:${pick('#000000', P.accent2, P.accent, '#fff')};height:${p.kicker ? 40 : 0}px`);
    const line = mk(box, '', '', `margin:10px 0 18px;width:420px;height:3px;background:#fff;transform-origin:0 50%`);
    const ttl = mk(box, '', '', `font:italic 400 88px/1.05 'DMSerif';color:#fff;text-shadow:0 4px 24px rgba(0,0,0,.7)`); prepT(ttl, p.title || ''); fit(ttl, 900, 88, 46, 200);
    const sub = p.sub ? mk(box, '', esc(W_(p.sub)), 'margin-top:10px;font:500 36px/1.3 Poppins;color:rgba(255,255,255,.8);text-shadow:0 2px 12px rgba(0,0,0,.7)') : null;
    const tT = wordTime(shot, p.at, 0.05), tS = p.sub ? wordTime(shot, p.sub_at, 0.6) : 0;
    ev(tT - 0.1, 'whoosh', 0.2); sfxT(ttl, tT, 0.5);
    return (t) => { const { o, a } = inOut(t, shot); vis(box, a * (1 - o)); vis(kick, eo((t - shot.start) / 0.5)); line.style.transform = `scaleX(${eo((t - shot.start) / 0.8).toFixed(3)})`; showT(ttl, t, tT); if (sub) vis(sub, eo((t - tS) / 0.5)); };
  }
  QV.chaptercard = function (root, shot, p) {
    mk(root, 'a', '', 'left:0;top:0;width:1080px;height:1920px;background:#050505');
    const n = ROMAN[chapN++ % ROMAN.length];
    const k = mk(root, 'a ctr', `CHAPITRE ${n}`, `top:680px;font:800 34px Poppins;letter-spacing:.5em;color:${pick('#050505', P.accent2, P.accent, '#fff')}`);
    const l1 = mk(root, 'a', '', 'left:340px;top:750px;width:400px;height:2px;background:rgba(255,255,255,.6)');
    const ttl = mk(root, 'a ctr', '', `top:800px;left:80px;width:920px;font:italic 400 170px/1 'DMSerif';color:#F4EFE6`); prepT(ttl, (p.title || '') + ' ?'); fit(ttl, 920, 170, 80, 360);
    const sub = p.sub ? mk(root, 'a ctr', esc(W_(p.sub)), `top:${840 + ttl.offsetHeight}px;left:80px;width:920px;font:400 54px/1.3 DMSerif;color:rgba(244,239,230,.7)`) : null;
    const tT = wordTime(shot, p.at, 0.05), tS = p.sub ? wordTime(shot, p.sub_at, 0.5) : 0;
    ev(shot.start, 'riser_short', 0.3); ev(tT, 'thud', 0.4);
    return (t) => { vis(k, eo((t - shot.start - 0.1) / 0.6)); l1.style.transform = `scaleX(${eo((t - shot.start) / 0.9).toFixed(3)})`; showT(ttl, t, tT); if (sub) vis(sub, eo((t - tS) / 0.6)); };
  };
  CV.letter = function (root, shot, p) {
    const opts = (p.options || []).slice(0, 2), ts = ctaTimes(shot, opts);
    mk(root, 'a', '', 'left:0;top:0;width:1080px;height:1920px;background:#0A0906');
    const paper = mk(root, 'a', '', `left:110px;top:300px;width:860px;height:1200px;background:#F2EAD8;background-image:${NOISE(0.12)};box-shadow:0 40px 90px rgba(0,0,0,.6)`);
    mk(paper, 'a', `${TU ? 'Écris-moi' : 'Écrivez-moi'},<br>en commentaire :`, `left:70px;top:80px;font:italic 400 76px/1.15 'DMSerif';color:#2B2418`);
    const rows = opts.map((o, i) => { const r = mk(paper, 'a', '', `left:70px;top:${340 + i * 200}px;width:720px;font:700 64px Poppins;color:#2B2418;border-bottom:3px solid rgba(43,36,24,.35);padding-bottom:18px`); r._text = '« ' + (o.text || '') + ' »'; return r; });
    const sig = p.stamp ? mk(paper, 'a', esc(W_(p.stamp)), `left:70px;top:${400 + opts.length * 200}px;font:italic 400 110px 'DMSerif';color:${P.bad}`) : null;
    const tR = p.stamp ? wordTime(shot, p.stamp_at || p.stamp, 0.85) : 0;
    ts.forEach((t0, i) => tickType(t0, rows[i]._text, 0.05)); if (sig) ev(tR, 'pencil', 0.7);
    return (t) => { const s = spring(t, shot.start); paper.style.transform = `translateY(${((1 - s) * 300).toFixed(0)}px) rotate(${(-1.5 + (1 - s) * 5).toFixed(2)}deg)`; rows.forEach((r, i) => typeText(r, r._text, t, ts[i], 0.05)); if (sig) sig.style.clipPath = `inset(0 ${((1 - eo((t - tR) / 0.7)) * 100).toFixed(1)}% 0 0)`; };
  };
  EV_.credits = function (root, shot, p) {
    const { lines, tB } = endTimes(shot, p);
    mk(root, 'a', '', 'left:0;top:0;width:1080px;height:1920px;background:#050505');
    const roll = mk(root, 'a ctr', `${lines.map((l) => `<div style="font:italic 400 76px/1.2 'DMSerif';color:#F4EFE6;margin-bottom:40px">${esc(W_(l.text))}</div>`).join('')}<div style="margin:80px auto;width:500px;padding:50px;background:#F4EFE6">${logoHTML(400, 220)}</div><div style="font:800 30px Poppins;letter-spacing:.5em;color:rgba(244,239,230,.6)">UN FILM DE</div><div style="margin-top:14px;font:400 90px DMSerif;color:#F4EFE6">${esc(BRAND || '')}</div>`, 'top:1920px;left:0;width:1080px');
    const bye = p.bye ? mk(root, 'a ctr', `<div style="font:italic 400 150px 'DMSerif';color:#F4EFE6">${esc(W_(p.bye.text))}</div><div style="margin:70px auto 0;width:420px;padding:40px;background:#F4EFE6">${logoHTML(340, 190)}</div>`, 'top:620px') : null;
    const dur = Math.max(1.5, (bye ? tB : shot.end) - shot.start - 0.2);
    ev(shot.start, 'riser_short', 0.3); if (bye) ev(tB, 'thud', 0.4);
    return (t) => {
      const u = clamp((t - shot.start) / dur); const H = roll.offsetHeight;
      roll.style.transform = `translateY(${(-u * (1920 * 0.5 + H * 0.9)).toFixed(0)}px)`;
      vis(roll, bye ? 1 - eo((t - tB + 0.3) / 0.4) : 1);
      if (bye) vis(bye, eo((t - tB) / 0.6));
    };
  };
  SV.doctitle = function (root, shot, p) {
    const w = mk(root, 'a ctr', `<div style="display:inline-block;padding:18px 44px 26px;background:rgba(5,5,5,.62);font:italic 400 110px/1.05 'DMSerif';color:#F4EFE6">${esc(W_(p.text || ''))}</div><div class="u" style="margin:24px auto 0;width:360px;height:3px;background:#F4EFE6;transform-origin:50% 50%"></div>`, 'top:360px;left:60px;width:960px');
    const u = w.querySelector('.u'); const tS = wordTime(shot, p.at, 0.15); ev(tS, 'thud', 0.5);
    return (t) => { const o = floatOut(t, shot); vis(w, eo((t - tS) / 0.5) * (1 - o)); u.style.transform = `scaleX(${eo((t - tS - 0.2) / 0.7).toFixed(3)})`; };
  };
  KV.location = function (root, shot, p) {
    const w = mk(root, 'a', `— ${sayUp(p.text)} —`, 'left:90px;top:260px;font:800 36px Poppins;letter-spacing:.4em;color:#F4EFE6;text-shadow:0 2px 14px rgba(0,0,0,.8)');
    const tK = wordTime(shot, p.at, 0.1);
    return (t) => { const o = floatOut(t, shot); vis(w, eo((t - tK) / 0.6) * (1 - o)); };
  };

  // ---------------------------------------------------------------- BENTO (tuiles)
  const tile = (root, x, y, w, h, bg) => mk(root, 'a', '', `left:${x}px;top:${y}px;width:${w}px;height:${h}px;border-radius:40px;background:${bg};overflow:hidden;box-sizing:border-box`);
  const tileIn = (el, t, t0, dir = 0) => { const s = spring(t, t0); vis(el, clamp((t - t0) * 6)); el.style.transform = `scale(${(0.82 + 0.18 * s).toFixed(3)})${dir ? ` translateY(${((1 - s) * 60).toFixed(0)}px)` : ''}`; };
  function tileSkin(root, shot, p) {
    const main = tile(root, 40, 850, 700, 360, P.light);
    const kick = p.kicker ? `<div style="font:800 26px Poppins;letter-spacing:.24em;color:${P.accent}">${esc(up(p.kicker))}</div>` : '';
    mk(main, 'a', kick, 'left:40px;top:36px');
    const ttl = mk(main, 'a', '', `left:40px;top:${p.kicker ? 80 : 44}px;width:620px;font-family:${HEAD};font-size:84px;line-height:1.02;color:${P.ink};${SERIF ? 'font-style:italic' : ''}`); prepT(ttl, SERIF ? (p.title || '') : up(p.title || '')); fit(ttl, 620, 84, 40, p.sub ? 170 : 250);
    const sub = p.sub ? mk(main, 'a', esc(W_(p.sub)), `left:40px;bottom:36px;width:620px;font:600 34px/1.25 Poppins;color:${rgba(P.ink, 0.7)}`) : null;
    const side = tile(root, 760, 850, 280, 360, P.accent);
    mk(side, 'a', p.badge ? `<div style="text-align:center">${icon(p.badge_icon || 'check', 110, on(P.accent), 2.2)}<div style="margin-top:14px;font:800 36px Poppins;color:${on(P.accent)}">${esc(up(p.badge))}</div></div>` : motif(150, on(P.accent)), 'inset:0;display:flex;align-items:center;justify-content:center');
    const tT = wordTime(shot, p.at, 0.05), tS = p.sub ? wordTime(shot, p.sub_at, 0.6) : 0, tB = p.badge ? wordTime(shot, p.badge_at || p.badge, 0.7) : shot.start + 0.2;
    ev(shot.start, 'pop_low', 0.5); ev(tB, 'pop', 0.4); sfxT(ttl, tT);
    return (t) => { const o = floatOut(t, shot); tileIn(main, t, shot.start, 1); tileIn(side, t, p.badge ? tB : shot.start + 0.12, 1); if (o > 0) { vis(main, 1 - o); vis(side, 1 - o); } showT(ttl, t, tT); if (sub) vis(sub, eo((t - tS) / 0.35)); };
  }
  QV.bentoq = function (root, shot, p) {
    const bg = shot.tone === 'light' ? P.light2 : P.dark;
    mk(root, 'a', '', `left:0;top:0;width:1080px;height:1920px;background:${bg}`);
    const a = tile(root, 40, 160, 1000, 760, P.accent), b = tile(root, 40, 950, 480, 480, P.light), c = tile(root, 560, 950, 480, 480, P.dark2), d = tile(root, 40, 1460, 1000, 300, P.light);
    mk(a, 'a', '?', `right:40px;top:-60px;font-family:${HEAD};font-size:900px;line-height:1;color:${rgba(on(P.accent), 0.18)}`);
    const ttl = mk(a, 'a', '', `left:50px;bottom:50px;width:900px;font-family:${HEAD};font-size:200px;line-height:.95;color:${on(P.accent)}`); prepT(ttl, up(p.title || '')); fit(ttl, 900, 200, 90, 500);
    mk(b, 'a', motif(260, P.accent), 'inset:0;display:flex;align-items:center;justify-content:center');
    mk(c, 'a', `<svg width="360" height="360" viewBox="0 0 360 360"><circle cx="180" cy="180" r="150" fill="none" stroke="${rgba('#FFFFFF', 0.25)}" stroke-width="18"/><circle class="arc" cx="180" cy="180" r="150" fill="none" stroke="${P.accent2}" stroke-width="18" stroke-linecap="round" pathLength="1" stroke-dasharray="1 1" stroke-dashoffset="1" transform="rotate(-90 180 180)"/></svg>`, 'inset:0;display:flex;align-items:center;justify-content:center');
    const arc = c.querySelector('.arc');
    const sub = mk(d, 'a', esc(W_(p.sub || '')), `left:50px;top:0;height:300px;width:900px;display:flex;align-items:center;font:800 76px/1.1 Poppins;color:${P.ink}`);
    const tT = wordTime(shot, p.at, 0.05), tS = p.sub ? wordTime(shot, p.sub_at, 0.5) : tT + 0.4;
    [a, b, c, d].forEach((_, i) => ev(shot.start + i * 0.1, 'pop_low', 0.35)); sfxT(ttl, tT);
    return (t) => { [a, b, c].forEach((e, i) => tileIn(e, t, shot.start + i * 0.1)); tileIn(d, t, tS - 0.1, 1); showT(ttl, t, tT); arc.setAttribute('stroke-dashoffset', (1 - eo((t - shot.start - 0.3) / 1.5) * 0.75).toFixed(3)); vis(sub, eo((t - tS) / 0.3)); };
  };
  CV.bentoc = function (root, shot, p) {
    const bg = shot.tone === 'light' ? P.light2 : P.dark;
    mk(root, 'a', '', `left:0;top:0;width:1080px;height:1920px;background:${bg}`);
    const opts = (p.options || []).slice(0, 2), ts = ctaTimes(shot, opts);
    const h = tile(root, 40, 160, 1000, 300, P.dark2);
    mk(h, 'a', `${icon('message', 90, P.accent2, 2.2)}<span style="font:800 64px/1.1 Poppins;color:#fff">${TU ? 'Écris en commentaire' : 'Écrivez en commentaire'}</span>`, 'left:50px;top:0;height:300px;display:flex;align-items:center;gap:30px');
    const os = opts.map((o, i) => { const e = tile(root, 40 + i * 520, 490, 480, 480, i ? P.accent2 : P.accent); mk(e, 'a', `<div style="font:400 180px/1 ${HEAD};color:${rgba(on(i ? P.accent2 : P.accent), 0.25)}">${i + 1}</div><div class="t" style="font:800 64px/1.1 Poppins;color:${on(i ? P.accent2 : P.accent)}">${sayUp(o.text)}</div>`, 'left:40px;top:40px;width:400px'); fit(e.querySelector('.t'), 400, 64, 34, 260); return e; });
    const lg = tile(root, 40, 1000, 1000, 420, '#fff');
    mk(lg, 'a', logoHTML(700, 300), 'inset:0;display:flex;align-items:center;justify-content:center');
    const rd = p.stamp ? tile(root, 40, 1450, 1000, 260, P.bad) : null;
    if (rd) mk(rd, 'a', sayUp(p.stamp), `inset:0;display:flex;align-items:center;justify-content:center;font-family:${HEAD};font-size:130px;color:#fff`);
    const tR = p.stamp ? wordTime(shot, p.stamp_at || p.stamp, 0.85) : 0;
    ts.forEach((t0) => ev(t0, 'pop', 0.6)); if (rd) ev(tR, 'impact', 0.6);
    return (t) => { tileIn(h, t, shot.start); os.forEach((e, i) => tileIn(e, t, ts[i] - 0.1, 1)); tileIn(lg, t, shot.start + 0.2); if (rd) tileIn(rd, t, tR, 1); };
  };
  EV_.bentoe = function (root, shot, p) {
    const { lines, t1, t2, tB } = endTimes(shot, p);
    const bg = shot.tone === 'light' ? P.light2 : P.dark;
    mk(root, 'a', '', `left:0;top:0;width:1080px;height:1920px;background:${bg}`);
    const lg = tile(root, 40, 160, 1000, 640, '#fff'); mk(lg, 'a', logoHTML(760, 420), 'inset:0;display:flex;align-items:center;justify-content:center');
    const ls = lines.map((l, i) => { const e = tile(root, 40 + (i ? 0 : 0), 830 + i * 290, i ? 1000 : 1000, 260, i ? P.dark2 : P.accent); mk(e, 'a', sayUp(l.text), `left:50px;top:0;height:260px;width:900px;display:flex;align-items:center;font-family:${HEAD};font-size:84px;line-height:1;color:${i ? '#fff' : on(P.accent)}`); return e; });
    const by = p.bye ? tile(root, 40, 830 + lines.length * 290, 1000, 300, P.accent2) : null;
    if (by) mk(by, 'a', sayUp(p.bye.text), `inset:0;display:flex;align-items:center;justify-content:center;font-family:${HEAD};font-size:140px;color:${on(P.accent2)}`);
    ev(shot.start, 'pop_low', 0.5); if (by) ev(tB, 'impact', 0.5);
    return (t) => { tileIn(lg, t, shot.start); ls.forEach((e, i) => tileIn(e, t, (i ? t2 : t1) - 0.1, 1)); if (by) tileIn(by, t, tB - 0.1, 1); };
  };
  SV.bentos = function (root, shot, p) {
    const e = tile(root, 40, 850, 1000, 360, P.bad);
    mk(e, 'a', `${icon('alert', 110, '#fff', 2.4)}<span style="font-family:${HEAD};font-size:120px;line-height:1;color:#fff">${sayUp(p.text)}</span>`, 'left:50px;top:0;height:360px;display:flex;align-items:center;gap:36px');
    const tS = wordTime(shot, p.at, 0.15); ev(tS, 'impact', 0.7); IMPACTS.push(tS);
    return (t) => { tileIn(e, t, tS, 1); const o = floatOut(t, shot); if (o > 0) vis(e, 1 - o); };
  };
  SV.bentos.shrinks = true;
  KV.bentok = function (root, shot, p) {
    const e = mk(root, 'a', `<span style="display:inline-flex;align-items:center;gap:16px">${motif(50, on(P.accent2))}${sayUp(p.text)}</span>`, `left:70px;top:1070px;padding:20px 34px;border-radius:26px;background:${P.accent2};box-shadow:0 14px 30px rgba(0,0,0,.35);font:800 46px Poppins;color:${on(P.accent2)}`);
    const tK = wordTime(shot, p.at, 0.1); ev(tK, 'pop', 0.5);
    return (t) => { const o = floatOut(t, shot); tileIn(e, t, tK); if (o > 0) vis(e, 1 - o); };
  };

  // Tampon encreur par-dessus l'image (négation, alerte, mot fort)
  SC.stamp_word = function (root, shot, p) {
    if (SV[G.s]) return SV[G.s](root, shot, p);
    const col = p.color === 'accent' ? P.accent : P.bad;
    const rot = -6 + rv(cardK++) * 5;
    const box = mk(root, 'a', '', `left:110px;top:${p.pos === 'low' ? LOW_BOTTOM - 360 : 300}px;width:860px;min-height:300px;box-sizing:border-box;border:14px solid ${col};border-radius:${Math.max(10, R)}px;display:flex;align-items:center;justify-content:center;padding:20px 40px;background:${rgba(col, 0.1)}`);
    const txt = mk(box, '', esc(up(W_(p.text || ''))).replace(/\|/g, '<br>'), `font-family:${HEAD};font-size:120px;line-height:1.02;color:${col};text-align:center;letter-spacing:.02em`);
    fit(txt, 760, 130, 60, 400);
    mk(box, 'a', '', `inset:0;background:${NOISE(0.5)};mix-blend-mode:destination-out;opacity:.5;border-radius:inherit`);
    const tS = wordTime(shot, p.at, 0.15);
    ev(tS, 'stamp', 0.9); ev(tS + 0.02, SND.impact || 'impact', 0.5); IMPACTS.push(tS);
    return (t) => {
      const s = pop(t, tS, 20, 0.45), o = eio((t - shot.end + 0.2) / 0.25);
      vis(box, clamp((t - tS) * 10) * (1 - o));
      box.style.transform = `rotate(${rot.toFixed(2)}deg) scale(${(1.8 - 0.8 * s - 0.1 * o).toFixed(3)})`;
    };
  };

  // Étiquette mot-clé en haut (lieu, thème, promesse courte)
  SC.keyword = function (root, shot, p) {
    if (KV[G.k]) return KV[G.k](root, shot, p);
    const bg = lum(P.accent2) > 0.5 ? P.accent2 : P.accent;
    const pill = mk(root, 'a ctr', `<span style="display:inline-flex;align-items:center;gap:16px;background:${bg};color:${on(bg)};font:800 50px Poppins;letter-spacing:.1em;padding:16px 40px;border-radius:${Math.max(16, R)}px;box-shadow:0 14px 34px rgba(0,0,0,.35)">${motif(52, on(bg))}${esc(up(W_(p.text || '')))}</span>`, `top:${p.pos === 'low' ? LOW_BOTTOM - 110 : MONT.masthead ? 360 : 220}px`);
    fit(pill.firstElementChild, 960, 50, 28);
    const tK = wordTime(shot, p.at, 0.1);
    ev(tK, 'pop', 0.6); ev(tK + 0.05, 'shimmer', 0.35);
    return (t) => {
      const q = spring(t, tK), o = eio((t - shot.end + 0.2) / 0.25);
      vis(pill, clamp((t - tK) * 7) * (1 - o));
      pill.style.transform = `scale(${(0.45 + 0.55 * q - 0.1 * o).toFixed(3)})`;
    };
  };

  // ------------------------------------------------------------------ SCÈNES PLEIN ÉCRAN propres au Studio
  // Question plein écran — 3 mises en page (choisies par la variante du montage):
  //   0 titre en haut + « ? » + cadran animé    1 « ? » géant en filigrane, titre centré
  //   2 titre calé à gauche, « ? » énorme penché à droite
  SC.question = function (root, shot, p) {
    if (QV[G.q]) return QV[G.q](root, shot, p);
    const dark = shot.tone !== 'light';
    const bg = dark ? P.dark : P.light;
    const tcol = pick(bg, P.accent2, P.accent, dark ? P.light : P.ink);
    const qcol = pick(bg, P.accent, P.bad, tcol);
    const rcol = pick(bg, P.accent2, P.accent, dark ? P.light : P.ink);
    const L = G.q === 'watermark' ? 1 : (LAYOUT === 1 ? 2 : 0);
    let ring = null, nd = null, wm = null;
    if (L === 0) {
      ring = mk(root, 'a', `<svg width="560" height="560" viewBox="0 0 560 560"><circle cx="280" cy="280" r="250" fill="none" stroke="${rgba(rcol, 0.55)}" stroke-width="4" stroke-dasharray="14 18"/><circle cx="280" cy="280" r="205" fill="none" stroke="${rgba(rcol, 0.25)}" stroke-width="2"/><g class="nd"><path d="M280 280 L280 70" stroke="${qcol}" stroke-width="10" stroke-linecap="round"/></g><circle cx="280" cy="280" r="20" fill="${rcol}"/></svg>`, 'left:260px;top:1010px');
      nd = ring.querySelector('.nd');
    } else if (L === 1) {
      wm = mk(root, 'a ctr', '?', `top:260px;font-family:${HEAD};font-size:1250px;line-height:1;color:${rgba(qcol, 0.13)}`);
    }
    const ttl = mk(root, 'a', '', `top:${L === 0 ? 420 : L === 1 ? 700 : 560}px;left:${L === 2 ? 80 : 60}px;width:${L === 2 ? 700 : 960}px;text-align:${L === 2 ? 'left' : 'center'};font-family:${HEAD};color:${tcol};line-height:1.02;${SERIF ? 'font-style:italic' : ''}`);
    prepT(ttl, SERIF ? p.title : up(p.title || ''), p.highlight);
    fit(ttl, L === 2 ? 700 : 960, L === 1 ? 240 : 210, 90, 520);
    const q = L === 1 ? null : mk(root, 'a', '?', L === 0
      ? `left:0;width:1080px;text-align:center;top:${420 + ttl.scrollHeight - 20}px;font-family:${HEAD};font-size:240px;color:${qcol};line-height:1`
      : `right:40px;top:380px;font-family:${HEAD};font-size:640px;color:${qcol};line-height:1;transform-origin:50% 80%`);
    const subTop = L === 0 ? 1620 : L === 1 ? 700 + ttl.scrollHeight + 70 : 560 + ttl.scrollHeight + 60;
    const subBg = dark ? P.light : P.dark;
    const sub = p.sub ? mk(root, 'a', `<span style="display:inline-block;max-width:860px;background:${subBg};color:${pick(subBg, dark ? P.ink : P.light)};font:${SERIF ? 'italic 400 56px/1.25 DMSerif' : '700 50px/1.25 Poppins'};padding:18px 40px 22px;border-radius:${Math.max(12, R)}px;box-shadow:0 16px 40px rgba(0,0,0,.35)">${esc(W_(p.sub))}</span>`, L === 2 ? `left:80px;top:${subTop}px` : `left:0;width:1080px;text-align:center;top:${subTop}px`) : null;
    const tT = wordTime(shot, p.at, 0.02), tQ = L === 1 ? shot.start + 0.05 : tT + 0.45, tS = p.sub ? wordTime(shot, p.sub_at, 0.5) : 0;
    sfxT(ttl, tT); ev(tQ, SND.impact || 'impact', 0.7); IMPACTS.push(tQ); if (sub) ev(tS, 'pop', 0.6);
    if (ring) for (let i = 0; i < 4; i++) ev(shot.start + 0.4 + i * 0.5, 'tick', 0.25);
    return (t) => {
      showT(ttl, t, tT);
      if (q) { const s = pop(t, tQ, 16, 0.45); vis(q, clamp((t - tQ) * 8)); q.style.transform = `scale(${(0.3 + 0.7 * s).toFixed(3)}) rotate(${((1 - s) * -30 + (L === 2 ? 12 : 0)).toFixed(1)}deg)`; }
      if (wm) { const s = spring(t, tQ); vis(wm, clamp((t - tQ) * 4)); wm.style.transform = `scale(${(0.8 + 0.2 * s + 0.02 * Math.sin(t * 1.7)).toFixed(3)}) rotate(${(Math.sin(t * 0.9) * 4).toFixed(2)}deg)`; }
      if (ring) { const r = spring(t, shot.start + 0.1); vis(ring, clamp((t - shot.start) * 4) * 0.95); ring.style.transform = `scale(${(0.7 + 0.3 * r).toFixed(3)}) rotate(${((t - shot.start) * 12).toFixed(1)}deg)`;
        nd.setAttribute('transform', `rotate(${(-40 + Math.sin(t * 2.3) * 150 + (t - shot.start) * 50).toFixed(1)} 280 280)`); }
      if (sub) { const u = eo((t - tS) / 0.4); vis(sub, u); sub.style.transform = `translateY(${((1 - u) * 50).toFixed(0)}px)`; }
    };
  };

  // Appel à commenter: mots-clés tapés dans des cartes + TOI ↔ NOUS + tampon final
  SC.comment_cta = function (root, shot, p) {
    if (CV[G.c]) return CV[G.c](root, shot, p);
    const dark = shot.tone !== 'light';
    const ink = dark ? P.light : P.ink;
    const barBg = dark ? '#000000' : P.dark, barFg = pick(barBg, P.accent2, P.accent, P.light);
    const bar = mk(root, 'a', `<div style="display:flex;align-items:center;gap:20px;height:140px;padding:0 50px">${icon('message', 56, barFg, 2.4)}<span style="font:800 44px Poppins;letter-spacing:.08em;color:${barFg}">${esc(up(p.title || (TU ? 'ÉCRIS EN COMMENTAIRE' : 'ÉCRIVEZ EN COMMENTAIRE')))}</span></div>`, `left:0;top:0;width:1080px;background:${dark ? rgba('#000000', 0.35) : P.dark}`);
    const pillBg = dark ? P.light : P.dark2, pillFg = pick(pillBg, P.accent2, P.accent, P.ink, P.light);
    fit(bar.querySelector('span'), 880, 44, 28);
    const opts = (p.options || []).slice(0, 2);
    let y = 230;
    const cards = opts.map((o, i) => {
      const lab = opts.length > 1 ? 'Option ' + (i + 1) : (TU ? 'Ton mot-clé' : 'Votre mot-clé');
      const { card, body } = chrome(root, 70, 940, CH === 'dossier' || CH === 'sticker' || CH === 'notification' || CH === 'terminal' ? lab : null, 40 + i, true);
      if (!(CH === 'dossier' || CH === 'sticker' || CH === 'notification' || CH === 'terminal')) mk(body, '', esc(up(lab)), `font:700 26px Poppins;letter-spacing:.16em;color:${KICK_COL};margin-bottom:8px`);
      const tt = mk(body, '', '', `display:inline-block;font:800 58px Poppins;color:${cardInk};min-height:70px;white-space:nowrap;${CH === 'terminal' ? 'margin:0 40px;' : ''}`);
      card.style.top = y + 'px';
      card._t = tt; card._text = up(o.text || '');
      tt.textContent = card._text; fit(tt, CH === 'postcard' ? 600 : 820, 58, 30); tt.textContent = '';
      y += card.offsetHeight + (i === 0 && opts.length > 1 ? 120 : 50);
      return card;
    });
    const orEl = opts.length > 1 ? mk(root, 'a ctr', `<span style="display:inline-block;background:${pillBg};color:${pillFg};font:800 32px Poppins;padding:10px 36px;border-radius:999px;box-shadow:0 8px 20px rgba(0,0,0,.25)">OU BIEN</span>`, `top:${Math.round((parseFloat(cards[0].style.top) + cards[0].offsetHeight + parseFloat(cards[1].style.top) - (CH === 'dossier' ? 54 : 0)) / 2 - 30)}px;z-index:2`) : null;
    const tOpt = cards.map((c, i) => wordTime(shot, opts[i].at, 0.2 + 0.3 * i));
    tOpt.forEach((t0, i) => { ev(t0 - 0.2, 'whoosh', 0.4); for (let c = 0; c < cards[i]._text.length; c += 2) ev(t0 + c * 0.035, 'tick', 0.35); });
    // duo TOI ↔ NOUS
    let duo = null, tDuo = 0;
    if (p.duo_at != null) {
      tDuo = wordTime(shot, p.duo_at, 0.7);
      duo = mk(root, 'a', '', `left:0;top:${Math.max(y + 20, 900)}px;width:1080px;height:330px`);
      const circ = (x, inner, lab, bg, bd) => mk(duo, 'a', `<div style="width:240px;height:240px;border-radius:50%;background:${bg};border:8px solid ${bd};box-shadow:0 16px 36px rgba(0,0,0,.3);display:flex;align-items:center;justify-content:center;overflow:hidden">${inner}</div><div style="text-align:center;font:800 36px Poppins;color:${ink};margin-top:14px">${lab}</div>`, `left:${x - 128}px;top:0;width:256px`);
      duo._a = circ(290, icon('user', 130, '#fff', 1.8), TU ? 'TOI' : 'VOUS', P.accent, '#fff');
      duo._b = circ(790, LOGO ? `<img src="${LOGO}" style="width:200px;height:200px;object-fit:contain">` : motif(120, P.accent), 'NOUS', '#fff', P.accent);
      duo._l = mk(duo, 'a', '', `left:418px;top:118px;height:8px;width:244px;background:${P.accent2};border-radius:4px;transform-origin:0 50%`);
      ev(tDuo, 'whoosh', 0.5); ev(tDuo + 0.55, 'pop', 0.6);
    }
    let stp = null, tStp = 0;
    if (p.stamp) {
      tStp = wordTime(shot, p.stamp_at || p.stamp, 0.85);
      stp = mk(root, 'a', `<div style="font-family:${HEAD};font-size:120px;line-height:1.04;color:${P.bad};text-align:center">${esc(up(W_(p.stamp))).replace(/\|/g, '<br>')}</div>`, `left:90px;top:${duo ? Math.max(y + 20, 900) + 380 : Math.max(y + 60, 1000)}px;width:900px;box-sizing:border-box;padding:24px 30px;border:14px solid ${P.bad};border-radius:${Math.max(12, R)}px;background:${rgba(P.bad, 0.08)}`);
      fit(stp.firstElementChild, 800, 120, 60, 280);
      ev(tStp, 'stamp', 0.95); ev(tStp + 0.02, 'impact_big', 0.6); IMPACTS.push(tStp);
    }
    return (t) => {
      const b = eo((t - shot.start) / 0.35); bar.style.transform = `translateY(${((1 - b) * -150).toFixed(0)}px)`;
      cards.forEach((c, i) => {
        const t0 = tOpt[i]; const q = spring(t, t0 - 0.2);
        vis(c, clamp((t - t0 + 0.25) * 6)); c.style.transform = `translateX(${((1 - q) * (i % 2 ? 600 : -600)).toFixed(0)}px) rotate(${c._rot}deg)`;
        const n = Math.min(c._text.length, Math.max(0, Math.floor((t - t0) / 0.035)));
        c._t.textContent = t >= t0 ? c._text.slice(0, n) + (n < c._text.length && Math.floor(t * 4) % 2 === 0 ? '▌' : '') : '';
      });
      if (orEl) { const q = spring(t, tOpt[1] - 0.45); vis(orEl, clamp((t - tOpt[1] + 0.5) * 6)); orEl.style.transform = `scale(${(0.4 + 0.6 * q).toFixed(3)})`; }
      if (duo) {
        const u = eio((t - tDuo) / 0.6);
        vis(duo, clamp((t - tDuo + 0.05) * 6));
        duo._a.style.transform = `translateX(${((1 - u) * -500).toFixed(0)}px)`;
        duo._b.style.transform = `translateX(${((1 - u) * 500).toFixed(0)}px)`;
        duo._l.style.transform = `scaleX(${eo((t - tDuo - 0.5) / 0.35).toFixed(3)})`;
      }
      if (stp) { const s = pop(t, tStp, 20, 0.45); vis(stp, clamp((t - tStp) * 10)); stp.style.transform = `rotate(-4deg) scale(${(1.7 - 0.7 * s).toFixed(3)})`; }
    };
  };

  // Carte de fin: phrase de clôture, accroche, LOGO en grand, au revoir
  SC.end_card = function (root, shot, p) {
    if (EV_[G.e]) return EV_[G.e](root, shot, p);
    const dark = shot.tone !== 'light';
    const ink = dark ? P.light : P.ink;
    const bgE = dark ? P.dark : P.light;
    const acE = pick(bgE, P.accent, P.accent2, ink);
    const LOGO_FIRST = LAYOUT === 1;
    mk(root, 'a', '', `left:28px;top:28px;right:28px;bottom:28px;border:3px ${CH === 'clean' || CH === 'neon' ? 'solid' : 'dashed'} ${rgba(P.accent2, 0.7)};border-radius:${Math.max(0, R - 6)}px`);
    const wm = mk(root, 'a', motif(420, rgba(P.accent, dark ? 0.1 : 0.08)), `left:${330 + Math.round((rv(7) - 0.5) * 120)}px;top:1360px;transform:rotate(${Math.round((rv(8) - 0.5) * 30)}deg)`);
    void wm;
    const lines = (p.lines || []).slice(0, 2);
    const l1 = lines[0] ? mk(root, 'a ctr', '', `top:250px;left:70px;width:940px;font-family:${SERIF ? "'DMSerif'" : HEAD};font-size:84px;line-height:1.14;color:${ink};${SERIF ? 'font-style:italic' : ''}`) : null;
    if (l1) { prepT(l1, SERIF ? lines[0].text : up(lines[0].text), []); fit(l1, 940, 90, 50, 330); }
    const rule = mk(root, 'a', '', `left:340px;top:${250 + (l1 ? l1.scrollHeight : 0) + 36}px;width:400px;height:5px;border-radius:3px;background:${pick(bgE, P.accent2, P.accent)};transform-origin:50% 50%`);
    const l2 = lines[1] ? mk(root, 'a ctr', esc(up(W_(lines[1].text))), `top:${250 + (l1 ? l1.scrollHeight : 0) + 80}px;left:70px;width:940px;font:800 44px/1.2 Poppins;letter-spacing:.06em;color:${acE}`) : null;
    if (l2) fit(l2, 940, 44, 26, 120);
    let logoTop = Math.max(700, 250 + (l1 ? l1.scrollHeight : 0) + (l2 ? l2.scrollHeight : 0) + 170);
    if (LOGO_FIRST) {  // variante: logo en haut, texte dessous
      const shift = 520;
      [l1, rule, l2].forEach((e) => { if (e) e.style.top = (parseFloat(e.style.top) + shift) + 'px'; });
      logoTop = 200;
    }
    const lg = mk(root, 'a ctr', LOGO ? `<span style="display:inline-block;${dark ? `background:#fff;padding:40px 56px;border-radius:${Math.max(18, R)}px;box-shadow:0 24px 60px rgba(0,0,0,.45),0 0 0 6px ${rgba(P.accent, 0.5)}` : ''}"><img src="${LOGO}" style="max-width:${dark ? 560 : 640}px;max-height:340px;object-fit:contain;display:block;filter:drop-shadow(0 12px 26px rgba(0,0,0,.18))"></span>` : `<span style="font-family:${HEAD};font-size:120px;color:${P.accent}">${esc(up(BRAND || ''))}</span>`, `top:${logoTop}px`);
    const byeTop = LOGO_FIRST ? Math.min(1560, 250 + 520 + (l1 ? l1.scrollHeight : 0) + (l2 ? l2.scrollHeight : 0) + 200) : Math.min(1480, logoTop + 480);
    const bye = p.bye ? mk(root, 'a ctr', `<span style="display:inline-block;background:${dark ? P.light : P.dark};color:${dark ? pick(P.light, P.ink) : pick(P.dark, P.accent2, P.accent, P.light)};font:${SERIF ? 'italic 400 88px/1 DMSerif' : `400 96px/1 ${HEAD}`};padding:18px 54px 26px;border-radius:${Math.max(16, R)}px;box-shadow:0 18px 44px rgba(0,0,0,.3)">${esc(SERIF ? W_(p.bye.text) : up(W_(p.bye.text)))}</span>`, `top:${byeTop}px`) : null;
    const tE = shot.start + 0.05, t1 = l1 ? wordTime(shot, lines[0].at, 0.05) : tE, t2 = l2 ? wordTime(shot, lines[1].at, 0.45) : tE, tB = bye ? wordTime(shot, p.bye.at, 0.9) : tE;
    ev(tE + 0.1, 'riser_short', 0.5); ev(tE + 0.3, 'shimmer', 0.6); if (l1) sfxT(l1, t1); if (l2) ev(t2, 'pop', 0.5); if (bye) { ev(tB - 0.05, SND.impact || 'impact', 0.5); }
    return (t) => {
      if (l1) showT(l1, t, t1);
      rule.style.transform = `scaleX(${eo((t - t1 - 0.3) / 0.5).toFixed(3)})`;
      if (l2) { const u = eo((t - t2) / 0.4); vis(l2, u); l2.style.transform = `translateY(${((1 - u) * 26).toFixed(0)}px)`; }
      const q = spring(t, tE + 0.15); vis(lg, clamp((t - tE) * 4)); lg.style.transform = `scale(${(0.6 + 0.4 * q + 0.015 * Math.sin(t * 2.2)).toFixed(3)})`;
      if (bye) { const s = spring(t, tB - 0.1); vis(bye, clamp((t - tB + 0.12) * 6)); bye.style.transform = `scale(${(0.45 + 0.55 * s).toFixed(3)})`; }
    };
  };

  // ------------------------------------------------------------------ décor + transitions des panneaux plein écran
  const FULL = [];
  function decorate(el, shot, i) {
    if (shot.layout === 'float') { el.style.background = 'transparent'; return; }
    if (MONT.world) worldDecorate(el);
    const dark = shot.tone !== 'light';
    const tx = document.createElement('div');
    tx.className = 'a'; tx.style.cssText = `left:0;top:0;width:1080px;height:1920px;pointer-events:none;${textureCSS(ST.panel, dark)}`;
    el.insertBefore(tx, el.firstChild);
    if (ST.panel === 'mesh') {
      el._blobs = [P.accent, P.accent2, P.dark2].map((c, k) => {
        const b = document.createElement('div'); b.className = 'a';
        b.style.cssText = `left:${[-200, 480, 100][k]}px;top:${[-100, 900, 1300][k]}px;width:900px;height:900px;border-radius:50%;background:radial-gradient(circle,${rgba(c, dark ? 0.38 : 0.28)} 0%,transparent 68%)`;
        el.insertBefore(b, tx.nextSibling); return b;
      });
    }
    if (ST.panel === 'scan') {
      el._scan = mk(el, 'a', '', `left:0;top:0;width:1080px;height:160px;background:linear-gradient(180deg,transparent,${rgba(P.accent, 0.1)},transparent);pointer-events:none`);
    }
    // filigrane du motif (sauf fin, qui a le sien)
    if (shot.scene.type !== 'end_card') {
      const m = document.createElement('div'); m.className = 'a';
      const x = rv(i * 3 + 1) > 0.5 ? 640 + rv(i) * 120 : -120 + rv(i) * 100, y = 120 + rv(i * 3 + 2) * 1300;
      m.style.cssText = `left:${x.toFixed(0)}px;top:${y.toFixed(0)}px;opacity:${dark ? 0.07 : 0.06};transform:rotate(${((rv(i + 5) - 0.5) * 40).toFixed(0)}deg);pointer-events:none`;
      m.innerHTML = motif(560, dark ? '#FFFFFF' : P.ink, 1.2);
      el.insertBefore(m, tx.nextSibling);
    }
    if (ST.transition === 'squeegee') el._blade = mk(stage, 'a', '', `left:0;top:-400px;width:70px;height:2800px;background:linear-gradient(90deg,${rgba(P.light, 0.9)},${P.accent2} 40%,${rgba(P.dark, 0.9)});box-shadow:0 0 40px rgba(0,0,0,.35);transform-origin:0 0;display:none;z-index:5`);
    FULL.push(shot);
    const a = shot.start, b = shot.end, tr = ST.transition;
    const inS = { paper: 'paper', tear: 'tear', squeegee: 'squeak', glitch: 'glitch', shutter: 'click', iris: SND.whoosh || 'whoosh', blinds: 'whoosh', zoom: 'whoosh_deep', slide: 'whoosh', whip: 'whoosh' }[tr] || 'whoosh';
    ev(a - 0.22, inS, 0.7); if (tr === 'shutter') ev(a + 0.18, 'thud', 0.35); if (tr === 'squeegee') ev(a - 0.15, 'spray', 0.25);
    ev(b - 0.18, tr === 'tear' ? 'tear' : tr === 'glitch' ? 'glitch' : 'whoosh', 0.4);
  }

  function reveal(el, kind, u, out, shot) {
    // u: 1 = panneau entièrement visible, 0 = absent
    el.style.transformOrigin = '540px 960px';
    el.style.clipPath = ''; el.style.webkitMaskImage = ''; el.style.maskImage = ''; el.style.filter = 'none'; el.style.opacity = '1';
    if (el._blade) el._blade.style.display = 'none';
    if (u >= 1) return '';
    const k = 1 - u;
    switch (kind) {
      case 'iris': { const cx = out ? 540 : 540, cy = out ? 360 : 1100; el.style.clipPath = `circle(${(u * 2250).toFixed(0)}px at ${cx}px ${cy}px)`; return ''; }
      case 'squeegee': {
        const s = u * 1900; // bord diagonal: x = s - 0.42*y
        el.style.clipPath = out ? `polygon(${(1080 - s + 0).toFixed(0)}px 0,1080px 0,1080px 1920px,${(1080 - s + 806).toFixed(0)}px 1920px)` : `polygon(0 0,${s.toFixed(0)}px 0,${(s - 806).toFixed(0)}px 1920px,0 1920px)`;
        if (el._blade && u > 0.01) { el._blade.style.display = 'block'; el._blade.style.transform = `translate(${(out ? 1080 - s : s - 35).toFixed(0)}px,0) rotate(${out ? -22.8 : 22.8}deg)`; }
        return '';
      }
      case 'slide': return `translateX(${(k * (out ? -1080 : 1080)).toFixed(1)}px)`;
      case 'paper': return `translateY(${(k * (out ? -1950 : 1950)).toFixed(0)}px) rotate(${(k * (out ? -5 : 7)).toFixed(2)}deg)`;
      case 'tear': {
        const y = u * 2000, pts = [];
        for (let i = 0; i <= 18; i++) pts.push(`${(i / 18 * 1080).toFixed(0)}px ${(y - 40 + rnd(i * 3.1 + (out ? 7 : 0)) * 80).toFixed(0)}px`);
        el.style.clipPath = `polygon(0 0,1080px 0,${pts.reverse().join(',')})`;
        return '';
      }
      case 'zoom': el.style.opacity = u.toFixed(3); el.style.filter = `blur(${(k * 18).toFixed(1)}px)`; return `scale(${(out ? 1 + 0.45 * k : 0.72 + 0.28 * u).toFixed(4)})`;
      case 'shutter': el.style.clipPath = `inset(${(k * 50).toFixed(2)}% 0 ${(k * 50).toFixed(2)}% 0)`; return '';
      case 'glitch': {
        const f = Math.floor((shot.start + (out ? 3 : 0)) * 10 + u * 12);
        el.style.opacity = (u > 0.15 ? 1 : u / 0.15).toFixed(3);
        el.style.filter = `drop-shadow(${(k * 16).toFixed(1)}px 0 0 rgba(255,0,90,.75)) drop-shadow(${(-k * 16).toFixed(1)}px 0 0 rgba(0,240,255,.75))`;
        const band = rnd(f) * 1700; el.style.clipPath = k > 0.2 ? `polygon(0 0,1080px 0,1080px ${band.toFixed(0)}px,${(1080 - k * 120).toFixed(0)}px ${(band + 90).toFixed(0)}px,1080px ${(band + 180).toFixed(0)}px,1080px 1920px,0 1920px)` : '';
        return `translateX(${((rnd(f + 1) - 0.5) * 140 * k).toFixed(1)}px) translateY(${(out ? -1 : 1) * k * 120}px)`;
      }
      case 'pageturn': el.style.transformOrigin = out ? '0 50%' : '100% 50%'; return `perspective(2600px) rotateY(${(k * (out ? -95 : 95)).toFixed(2)}deg)`;
      case 'blinds': { const m = `repeating-linear-gradient(180deg,#000 0 ${(u * 160).toFixed(1)}px,transparent ${(u * 160).toFixed(1)}px 160px)`; el.style.webkitMaskImage = m; el.style.maskImage = m; return ''; }
      default: el.style.filter = `blur(${(k * 22).toFixed(1)}px)`; return `translateY(${(k * (out ? -760 : 760)).toFixed(0)}px)`; // whip
    }
  }

  function transition(el, t, a, b, shot) {
    if (MONT.world) { worldPlace(el, t, shot); return; }
    if (shot.layout === 'float') { el.style.transform = ''; el.style.clipPath = ''; el.style.opacity = '1'; el.style.filter = 'none'; return; }
    const uin = eio((t - (a - 0.2)) / 0.42), uout = 1 - eio((t - (b - 0.2)) / 0.42);
    const out = uout < uin;
    const kindT = MONT.full === 'pageturn' ? 'pageturn' : ST.transition;
    const tr = reveal(el, kindT, Math.min(uin, uout), out, shot);
    const push = 1 + (M.push || 0.04) * clamp((t - a) / Math.max(0.1, b - a));
    el.style.transform = `${tr} scale(${push.toFixed(4)})`;
    if (el._blobs) el._blobs.forEach((bl, k) => { bl.style.transform = `translate(${(Math.sin(t * 0.5 + k * 2) * 90).toFixed(0)}px,${(Math.cos(t * 0.4 + k) * 70).toFixed(0)}px)`; });
    if (el._scan) el._scan.style.top = (((t * 420) % 2200) - 200).toFixed(0) + 'px';
  }

  // ------------------------------------------------------------------ LE VISAGE (images de la vidéo montée)
  const FR = STORY.frames || null;           // {url, fps, count, ext}
  const RECT = {
    full: { x: 0, y: 0, w: 1080, h: 1920, r: 0, rot: 0 },
    window: { x: 80, y: 450, w: 920, h: 1120, r: Math.max(18, R), rot: 0 },
    phone: { x: 190, y: 250, w: 700, h: 1380, r: 84, rot: -3.5 },
    polaroid: { x: 200, y: 330, w: 680, h: 860, r: 4, rot: -2.5 },
    split: { x: 0, y: 0, w: 1080, h: 1180, r: 0, rot: 0 },
    circle: { x: 210, y: 250, w: 660, h: 660, r: 330, rot: 0 },
    bento: { x: 40, y: 40, w: 1000, h: 1160, r: 40, rot: 0 },
  };
  const BENTO_SMALL = { x: 40, y: 40, w: 1000, h: 780, r: 40, rot: 0 };
  const BASE = RECT[MONT.face] || RECT.full;
  const BUBBLE = { x: 750, y: 1600, w: 290, h: 290, r: 145, rot: 0 };
  const ZOOMIN = { x: -620, y: -1250, w: 2320, h: 4420, r: 0, rot: 0 };
  const framed = MONT.face !== 'full' && MONT.face !== 'split';
  const back = mk(stage, 'a', '', 'left:0;top:0;width:1080px;height:1920px;z-index:0');
  stage.insertBefore(back, stage.firstChild);
  const BACK_BG = MONT.face === 'polaroid' ? P.light2 : (ST.tone === 'light' ? P.light : P.dark);
  if (framed || MONT.face === 'split') {
    const dark = lum(BACK_BG) < 0.5;
    back.style.background = MONT.face === 'polaroid' ? `radial-gradient(ellipse at 50% 40%,${P.light},${P.light2})` : bgFor({ tone: dark ? 'dark' : 'light' });
    mk(back, 'a', '', `left:0;top:0;width:1080px;height:1920px;${textureCSS(MONT.face === 'polaroid' ? 'paper' : ST.panel, dark)}`);
    mk(back, 'a', motif(640, dark ? 'rgba(255,255,255,.06)' : rgba(P.ink, 0.05), 1.2), `left:${rv(3) > 0.5 ? 560 : -180}px;top:${1250 + rv(4) * 200}px;transform:rotate(${((rv(5) - 0.5) * 40).toFixed(0)}deg)`);
  }
  const BAND_BG = P.dark, BAND_INK = pick(P.dark, P.light, '#FFFFFF');
  if (MONT.face === 'split') {
    mk(back, 'a', '', `left:0;top:1180px;width:1080px;height:740px;background:${BAND_BG}`);
    mk(back, 'a', '', `left:0;top:1172px;width:1080px;height:16px;background:${P.accent}`);
  }
  const rig = mk(stage, 'a', '', `left:0;top:0;width:1080px;height:1920px;transform-origin:0 0;z-index:1`);
  stage.insertBefore(rig, back.nextSibling);
  const pad = MONT.face === 'world' ? [16, 16, 16, 16] : MONT.face === 'circle' ? [14, 14, 14, 14] : MONT.face === 'polaroid' ? [30, 30, 150, 30] : MONT.face === 'phone' ? [22, 22, 22, 22] : MONT.face === 'window' ? [12, 12, 12, 12] : [0, 0, 0, 0];
  const frameBg = MONT.face === 'world' ? '#FFFFFF' : MONT.face === 'circle' ? P.accent : MONT.face === 'bento' ? 'transparent' : MONT.face === 'polaroid' ? '#FFFFFF' : MONT.face === 'phone' ? '#0D0D10' : MONT.face === 'window' ? P.light : 'transparent';
  rig.style.cssText += `;box-sizing:border-box;background:${frameBg};${framed ? 'box-shadow:0 40px 90px rgba(0,0,0,.45)' : ''}`;
  const faceBox = mk(rig, 'a', '', 'overflow:hidden;background:#000');
  const faceImg = document.createElement('img');
  faceImg.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%;object-fit:cover;object-position:50% 38%;transform-origin:50% 40%';
  faceBox.appendChild(faceImg);
  if (MONT.letterbox) faceImg.style.filter = 'saturate(.7) contrast(1.1) sepia(.12) brightness(.96)';
  const shade = mk(faceBox, 'a', '', 'inset:0;background:radial-gradient(ellipse at 50% 45%,rgba(0,0,0,.25),rgba(0,0,0,.75));opacity:0');
  if (MONT.masthead) {  // couverture: dégradés pour que le titre du magazine et les accroches restent lisibles
    mk(faceBox, 'a', '', 'left:0;top:0;width:100%;height:520px;background:linear-gradient(180deg,rgba(0,0,0,.62),rgba(0,0,0,0))');
    mk(faceBox, 'a', '', 'left:0;bottom:0;width:100%;height:900px;background:linear-gradient(0deg,rgba(0,0,0,.7),rgba(0,0,0,0))');
  }
  if (MONT.face === 'phone') mk(rig, 'a', '', 'left:50%;top:34px;margin-left:-90px;width:180px;height:40px;border-radius:20px;background:#0D0D10;z-index:2');
  if (MONT.face === 'polaroid') {
    mk(rig, 'a', '', `left:50%;top:-30px;margin-left:-120px;width:240px;height:60px;background:${rgba(P.accent2, 0.6)};transform:rotate(${((rv(9) - 0.5) * 8).toFixed(1)}deg);z-index:2`);
    if (BRAND) mk(rig, 'a', esc(BRAND), `left:0;right:0;bottom:44px;text-align:center;font:italic 400 58px DMSerif;color:${P.ink};z-index:2`);
  }
  let curSrc = '', decoding = Promise.resolve();
  function setFrame(t) {
    if (!FR) return;
    const n = Math.max(1, Math.min(FR.count, Math.floor(t * FR.fps + 1e-4) + 1));
    const src = `${FR.url}${String(n).padStart(5, '0')}.${FR.ext || 'jpg'}`;
    if (src !== curSrc) { curSrc = src; faceImg.src = src; decoding = faceImg.decode().catch(() => null); }
  }
  // temps forts pour la caméra: début de chaque phrase / groupe de souffle
  const BEATS = []; WORDS.forEach((w, i) => { const pv = WORDS[i - 1]; if (!pv || w.s - pv.e > 0.25 || /[.?!,]$/.test(pv.w)) BEATS.push(w.s); });
  const Z = [1.0, 1.16, 1.07, 1.22, 1.1];
  function camAt(t) {
    const A = MONT.cam || 0; if (!A) return { z: 1, x: 0, y: 0, r: 0 };
    let i = -1; for (let k = 0; k < BEATS.length; k++) { if (BEATS[k] <= t) i = k; else break; }
    const tgt = (j) => (j < 0 ? { z: 1, x: 0, r: 0 } : { z: Z[j % Z.length], x: (j % 2 ? 1 : -1) * 26, r: (j % 3 === 1 ? 1.4 : j % 3 === 2 ? -1.1 : 0) });
    const a = tgt(i - 1), b = tgt(i), u = i < 0 ? 1 : eo((t - BEATS[i]) / 0.22);
    return { z: 1 + A * (lerp(a.z, b.z, u) - 1), x: A * lerp(a.x, b.x, u), y: 0, r: A * lerp(a.r, b.r, u) };
  }
  const mixRect = (A, B, k) => ({ x: lerp(A.x, B.x, k), y: lerp(A.y, B.y, k), w: lerp(A.w, B.w, k), h: lerp(A.h, B.h, k), r: lerp(A.r, B.r, k), rot: lerp(A.rot, B.rot, k) });
  function fullK(t) { // 0 = état normal, 1 = pendant une démonstration plein écran
    return FULL.reduce((m, s) => Math.max(m, eio(clamp(Math.min((t - s.start + 0.3) / 0.45, (s.end + 0.3 - t) / 0.45)))), 0);
  }
  function floatK(t) { // 0..1 pendant une idée flottante qui prend une tuile
    return (STORY.shots || []).reduce((m, s) => (s.layout === 'float' && (s.scene.type === 'float_card' || s.scene.type === 'stamp_word')
      ? Math.max(m, eio(clamp(Math.min((t - s.start + 0.15) / 0.4, (s.end + 0.1 - t) / 0.4)))) : m), 0);
  }
  function placeFace(t) {
    if (MONT.world) {
      rig.style.left = '70px'; rig.style.top = '170px'; rig.style.width = '940px'; rig.style.height = '1580px';
      rig.style.borderRadius = '56px'; rig.style.transform = ''; rig.style.zIndex = '1'; rig.style.opacity = '1';
      faceBox.style.left = pad[3] + 'px'; faceBox.style.top = pad[0] + 'px';
      faceBox.style.width = `calc(100% - ${pad[1] + pad[3]}px)`; faceBox.style.height = `calc(100% - ${pad[0] + pad[2]}px)`; faceBox.style.borderRadius = '44px';
      const c0 = camAt(t); faceImg.style.transform = `translate(${c0.x.toFixed(1)}px,0) rotate(${c0.r.toFixed(2)}deg) scale(${c0.z.toFixed(4)})`;
      return;
    }
    const k = MONT.full === 'bubble' || MONT.full === 'zoomin' ? fullK(t) : 0;
    let R2 = k > 0 ? mixRect(BASE, MONT.full === 'bubble' ? BUBBLE : ZOOMIN, k) : BASE;
    if (MONT.face === 'bento') R2 = mixRect(R2, BENTO_SMALL, floatK(t));
    const pd = k > 0 && MONT.full === 'bubble' ? [8 * k, 8 * k, 8 * k, 8 * k] : pad;
    let sx = 0, sy = 0; IMPACTS.forEach((q, i) => { const d = t - q; if (d > 0 && d < 0.35) { const a = (1 - d / 0.35) * 10 * (M.shake || 1); sx += a * Math.sin(d * 90 + i); sy += a * Math.cos(d * 77 + i * 2); } });
    const drift = framed ? Math.sin(t * 0.6) * 0.6 : 0;
    rig.style.left = (R2.x + (framed ? sx * 0.5 : 0)).toFixed(1) + 'px'; rig.style.top = (R2.y + (framed ? sy * 0.5 : 0)).toFixed(1) + 'px';
    rig.style.width = R2.w.toFixed(1) + 'px'; rig.style.height = R2.h.toFixed(1) + 'px';
    rig.style.borderRadius = (R2.r + (framed ? 8 : 0)).toFixed(1) + 'px';
    rig.style.transform = `rotate(${(R2.rot + drift).toFixed(2)}deg)`;
    rig.style.zIndex = MONT.full === 'bubble' && k > 0.02 ? '3' : '1';
    rig.style.opacity = MONT.full === 'zoomin' ? (1 - k).toFixed(3) : '1';
    if (MONT.full === 'bubble') { rig.style.background = k > 0.02 ? P.accent : frameBg; rig.style.boxShadow = k > 0.02 ? `0 20px 50px rgba(0,0,0,${(0.5 * k).toFixed(2)})` : ''; }
    faceBox.style.left = pd[3] + 'px'; faceBox.style.top = pd[0] + 'px';
    faceBox.style.width = `calc(100% - ${pd[1] + pd[3]}px)`; faceBox.style.height = `calc(100% - ${pd[0] + pd[2]}px)`;
    faceBox.style.borderRadius = Math.max(0, R2.r - 4).toFixed(1) + 'px';
    const c = camAt(t);
    faceImg.style.transform = `translate(${(c.x + (framed ? 0 : sx)).toFixed(1)}px,${(c.y + (framed ? 0 : sy)).toFixed(1)}px) rotate(${c.r.toFixed(2)}deg) scale(${(c.z * ((sx || sy) && !framed ? 1.03 : 1)).toFixed(4)})`;
    // assombrir le visage quand la typo cinétique ou le mot géant occupe l'image
    const kin = (MONT.skin === 'kinetic' || MONT.skin === 'keyword') ? (STORY.shots || []).reduce((m, s) => (s.layout === 'float' && s.scene.type === 'float_card' ? Math.max(m, clamp(Math.min((t - s.start) / 0.2, (s.end - t) / 0.25))) : m), 0) : 0;
    shade.style.opacity = (0.85 * kin).toFixed(3);
  }

  // habillages permanents de certains modes
  let ticker = null, mast = null;
  if (MONT.ticker) {
    const items = (STORY.shots || []).map((s) => s.scene.title || s.scene.text || '').filter(Boolean).map((x) => up(String(x).replace(/\u00a0/g, ' ')));
    const line = (items.length ? items : [up(BRAND || '')]).join('   •   ');
    ticker = mk(stage, 'a', `<div class="tk" style="white-space:nowrap;font:800 38px/80px Poppins;color:${pick(P.dark, P.light)};padding-left:1080px">${esc(line + '   •   ' + line)}</div>`, `left:0;top:1840px;width:1080px;height:80px;overflow:hidden;background:${P.dark};border-top:6px solid ${P.accent};z-index:5`);
    if (BRAND) mk(ticker, 'a', esc(up(BRAND)), `left:0;top:0;height:80px;padding:0 26px;display:flex;align-items:center;background:${P.bad};font:800 34px Poppins;color:#fff;letter-spacing:.08em`);
  }
  if (MONT.masthead && (BRAND || STORY.masthead)) {
    mast = mk(stage, 'a ctr', '', `top:36px;left:30px;width:1020px;font-family:${HEAD};color:#FFFFFF;line-height:1;letter-spacing:.02em;text-shadow:0 8px 30px rgba(0,0,0,.45);z-index:5`);
    mast.textContent = up(STORY.masthead || BRAND); fit(mast, 1020, 250, 90, 260);
    mk(stage, 'a', '', `left:60px;top:${46 + mast.offsetHeight}px;width:960px;height:4px;background:${P.accent};z-index:5`).className = 'a mrule';
  }

  // habillages permanents des nouvelles grammaires
  const EXTRA = [];
  if (MONT.stories) {
    const segs = []; let prev = 0; WORDS.forEach((w, i) => { const pv = WORDS[i - 1]; if (pv && (w.s - pv.e > 0.45 || /[.?!]$/.test(pv.w)) && w.s - prev > 3) { segs.push([prev, w.s]); prev = w.s; } }); segs.push([prev, T]);
    const top = mk(stage, 'a', '', 'left:24px;top:24px;width:1032px;height:120px;z-index:5');
    const bars = segs.map((sg, i) => mk(top, 'a', '<i style="position:absolute;left:0;top:0;height:100%;background:#fff;border-radius:3px;display:block;width:0"></i>', `left:${(i * 1032 / segs.length).toFixed(1)}px;top:0;width:${(1032 / segs.length - 8).toFixed(1)}px;height:7px;border-radius:4px;background:rgba(255,255,255,.35);overflow:hidden`));
    mk(top, 'a', `<div style="display:flex;align-items:center;gap:18px"><div style="width:82px;height:82px;border-radius:50%;padding:4px;background:${IG}"><div style="width:74px;height:74px;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;overflow:hidden">${LOGO ? `<img src="${LOGO}" style="width:66px;height:66px;object-fit:contain">` : ''}</div></div><span style="font:700 38px Poppins;color:#fff;text-shadow:0 2px 10px rgba(0,0,0,.5)">${esc(BRAND || '')}</span></div>`, 'left:6px;top:28px');
    mk(top, 'a', icon('x', 56, '#fff', 2.6), 'right:6px;top:40px');
    const bot = mk(stage, 'a', `<div style="flex:1;height:110px;border-radius:999px;border:3px solid rgba(255,255,255,.75);display:flex;align-items:center;padding-left:40px;font:500 38px Poppins;color:#fff">Envoyer un message</div>${icon('heart', 62, '#fff', 2.2)}${icon('arrowRight', 62, '#fff', 2.2)}`, 'left:30px;top:1780px;width:1020px;display:flex;align-items:center;gap:30px;z-index:5');
    void bot;
    EXTRA.push((t) => { const hide = fullK(t); vis(top, 1 - hide * 0.0); bars.forEach((b, i) => { const [a, e] = segs[i]; b.firstElementChild.style.width = (clamp((t - a) / (e - a)) * 100).toFixed(1) + '%'; }); });
  }
  if (MONT.hud) {
    const corners = [[0, 0, 0], [1, 0, 90], [1, 1, 180], [0, 1, 270]].map(([x, y, r]) => mk(stage, 'a', `<svg width="120" height="120"><path d="M8 70 V8 H70" fill="none" stroke="#fff" stroke-width="10" stroke-linecap="square"/></svg>`, `left:${x ? 942 : 18}px;top:${y ? 1782 : 18}px;transform:rotate(${r}deg);z-index:5;opacity:.85`));
    const hud = mk(stage, 'a', `<div style="font:400 50px/1 'Bebas';color:#FFD23F;letter-spacing:.08em;text-shadow:0 3px 0 #000">NIV. <span class="lv">1</span></div>
      <div style="display:flex;align-items:center;gap:12px;margin-top:10px"><span style="font:400 36px 'Bebas';color:#fff;width:46px">PV</span><div style="width:300px;height:26px;border:4px solid #fff;background:rgba(0,0,0,.5);padding:3px;box-sizing:border-box;display:flex;gap:3px">${Array.from({ length: 10 }, () => '<i style="flex:1;background:#34D399;display:block"></i>').join('')}</div></div>
      <div style="display:flex;align-items:center;gap:12px;margin-top:8px"><span style="font:400 36px 'Bebas';color:#fff;width:46px">XP</span><div style="width:300px;height:26px;border:4px solid #fff;background:rgba(0,0,0,.5);padding:3px;box-sizing:border-box"><i class="xp" style="display:block;height:100%;background:#60A5FA;width:0"></i></div></div>`, 'left:60px;top:60px;z-index:5');
    const lv = hud.querySelector('.lv'), xp = hud.querySelector('.xp');
    const fulls = (STORY.shots || []).filter((s) => s.layout === 'full').map((s) => s.start);
    EXTRA.push((t) => { lv.textContent = String(1 + fulls.filter((a) => t >= a).length); xp.style.width = (clamp(t / T) * 100).toFixed(1) + '%'; void corners; });
  }
  if (MONT.wave) {
    const ring = mk(stage, 'a', '', 'left:0;top:0;width:1080px;height:1920px;z-index:1;pointer-events:none');
    stage.insertBefore(ring, rig);
    const N = 72, cx = 540, cy = 580, R0 = 350;
    const bars = Array.from({ length: N }, (_, i) => mk(ring, 'a', '', `left:${cx - 5}px;top:${cy}px;width:10px;border-radius:5px;background:${i % 2 ? P.accent : P.accent2};transform-origin:5px 0;transform:rotate(${(i / N * 360 + 180).toFixed(1)}deg) translateY(${R0}px)`));
    const info = mk(stage, 'a ctr', `<div style="font:800 30px Poppins;letter-spacing:.3em;color:${P.accent}">● ÉPISODE</div><div style="margin-top:8px;font:800 56px Poppins;color:${pick(BACK_BG, P.light, '#fff')}">${esc(BRAND || '')}</div>`, 'top:955px;z-index:2');
    const player = mk(stage, 'a', `<div style="display:flex;align-items:center;gap:26px"><div style="width:96px;height:96px;border-radius:50%;background:${P.accent};display:flex;align-items:center;justify-content:center"><svg width="40" height="40" viewBox="0 0 24 24"><rect x="5" y="4" width="5" height="16" fill="${on(P.accent)}"/><rect x="14" y="4" width="5" height="16" fill="${on(P.accent)}"/></svg></div><div style="flex:1"><div style="height:12px;border-radius:6px;background:rgba(255,255,255,.2)"><i class="f" style="display:block;height:12px;border-radius:6px;background:${P.accent};width:0"></i></div><div style="display:flex;justify-content:space-between;margin-top:10px;font:600 30px Poppins;color:rgba(255,255,255,.6)"><span class="c">0:00</span><span>${mmss(T)}</span></div></div></div>`, 'left:60px;top:1760px;width:960px;z-index:2');
    const pf = player.querySelector('.f'), pc = player.querySelector('.c');
    EXTRA.push((t) => { const k = fullK(t); vis(ring, 1 - k); vis(info, 1 - k); bars.forEach((b, i) => { b.style.height = (14 + 90 * VOICE(t, i)).toFixed(0) + 'px'; }); pf.style.width = (clamp(t / T) * 100).toFixed(1) + '%'; pc.textContent = mmss(t); });
  }
  if (MONT.letterbox) {
    ['top', 'bottom'].forEach((side) => mk(stage, 'a', '', `left:0;${side}:0;width:1080px;height:200px;background:#000;z-index:5`));
    mk(stage, 'a', '', 'left:0;top:0;width:1080px;height:1920px;background:radial-gradient(ellipse at 50% 45%,transparent 55%,rgba(0,0,0,.45) 100%);z-index:1;pointer-events:none');
  }
  if (MONT.bento) {
    const capTile = mk(back, 'a', '', `left:40px;top:1240px;width:1000px;height:640px;border-radius:40px;background:${P.dark2}`);
    mk(capTile, 'a', motif(120, rgba('#FFFFFF', 0.12)), 'right:40px;bottom:40px');
    mk(capTile, 'a', `<span style="font:800 26px Poppins;letter-spacing:.3em;color:${P.accent}">EN DIRECT DE LA VIDÉO</span>`, 'left:50px;top:44px');
  }

  // ------------------------------------------------------------------ calque permanent: badge logo + sous-titres
  const persist = mk(stage, 'a', '', 'left:0;top:0;width:1080px;height:1920px;pointer-events:none;z-index:4');
  let badge = null;
  const BK = (ST.badge && ST.badge.kind) || 'card', corner = MONT.ticker || MONT.masthead || MONT.face === 'phone' || MONT.hud ? 'tr' : ((ST.badge && ST.badge.corner) || 'tl');
  if (LOGO && !(MONT.masthead && BRAND) && !MONT.stories) {
    const side = corner === 'tr' ? 'right:36px' : 'left:36px';
    const inner = `<img src="${LOGO}" style="display:block;${BK === 'round' ? 'width:170px;height:170px;object-fit:contain' : BK === 'pill' ? 'height:74px;max-width:300px;object-fit:contain' : 'width:260px;max-height:170px;object-fit:contain'}">`;
    const css = {
      card: 'padding:14px 18px;border-radius:22px;background:rgba(255,255,255,.96);box-shadow:0 10px 26px rgba(0,0,0,.3)',
      bare: 'filter:drop-shadow(0 4px 10px rgba(0,0,0,.55)) drop-shadow(0 0 2px rgba(255,255,255,.8))',
      pill: 'padding:12px 30px;border-radius:999px;background:rgba(255,255,255,.95);box-shadow:0 10px 26px rgba(0,0,0,.3)',
      round: 'padding:8px;border-radius:50%;background:#fff;box-shadow:0 10px 26px rgba(0,0,0,.35);border:5px solid ' + P.accent,
    }[BK] || '';
    badge = mk(persist, 'a', inner, `${side};top:40px;${css}`);
  }
  const capEl = mk(persist, 'a', '', `left:50px;width:980px;top:${CAP_Y}px;text-align:center`);
  const CS = CAP.style || 'box';
  const capFont = {
    box: '700 64px/1.18 Poppins', pill: '700 58px/1.2 Poppins', underline: '800 62px/1.2 Poppins', highlight: '800 62px/1.2 Poppins',
    outline: `400 92px/1.05 ${HEAD}`, bounce: '800 66px/1.18 Poppins', serif: 'italic 400 76px/1.12 DMSerif', ticker: "400 96px/1.02 'Bebas'",
  }[CS] || '700 62px/1.2 Poppins';
  capEl.style.font = capFont;
  const CAPS = CS === 'outline' || CS === 'ticker' || CS === 'underline' || CS === 'highlight';
  // groupes de 1 à 3 mots (≤ 22 caractères), coupés sur la ponctuation et les pauses
  const groups = []; let cur = [];
  WORDS.forEach((w, i) => {
    cur.push(w); const nx = WORDS[i + 1]; const len = cur.map((x) => x.w).join(' ').length;
    if (!nx || cur.length >= 3 || len >= 18 || /[.?!,;:]$/.test(w.w) || nx.s - w.e > 0.32) { groups.push(cur); cur = []; }
  });
  const clean = (s) => String(s).replace(/[.,;:]+$/, '');
  function captionHTML(g, t) {
    return g.map((w) => {
      const act = t >= w.s - 0.02 && t < w.e + 0.06, said = t >= w.s - 0.02;
      let txt = esc(clean(w.w)); if (CAPS) txt = txt.toUpperCase();
      const base = `display:inline-block;margin:0 ${CS === 'bounce' ? 14 : CS === 'outline' || CS === 'ticker' ? 8 : 6}px;`;
      switch (CS) {
        case 'box': return `<span style="${base}padding:0 10px;border-radius:12px;${act ? `background:${P.accent};color:${on(P.accent)};` : `color:${said ? '#fff' : 'rgba(255,255,255,.6)'};`}text-shadow:${act ? 'none' : '0 4px 0 rgba(0,0,0,.45),0 0 20px rgba(0,0,0,.5)'}">${txt}</span>`;
        case 'pill': return `<span style="${base}color:${act ? P.accent : '#fff'}">${txt}</span>`;
        case 'underline': return `<span style="${base}color:#fff;text-shadow:0 4px 14px rgba(0,0,0,.6);background:linear-gradient(${P.accent},${P.accent}) no-repeat 0 100%/${act ? 100 : 0}% 10px;padding-bottom:6px">${txt}</span>`;
        case 'highlight': return `<span style="${base}padding:0 12px;color:${act ? P.ink : '#fff'};background:${act ? P.accent2 : 'transparent'};transform:${act ? 'rotate(-1.5deg)' : 'none'};text-shadow:${act ? 'none' : '0 4px 14px rgba(0,0,0,.7)'}">${txt}</span>`;
        case 'outline': return `<span style="${base}color:${act ? P.accent : '#fff'};-webkit-text-stroke:10px ${P.dark};paint-order:stroke fill;letter-spacing:.02em">${txt}</span>`;
        case 'bounce': { const s = act ? 1 + 0.16 * Math.max(0, 1 - (t - w.s) / 0.18) + 0.06 : 1; return `<span style="${base}color:${act ? P.accent : '#fff'};transform:scale(${s.toFixed(3)});-webkit-text-stroke:8px rgba(0,0,0,.55);paint-order:stroke fill">${txt}</span>`; }
        case 'serif': return `<span style="${base}color:${act ? P.accent2 : '#fff'};text-shadow:0 4px 18px rgba(0,0,0,.75)">${txt}</span>`;
        case 'ticker': return `<span style="${base}padding:0 12px;${act ? `background:${P.light};color:${P.ink};` : 'color:#fff;'}text-shadow:${act ? 'none' : '0 4px 12px rgba(0,0,0,.7)'}">${txt}</span>`;
        default: return `<span style="${base}color:#fff">${txt}</span>`;
      }
    }).join('');
  }
  const covering = (t) => FULL.some((s) => t >= s.start - 0.05 && t <= s.end + 0.05);
  const floatLow = (t) => (STORY.shots || []).some((s) => s.layout === 'float' && s.scene.type === 'float_card' && t >= s.start && t <= s.end
    && (s.scene.hide_captions || MONT.skin === 'kinetic' || MONT.skin === 'keyword' || MONT.skin === 'dialog' || MONT.skin === 'sticker' || (MONT.skin === 'card' && MONT.face === 'full' && false)));


  // ================================================================== VOYAGE PLAN-SÉQUENCE
  // L'image n'est plus un écran: c'est une immense carte. Le visage est posé sur une
  // étape, chaque démonstration est une autre étape plus loin sur la route. Entre les
  // deux, la caméra VOYAGE (dézoom, déplacement, rotation). Avant la fin elle recule
  // pour montrer tout le chemin parcouru, puis plonge sur la carte d'arrivée.
  const WORLD = !!MONT.world;
  const PAGES = [];            // {x, y, rot, kind: 'home'|'stop', shot, from}
  const HOLDS = [];            // {t0, t1, page} — la caméra est posée sur la page
  let wf = null, wb = null, homeEl = null, WB0 = { x: 0, y: 0 };
  if (WORLD) {
    const fulls = (STORY.shots || []).filter((s) => s.layout === 'full').sort((a, b) => a.start - b.start);
    let x = 0, y = 0, k = 0;
    const next = (kind, shot) => {
      if (PAGES.length) {
        const ang = (rv(k * 7 + 1) - 0.5) * 1.3 + (k % 2 ? 0.35 : -0.35);
        x += Math.round(1500 * Math.cos(ang)); y += Math.round(1150 * Math.sin(ang) + 520);
      }
      const pg = { x, y, rot: +((rv(k * 7 + 3) - 0.5) * 16).toFixed(2), kind, shot, i: PAGES.length }; k++;
      PAGES.push(pg); return pg;
    };
    let home = next('home', null); home.from = -1;
    let tFree = 0;
    let skipHome = false;
    fulls.forEach((s, j) => {
      const isEnd = s.scene.type === 'end_card';
      const tr = isEnd ? 1.6 : 0.75;
      if (!skipHome) HOLDS.push({ t0: tFree, t1: Math.max(tFree, s.start - tr + 0.15), page: home });
      skipHome = false;
      const stop = next('stop', s); s._page = stop;
      const nxt = fulls[j + 1];
      const adj = nxt && nxt.start - s.end <= 1.9;
      const trN = nxt && nxt.scene.type === 'end_card' ? 1.6 : 0.75;
      HOLDS.push({ t0: s.start + 0.15, t1: adj ? Math.max(s.start + 0.2, Math.min(s.end - 0.05, nxt.start - trN + 0.15)) : s.end - 0.05, page: stop, deep: isEnd });
      if (!isEnd && !adj) {
        home = next('home', null); home.from = s.end - 0.05; tFree = s.end + 0.7;
      } else { tFree = s.end + 0.05; skipHome = true; }
    });
    if (!fulls.length || fulls[fulls.length - 1].scene.type !== 'end_card') HOLDS.push({ t0: tFree, t1: T + 1, page: home });
    // couches du monde (fond, visage, scènes) sous une seule caméra
    const xs = PAGES.map((p) => p.x), ys = PAGES.map((p) => p.y);
    WB0 = { x: Math.min(...xs) - 6000, y: Math.min(...ys) - 6000 };
    const WW = Math.max(...xs) - WB0.x + 1080 + 6000, WH = Math.max(...ys) - WB0.y + 1920 + 6000;
    wb = mk(stage, 'a', '', `left:0;top:0;width:${WW}px;height:${WH}px;transform-origin:0 0;z-index:0;background:${P.dark};` +
      `background-image:radial-gradient(${rgba(P.light, 0.13)} 3px,transparent 3.5px),linear-gradient(${rgba(P.light, 0.04)} 2px,transparent 2px),linear-gradient(90deg,${rgba(P.light, 0.04)} 2px,transparent 2px);background-size:60px 60px,360px 360px,360px 360px`);
    stage.insertBefore(wb, stage.firstChild);
    // la route: courbe pointillée qui relie les étapes dans l'ordre de visite
    const C_ = PAGES.map((p) => [p.x - WB0.x + 540, p.y - WB0.y + 960]);
    let d = `M${C_[0][0]} ${C_[0][1]}`;
    for (let i = 1; i < C_.length; i++) { const [ax, ay] = C_[i - 1], [bx, by] = C_[i]; d += ` Q${((ax + bx) / 2 + (i % 2 ? 380 : -380)).toFixed(0)} ${((ay + by) / 2).toFixed(0)} ${bx} ${by}`; }
    wb.innerHTML = `<svg width="${WW}" height="${WH}" style="position:absolute;left:0;top:0"><path d="${d}" fill="none" stroke="${rgba(P.accent, 0.95)}" stroke-width="22" stroke-dasharray="46 34" stroke-linecap="round"/>` +
      C_.map(([cx, cy], i) => `<circle cx="${cx}" cy="${cy}" r="120" fill="${P.accent}" opacity=".18"/>`).join('') + '</svg>';
    // décor de carte: motifs et repères éparpillés
    for (let i = 0; i < 26; i++) mk(wb, 'a', motif(180 + Math.round(rv(i + 400) * 200), rgba(P.light, 0.07), 1.4), `left:${Math.round(rv(i + 500) * (WW - 300))}px;top:${Math.round(rv(i + 600) * (WH - 300))}px;transform:rotate(${Math.round((rv(i + 700) - 0.5) * 60)}deg)`);
    // chaque étape: numéro sur la route + empreinte (cadre vide) là où le visage est passé
    PAGES.forEach((p, i) => {
      const lx = p.x - WB0.x, ly = p.y - WB0.y;
      mk(wb, 'a', `<span style="display:inline-flex;align-items:center;gap:14px;background:${P.light};color:${P.ink};font:800 44px Poppins;letter-spacing:.12em;padding:14px 30px;border-radius:999px;box-shadow:0 10px 30px rgba(0,0,0,.35)">${icon('target', 44, P.accent, 2.6)}ÉTAPE ${i + 1}</span>`, `left:${lx + 60}px;top:${ly - 260}px;transform:rotate(${p.rot}deg);transform-origin:480px 1220px`);
      if (p.kind === 'home') mk(wb, 'a', '', `left:${lx + 70}px;top:${ly + 170}px;width:940px;height:1580px;border:10px dashed ${rgba(P.light, 0.25)};border-radius:56px;transform:rotate(${p.rot}deg);transform-origin:470px 790px`);
    });
    wf = mk(stage, 'a', '', 'left:0;top:0;width:1080px;height:1920px;transform-origin:0 0;z-index:1');
    stage.insertBefore(wf, wb.nextSibling);
    homeEl = mk(wf, 'a', '', 'left:0;top:0;width:1080px;height:1920px;transform-origin:540px 960px');
  }
  const worldPage = (pg) => `translate(${pg.x}px,${pg.y}px) rotate(${pg.rot}deg)`;
  function homeAt(t) {
    let h = PAGES[0];
    PAGES.forEach((p) => { if (p.kind === 'home' && p.from <= t) h = p; });
    return h;
  }
  const pageCam = (pg) => ({ x: pg.x + 540, y: pg.y + 960, z: 1, r: pg.rot });
  function worldCam(t) {
    let i = HOLDS.findIndex((h) => t <= h.t1);
    if (i < 0) i = HOLDS.length - 1;
    const h = HOLDS[i];
    if (t >= h.t0 || i === 0) return pageCam(h.page);
    const pv = HOLDS[i - 1], A_ = pageCam(pv.page), B_ = pageCam(h.page);
    const u = clamp((t - pv.t1) / Math.max(0.05, h.t0 - pv.t1)), e = eio(u);
    const zmin = h.deep ? 0.19 : 0.43;
    const z = lerp(A_.z, B_.z, e) * (1 - (1 - zmin) * Math.sin(Math.PI * u));
    return { x: lerp(A_.x, B_.x, e), y: lerp(A_.y, B_.y, e), z, r: lerp(A_.r, B_.r, e) };
  }
  if (WORLD) cam.style.transformOrigin = '0 0';
  function applyWorld(t) {
    const c = worldCam(t);
    let sx = 0, sy = 0; IMPACTS.forEach((q, i) => { const d = t - q; if (d > 0 && d < 0.35) { const a = (1 - d / 0.35) * 12 * (M.shake || 1); sx += a * Math.sin(d * 90 + i); sy += a * Math.cos(d * 77 + i * 2); } });
    const cam3 = `translate(${(540 + sx).toFixed(1)}px,${(960 + sy).toFixed(1)}px) rotate(${(-c.r).toFixed(3)}deg) scale(${c.z.toFixed(4)}) translate(${(-c.x).toFixed(1)}px,${(-c.y).toFixed(1)}px)`;
    wf.style.transform = cam3; cam.style.transform = cam3;
    wb.style.transform = `${cam3} translate(${WB0.x}px,${WB0.y}px)`;
    homeEl.style.transform = worldPage(homeAt(t));
    return c;
  }
  // étapes plein écran: de vraies pages posées sur la carte
  function worldDecorate(el) {
    el.style.borderRadius = '56px'; el.style.boxShadow = '0 60px 140px rgba(0,0,0,.55)';
    el.style.outline = `14px solid ${P.light}`;
  }
  function worldPlace(el, t, shot) {
    el.style.clipPath = ''; el.style.opacity = '1'; el.style.filter = 'none'; el.style.webkitMaskImage = '';
    el.style.transformOrigin = '540px 960px';
    el.style.transform = worldPage(shot.layout === 'full' && shot._page ? shot._page : homeAt(t));
  }

  // ---- scènes propres au voyage
  // panneau indicateur: deux flèches de bois qui pivotent sur le poteau
  QV.signpost = function (root, shot, p) {
    const post = mk(root, 'a', '', 'left:505px;top:420px;width:70px;height:1320px;border-radius:14px;background:linear-gradient(90deg,#6B4423,#9A6536 45%,#6B4423)');
    mk(root, 'a', '', 'left:340px;top:1700px;width:400px;height:70px;border-radius:50%;background:rgba(0,0,0,.35)');
    const board = (txt, y, dir, bg, fg, size) => {
      const b = mk(root, 'a', `<div style="padding:40px ${dir > 0 ? 150 : 70}px 40px ${dir > 0 ? 70 : 150}px;font-family:${HEAD};font-size:${size}px;line-height:1;color:${fg};white-space:nowrap">${sayUp(txt)}</div>`,
        `${dir > 0 ? 'left:500px' : 'right:500px'};top:${y}px;background:${bg};clip-path:polygon(${dir > 0 ? '0 0,86% 0,100% 50%,86% 100%,0 100%' : '14% 0,100% 0,100% 100%,14% 100%,0 50%'});transform-origin:${dir > 0 ? '0' : '100%'} 50%`);
      fit(b.firstElementChild, dir > 0 ? 560 : 480, size, 40);
      return b;
    };
    const b1 = board(p.title + ' ?', 520, 1, P.accent, on(P.accent), 150);
    const b2 = p.sub ? board(String(p.sub).replace(/ /g, ' '), 820, -1, P.light, P.ink, 96) : null;
    const tT = wordTime(shot, p.at, 0.05), tS = p.sub ? wordTime(shot, p.sub_at, 0.5) : 0;
    ev(shot.start, 'thud', 0.5); ev(tT, 'whoosh', 0.5); ev(tT + 0.12, 'impact', 0.6); IMPACTS.push(tT + 0.12); if (b2) { ev(tS, 'whoosh', 0.4); ev(tS + 0.12, 'thud', 0.5); }
    return (t) => {
      const g = spring(t, shot.start); post.style.transform = `scaleY(${clamp(g, 0, 1.05).toFixed(3)})`; post.style.transformOrigin = '50% 100%';
      const s1 = pop(t, tT, 12, 0.35); vis(b1, clamp((t - tT) * 8)); b1.style.transform = `rotate(${((1 - s1) * 80).toFixed(1)}deg)`;
      if (b2) { const s2 = pop(t, tS, 12, 0.35); vis(b2, clamp((t - tS) * 8)); b2.style.transform = `rotate(${((1 - s2) * -80).toFixed(1)}deg)`; }
    };
  };
  // cartes d'embarquement: la destination = le mot à écrire en commentaire
  CV.boarding = function (root, shot, p) {
    const opts = (p.options || []).slice(0, 2), ts = ctaTimes(shot, opts);
    mk(root, 'a ctr', `<span style="display:inline-flex;align-items:center;gap:20px;font:800 50px Poppins;letter-spacing:.1em;color:${pick(shot.tone === 'light' ? P.light : P.dark, P.accent, '#fff')}">${icon('plane', 60, P.accent, 2.4)}${TU ? 'ÉCRIS EN COMMENTAIRE' : 'ÉCRIVEZ EN COMMENTAIRE'}</span>`, 'top:170px');
    const passes = opts.map((o, i) => {
      const e = mk(root, 'a', `<div style="display:flex;height:100%"><div style="flex:1;padding:34px 44px;border-right:6px dashed ${rgba(P.ink, 0.25)}">
        <div style="display:flex;justify-content:space-between;font:800 26px Poppins;letter-spacing:.2em;color:${P.accent}"><span>CARTE D'EMBARQUEMENT</span><span>${'AB'[i]}${String(10 + Math.floor(rv(i + 90) * 80))}</span></div>
        <div style="margin-top:22px;font:700 24px Poppins;letter-spacing:.2em;color:${rgba(P.ink, 0.55)}">DESTINATION</div>
        <div class="t" style="margin-top:4px;font-family:${HEAD};font-size:84px;line-height:1;color:${P.ink};white-space:nowrap"></div>
        <div style="display:flex;gap:60px;margin-top:22px;font:700 24px Poppins;letter-spacing:.14em;color:${rgba(P.ink, 0.55)}"><span>PASSAGER<br><b style="font:800 40px Poppins;color:${P.ink};letter-spacing:0">${TU ? 'TOI' : 'VOUS'}</b></span><span>PORTE<br><b style="font:800 40px Poppins;color:${P.ink};letter-spacing:0">COMMENTAIRES</b></span></div></div>
        <div style="width:170px;display:flex;align-items:center;justify-content:center;background:${P.accent}">${icon('plane', 90, on(P.accent), 2.2)}</div></div>`,
        `left:60px;top:${320 + i * 470}px;width:960px;height:410px;background:#fff;border-radius:34px;box-shadow:0 30px 60px rgba(0,0,0,.35);overflow:hidden`);
      e._t = e.querySelector('.t'); e._text = up(o.text || ''); e._t.textContent = e._text; fit(e._t, 700, 84, 40); e._t.textContent = '';
      return e;
    });
    ts.forEach((t0, i) => { ev(t0 - 0.2, 'whoosh', 0.45); tickType(t0, passes[i]._text, 0.04); });
    let stp = null, tR = 0;
    if (p.stamp) {
      tR = wordTime(shot, p.stamp_at || p.stamp, 0.85);
      stp = mk(root, 'a', `<div style="width:400px;height:400px;border-radius:50%;border:14px double ${P.bad};display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;color:${P.bad};font-family:${HEAD};font-size:70px;line-height:1">${icon('check', 70, P.bad, 3)}<div style="margin-top:10px">${sayUp(p.stamp).replace('-', '-<br>')}</div></div>`, `left:600px;top:${320 + opts.length * 470 - 120}px`);
      ev(tR, 'stamp', 0.9); IMPACTS.push(tR);
    }
    return (t) => {
      passes.forEach((e, i) => { const s = spring(t, ts[i] - 0.25); vis(e, clamp((t - ts[i] + 0.3) * 6)); e.style.transform = `translateX(${((1 - s) * 1200).toFixed(0)}px) rotate(${(i ? 2.5 : -2) * s}deg)`; typeText(e._t, e._text, t, ts[i], 0.04, true); });
      if (stp) { const q = pop(t, tR, 20, 0.45); vis(stp, clamp((t - tR) * 10)); stp.style.transform = `rotate(-16deg) scale(${(1.8 - 0.8 * q).toFixed(3)})`; }
    };
  };
  // arrivée: une épingle de carte tombe sur le logo, « destination atteinte »
  EV_.arrival = function (root, shot, p) {
    const { lines, t1, t2, tB } = endTimes(shot, p);
    const dark = shot.tone !== 'light', bgc = dark ? P.dark : P.light;
    const head = mk(root, 'a ctr', `<span style="font:800 40px Poppins;letter-spacing:.3em;color:${pick(bgc, P.accent, P.accent2)}">DESTINATION ATTEINTE</span>`, 'top:170px');
    const plaque = mk(root, 'a', `<div style="padding:60px 50px">${logoHTML(700, 380)}</div>`, `left:110px;top:520px;width:860px;background:#fff;border-radius:40px;box-shadow:0 40px 90px rgba(0,0,0,.45)`);
    const pin = mk(root, 'a', `<svg width="180" height="240" viewBox="0 0 24 32"><path d="M12 0C5.4 0 0 5.4 0 12c0 9 12 20 12 20s12-11 12-20C24 5.4 18.6 0 12 0z" fill="${P.bad}"/><circle cx="12" cy="12" r="5" fill="#fff"/></svg>`, 'left:450px;top:300px;transform-origin:90px 240px');
    let ly2 = 560 + plaque.offsetHeight + 60;
    const ln = lines.map((l, i) => mk(root, 'a ctr', esc(W_(l.text)), `top:${ly2}px;left:60px;width:960px;font:${i ? '800 46px Poppins' : `italic 400 84px/1.1 'DMSerif'`};color:${i ? pick(bgc, P.accent, P.light) : pick(bgc, P.light, P.ink)}`));
    ln.forEach((e) => { e.style.top = ly2 + 'px'; ly2 += e.offsetHeight + 24; });
    const bye = p.bye ? mk(root, 'a ctr', sayUp(p.bye.text), `top:${Math.max(1520, ly2 + 40)}px;font-family:${HEAD};font-size:150px;color:${pick(bgc, P.accent, '#fff')}`) : null;
    const tP = shot.start + 0.5;
    ev(shot.start + 0.1, 'whoosh', 0.5); ev(tP, 'thud', 0.8); ev(tP + 0.05, 'pop_low', 0.5); IMPACTS.push(tP); if (bye) ev(tB, 'ding', 0.6);
    return (t) => {
      vis(head, eo((t - shot.start) / 0.4));
      const s = spring(t, shot.start); vis(plaque, clamp((t - shot.start) * 5)); plaque.style.transform = `scale(${(0.85 + 0.15 * s).toFixed(3)})`;
      const d = pop(t, tP - 0.35, 14, 0.4); vis(pin, clamp((t - tP + 0.35) * 8)); pin.style.transform = `translateY(${((1 - d) * -500).toFixed(0)}px) scale(${(t > tP && t < tP + 0.15 ? 1.08 : 1)},${(t > tP && t < tP + 0.15 ? 0.9 : 1)})`;
      ln.forEach((e, i) => vis(e, eo((t - (i ? t2 : t1)) / 0.4)));
      if (bye) { const q = spring(t, tB - 0.1); vis(bye, clamp((t - tB + 0.1) * 6)); bye.style.transform = `scale(${(0.4 + 0.6 * q).toFixed(3)})`; }
    };
  };
  // panneau routier « attention » qui bascule sur son poteau
  SV.roadsign = function (root, shot, p) {
    const g = mk(root, 'a', `<div style="position:absolute;left:170px;top:280px;width:28px;height:420px;background:#9aa0a6"></div>
      <div style="position:absolute;left:34px;top:0;width:300px;height:300px;transform:rotate(45deg);background:#FFC400;border:16px solid #111;border-radius:26px;box-sizing:border-box"></div>
      <div style="position:absolute;left:0;top:40px;width:368px;text-align:center;font-family:'Anton';font-size:200px;line-height:1;color:#111">!</div>
      <div class="pl" style="position:absolute;left:-220px;top:380px;width:820px;text-align:center"><span style="display:inline-block;background:#fff;border:8px solid #111;border-radius:18px;padding:14px 34px;font-family:${HEAD};font-size:84px;line-height:1;color:#111">${sayUp(p.text)}</span></div>`,
      'left:356px;top:210px;width:368px;height:720px;transform-origin:184px 720px');
    fit(g.querySelector('.pl span'), 780, 84, 40);
    const tS = wordTime(shot, p.at, 0.15); ev(tS - 0.1, 'whoosh', 0.5); ev(tS + 0.1, 'thud', 0.7); IMPACTS.push(tS + 0.1);
    return (t) => { const s = pop(t, tS - 0.1, 14, 0.38), o = floatOut(t, shot); vis(g, clamp((t - tS + 0.15) * 8) * (1 - o)); g.style.transform = `rotate(${((1 - s) * -75 + o * 70).toFixed(1)}deg)`; };
  };
  // épingle de carte qui se plante avec son étiquette
  KV.pin = function (root, shot, p) {
    const w = mk(root, 'a', `<svg width="110" height="146" viewBox="0 0 24 32" style="position:absolute;left:0;top:0"><path d="M12 0C5.4 0 0 5.4 0 12c0 9 12 20 12 20s12-11 12-20C24 5.4 18.6 0 12 0z" fill="${P.accent}"/><circle cx="12" cy="12" r="5" fill="#fff"/></svg>
      <span style="position:absolute;left:130px;top:24px;white-space:nowrap;background:${P.light};color:${P.ink};font:800 50px Poppins;letter-spacing:.06em;padding:14px 30px;border-radius:18px;box-shadow:0 14px 30px rgba(0,0,0,.35)">${sayUp(p.text)}</span>`, 'left:90px;top:230px;width:900px;height:160px');
    const tK = wordTime(shot, p.at, 0.1); ev(tK, 'thud', 0.5); ev(tK + 0.05, 'pop', 0.4);
    return (t) => { const d = pop(t, tK - 0.25, 15, 0.42), o = floatOut(t, shot); vis(w, clamp((t - tK + 0.3) * 8) * (1 - o)); w.style.transform = `translateY(${((1 - d) * -300).toFixed(0)}px)`; };
  };

  if (WORLD) { back.style.display = 'none'; homeEl.appendChild(rig); rig.style.boxShadow = '0 60px 140px rgba(0,0,0,.55)'; }

  function update(t) {
    if (WORLD) applyWorld(t);
    const full = covering(t);
    setFrame(t); placeFace(t);
    EXTRA.forEach((f) => f(t));
    if (ticker) { ticker.firstElementChild.style.transform = `translateX(${(-(t * 170) % (ticker.firstElementChild.scrollWidth / 2 + 1)).toFixed(0)}px)`; vis(ticker, 1 - fullK(t) * 0.0); }
    if (mast) { const k = fullK(t); vis(mast, 1 - k); const r = stage.querySelector('.mrule'); if (r) vis(r, 1 - k); }
    if (badge) {
      const fade = FULL.reduce((m, s) => Math.max(m, clamp(Math.min((t - s.start + 0.2) / 0.25, (s.end + 0.2 - t) / 0.25))), 0);
      vis(badge, clamp((t - 0.1) * 4) * (1 - fade));
    }
    const g = groups.find((gr) => t >= gr[0].s - 0.06 && t < gr[gr.length - 1].e + 0.18);
    const show = g && !full && !floatLow(t);
    capEl.style.display = show ? 'block' : 'none';
    if (show) {
      capEl.innerHTML = CS === 'pill' ? `<span style="display:inline-block;padding:10px 26px;border-radius:999px;background:${rgba(P.dark, 0.72)}">${captionHTML(g, t)}</span>` : captionHTML(g, t);
      const e = spring(t, g[0].s - 0.06); capEl.style.transform = `translateY(${((1 - Math.min(1, e)) * 26).toFixed(1)}px) scale(${(0.92 + 0.08 * Math.min(1.05, e)).toFixed(3)})`;
    }
  }
  const grainOn = (t) => covering(t);

  function preload() {
    setFrame(0);
    if (!LOGO) return decoding.then(() => true);
    return new Promise((r) => { const im = new Image(); im.onload = () => r(true); im.onerror = () => r(false); im.src = LOGO; });
  }
  const ready = () => decoding;
  const keep = (shot) => WORLD && shot.layout === 'full';
  return { bgFor, decorate, transition, update, grainOn, preload, ready, keep };
};
