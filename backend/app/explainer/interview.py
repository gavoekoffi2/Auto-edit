"""Entretien « motion designer »: récolte le brief par une conversation.

Sans état côté serveur: le client renvoie le brief partiel et l'historique.
  * Avec clé OpenRouter: l'IA reformule, extrait les infos des réponses libres
    et pose la question suivante la plus utile.
  * Sans clé: questionnaire guidé (mêmes champs, même ordre), toujours fiable.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

from .schema import Brief
from .templates import ANGLES, TEMPLATES

logger = logging.getLogger(__name__)

from .montages import (AUTO, DOMAINS, FORMATS, MONTAGES, auto_montage, match_domain, match_format, match_montage,
                       match_voice, public_voices, resolve_domain, resolve_format)

_HEX = re.compile(r"^[0-9a-f]{32}$")
_is_classic = lambda b: b.get("montage") == "classique"  # noqa: E731

OFFER_Q = {
    "ecommerce": "Qu'est-ce que tu vends en ligne ? Donne le nom du produit (ou de la gamme).",
    "physique": "Quel produit veux-tu mettre en avant ? (nom du produit ou de la gamme)",
    "digital": "Quel est ton produit digital ? (formation, e-book, logiciel, application… et son nom)",
    "services": "Quel service proposes-tu exactement ? (nom de l'offre)",
    "food": "Quel plat, produit ou formule veux-tu vendre ?",
    "beaute": "Quel soin, produit ou prestation veux-tu mettre en avant ?",
    "immobilier": "Qu'est-ce que tu proposes ? (terrains, maisons, construction, plans…)",
    "education": "Quelle formation, école ou programme veux-tu promouvoir ?",
}

STEPS: list[dict[str, Any]] = [
    {"field": "domain", "q": "Bonjour ! Je suis ton motion designer IA 🎬 On va créer ta pub vidéo ensemble, de A à Z. Pour commencer : dans quel domaine est ton activité ?",
     "suggestions": [f"{d['emoji']} {d['name']}" for d in DOMAINS.values()]},
    {"field": "business", "q": "Comment s'appelle ton entreprise ou ta marque ?"},
    {"field": "offer", "q": "Qu'est-ce que tu vends exactement ? (nom du produit ou du service)"},
    {"field": "product_desc", "q": "Décris-le-moi comme à un client : ce que c'est, comment ça marche, ce qui le rend différent des autres."},
    {"field": "audience", "q": "À qui s'adresse cette pub ? Décris ta cible (ex : femmes actives de Lomé, commerçants, parents d'élèves…)"},
    {"field": "problem", "q": "Quel est LE problème de ces personnes, avec leurs mots à elles ? (c'est l'accroche de la pub)"},
    {"field": "consequences", "q": "Qu'est-ce que ce problème leur coûte au quotidien ? Donne 2 ou 3 conséquences concrètes (temps, argent, image, stress…)."},
    {"field": "promise", "q": "Avec ton produit, quel résultat concret obtiennent-elles ?"},
    {"field": "benefits", "q": "Donne-moi 3 avantages concrets (un par ligne)."},
    {"field": "price", "q": "Un prix ou une offre spéciale à annoncer ? (ex : 5 000 FCFA, -20 % cette semaine) — sinon réponds « non ».", "suggestions": ["Non"]},
    {"field": "proof", "q": "As-tu une preuve RÉELLE à montrer ? (nombre de clients, ancienneté, avis…) Sinon « non » — je n'invente jamais de chiffres.",
     "suggestions": ["Non"]},
    {"field": "contact_phone", "q": "Quel numéro afficher et faire prononcer à la fin (appel / WhatsApp) ? Sinon « non ».", "suggestions": ["Non"]},
    {"field": "cta_detail", "q": "Une phrase de fin ou un slogan pour ta marque ? (ex : « Votre peau mérite le meilleur ») — ou « non »."},
    {"field": "product_asset", "q": "Envoie une photo de ton produit 📸 (sur fond uni, il sera détouré automatiquement et posé sur un socle). Sinon clique « Passer ».",
     "suggestions": ["Passer"], "upload": True},
    {"field": "logo_asset", "q": "Et ton logo ? Il apparaîtra sur l'écran de fin.", "suggestions": ["Passer"], "upload": True},
    {"field": "photo_assets", "q": "As-tu des photos à mettre dans la pub ? (toi, ton équipe, tes clients, ton lieu, ton événement — jusqu'à 6). "
                                   "Sinon clique « Passer » : j'utiliserai des illustrations.", "suggestions": ["Passer"], "upload": True, "multiple": True},
    {"field": "screen_assets", "q": "Des captures d'écran de ton application ou de ton site ? Elles s'afficheront dans les téléphones et les écrans animés.",
     "suggestions": ["Passer"], "upload": True, "multiple": True, "when": lambda b: b.get("domain") in ("appli", "digital", "services")},
    {"field": "tone", "q": "On parle à ta cible en « vous » ou en « tu » ?", "suggestions": ["Vouvoiement", "Tutoiement"]},
    {"field": "format", "q": "Où vas-tu publier ta pub ? Je cadre tout le montage pour ce format :",
     "suggestions": [f"{f['name']} — {f['hint']}" for f in FORMATS], "format_picker": True},
    {"field": "montage", "q": "Choisis le mode de montage de ta pub (chaque mode a sa propre mise en scène), ou laisse-moi choisir :",
     "suggestions": ["✨ Choix automatique (recommandé)"] + [m["name"] for m in MONTAGES.values() if m["available"]], "montage": True},
    {"field": "voice", "q": "Et la voix off ?", "suggestions": [v["name"] for v in public_voices()]},
    {"field": "template", "q": "Choisis le style visuel :", "suggestions": [t["name"] for t in TEMPLATES.values()], "when": _is_classic},
    {"field": "angle", "q": "Et l'angle publicitaire ? (chaque angle raconte ta pub différemment)",
     "suggestions": ["Choisis pour moi"] + [a["name"] for a in ANGLES.values()], "when": _is_classic},
]

REQUIRED = ["business", "offer", "audience", "problem", "promise"]


_NO = re.compile(r"(?i)\s*(non|no|aucune?|rien|pas encore|passer|pas de .*|sans)\.?\s*")


def _apply(brief: dict[str, Any], field: str, answer: str) -> None:
    a = (answer or "").strip()
    if field == "domain":
        brief["domain"] = match_domain(a)
    elif field == "montage":
        brief["montage"] = match_montage(a)
    elif field == "voice":
        brief["voice"] = match_voice(a)
    elif field in ("price", "contact_phone", "consequences"):
        brief[field] = "" if _NO.fullmatch(a) else a
    elif field in ("product_asset", "logo_asset"):
        brief[field] = a if _HEX.match(a) else ""
    elif field in ("photo_assets", "screen_assets"):
        brief[field] = [x for x in re.split(r"[\s,;]+", a) if _HEX.match(x)][:6]
    elif field == "format":
        brief["format"] = match_format(a)
    elif field == "benefits":
        brief["benefits"] = [x.strip(" -•*") for x in re.split(r"\n|;|•", a) if x.strip(" -•*")][:4]
    elif field == "proof":
        brief["proof"] = "" if re.fullmatch(r"(?i)\s*(non|no|aucune?|rien|pas encore)\.?\s*", a) else a
    elif field == "tone":
        brief["tone"] = "tu" if re.search(r"(?i)\btu\b|tutoi", a) else "vous"
    elif field == "template":
        low = a.lower()
        brief["template"] = next((k for k, t in TEMPLATES.items() if t["name"].lower() in low or k in low), "prestige")
    elif field == "angle":
        low = a.lower()
        brief["angle"] = next((k for k, v in ANGLES.items() if v["name"].lower() in low or k in low), "auto")
    elif field == "cta_detail":
        brief["cta_detail"] = "" if _NO.fullmatch(a) else a
        if re.search(r"(?i)whatsapp", a):
            brief["cta_action"] = "Écrivez-nous sur WhatsApp grâce au bouton juste en bas de cette vidéo"
    else:
        brief[field] = a


def next_step(brief: dict[str, Any]) -> Optional[dict[str, Any]]:
    asked = set(brief.get("_asked", []))
    for st in STEPS:
        if st["field"] in asked or (st.get("when") and not st["when"](brief)):
            continue
        if st["field"] == "offer":
            st = {**st, "q": OFFER_Q.get(brief.get("domain", ""), st["q"])}
        if st["field"] == "montage":
            fmt = resolve_format(brief.get("format"))
            st = {**st, "suggestions": ["✨ Choix automatique (recommandé)"] + [m["name"] for m in MONTAGES.values()
                                                                               if m["available"] and fmt in m.get("formats", ["9:16"])]}
        return st
    return None


def choose_angle(brief: dict[str, Any]) -> str:
    """« Choisis pour moi »: angle déduit du contenu du brief."""
    txt = " ".join(str(brief.get(k, "")) for k in ("problem", "promise", "offer", "audience")).lower()
    if re.search(r"prot[èe]g|assuranc|risque|famille|s[ée]curit", txt):
        return "histoire" if re.search(r"retraite|imp[ôo]t|patrimoine|[ée]pargn", txt) else "protection"
    if re.search(r"premium|luxe|exclusi|haut de gamme|vip", txt):
        return "exclusivite"
    if re.search(r"attend|plus tard|repouss|chaque mois", txt):
        return "attente"
    return "douleur"


def _summary(b: dict[str, Any]) -> str:
    ben = "".join(f"\n• {x}" for x in b.get("benefits") or [])
    if b.get("montage") == AUTO:
        mid, _why = auto_montage(b)
        mont = f"automatique (je partirai sur « {MONTAGES[mid]['name']} »)"
    else:
        mont = MONTAGES.get(b.get("montage", ""), MONTAGES["impact"])["name"]
    fmt = next((f"{f['name']} ({f['hint']})" for f in FORMATS if f["id"] == resolve_format(b.get("format"))), "Vertical 9:16")
    voice = next((v["name"].split(" — ")[0] for v in public_voices() if v["id"] == b.get("voice")), "Henri")
    if _is_classic(b):
        tpl = TEMPLATES.get(b.get("template", ""), TEMPLATES["prestige"])["name"]
        ang = ANGLES.get(b.get("angle", ""), ANGLES["douleur"])["name"]
        style = f"Montage : {mont} · Style : {tpl} · Angle : {ang}"
    else:
        style = f"Format : {fmt}\nMontage : {mont} · Voix : {voice}"
    extra = "".join(x for x in [f"\nPrix / offre : {b['price']}" if b.get("price") else "",
                                f"\nNuméro : {b['contact_phone']}" if b.get("contact_phone") else "",
                                "\nPhoto produit : ✅" if b.get("product_asset") else "",
                                f"\nPhotos : {len(b.get('photo_assets') or [])}" if b.get("photo_assets") else "",
                                f"\nCaptures d'écran : {len(b.get('screen_assets') or [])}" if b.get("screen_assets") else ""])
    return (f"Parfait, j'ai tout ce qu'il me faut ✅\n\n**{b.get('business')}** — {b.get('offer')} ({resolve_domain(b.get('domain'))['name']})\n"
            f"Cible : {b.get('audience')}\nProblème : {b.get('problem')}\nCe que ça coûte : {b.get('consequences') or '—'}\n"
            f"Promesse : {b.get('promise')}{ben}{extra}\n{style}\n\n"
            "Le script suivra la méthode : problème → agitation → solution → appel à l'action.\n"
            "Clique sur « Créer ma pub » et je m'occupe du script, de la voix off, de l'animation et du son.")


def _llm_turn(brief: dict[str, Any], history: list[dict[str, str]], answer: str, key: Optional[str]) -> Optional[dict[str, Any]]:
    from .writer import _extract_json, chat, llm_available
    missing = [f for f in REQUIRED + ["product_desc", "consequences", "benefits"] if not brief.get(f)]
    prompt = f"""Tu es un motion designer publicitaire chaleureux qui interroge un client (francophone) pour écrire sa pub vidéo.
