"""Script par RÔLES narratifs, puis traduction en scènes selon le mode de montage.

Un même plan de pub (accroche → symptômes → coup de poing → bascule → révélation → comment ça marche
→ bénéfices → bonus → preuve → offre → action) est mis en scène différemment par chaque mode :
« Studio blanc » le joue avec un ordinateur et des silhouettes, « App 3D » avec un téléphone qui pivote,
« Événement » avec des photos et des montants géants, etc.

IA si disponible (rôles + données d'écran), sinon gabarit rempli avec les réponses de l'entretien.
Jamais de chiffre, de prix, de rareté ou de preuve inventés.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Optional

from .impact_writer import _items, _keyword, _lines, _sent, _you, emoji_for, format_phone, spoken_phone
from .montages import resolve_domain
from .schema import Beat, Brief, Storyboard

logger = logging.getLogger(__name__)

ROLES = ["hook", "symptoms", "punch", "pivot", "reveal", "how", "benefits", "bonus", "proof", "offer", "urgency", "cta"]
ROLE_DOC = {
    "hook": "accroche : la douleur ou le désir de la cible (constat, question, chiffre UNIQUEMENT s'il est fourni). data: {big: '1-2 mots géants', line: 'phrase courte'}",
    "symptoms": "2-4 symptômes / erreurs concrètes. data: {items: [{text: '2-5 mots', emoji, at: 'mot dit'}]}",
    "punch": "coup de poing émotionnel très court (« Et ça, ça fait mal. »). data: {text: '2-4 mots'}",
    "pivot": "bascule « C'est exactement pour ça que… ». data: {lines: ['…'], name: 'marque'}",
    "reveal": "révélation du produit/service. data: {name, tagline: '2-5 mots'}",
    "how": "comment ça marche / démonstration (étapes). data: {title, steps: [{text, at}]}",
    "benefits": "3 bénéfices concrets. data: {items: [{text, emoji, at}]}",
    "bonus": "bonus (UNIQUEMENT si fourni). data: {items: [{text, emoji}]}",
    "proof": "preuve réelle (UNIQUEMENT si fournie). data: {label, items: [...]}",
    "offer": "prix / remise (UNIQUEMENT si fourni). data: {big: 'prix', label}",
    "urgency": "rareté / date limite (UNIQUEMENT si fournie). data: {big, stamp}",
    "cta": "appel à l'action final. data: {button, tagline}",
}


_STOP_END = {"de", "des", "du", "la", "le", "les", "tes", "ses", "vos", "nos", "ton", "ta", "ton", "votre", "notre", "en", "et", "à", "a", "au", "aux",
             "un", "une", "pour", "sur", "dans", "avec", "par", "d", "l", "qui", "que"}


def _short(text: str, n: int = 5) -> str:
    """Accroche courte qui ne se termine jamais sur un mot-outil (« Une vision claire »)."""
    ws = (text or "").split()[:n]
    while ws and ws[-1].lower().strip(",.'’") in _STOP_END:
        ws.pop()
    return " ".join(ws).rstrip(",;:")


# --------------------------------------------------------------------------- plan sans IA
def plan_fallback(b: Brief) -> list[dict[str, Any]]:
    y = _you(b); dom = resolve_domain(b.domain)
    name = (b.offer or b.business or "Notre offre").strip(); brand = (b.business or name).strip()
    plan: list[dict[str, Any]] = []
    add = lambda role, say, **data: plan.append({"role": role, "text": say, "data": data})  # noqa: E731
    prob = _sent(b.problem) or _sent(f"{y['vous'].capitalize()} cherchez une solution qui marche vraiment")
    add("hook", prob, big=_keyword(b.audience or b.problem).upper()[:12] or "STOP", line=prob.rstrip("."))
    cons = _items(b.consequences) or ["Du temps perdu", "De l'argent gaspillé", "Toujours le même problème"]
    cons = cons[:3]
    low = lambda c: c[:1].lower() + c[1:] if len(c) > 1 and c[1:2].islower() else c  # noqa: E731
    add("symptoms", "Résultat : " + ", ".join(low(c) for c in cons) + ".", items=[{"text": c, "emoji": emoji_for(c, "❌"), "at": _keyword(c)} for c in cons])
    add("punch", "Et ça, ça fait mal.", text="Ça fait mal")
    add("pivot", f"C'est exactement pour ça que {brand} existe.", lines=["C'est exactement", "pour ça que"], name=brand)
    desc = b.product_desc if b.product_desc and len(b.product_desc.split()) <= 20 else ""
    steps = _items(b.product_desc, 3) if b.product_desc else []
    if len(steps) >= 2:  # la description passe dans « comment ça marche », la révélation reste courte
        add("reveal", f"Voici {name}.", name=name, tagline=_short(b.promise))
    else:
        add("reveal", f"Voici {name}. {_sent(desc)}".strip(), name=name, tagline=_short(b.promise))
    if desc or b.promise:
        if len(steps) >= 2:
            add("how", "Concrètement : " + ", ".join(low(s) for s in steps) + ".", title="Comment ça marche", steps=[{"text": s, "at": _keyword(s)} for s in steps])
    bens = [x for x in (b.benefits or []) if x][:3]
    if bens:
        add("benefits", " ".join(_sent(x) for x in bens), items=[{"text": x, "emoji": emoji_for(x, "✅"), "at": _keyword(x)} for x in bens])
    if b.proof:
        add("proof", _sent(b.proof), label="Testé et approuvé", items=[{"text": b.proof[:40], "emoji": "⭐"}])
    if b.promise:
        prom = _sent(b.promise)
        add("benefits" if not bens else "how", f"Résultat : {prom[:1].lower() + prom[1:]}", items=[{"text": b.promise[:40], "emoji": "🚀", "at": _keyword(b.promise)}],
            title="Le résultat", result=True, steps=[{"text": " ".join(b.promise.split()[:6]), "at": _keyword(b.promise)}])
    if b.price:
        add("offer", f"Et tout ça pour seulement {b.price.strip().rstrip('.')}.", big=b.price.strip().rstrip(".")[:30], label="Seulement")
    phone = format_phone(b.contact_phone)
    cta = f"{y['cliquez']} sur le lien sous cette vidéo"
    cta += f", ou {y['appelez']} dès maintenant le {spoken_phone(phone)}." if phone else "."
    add("cta", cta, button=f"{y['cliquez']} sur le lien", tagline=(b.cta_detail or brand)[:44], phone=phone)
    return plan


# --------------------------------------------------------------------------- traduction rôle -> scène
def _it(d: dict, key: str = "items") -> list[dict[str, Any]]:
    out = []
    for x in d.get(key) or []:
        out.append(x if isinstance(x, dict) else {"text": str(x)})
    return out


Mapper = Callable[[str, str, dict[str, Any], Brief, int], dict[str, Any]]


def map_studio(role: str, text: str, d: dict[str, Any], b: Brief, i: int) -> dict[str, Any]:
    if role == "hook":
        big = str(d.get("big") or "").strip()
        if big and len(big) <= 9:
            return {"type": "st_stat", "big": big, "line": d.get("line") or text, "big_at": big}
        return {"type": "st_words", "lines": _lines(text, 3, 3)}
    if role == "symptoms":
        return {"type": "st_pattern", "pattern": (b.offer or b.business or "").split()[0] if (b.offer or b.business) else "STOP",
                "items": _it(d)[:4], "emoji": (_it(d) or [{}])[0].get("emoji", "😩")}
    if role == "punch":
        return {"type": "st_dark", "text": d.get("text") or "Ça fait mal", "at": "mal"}
    if role == "pivot":
        return {"type": "st_chess", "big": d.get("name") or b.business, "sub": text, "at": _keyword(d.get("name") or b.business)}
    if role == "reveal":
        return {"type": "st_product", "name": d.get("name") or b.offer, "sub": d.get("tagline", ""), "at": _keyword(d.get("name") or b.offer)}
    if role == "how":
        steps = _it(d, "steps")
        return {"type": "st_laptop", "title": d.get("title") or "Comment ça marche", "screen": "list",
                "rows": [s.get("text", "") for s in steps][:4] or None, "sub": steps[0].get("text", "") if steps else "",
                "tag": steps[-1].get("text", "")[:22] if len(steps) > 1 else "", "tag_at": steps[-1].get("at") if steps else None}
    if role == "benefits":
        return {"type": "st_checklist", "badge": b.offer or b.business, "items": _it(d)[:4], "title": "Ce que tu obtiens" if b.tone == "tu" else "Ce que vous obtenez"}
    if role == "bonus":
        return {"type": "st_bonus", "items": _it(d)[:4]}
    if role == "proof":
        return {"type": "st_shield", "label": d.get("label") or "Testé et approuvé", "items": _it(d)[:3]}
    if role == "offer":
        return {"type": "st_offer", "big": d.get("big") or b.price, "label": d.get("label") or "Offre exceptionnelle", "at": _keyword(str(d.get("big") or ""))}
    if role == "urgency":
        return {"type": "st_scarcity", "big": d.get("big", ""), "stamp": d.get("stamp", "")}
    if role == "cta":
        return {"type": "st_cta", "button": d.get("button") or "Clique sur le bouton", "stamp": "Profitez de l'offre", "phone": d.get("phone") or format_phone(b.contact_phone),
                "call_at": "appel", "tagline": d.get("tagline", "")}
    return {"type": "st_words", "lines": _lines(text, 3, 3)}


def map_dossier(role: str, text: str, d: dict[str, Any], b: Brief, i: int) -> dict[str, Any]:
    name = d.get("name") or b.offer or b.business
    if role == "hook":
        return {"type": "ds_count", "line": d.get("line") or text.rstrip("."), "at": _keyword(text)}
    if role == "symptoms":
        return {"type": "ds_timer", "brand": (b.offer or b.business or "")[:40], "items": _it(d)[:4]}
    if role == "punch":
        return {"type": "ds_envelope", "line": d.get("text") or "Ça fait mal", "stamp": "REFUSÉ", "paper": "Résultat", "at": _keyword(text)}
    if role == "pivot":
        return {"type": "ds_title", "red": True, "lines": [" ".join(d.get("lines") or ["C'est pour ça que"]), d.get("name") or b.business]}
    if role == "reveal":
        return {"type": "ds_reveal", "name": name, "pre": d.get("tagline", ""), "at": _keyword(name)}
    if role == "how":
        if d.get("result"):
            return {"type": "ds_imagine", "line": text.rstrip("."), "at": _keyword(text), "emoji": "🥳"}
        steps = _it(d, "steps")
        return {"type": "ds_folders", "title": d.get("title") or "Au programme", "items": steps[:5]}
    if role == "benefits":
        return {"type": "ds_book", "items": _it(d)[:4]}
    if role == "bonus":
        return {"type": "ds_bonus", "items": _it(d)[:3], "title": "En bonus"}
    if role == "proof":
        return {"type": "ds_proof", "items": _it(d)[:3]}
    if role == "offer":
        return {"type": "ds_offer", "big": d.get("big") or b.price, "label": d.get("label") or "Seulement", "at": _keyword(str(d.get("big") or ""))}
    if role == "urgency":
        return {"type": "ds_title", "red": True, "lines": [x for x in (d.get("big", ""), d.get("stamp", "")) if x] or _lines(text, 3, 3)}
    if role == "cta":
        return {"type": "ds_cta", "button": d.get("button") or "Cliquez sur le lien", "stamp": "VALIDÉ", "phone": d.get("phone") or format_phone(b.contact_phone),
                "click_at": "lien", "call_at": "appel"}
    return {"type": "ds_title", "lines": _lines(text, 3, 3)}


def map_app(role: str, text: str, d: dict[str, Any], b: Brief, i: int) -> dict[str, Any]:
    name = d.get("name") or b.offer or b.business
    y = _you(b)
    if role == "hook":
        big = str(d.get("big") or _keyword(text)).strip()
        return {"type": "ap_hook", "pill": big[:18], "line": d.get("line") or text.rstrip("."), "at": _keyword(big)}
    if role == "symptoms":
        return {"type": "ap_pills", "items": _it(d)[:4]}
    if role == "punch":
        return {"type": "ap_person", "bubble": d.get("text") or "Ça fait mal", "emoji": "😩", "at": _keyword(d.get("text") or text)}
    if role == "pivot":
        return {"type": "ap_trio", "title": d.get("name") or b.business}
    if role == "reveal":
        return {"type": "ap_reveal", "name": name, "tagline": d.get("tagline", ""), "at": _keyword(name)}
    if role == "how":
        if d.get("result"):
            st = _it(d, "steps")
            return {"type": "ap_kin", "small": "Résultat :", "big": (st[0].get("text") if st else "") or text, "screen": "success", "at": st[0].get("at") if st else None}
        return {"type": "ap_steps", "title": d.get("title") or "Comment ça marche ?", "steps": _it(d, "steps")[:3]}
    if role == "benefits":
        return {"type": "ap_chips", "title": "Ce que tu obtiens" if b.tone == "tu" else "Ce que vous obtenez", "items": _it(d)[:4]}
    if role == "bonus":
        return {"type": "ap_pills", "title": "En bonus", "items": _it(d)[:3]}
    if role == "proof":
        return {"type": "ap_person", "bubble": (d.get("label") or "Testé et approuvé")[:30], "emoji": "😃"}
    if role == "offer":
        return {"type": "ap_price", "big": d.get("big") or b.price, "label": d.get("label") or "Seulement", "at": _keyword(str(d.get("big") or ""))}
    if role == "urgency":
        return {"type": "ap_text", "lines": [x for x in (d.get("big", ""), d.get("stamp", "")) if x] or _lines(text, 3, 3)}
    if role == "cta":
        return {"type": "ap_cta", "button": d.get("button") or f"{y['cliquez']} sur le lien", "phone": d.get("phone") or format_phone(b.contact_phone),
                "tagline": d.get("tagline", ""), "click_at": "lien", "call_at": "appel"}
    return {"type": "ap_text", "lines": _lines(text, 3, 3)}


def map_lifestyle(role: str, text: str, d: dict[str, Any], b: Brief, i: int) -> dict[str, Any]:
    name = d.get("name") or b.offer or b.business
    y = _you(b)
    if role == "hook":
        big = str(d.get("big") or "").strip()
        return {"type": "ls_hero", "big": big if big and len(big) <= 14 else _keyword(text).upper(), "line": d.get("line") or text.rstrip("."), "at": _keyword(big or text), "emoji": "🤔"}
    if role == "symptoms":
        return {"type": "ls_switch", "items": _it(d)[:4]}
    if role == "punch":
        return {"type": "ls_punch", "text": d.get("text") or "Ça fait mal", "at": _keyword(d.get("text") or text)}
    if role == "pivot":
        return {"type": "ls_text", "lines": [" ".join(d.get("lines") or ["C'est pour ça que"]), d.get("name") or b.business]}
    if role == "reveal":
        return {"type": "ls_reveal", "name": name, "tagline": d.get("tagline", ""), "at": _keyword(name)}
    if role == "how":
        st = _it(d, "steps")
        if d.get("result"):
            return {"type": "ls_hero", "big": _short((st[0].get("text") if st else "") or text, 4), "line": "", "at": st[0].get("at") if st else None, "emoji": "😍"}
        return {"type": "ls_device", "line": text.rstrip("."), "screen": d.get("title") or name}
    if role == "benefits":
        return {"type": "ls_benefits", "items": _it(d)[:4]}
    if role == "bonus":
        return {"type": "ls_switch", "items": _it(d)[:3]}
    if role == "proof":
        return {"type": "ls_text", "lines": [d.get("label") or "Testé et approuvé", *(x.get("text", "") for x in _it(d)[:1])]}
    if role == "offer":
        return {"type": "ls_price", "big": d.get("big") or b.price, "label": d.get("label") or "Seulement", "at": _keyword(str(d.get("big") or ""))}
    if role == "urgency":
        return {"type": "ls_text", "lines": [x for x in (d.get("big", ""), d.get("stamp", "")) if x] or _lines(text, 3, 3)}
    if role == "cta":
        return {"type": "ls_cta", "button": d.get("button") or f"{y['cliquez']} sur le lien", "phone": d.get("phone") or format_phone(b.contact_phone),
                "tagline": d.get("tagline", ""), "click_at": "lien", "call_at": "appel"}
    return {"type": "ls_text", "lines": _lines(text, 3, 3)}


def map_event(role: str, text: str, d: dict[str, Any], b: Brief, i: int) -> dict[str, Any]:
    name = d.get("name") or b.offer or b.business
    y = _you(b)
    if role == "hook":
        return {"type": "ev_photo", "line": d.get("line") or text.rstrip("."), "hi": _keyword(text), "at": _keyword(text)}
    if role == "symptoms":
        return {"type": "ev_list", "items": _it(d)[:4]}
    if role == "punch":
        return {"type": "ev_punch", "text": d.get("text") or "Ça fait mal", "at": _keyword(d.get("text") or text)}
    if role == "pivot":
        return {"type": "ev_title", "line": text.rstrip("."), "hi": d.get("name") or b.business}
    if role == "reveal":
        return {"type": "ev_reveal", "pre": "Voici", "name": name, "tagline": d.get("tagline", ""), "at": _keyword(name)}
    if role == "how":
        if d.get("result"):
            st = _it(d, "steps")
            return {"type": "ev_title", "line": text.rstrip("."), "hi": (st[0].get("text") if st else "") or _keyword(text)}
        return {"type": "ev_list", "title": d.get("title") or "Au programme", "items": _it(d, "steps")[:4]}
    if role == "benefits":
        return {"type": "ev_list", "title": "Ce que tu gagnes" if b.tone == "tu" else "Ce que vous gagnez", "items": _it(d)[:4]}
    if role == "bonus":
        return {"type": "ev_list", "title": "En bonus", "items": _it(d)[:3]}
    if role == "proof":
        return {"type": "ev_photo", "line": text.rstrip("."), "hi": d.get("label") or ""}
    if role == "offer":
        return {"type": "ev_amount", "big": d.get("big") or b.price, "label": d.get("label") or "Seulement", "at": _keyword(str(d.get("big") or ""))}
    if role == "urgency":
        return {"type": "ev_date", "big": d.get("big", "") or _short(text, 4), "stamp": d.get("stamp", "")}
    if role == "cta":
        return {"type": "ev_poster", "button": d.get("button") or f"{y['cliquez']} sur le lien", "phone": d.get("phone") or format_phone(b.contact_phone),
                "tagline": d.get("tagline", "") or name, "click_at": "lien", "call_at": "appel"}
    return {"type": "ev_title", "line": text.rstrip(".")}


MAPPERS: dict[str, Mapper] = {"studio": map_studio, "dossier": map_dossier, "app": map_app, "lifestyle": map_lifestyle, "event": map_event}
STUDIO_ROLES_SCENES = {
    "studio": ["st_stat", "st_laptop", "st_grid", "st_figure", "st_dark", "st_pattern", "st_product", "st_chess", "st_stage",
               "st_checklist", "st_shield", "st_bonus", "st_scarcity", "st_offer", "st_cta", "st_words"],
    "dossier": ["ds_count", "ds_timer", "ds_envelope", "ds_reveal", "ds_folders", "ds_book", "ds_bonus", "ds_imagine", "ds_proof",
                "ds_offer", "ds_cta", "ds_title"],
    "lifestyle": ["ls_hero", "ls_device", "ls_switch", "ls_punch", "ls_reveal", "ls_benefits", "ls_price", "ls_cta", "ls_text"],
    "event": ["ev_title", "ev_photo", "ev_list", "ev_punch", "ev_reveal", "ev_amount", "ev_date", "ev_poster"],
    "app": ["ap_hook", "ap_kin", "ap_pills", "ap_person", "ap_reveal", "ap_steps", "ap_trio", "ap_chips", "ap_price", "ap_cta", "ap_text"],
}


def plan_to_board(plan: list[dict[str, Any]], b: Brief, montage: str) -> Storyboard:
    mapper = MAPPERS[montage]
    beats = []
    for i, step in enumerate(plan):
        role = step.get("role") if step.get("role") in ROLES else "pivot"
        if role in ("offer",) and not b.price:
            continue
        if role in ("proof",) and not b.proof:
            continue
        sc = mapper(role, step["text"], dict(step.get("data") or {}), b, i)
        sc["role"] = role
        beats.append(Beat(text=re.sub(r"\s+", " ", step["text"]).strip(), scene=sc, pause_after=0.22))
    # l'appel à l'action est toujours le dernier, avec le vrai numéro
    if not beats or beats[-1].scene.get("role") != "cta":
        cta = next((s for s in plan_fallback(b) if s["role"] == "cta"), None)
        if cta:
            sc = mapper("cta", cta["text"], cta["data"], b, len(beats)); sc["role"] = "cta"
            beats.append(Beat(text=cta["text"], scene=sc, pause_after=0.3))
    phone = format_phone(b.contact_phone)
    beats[-1].scene["phone"] = phone
    if phone and spoken_phone(phone).split(",")[0] not in beats[-1].text:
        y = _you(b)
        beats[-1].text = re.sub(r"[.!]*$", "", beats[-1].text) + f", ou {y['appelez']} le {spoken_phone(phone)}."
    return Storyboard(angle="pas", template=b.template, beats=beats[:18], title=f"{b.business} — {montage}", notes=[])


# --------------------------------------------------------------------------- IA
def build_prompt(b: Brief, montage: str) -> str:
    dom = resolve_domain(b.domain)
    phone = format_phone(b.contact_phone)
    brief = {k: v for k, v in b.to_dict().items() if v and k not in ("product_image_path", "logo_path", "product_asset", "logo_asset", "template", "angle", "voice", "photo_assets", "screen_assets", "photo_paths", "screen_paths")}
    return f"""Tu es un copywriter publicitaire francophone d'élite (réponse directe, 20 ans) qui écrit pour des pubs vidéo motion design.
