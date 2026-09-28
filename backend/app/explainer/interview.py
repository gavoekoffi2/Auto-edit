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

STEPS: list[dict[str, Any]] = [
    {"field": "business", "q": "Bonjour ! Je suis ton motion designer IA 🎬 On va créer ta pub ensemble. Comment s'appelle ton entreprise ou ta marque ?"},
    {"field": "offer", "q": "Qu'est-ce que tu vends exactement ? (produit, service, formation, abonnement…)"},
    {"field": "audience", "q": "À qui s'adresse cette pub ? Décris ta cible (ex : médecins et avocats, mamans actives, commerçants de Lomé…)"},
    {"field": "problem", "q": "Quel est le problème principal de ces personnes, avec leurs mots à elles ?"},
    {"field": "promise", "q": "Quel résultat concret obtiennent-elles grâce à toi ?"},
    {"field": "benefits", "q": "Donne-moi 2 ou 3 avantages concrets (un par ligne)."},
    {"field": "proof", "q": "As-tu une preuve RÉELLE à montrer ? (chiffre vérifiable, nombre de clients, ancienneté…) Sinon réponds « non » — je n'invente jamais de chiffres.",
     "suggestions": ["Non"]},
    {"field": "cta_detail", "q": "À la fin, que doit faire la personne et qu'obtient-elle ? (ex : cliquer sur le bouton pour 30 minutes de conseil offertes, écrire sur WhatsApp…)"},
    {"field": "tone", "q": "Tu préfères qu'on parle à ta cible en « vous » ou en « tu » ?", "suggestions": ["Vouvoiement", "Tutoiement"]},
    {"field": "template", "q": "Choisis le style visuel :", "suggestions": [t["name"] for t in TEMPLATES.values()]},
    {"field": "angle", "q": "Et l'angle publicitaire ? (chaque angle raconte ta pub différemment)",
     "suggestions": ["Choisis pour moi"] + [a["name"] for a in ANGLES.values()]},
]

REQUIRED = ["business", "offer", "audience", "problem", "promise"]


def _apply(brief: dict[str, Any], field: str, answer: str) -> None:
    a = (answer or "").strip()
    if field == "benefits":
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
        brief["cta_detail"] = a
        if re.search(r"(?i)whatsapp", a):
            brief["cta_action"] = "Écrivez-nous sur WhatsApp grâce au bouton juste en bas de cette vidéo"
    else:
        brief[field] = a


def next_step(brief: dict[str, Any]) -> Optional[dict[str, Any]]:
    asked = set(brief.get("_asked", []))
    for st in STEPS:
        if st["field"] not in asked:
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
    tpl = TEMPLATES.get(b.get("template", ""), TEMPLATES["prestige"])["name"]
    ang = ANGLES.get(b.get("angle", ""), ANGLES["douleur"])["name"]
    ben = "".join(f"\n• {x}" for x in b.get("benefits") or [])
    return (f"Parfait, j'ai tout ce qu'il me faut ✅\n\n**{b.get('business')}** — {b.get('offer')}\n"
            f"Cible : {b.get('audience')}\nProblème : {b.get('problem')}\nPromesse : {b.get('promise')}{ben}\n"
            f"Fin : {b.get('cta_detail') or b.get('cta_action')}\nStyle : {tpl} · Angle : {ang}\n\n"
            "Clique sur « Créer ma pub » et je m'occupe du script, de la voix off, de l'animation et du son.")


def _llm_turn(brief: dict[str, Any], history: list[dict[str, str]], answer: str, key: Optional[str]) -> Optional[dict[str, Any]]:
    from .writer import _extract_json, chat, llm_available
    missing = [f for f in REQUIRED + ["benefits", "cta_detail"] if not brief.get(f)]
    prompt = f"""Tu es un motion designer publicitaire chaleureux qui interroge un client (francophone) pour écrire sa pub vidéo.
Brief actuel (JSON): {json.dumps({k: v for k, v in brief.items() if not k.startswith('_')}, ensure_ascii=False)}
Champs encore manquants: {missing}
Historique récent: {json.dumps(history[-6:], ensure_ascii=False)}
Dernière réponse du client: {answer!r}

Extrais de la dernière réponse TOUTES les informations utiles pour les champs: business, offer, audience, problem, promise, benefits (liste), proof (seulement si réel et fourni), cta_detail, tone (vous/tu).
N'invente rien. Puis écris une réponse courte (1-2 phrases, tutoiement, ton pro et chaleureux) qui accuse réception et pose UNE seule question pour le champ manquant le plus important. S'il ne manque plus rien, mets done=true.
Réponds uniquement en JSON: {{"patch": {{...}}, "reply": "...", "done": false}}"""
    try:
        data = _extract_json(chat(prompt, key, temperature=0.4, timeout=45))
        return data if isinstance(data, dict) else None
    except Exception as e:
        logger.warning("entretien IA indisponible: %s", e)
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
    if answer is not None and current:
        _apply(b, current, answer)
        if current not in b["_asked"]:
            b["_asked"].append(current)
        # l'IA complète les autres champs à partir d'une réponse riche
        if use_llm and current in ("business", "offer", "audience", "problem", "promise") and len(answer) > 60:
            res = _llm_turn(b, history or [], answer, key)
            if res and isinstance(res.get("patch"), dict):
                for k, v in res["patch"].items():
                    if k in Brief.__dataclass_fields__ and v and not b.get(k):  # type: ignore[attr-defined]
                        b[k] = v
                        if k not in b["_asked"] and k in {s["field"] for s in STEPS}:
                            b["_asked"].append(k)
    st = next_step(b)
    if st is None:
        if b.get("angle") in (None, "", "auto"):
            b["angle"] = choose_angle(b)
        b["_current"] = None
        clean = {k: v for k, v in b.items()}
        return {"reply": _summary(b), "brief": clean, "done": True, "suggestions": ["Créer ma pub"], "field": None}
    b["_current"] = st["field"]
    q = st["q"]
    if st["field"] == "business" and answer is not None:
        q = st["q"].split("! ", 1)[-1]
    return {"reply": q, "brief": b, "done": False, "suggestions": st.get("suggestions", []), "field": st["field"]}


def brief_from_interview(b: dict[str, Any]) -> Brief:
    data = {k: v for k, v in (b or {}).items() if not k.startswith("_")}
    if data.get("angle") in (None, "", "auto"):
        data["angle"] = choose_angle(data)
    return Brief.from_dict(data)