Brief actuel (JSON): {json.dumps({k: v for k, v in brief.items() if not k.startswith('_')}, ensure_ascii=False)}
Champs encore manquants: {missing}
Historique récent: {json.dumps(history[-6:], ensure_ascii=False)}
Dernière réponse du client: {answer!r}

Extrais de la dernière réponse TOUTES les informations utiles pour les champs: business, offer, product_desc, audience, problem, consequences, promise, benefits (liste), price (seulement si donné), proof (seulement si réel et fourni), contact_phone, tone (vous/tu).
N'invente rien. Puis écris une réponse courte (1-2 phrases, tutoiement, ton pro et chaleureux) qui accuse réception et pose UNE seule question pour le champ manquant le plus important. S'il ne manque plus rien, mets done=true.
Réponds uniquement en JSON: {{"patch": {{...}}, "reply": "...", "done": false}}"""
    try:
        data = _extract_json(chat(prompt, key, temperature=0.4, timeout=45))
        return data if isinstance(data, dict) else None
    except Exception as e:
        logger.warning("entretien IA indisponible: %s", e)
        return None


FOLLOWUP = {
    "product_desc": "Peux-tu m'en dire un peu plus ? Ce qui le rend vraiment différent : ingrédients, matière, méthode, garantie, livraison…",
    "problem": "Donne-moi une situation concrète où tes clients vivent ce problème (le moment, ce qu'ils ressentent, ce qu'ils se disent).",
    "consequences": "Et concrètement, qu'est-ce que ça leur fait perdre ? (argent, temps, clients, confiance, image…)",
    "promise": "Quel changement visible après ? Plus il est concret (avant / après), plus la pub convainc.",
}


def _llm_followup(brief: dict[str, Any], field: str, answer: str, key: Optional[str]) -> Optional[str]:
    from .writer import chat
    ctx = {k: v for k, v in brief.items() if not k.startswith("_") and v}
    prompt = (f"Tu es un motion designer publicitaire qui interroge un client pour écrire sa pub (méthode problème → solution).\n"
              f"Brief: {json.dumps(ctx, ensure_ascii=False)}\nChamp: {field}. Sa réponse est trop vague: {answer!r}.\n"
              "Pose UNE question courte (tutoiement, chaleureuse, 1 phrase, avec un exemple adapté à SON produit) pour obtenir un détail concret et vendeur. "
              "Réponds uniquement par la question.")
    try:
        q = chat(prompt, key, temperature=0.5, timeout=30).strip().strip('"')
        return q if 10 < len(q) < 300 and q.endswith("?") else None
    except Exception:  # noqa: BLE001
        return None


def interview_turn(brief: dict[str, Any] | None, answer: Optional[str] = None,
                   history: Optional[list[dict[str, str]]] = None, api_key: Optional[str] = None) -> dict[str, Any]:
    """Un tour d'entretien. Renvoie {reply, brief, done, suggestions, field}."""
    b = dict(brief or {})
    b.setdefault("_asked", [])
    current = b.get("_current")
    from .conf import setting
    # api_key="" désactive l'IA (tests); None = passerelles configurées (FreeLLMAPI, OpenRouter)
    from .writer import llm_available
    use_llm = bool(api_key) if api_key is not None else llm_available()
    key = api_key or None
    fu = b.pop("_followup", None)
    if answer is not None and fu:
        # réponse à une question d'approfondissement : complète le champ
        if not _NO.fullmatch(answer.strip()):
            b[fu] = (str(b.get(fu) or "") + ". " + answer.strip()).strip(". ") if b.get(fu) else answer.strip()
    elif answer is not None and current:
        _apply(b, current, answer)
        if current not in b["_asked"]:
            b["_asked"].append(current)
        # l'agent creuse une réponse trop vague (une seule fois par champ)
        if current in FOLLOWUP and len(answer.split()) < 7 and current not in b.setdefault("_dug", []):
            b["_dug"].append(current)
            q = _llm_followup(b, current, answer, key) if use_llm else None
            q = q or FOLLOWUP[current]
            b["_followup"] = current
            return {"reply": q, "brief": b, "done": False, "suggestions": ["Non, c'est tout"], "field": current, "upload": False, "multiple": False, "montage_picker": False, "format_picker": False}
        # l'IA complète les autres champs à partir d'une réponse riche
        if use_llm and current in ("business", "offer", "product_desc", "audience", "problem", "promise") and len(answer) > 60:
            res = _llm_turn(b, history or [], answer, key)
            if res and isinstance(res.get("patch"), dict):
                for k, v in res["patch"].items():
                    if k in Brief.__dataclass_fields__ and v and not b.get(k):  # type: ignore[attr-defined]
                        b[k] = v
                        if k not in b["_asked"] and k in {s["field"] for s in STEPS}:
                            b["_asked"].append(k)
    note = ""
    if answer is not None and current == "domain" and not fu:
        note = f"Domaine retenu : {resolve_domain(b.get('domain'))['emoji']} {resolve_domain(b.get('domain'))['name']} (dis-le-moi si ce n'est pas ça).\n\n"
    elif answer is not None and current == "montage" and not fu:
        fmt = resolve_format(b.get("format"))
        if b.get("montage") == AUTO:
            mid, why = auto_montage(b)
            note = f"Je te propose « {MONTAGES[mid]['name']} » ({why}). Tu peux me demander un autre montage à tout moment.\n\n"
        elif fmt not in MONTAGES.get(b.get("montage", ""), {}).get("formats", ["9:16"]):
            mid, why = auto_montage(b)
            note = f"« {MONTAGES[b['montage']]['name']} » n'existe qu'en vertical : pour le format {fmt} je prends « {MONTAGES[mid]['name']} ».\n\n"
            b["montage"] = mid
    st = next_step(b)
    if st is None:
        if b.get("angle") in (None, "", "auto"):
            b["angle"] = choose_angle(b)
        b["_current"] = None
        clean = {k: v for k, v in b.items()}
        return {"reply": note + _summary(b), "brief": clean, "done": True, "suggestions": ["Créer ma pub"], "field": None}
    b["_current"] = st["field"]
    q = st["q"]
    if st["field"] == "domain" and answer is not None:
        q = st["q"].split("! ", 1)[-1]
    return {"reply": note + q, "brief": b, "done": False, "suggestions": st.get("suggestions", []), "field": st["field"],
            "upload": bool(st.get("upload")), "multiple": bool(st.get("multiple")), "montage_picker": bool(st.get("montage")),
            "format_picker": bool(st.get("format_picker"))}


def brief_from_interview(b: dict[str, Any]) -> Brief:
    # les chemins de fichiers ne viennent JAMAIS du client (résolus par le worker depuis les ids)
    data = {k: v for k, v in (b or {}).items() if not k.startswith("_") and k not in ("product_image_path", "logo_path", "photo_paths", "screen_paths")}
    if data.get("angle") in (None, "", "auto"):
        data["angle"] = choose_angle(data)
    return Brief.from_dict(data)
