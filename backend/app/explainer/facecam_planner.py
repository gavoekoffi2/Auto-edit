"""Plan des animations plein écran pour une vidéo face caméra.

Entrée: les mots minutés de la vidéo DÉJÀ montée. Sortie: des « cutaways »
{start, end, scene} — des fenêtres où une animation plein écran démontre ce
que dit la personne, entre lesquelles on revient sur son visage.

IA (OpenRouter) si une clé existe, sinon règles locales. Dans les deux cas:
pas d'animation dans l'accroche (1re seconde), au moins ~1,4 s de visage entre
deux animations, aucun chiffre qui ne soit pas prononcé.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from .templates import ICON_NAMES, SCENE_CATALOG
from .writer import _extract_json, _short, chat, guess_icon

logger = logging.getLogger(__name__)

DENSITY = {"light": 0.30, "medium": 0.50, "heavy": 0.68}
MIN_FACE_GAP = 1.4
MIN_LEN, MAX_LEN = 2.2, 8.5
HOOK_FACE = 1.0

_MONEY = re.compile(r"imp[ôo]t|tax|perd|perte|frais|argent|d[ée]pens|co[ûu]t|gaspill|dette|trop cher", re.I)
_CTA = re.compile(r"clique|cliquez|\blien\b|bouton|abonne|whatsapp|[ée]cri(s|vez)[- ]|contacte|appelle[zr]?\b|inscri|commande", re.I)
_NUMW = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9,
         "dix": 10, "quinze": 15, "vingt": 20, "trente": 30, "quarante": 40, "cinquante": 50, "soixante": 60, "cent": 100}
_UNIT = re.compile(r"^(minutes?|min|heures?|jours?|semaines?|mois|ans|années?)$", re.I)
_PCT = re.compile(r"\d+[\d.,]*\s*(%|pour ?cent)", re.I)
_EXCL = re.compile(r"pas pour tout le monde|pas n'importe qui|exclusi|seulement pour|r[ée]serv[ée]|pas donn[ée] à tout", re.I)
_SOL_CUE = re.compile(r"^(?:gr[âa]ce|travers|via|solution|d[ée]couvre[zr]?|utilise[zr]?|choisi[sr]|choisissez)$", re.I)
_PROTECT = re.compile(r"prot[èée]g|s[ée]curis|garanti", re.I)
_COMPARE = re.compile(r"diff[ée]rence entre (\w+) et (?:un |une |les |le |la |l')?([\wÀ-ÿ'-]+)|(?:pas donn[ée]e?|pas pour|pas accessible) (?:aux|à des|aux simples) ([\wÀ-ÿ-]+)", re.I)

_LEAD = re.compile(r"^(?:bonjour|salut|hello|chers?|ch[èe]res?|mes|amis?|et|ou|alors|donc|aussi|m[êe]me|surtout|les gens qui sont|ceux qui sont|celles qui sont|les personnes qui sont|vous qui [êe]tes|toi qui es|en tant que|en tant qu'|comme|si vous [êe]tes|si tu es|tu es|vous [êe]tes|pour les|pour|qu'on soit|que vous soyez|que tu sois)\s+", re.I)
_ART = {"le", "la", "les", "l'", "un", "une", "des", "du", "de", "d'", "dans", "au", "aux", "mon", "ma", "mes", "ton", "ta", "tes",
        "son", "sa", "ses", "notre", "nos", "votre", "vos", "leur", "leurs", "ce", "ces", "cet", "cette"}
_NOT_ITEM = {"que", "qui", "quoi", "savez", "savez-vous", "sais-tu", "est", "c'est", "sont", "pas", "ne", "n'est", "je", "il", "on",
             "nous", "vous", "tu", "moi", "toi", "vient", "fait", "faire", "voir", "allez-y", "ici", "ça", "cela", "comment", "pourquoi"}
_PREP = {"sur", "à", "a", "avec", "par", "sans", "vers", "chez", "sous", "pour", "contre", "entre", "quand", "après", "avant", "depuis"}
_STOPW = _ART | _NOT_ITEM | {"et", "ou", "à", "a", "en", "pour", "sur", "avec", "sans", "par", "très", "plus", "moins", "tout", "tous", "bien"}


def merge_tokens(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recolle les jetons Whisper « d » + « 'entreprise », « savez » + « -vous », « l' » + « assurance »."""
    out: list[dict[str, Any]] = []
    for w in words:
        t = (w.get("w") or "").strip()
        if not t:
            continue
        if out and (t[0] in "'’-" or out[-1]["w"].endswith(("'", "’"))) and not out[-1]["w"].endswith((".", "!", "?", ",")):
            out[-1] = {**out[-1], "w": out[-1]["w"] + t.replace("’", "'"), "e": w["e"]}
            continue
        out.append({**w, "w": t.replace("’", "'")})
    return out


