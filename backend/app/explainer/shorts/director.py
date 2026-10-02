"""Le « réalisateur »: ordre du récit, chapitres, corrections, cartes animées.

Partage des rôles (économie de jetons):
  * LLM (FreeLLMAPI d'abord, OpenRouter ensuite) — ce qui demande d'ÉCRIRE:
    remettre les passages des différents rushes dans un ordre cohérent, couper
    les doublons de fond (même idée reformulée), corriger les mots mal
    transcrits, titrer les chapitres, rédiger le contenu des cartes.
    Il reçoit un transcript compact (« B12: texte »), sans timecodes.
  * Jev — ce qui demande de DÉCIDER: type de contenu, thème visuel, cadrage,
    et VÉRIFICATION de chaque carte proposée par le LLM (fidèle à ce qui est dit ?
    ce verset est-il vraiment celui évoqué ?). Une carte douteuse est retirée.
  * Règles — si aucune IA n'est joignable: ordre des rushes, versets cités à
    voix haute, appel à s'abonner détecté. La vidéo sort quand même.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any, Optional

from . import bible, jev
from .rushes import norm

logger = logging.getLogger(__name__)

CARD_TYPES = ("compare", "list", "steps", "verse", "contrast", "versus", "alert", "keyword", "full", "cta")
TAGS = {"enseignement": "Enseignement", "conseil": "Conseil", "tutoriel": "Tutoriel", "temoignage": "Témoignage",
        "business": "Business", "motivation": "Motivation", "astuce": "Astuce", "analyse": "Analyse", "histoire": "Histoire",
        "actualite": "Actualité", "sante": "Bien-être", "tech": "Tech"}
THEMES = {
    "or_noir": "noir et or, solennel, premium (enseignement, foi, leadership)",
    "braise": "noir, orange et rouge, énergique et percutant (motivation, business, coup de gueule)",
    "ocean": "bleu nuit et cyan, clair et rassurant (tutoriel, tech, santé, explication)",
    "menthe": "vert menthe et crème, frais et positif (conseils de vie, bien-être, astuces)",
    "royal": "violet profond et or, inspirant (témoignage, histoire, foi)",
}

PROMPT = """Tu es le monteur d'une vidéo verticale TikTok « face caméra » en {lang}.
L'orateur a filmé plusieurs rushes (A, B, C…), parfois dans le désordre, parfois en refaisant une partie.
Voici ses passages, un par ligne, sous la forme « ID: texte » (ordre de tournage, rush par rush):

{units}

Durée brute ≈ {dur:.0f} s. Réponds UNIQUEMENT avec un objet JSON valide, sans commentaire:
{{
 "tag": "1 ou 2 mots pour l'étiquette du haut (ex: Enseignement, Conseil, Tutoriel)",
 "order": ["IDs gardés, dans l'ordre FINAL du récit"],
 "fixes": [{{"unit": "ID", "from": "mots mal transcrits (copiés tels quels)", "to": "ce que l'orateur a vraiment dit"}}],
 "chapters": [{{"unit": "ID où commence la partie", "title": "titre court, 2 à 5 mots"}}],
 "cards": [ ... ]
}}

RÈGLES DU MONTAGE
- Commence par l'accroche la plus forte (souvent le début du premier rush). Garde la logique du raisonnement.
- Si une partie a été refaite dans un autre rush, garde la version la plus claire et complète, jette l'autre.
- Jette les passages confus, les redites et les phrases abandonnées. Ne jette JAMAIS une idée unique.
- Une seule conclusion / un seul appel à s'abonner, à la fin.
- « fixes »: uniquement des mots manifestement mal entendus par la transcription (nom propre, homophone), une entrée par passage concerné. Jamais de reformulation.
- 4 à 9 chapitres pour une vidéo de plusieurs minutes, 2 à 4 pour une vidéo courte.