Écris le plan d'une pub de 40 à 65 secondes pour ce client. Chaque élément = UNE phrase de voix off + un RÔLE + des données d'écran.

BRIEF : {json.dumps(brief, ensure_ascii=False)}
DOMAINE : {dom['name']}

RÔLES disponibles (dans cet ordre, certains optionnels) :
{json.dumps(ROLE_DOC, ensure_ascii=False, indent=0)}

RÈGLES :
- Ordre obligatoire : hook → symptoms → punch → pivot → reveal → (how) → benefits → (bonus) → (proof) → (offer) → (urgency) → cta.
- Français oral, phrases courtes (3 à 16 mots), rythme rapide, {'tutoiement' if b.tone == 'tu' else 'vouvoiement'}.
- 9 à 14 éléments. Textes à l'écran très courts (1 à 5 mots). Les « at » sont des mots EXACTS de la phrase.
- N'invente AUCUN chiffre, prix, bonus, preuve ou rareté qui n'est pas dans le brief (rôles bonus/proof/offer/urgency seulement si l'info existe).
- cta : « {_you(b)['cliquez']} sur le lien sous cette vidéo »{(', puis le numéro ÉCRIT EN LETTRES : « ' + spoken_phone(phone) + ' »') if phone else ''}.

Réponds UNIQUEMENT en JSON : {{"title": "...", "plan": [{{"role": "...", "text": "...", "data": {{...}}}}]}}"""


def write_motion(b: Brief, montage: str, api_key: Optional[str] = None) -> Storyboard:
    from .writer import _extract_json, chat, llm_available
    if llm_available(api_key):
        try:
            data = _extract_json(chat(build_prompt(b, montage), api_key, temperature=0.8, timeout=120))
            plan = [x for x in data.get("plan", []) if isinstance(x, dict) and str(x.get("text", "")).strip()]
            if len(plan) >= 6:
                board = plan_to_board(plan, b, montage)
                board.notes = ["Script écrit par l'IA."]
                return board
        except Exception as e:  # noqa: BLE001
            logger.warning("script IA (%s) indisponible: %s — gabarit", montage, e)
    board = plan_to_board(plan_fallback(b), b, montage)
    board.notes = ["Script écrit sans IA (gabarit)."]
    return board


def sanitize_motion(board: Storyboard, b: Brief, montage: str) -> Storyboard:
    """Storyboard fourni par le client (aperçu modifié) : on revalide les types et la fin."""
    valid = set(STUDIO_ROLES_SCENES.get(montage, []))
    plan = []
    for beat in board.beats:
        sc = dict(beat.scene or {})
        if valid and sc.get("type") not in valid:
            plan.append({"role": sc.get("role", "pivot"), "text": beat.text, "data": {}})
        else:
            plan.append({"role": sc.get("role", "pivot"), "text": beat.text, "data": {}, "_scene": sc})
    out = plan_to_board([p for p in plan], b, montage)
    for beat, p in zip(out.beats, plan):
        if p.get("_scene"):
            beat.scene = {**p["_scene"], "role": p["role"]}
    return out