def _n(s: str) -> str:
    return re.sub(r"[^\wÀ-ÿ'-]", "", (s or "").lower())


def _cap(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip(" ,.;:!?")).strip()
    return s[:1].upper() + s[1:] if s else s


def sentences(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Phrases (ponctuation ou pause > 0,55 s), 22 mots max."""
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        gap = (nxt["s"] - w["e"]) if nxt else 9
        if re.search(r"[.!?…;]$", w["w"]) or gap > 0.55 or len(cur) >= 22 or nxt is None:
            out.append({"i": len(out), "start": cur[0]["s"], "end": cur[-1]["e"], "words": cur,
                        "text": " ".join(x["w"] for x in cur).strip()})
            cur = []
    return out


def clauses(ws: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Propositions: coupe après , ; : et avant « et »/« ou »."""
    out, cur = [], []
    for k, w in enumerate(ws):
        tant = _n(w["w"]) == "en" and k + 2 < len(ws) and _n(ws[k + 1]["w"]) == "tant" and _n(ws[k + 2]["w"]).startswith("qu")
        if (_n(w["w"]) in ("et", "ou") or tant) and cur:
            out.append(cur); cur = []
        cur.append(w)
        if re.search(r"[,;:.!?]$", w["w"]):
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    return out


def _text(ws: list[dict[str, Any]]) -> str:
    return " ".join(w["w"] for w in ws).strip(" ,.;:")


def _item(cl: list[dict[str, Any]]) -> Optional[tuple[str, float]]:
    """« les gens qui sont infirmiers, » → (« Infirmiers », t). None si ce n'est pas un élément de liste."""
    ws = list(cl)
    if ws and _n(ws[0]["w"]) in _PREP - {"pour"}:
        return None
    changed = True
    while changed and ws:
        changed = False
        txt = " ".join(_n(w["w"]) for w in ws)
        m = _LEAD.match(txt + " ")
        if m:
            k = len(m.group(0).split())
            if k < len(ws):
                ws = ws[k:]; changed = True
        while ws and _n(ws[0]["w"]) in _ART:
            ws = ws[1:]; changed = True
    if not ws or len(ws) > 4:
        return None
    if _n(ws[0]["w"]) in _PREP:
        return None  # « sur ces biens », « à la retraite »: compléments, pas des éléments
    if any(_n(w["w"]) in _NOT_ITEM or re.search(r"(ez|-(moi|toi|vous|nous|y|le|la|les|lui))$", _n(w["w"])) for w in ws):
        return None  # verbes (« cliquez », « revenez-moi »): pas des éléments de liste
    if _CTA.search(" ".join(w["w"] for w in ws)):
        return None
    if not any(len(_n(w["w"])) >= 4 and _n(w["w"]) not in _STOPW for w in ws):
        return None
    words = [w["w"].strip(" ,.;:!?") for w in ws][:3]
    while len(words) > 1 and _n(words[-1]) in _STOPW:
        words.pop()
    lab = re.sub(r"^[ld]'", "", " ".join(words), flags=re.I)
    return _cap(lab), ws[0]["s"]


def detect_list(ws: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    items, ends, seen = [], [], set()
    for cl in clauses(ws):
        it = _item(cl)
        if not it:
            continue
        key = re.sub(r"s\b", "", " ".join(x for x in it[0].lower().split() if x not in ("grand", "grande", "petit", "petite", "gros", "vrai", "vrais")))
        if key in seen:
            continue
        seen.add(key); items.append(it); ends.append(cl[-1]["e"])
    if len(items) < 3:
        return None
    items, ends = items[:4], ends[:4]
    # on revient au visage à la fin de la proposition du dernier élément, jamais au milieu
    return {"span": (items[0][1], ends[-1]), "items": items}


def _num(tok: str) -> Optional[int]:
    t = _n(tok)
    if t.isdigit():
        return int(t)
    return _NUMW.get(t)


def solution_names(words: list[dict[str, Any]]) -> list[tuple[str, float]]:
    """Noms de solution/produit introduits par « grâce à / à travers / via / découvrez… »."""
    out = []
    for i, w in enumerate(words):
        if not _SOL_CUE.match(_n(w["w"])):
            continue
        j = i + 1
        while j < len(words) and _n(words[j]["w"]) in ("à", "a", "de", "du", "la", "le", "les", "l'", "c'est", "est"):
            j += 1
        name = []
        k = j
        while k < len(words) and len(name) < 3:
            raw = words[k]["w"]; t = _n(raw)
            if t in _NOT_ITEM or (t in _STOPW and name) or t in ("et", "ou", "parce", "car"):
                break
            name.append(raw.strip(" ,.;:!?"))
            k += 1
            if re.search(r"[,;:.!?]$", raw):
                break
        lab = re.sub(r"^[ld]'", "", " ".join(name), flags=re.I)
        if name and len(lab) >= 5 and _n(name[0]) not in _STOPW:
            out.append((_cap(lab), words[j]["s"]))
    return out


def _t(ws: list[dict[str, Any]], pat: str) -> Optional[float]:
    r = re.compile(pat, re.I)
    return next((w["s"] for w in ws if r.search(w["w"])), None)


def detect(sent: dict[str, Any], ctx: dict[str, Any]) -> list[tuple[float, dict[str, Any], tuple[float, float]]]:
    """Scènes possibles pour une phrase: (score, scène, (début, fin) du passage utile)."""
    ws = sent["words"]; t = sent["text"]; low = t.lower(); tone = ctx["tone"]
    whole = (sent["start"], sent["end"])
    found = []
    if _CTA.search(t):
        cls = clauses(ws)
        cl = next((c for c in cls if _CTA.search(_text(c))), ws)
        title = re.sub(r"^(allez-y|alors|donc|et|bon|maintenant)\s*,?\s*", "", _text(cl), flags=re.I)
        wa = re.search(r"whatsapp|[ée]cri", low)
        btn = ("ÉCRIS-MOI" if tone == "tu" else "ÉCRIVEZ-NOUS") if wa else ("CLIQUE ICI" if tone == "tu" else "CLIQUEZ ICI")
        found.append((9, {"type": "cta_button", "title": _cap(" ".join(title.split()[:6])), "button": btn,
                          "click_at": _t(ws, r"lien|bouton|clique|whatsapp|[ée]cri"), "down_at": "bas"}, whole))
    for k, w in enumerate(ws[:-1]):
        v = _num(w["w"])
        if v and _UNIT.match(_n(ws[k + 1]["w"])) and not (v == 1 and _n(w["w"]) in ("un", "une")):
            unit = _n(ws[k + 1]["w"]).upper()
            cap = _cap(_text(next((c for c in clauses(ws) if w in c), ws)))
            found.append((8, {"type": "timer_ring", "value": v, "unit": unit, "at": w["s"], "caption": " ".join(cap.split()[:8])}, whole))
            break
    m = _PCT.search(t)
    if m:
        v = m.group(0).replace("pour cent", "%").replace(" ", "")
        found.append((8, {"type": "stat_number", "value": v, "label": _short(re.sub(re.escape(m.group(0)), "", t), 6), "at": m.group(0).split()[0]}, whole))
    lst = ctx.get("lists", {}).get(sent["i"])
    if lst:
        audience = re.search(r"en tant qu|gens qui sont|vous [êe]tes|tu es|chers?|ch[èe]res", low)
        title = ("Tu es…" if tone == "tu" else "Vous êtes…") if audience else ""
        sc = {"type": "icon_cards", "items": [{"icon": guess_icon(l), "label": l, "at": tt} for l, tt in lst["items"]]}
        if title:
            sc["title"] = title
        found.append((8.5, sc, lst["span"]))
    m = _EXCL.search(t)
    if m:
        cl = next((c for c in clauses(ws) if _EXCL.search(_text(c))), ws)
        found.append((7.5, {"type": "crowd_select", "title": _cap(" ".join(_text(cl).split()[:6])), "at": cl[0]["s"],
                            "select_at": _t(cl, r"importe|monde|seulement|r[ée]serv|donn") or cl[-1]["s"]}, whole))
    m = _COMPARE.search(t)
    if m:
        me = (m.group(1) or "").lower()
        other = (m.group(2) or m.group(3) or "").strip(" ,.?!")
        you = "TOI" if (me in ("toi", "tu") or tone == "tu") else "VOUS"
        a = {"label": other.upper(), "at": _t(ws, re.escape(other[:5])) if other else None,
             "loss": "− IMPÔT" if ctx.get("tax") else "− ARGENT"}
        b = {"label": you, "tag": ctx.get("product") or "", "at": _t(ws, r"^(toi|vous)\b")}
        if other and len(other) >= 4:
            found.append((7, {"type": "split_compare", "a": a, "b": b, "emblem": "shield" if ctx.get("protect") else "star"}, whole))
    if _MONEY.search(t):
        lab = "IMPÔT" if re.search(r"imp[ôo]t|tax", t, re.I) else ("FRAIS" if re.search(r"frais|co[ûu]t|cher", t, re.I) else "PERTES")
        tag = "À LA RETRAITE" if "retraite" in low else ""
        tw = _t(ws, r"imp[ôo]t|tax|frais|perd|perte|argent|co[ûu]t")
        span = (max(sent["start"], (tw or sent["start"]) - 1.8), min(sent["end"], (tw or sent["start"]) + 3.0))
        found.append((6.5, {"type": "loss_drain", "tag": tag, "tag_at": _t(ws, "retraite"), "label": lab,
                            "drain_at": _t(ws, r"payer|perd|perte|gaspill|d[ée]pens") or tw, "label_at": tw}, span))
    names = [n for n in ctx.get("names", []) if sent["start"] - 0.01 <= n[1] <= sent["end"]]
    if names:
        name, tn = names[0]
        other = next((n for n in names[1:] if _n(n[0]) != _n(name)), None)
        sc = {"type": "hero_reveal", "kicker": "La solution", "name": name, "at": tn,
              "emblem": "shield" if ctx.get("protect") else "star"}
        if other:
            sc["sub"] = other[0]; sc["sub_at"] = other[1]
        found.append((7, sc, (max(sent["start"], tn - 1.3), sent["end"])))
    if _PROTECT.search(t):
        cl = next((c for c in clauses(ws) if _PROTECT.search(_text(c))), ws)
        i0 = next(i for i, w in enumerate(cl) if _PROTECT.search(w["w"]))
        name = _cap(" ".join(w["w"] for w in cl[i0:i0 + 3]))
        found.append((5.5, {"type": "hero_reveal", "kicker": "", "name": name, "at": cl[i0]["s"], "emblem": "shield"},
                     (max(sent["start"], cl[i0]["s"] - 1.2), sent["end"])))
    if "?" in t and len(ws) >= 4:
        found.append((4, {"type": "title_slam", "title": _short(t, 7), "at": ws[0]["s"]}, whole))
    return found


def _tone(words: list[dict[str, Any]]) -> str:
    txt = " ".join(w["w"].lower() for w in words)
    return "tu" if len(re.findall(r"\b(tu|ton|ta|tes|toi)\b", txt)) > len(re.findall(r"\b(vous|votre|vos)\b", txt)) else "vous"


def _context(words: list[dict[str, Any]], sents: list[dict[str, Any]]) -> dict[str, Any]:
    txt = " ".join(w["w"] for w in words)
    names = solution_names(words)
    counts: dict[str, int] = {}
    low = txt.lower()
    for n, _ in names:
        counts[n] = low.count(n.lower())
    product = max(counts, key=lambda k: (counts[k], -len(k))) if counts else ""
    lists = {}
    for s in sents:
        for span in ([s], [s, sents[s["i"] + 1]] if s["i"] + 1 < len(sents) else []):
            if not span:
                continue
            d = detect_list([w for x in span for w in x["words"]])
            if d and (s["i"] not in lists or len(d["items"]) > len(lists[s["i"]]["items"])):
                lists[s["i"]] = d
    return {"tone": _tone(words), "names": names, "product": product, "lists": lists,
            "tax": bool(re.search(r"imp[ôo]t", txt, re.I)), "protect": bool(re.search(r"prot[èe]g|assur|s[ée]cur", txt, re.I))}


def _grow(sents: list[dict[str, Any]], i: int, a: float, b: float) -> tuple[float, float]:
    """Élargit un passage trop court: petite phrase juste avant (ex. « … avec moi. » avant
    « Cliquez sur ce lien. »), sinon quelques mots de la suite — jamais une phrase entière."""
    prev = sents[i - 1] if i > 0 else None
    if b - a < MIN_LEN and prev and a - prev["end"] < 0.7 and prev["end"] - prev["start"] < 2.6 \
            and prev["start"] >= HOOK_FACE and b - prev["start"] <= MAX_LEN:
        a = prev["start"]
    if b - a < MIN_LEN:
        after = [w for s in sents[i:] for w in s["words"] if w["e"] >= a + MIN_LEN]
        if after:
            b = max(b, after[0]["e"])
            host = next((x for x in sents[i:] if x["start"] <= after[0]["s"] <= x["end"]), None)
            if host and host["end"] - b <= 2.2 and host["end"] - a <= MAX_LEN:
                b = host["end"]  # finir la phrase plutôt que couper au milieu
    return a, b


MAX_CHAIN = 11.0


def _block(chosen: list[dict[str, Any]], a: float, b: float) -> float:
    """Durée du bloc d'animations contiguës qui contiendrait [a, b]."""
    lo, hi = a, b
    changed = True
    while changed:
        changed = False
        for c in chosen:
            if (abs(c["end"] - lo) < 0.05 or abs(c["start"] - hi) < 0.05) and not (lo <= c["start"] and c["end"] <= hi):
                lo, hi = min(lo, c["start"]), max(hi, c["end"]); changed = True
    return hi - lo


def plan_rules(words: list[dict[str, Any]], duration: float, density: str = "medium") -> list[dict[str, Any]]:
    words = merge_tokens(words)
    sents = sentences(words)
    ctx = _context(words, sents)
    target = DENSITY.get(density, 0.5) * duration
    cands = []
    for s in sents:
        for sc, scene, span in detect(s, ctx):
            cands.append((sc, s["i"], scene, span))
    cands.sort(key=lambda c: (-c[0], c[1]))
    chosen: list[dict[str, Any]] = []
    used = 0.0
    for sc, i, scene, (a, b) in cands:
        if used >= target:
            break
        a, b = _grow(sents, i, a, b)
        a = max(HOOK_FACE, a - 0.15)
        nxt = next((w["s"] for w in words if w["s"] >= b - 0.01), None)
        b = min(duration - 0.4, b + 0.3, a + MAX_LEN, max(b + 0.05, (nxt or 1e9) - 0.03))
        if b - a < 1.6:
            continue
        ok = True
        for c in sorted(chosen, key=lambda x: x["start"]):
            if c["end"] + MIN_FACE_GAP <= a or b + MIN_FACE_GAP <= c["start"]:
                continue
            # trop proche: on enchaîne les deux animations bord à bord (motion → motion)
            if c["start"] < a and b - c["end"] >= MIN_LEN:
                a = c["end"]; continue
            if b < c["end"] and c["start"] - a >= MIN_LEN:
                b = c["start"]; continue
            ok = False; break
        if ok and _block(chosen, a, b) > MAX_CHAIN:
            ok = False  # on revient au visage au moins toutes les ~11 s
        if not ok or b - a < 1.6:
            continue
        if any(c["scene"]["type"] == scene["type"] and abs(c["start"] - a) < 12 and scene["type"] != "cta_button" for c in chosen):
            continue  # pas deux fois la même scène coup sur coup
        chosen.append({"start": round(a, 3), "end": round(b, 3), "scene": scene,
                       "text": " ".join(w["w"] for w in words if a <= w["s"] < b)})
        used += b - a
    chosen.sort(key=lambda c: c["start"])
    # variété: une deuxième liste devient une liste cochée
    seen_cards = False
    for c in chosen:
        sc = c["scene"]
        if sc["type"] == "icon_cards":
            if seen_cards:
                c["scene"] = {"type": "checklist", "title": sc.get("title") or "À retenir",
                              "items": [{**it, "icon": it.get("icon") or "check"} for it in sc["items"][:4]]}
            seen_cards = True
    return chosen


def plan_llm(words: list[dict[str, Any]], duration: float, density: str, api_key: str, language: str = "fr") -> list[dict[str, Any]]:
    words = merge_tokens(words)
    sents = sentences(words)
    listing = [{"i": s["i"], "t": [round(s["start"], 2), round(s["end"], 2)], "text": s["text"]} for s in sents]
    catalog = {k: {"desc": v["desc"], "params": v["params"]} for k, v in SCENE_CATALOG.items() if k not in ("end_card",)}
    prompt = f"""Tu es motion designer. Une personne parle face caméra (vidéo verticale). Choisis les passages où une animation PLEIN ÉCRAN doit DÉMONTRER ce qu'elle dit, puis on revient sur son visage.
Phrases (index, [début, fin] en secondes, texte): {json.dumps(listing, ensure_ascii=False)}
Durée: {duration:.1f} s. Densité: {density} → animations ≈ {int(DENSITY.get(density, .5) * 100)} % de la durée.
Règles:
- Chaque animation couvre 1 à 3 phrases consécutives (from, to), dure 2,5 à 8 s, jamais dans la première seconde, au moins 1,5 s de visage entre deux.
- Garde le visage sur les phrases personnelles/émotionnelles et l'accroche.
- Illustre concrètement: listes → icon_cards/checklist, argent perdu → loss_drain, solution/produit → hero_reveal, comparaison → split_compare/choice_cards, durée → timer_ring, appel à l'action → cta_button, question choc → title_slam, exclusivité → crowd_select, conversation → chat_bubbles.
- Textes à l'écran en {language}, 1 à 5 mots, pris du discours. Les champs « at »/« *_at » = un mot EXACT de la phrase.
- N'invente AUCUN chiffre: stat_number/timer_ring seulement si le chiffre est prononcé.
- Varie les scènes (jamais deux fois la même d'affilée). Icônes: {', '.join(ICON_NAMES)}.
Catalogue: {json.dumps(catalog, ensure_ascii=False)}
Réponds en JSON: {{"cutaways": [{{"from": 0, "to": 1, "scene": {{"type": "...", ...}}}}]}}"""
    data = _extract_json(chat(prompt, api_key, temperature=0.6, timeout=90))
    spoken = " ".join(w["w"] for w in words)
    nums = set(re.findall(r"\d+", spoken)) | {str(_NUMW[w]) for w in re.findall(r"[a-zà-ÿ]+", spoken.lower()) if w in _NUMW}
    out: list[dict[str, Any]] = []
    for c in data.get("cutaways", []):
        try:
            i, j = int(c["from"]), int(c.get("to", c["from"]))
        except (KeyError, TypeError, ValueError):
            continue
        if not (0 <= i <= j < len(sents)):
            continue
        sc = dict(c.get("scene") or {})
        if sc.get("type") not in SCENE_CATALOG or sc.get("type") == "end_card":
            continue
        if sc["type"] in ("stat_number", "timer_ring") and not set(re.findall(r"\d+", str(sc.get("value", "")))) <= nums:
            continue
        for it in sc.get("items", []) if isinstance(sc.get("items"), list) else []:
            if isinstance(it, dict) and it.get("icon") not in ICON_NAMES:
                it["icon"] = guess_icon(it.get("label", ""))
        nxt = sents[j + 1]["start"] if j + 1 < len(sents) else None
        a, b = _window(sents, i, j, nxt)
        b = min(b, a + MAX_LEN)
        if a < HOOK_FACE or b - a < 1.6:
            continue
        if any(not (b + MIN_FACE_GAP <= o["start"] or a >= o["end"] + MIN_FACE_GAP) for o in out):
            continue
        out.append({"start": a, "end": b, "scene": sc, "text": " ".join(s["text"] for s in sents[i:j + 1])})
    out.sort(key=lambda c: c["start"])
    return out


def plan_cutaways(words: list[dict[str, Any]], duration: float, density: str = "medium",
                  api_key: Optional[str] = None, language: str = "fr") -> tuple[list[dict[str, Any]], str]:
    if api_key:
        try:
            plan = plan_llm(words, duration, density, api_key, language)
            if plan:
                return plan, "ia"
        except Exception as e:  # repli local
            logger.warning("plan IA échoué: %s", e)
    return plan_rules(words, duration, density), "regles"