CARTES ANIMÉES (affichées sur le torse de l'orateur pendant qu'il parle; « say » = 1 à 5 mots COPIÉS EXACTEMENT
du passage « unit », au moment où l'élément doit apparaître). Environ une carte toutes les 15 à 25 secondes, jamais deux en même temps.
Types possibles:
 {{"type":"compare","unit":"ID","rows":[{{"a":"…","b":"…","ok":true,"say":"…"}}]}}         (2 lignes « A → B ✅/❌ », idéal pour l'accroche)
 {{"type":"list","unit":"ID","title":"optionnel","items":[{{"text":"2 à 5 mots","emoji":"💧","say":"…"}}]}}   (2 à 4 éléments énumérés)
 {{"type":"steps","unit":"ID","title":"…","items":[{{"text":"…","say":"…"}}]}}               (3 à 5 étapes d'un processus)
 {{"type":"verse","unit":"ID","ref":"Livre chapitre:verset","say":"…"}}                      (UNIQUEMENT si l'orateur cite ou évoque clairement ce verset biblique)
 {{"type":"contrast","unit":"ID","a":"…","b":"…","say_a":"…","say_b":"…"}}                  (« A → B », une opposition forte)
 {{"type":"versus","unit":"ID","a":{{"emoji":"⛪","label":"…"}},"b":{{"emoji":"🙋🏾‍♂️","label":"…"}},"say_a":"…","say_x":"…","say_b":"…"}} (A barré ≠ B)
 {{"type":"alert","unit":"ID","title":"…","sub":"…","say":"…"}}                             (mise en garde)
 {{"type":"keyword","unit":"ID","text":"2 à 4 mots","emoji":"🔥","say":"…"}}                 (idée clé martelée)
 {{"type":"full","unit":"ID","style":"statement|fill|sign","title":"…","sub":"…","emoji":"…","say":"…"}}  (scène plein écran, 1 par minute AU PLUS)
 {{"type":"cta","unit":"ID","say":"…","label":"Abonne-toi","sub":"…"}}                        (seulement si l'orateur demande de s'abonner/commenter)
Tous les textes affichés en {lang}, courts, fidèles à ce que dit l'orateur. N'invente aucun fait."""


# ----------------------------------------------------------------- LLM
def build_prompt(units: list[dict[str, Any]], lang: str = "français") -> str:
    lines = "\n".join(f"{u['id']}: {u['text']}" for u in units)
    dur = sum(u["e"] - u["s"] for u in units)
    return PROMPT.format(lang=lang, units=lines, dur=dur)


def _str(x: Any, n: int = 60) -> str:
    return re.sub(r"\s+", " ", str(x or "")).strip()[:n]


def _say_ok(say: Any, unit: dict[str, Any]) -> bool:
    """« say » doit être copié du passage (ou des 3 suivants dans l'ordre final: `unit["window"]`)."""
    s = norm(str(say or ""))
    return bool(s) and s in norm(unit.get("window") or unit["text"])


def sanitize_card(c: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> Optional[dict[str, Any]]:
    t = c.get("type")
    u = by_id.get(str(c.get("unit") or ""))
    if t not in CARD_TYPES or not u:
        return None
    out: dict[str, Any] = {"type": t, "unit": u["id"]}
    say = lambda k="say": str(c.get(k) or "") if _say_ok(c.get(k), u) else ""  # noqa: E731
    if t == "compare":
        rows = [{"a": _str(r.get("a"), 26), "b": _str(r.get("b"), 26), "ok": bool(r.get("ok")), "say": say_of(r, u)}
                for r in (c.get("rows") or [])[:3] if isinstance(r, dict) and r.get("a") and r.get("b")]
        if len(rows) < 1:
            return None
        out["rows"] = rows
    elif t in ("list", "steps"):
        items = [{"text": _str(i.get("text"), 40), "emoji": _str(i.get("emoji"), 8), "say": say_of(i, u)}
                 for i in (c.get("items") or [])[:5 if t == "steps" else 4] if isinstance(i, dict) and i.get("text")]
        if len(items) < 2:
            return None
        out.update(items=items, title=_str(c.get("title"), 40))
    elif t == "verse":
        v = bible.lookup(str(c.get("ref") or ""))
        if not v:
            return None
        out.update(ref=v["ref"], text=v["text"], say=say())
    elif t == "contrast":
        if not (c.get("a") and c.get("b")):
            return None
        out.update(a=_str(c["a"], 18), b=_str(c["b"], 18), say_a=say("say_a"), say_b=say("say_b"))
    elif t == "versus":
        a, b = c.get("a") or {}, c.get("b") or {}
        if not (isinstance(a, dict) and isinstance(b, dict) and a.get("label") and b.get("label")):
            return None
        out.update(a={"emoji": _str(a.get("emoji"), 8), "label": _str(a.get("label"), 22)},
                   b={"emoji": _str(b.get("emoji"), 8), "label": _str(b.get("label"), 22)},
                   say_a=say("say_a"), say_x=say("say_x"), say_b=say("say_b"))
    elif t == "alert":
        if not c.get("title"):
            return None
        out.update(title=_str(c["title"], 30), sub=_str(c.get("sub"), 70), say=say())
    elif t == "keyword":
        if not c.get("text"):
            return None
        out.update(text=_str(c["text"], 30), emoji=_str(c.get("emoji"), 8), say=say())
    elif t == "full":
        if not c.get("title"):
            return None
        style = c.get("style") if c.get("style") in ("statement", "fill", "sign") else "statement"
        out.update(style=style, title=_str(c["title"], 40), sub=_str(c.get("sub"), 40), emoji=_str(c.get("emoji"), 8), say=say())
    elif t == "cta":
        out.update(label=_str(c.get("label") or "Abonne-toi", 22), sub=_str(c.get("sub"), 40), say=say())
    return out


def say_of(item: dict[str, Any], unit: dict[str, Any]) -> str:
    return str(item.get("say") or "") if _say_ok(item.get("say"), unit) else ""


def parse_plan(text: str, units: list[dict[str, Any]]) -> dict[str, Any]:
    from ..writer import _extract_json
    data = _extract_json(text)
    by_id = {u["id"]: u for u in units}
    order, seen = [], set()
    for x in data.get("order") or []:
        x = str(x).strip()
        if x in by_id and x not in seen:
            order.append(x); seen.add(x)
    words_in = sum(len(u["words"]) for u in units)
    words_kept = sum(len(by_id[x]["words"]) for x in order)
    if not order or words_kept < 0.45 * words_in:
        logger.warning("ordre IA rejeté (%d/%d mots gardés): ordre des rushes", words_kept, words_in)
        order = [u["id"] for u in units]
    kept = set(order)
    # fenêtre de texte de chaque passage: lui + les 3 suivants dans l'ordre final
    for k, x in enumerate(order):
        by_id[x] = {**by_id[x], "window": " ".join(by_id[y]["text"] for y in order[k:k + 4])}
    fixes = []
    for f in data.get("fixes") or []:
        if not isinstance(f, dict):
            continue
        u = by_id.get(str(f.get("unit") or ""))
        a, b = str(f.get("from") or "").strip(), str(f.get("to") or "").strip()
        if u and a and b and norm(a) and norm(a) in norm(u["text"]) and len(b.split()) <= 2 * len(a.split()) + 3 and norm(a) != norm(b):
            fixes.append({"unit": u["id"], "from": a, "to": b})
    chapters = []
    for c in data.get("chapters") or []:
        if isinstance(c, dict) and str(c.get("unit")) in kept and c.get("title"):
            chapters.append({"unit": str(c["unit"]), "title": _str(c["title"], 34)})
    cards = [x for x in (sanitize_card(c, by_id) for c in (data.get("cards") or []) if isinstance(c, dict)) if x and x["unit"] in kept]
    return {"tag": _str(data.get("tag"), 18), "order": order, "fixes": fixes, "chapters": chapters, "cards": cards, "source": "llm"}


# ----------------------------------------------------------------- règles
CTA_RX = re.compile(r"\b(abonne|abonnez|abonnes|like|partage|commentaire|commente|dis moi|dites moi)\b")


def rules_order(units: list[dict[str, Any]], use_jev: bool = True) -> list[str]:
    """Ordre sans LLM: le rush d'introduction d'abord (Jev), les autres dans l'ordre
    d'import, et UNE seule conclusion (« abonne-toi… ») tout à la fin."""
    by_rush: dict[int, list[dict[str, Any]]] = {}
    for u in units:
        by_rush.setdefault(u["rush"], []).append(u)
    rush_ids = sorted(by_rush)
    outros: dict[int, list[dict[str, Any]]] = {}
    for r, us in by_rush.items():
        tail = us[-8:]
        k = next((i for i, u in enumerate(tail) if CTA_RX.search(norm(u["text"]))), None)
        if k is not None:
            outros[r] = tail[k:]
    if use_jev and len(rush_ids) > 1 and jev.available():
        crit = {f"r{r}": " ".join(u["text"] for u in by_rush[r][:2])[:300] for r in rush_ids}
        ans = jev.decide("Débuts des rushes d'une vidéo face caméra, filmés séparément.",
                         {"intro": jev.choice("Quel rush commence la vidéo (accroche, présentation du sujet) ?", crit)})
        first = jev.picked(ans.get("intro"), 0.4)
        if first and int(first[1:]) in by_rush:
            rush_ids.remove(int(first[1:])); rush_ids.insert(0, int(first[1:]))
    best_outro = max(outros.values(), key=lambda us: sum(len(u["words"]) for u in us)) if outros else []
    skip = {u["id"] for us in outros.values() for u in us}
    order = [u["id"] for r in rush_ids for u in by_rush[r] if u["id"] not in skip]
    return order + [u["id"] for u in best_outro]


def rules_plan(units: list[dict[str, Any]], use_jev: bool = False) -> dict[str, Any]:
    cards: list[dict[str, Any]] = []
    for u in units:
        for ref in bible.find_spoken_refs(u["text"]):
            v = bible.lookup(ref)
            if v:
                cards.append({"type": "verse", "unit": u["id"], "ref": v["ref"], "text": v["text"], "say": ""})
    order = rules_order(units, use_jev)
    by_id = {u["id"]: u for u in units}
    cta = next((by_id[i] for i in order[-8:] if CTA_RX.search(norm(by_id[i]["text"]))), None)
    if cta:
        cards.append({"type": "cta", "unit": cta["id"], "label": "Abonne-toi", "sub": "Dis-moi ce que tu en penses", "say": ""})
    return {"tag": "", "order": order, "fixes": [], "chapters": [], "cards": cards, "source": "rules"}


# ----------------------------------------------------------------- Jev
def jev_review(plan: dict[str, Any], units: list[dict[str, Any]], *, landscape: bool, hd: bool, seed: str) -> dict[str, Any]:
    """Décisions et vérifications confiées à Jev (une à deux requêtes)."""
    by_id = {u["id"]: u for u in units}
    ordered = [by_id[i] for i in plan["order"] if i in by_id]
    transcript = "\n".join(f"{u['id']}: {u['text']}" for u in ordered)
    qs: dict[str, Any] = {
        "theme": jev.choice("Quel habillage visuel correspond le mieux au ton et au sujet de cette vidéo face caméra ?", THEMES),
    }
    if not plan.get("tag"):
        qs["tag"] = jev.choice("Quel est le genre de cette vidéo ?", {k: v for k, v in TAGS.items()})
    if landscape and hd:
        qs["layout"] = jev.choice("Quel cadrage vertical convient le mieux à cette vidéo ?", {
            "cadre": "orateur dans une fenêtre 4:5 encadrée, bandeau titre en haut, sous-titres en bas: posé, pédagogique, long format",
            "plein": "orateur plein écran 9:16, très proche: énergique, rythmé, format court"})
    for k, c in enumerate(plan["cards"]):
        u = by_id.get(c["unit"])
        if not u:
            continue
        if c["type"] == "verse":
            qs[f"card_{k}"] = jev.noul(f"Dans le passage {u['id']}, l'orateur cite, paraphrase ou évoque clairement ce texte biblique ({c['ref']}): « {c['text']} »",
                                       "oui, c'est bien ce texte qu'il évoque", "non, ce verset n'a pas de lien direct avec ce qu'il dit")
        else:
            qs[f"card_{k}"] = jev.noul(f"Cette carte affichée pendant le passage {u['id']} est fidèle à ce que dit l'orateur, sans rien inventer: {_card_text(c)}",
                                       "fidèle", "hors sujet ou inventée")
    ans = jev.decide("Transcript monté d'une vidéo face caméra, un passage par ligne:\n" + transcript, qs)
    review: dict[str, Any] = {"decider": "jev" if ans else "rules"}
    h = int(hashlib.sha1(seed.encode()).hexdigest(), 16)
    review["theme"] = jev.picked(ans.get("theme")) if jev.picked(ans.get("theme")) in THEMES else list(THEMES)[h % len(THEMES)]
    tag = plan.get("tag") or TAGS.get(jev.picked(ans.get("tag"), 0.3) or "", "")
    review["tag"] = tag
    review["layout"] = (jev.picked(ans.get("layout")) if landscape and hd else None) or ("cadre" if landscape else "plein")
    kept, dropped = [], []
    for k, c in enumerate(plan["cards"]):
        p = jev.p_true(ans.get(f"card_{k}"))
        limit = 0.3 if c["type"] == "verse" else 0.25
        if p is not None and p < limit and plan.get("source") == "llm":
            dropped.append({"type": c["type"], "unit": c["unit"], "p": round(p, 2)})
            continue
        kept.append(c)
    review["cards"] = kept
    review["cards_dropped"] = dropped
    return review


def _card_text(c: dict[str, Any]) -> str:
    keys = ("title", "text", "label", "sub", "a", "b")
    parts = [str(c[k]) for k in keys if isinstance(c.get(k), str) and c.get(k)]
    for coll in ("items", "rows"):
        for it in c.get(coll) or []:
            parts += [str(it.get(x)) for x in ("text", "a", "b") if it.get(x)]
    for side in ("a", "b"):
        if isinstance(c.get(side), dict):
            parts.append(str(c[side].get("label")))
    return " | ".join(parts)[:300]


# ----------------------------------------------------------------- orchestration
def direct(units: list[dict[str, Any]], *, language: str = "fr", landscape: bool = True, hd: bool = False,
           seed: str = "", use_llm: bool = True) -> dict[str, Any]:
    lang = {"fr": "français", "en": "anglais", "es": "espagnol", "pt": "portugais"}.get((language or "fr")[:2], "français")
    plan: Optional[dict[str, Any]] = None
    info: dict[str, Any] = {"llm": False}
    if use_llm:
        from ..writer import chat, llm_available
        if llm_available():
            try:
                text = chat(build_prompt(units, lang), temperature=0.3, timeout=240)
                plan = parse_plan(text, units)
                info["llm"] = True
            except Exception as e:  # jamais bloquant
                logger.warning("réalisateur IA indisponible: %s", e)
    if plan is None:
        plan = rules_plan(units, use_jev=True)
    # versets dits à voix haute que le LLM aurait oubliés
    have = {(c["unit"], c.get("ref")) for c in plan["cards"] if c["type"] == "verse"}
    kept = set(plan["order"])
    for c in rules_plan(units)["cards"]:
        if c["type"] == "verse" and c["unit"] in kept and (c["unit"], c["ref"]) not in have \
                and not any(x["unit"] == c["unit"] for x in plan["cards"]):
            plan["cards"].append(c)
    review = jev_review(plan, units, landscape=landscape, hd=hd, seed=seed or json.dumps(plan["order"][:5]))
    plan.update(theme=review["theme"], tag=review["tag"], layout=review["layout"], cards=review["cards"])
    info.update(source=plan["source"], decider=review["decider"], cards_dropped=review["cards_dropped"])
    plan["info"] = info
    return plan
