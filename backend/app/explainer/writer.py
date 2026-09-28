"""Brief → storyboard (script + scènes).

1. IA (OpenRouter, clé OPENROUTER_API_KEY) avec le catalogue de scènes et les
   règles de la méthode (rythme, angles, aucune donnée inventée).
2. Repli SANS clé: gabarits d'angles remplis avec les réponses du brief.
   La vidéo sort toujours, même sans IA.
Dans les deux cas le résultat passe par `sanitize()` (garde-fous).
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

from .schema import Beat, Brief, Storyboard
from .templates import ANGLES, ICON_NAMES, SCENE_CATALOG

logger = logging.getLogger(__name__)
OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
from .conf import setting

LLM_MODEL = setting("EXPLAINER_LLM_MODEL", "google/gemini-2.5-flash") or "google/gemini-2.5-flash"

_ICON_HINTS = [
    (r"m[ée]decin|docteur|sant[ée]|clinic|infirmi|pharmac", "stethoscope"), (r"avocat|juri|droit|notaire", "scale"),
    (r"entrepr|patron|chef|dirigeant|business|pme", "briefcase"), (r"agence|bureau|soci[ée]t[ée]|cabinet", "building"), (r"[ée]v[ée]nement|f[êe]te|mariage|anniversaire|organisat", "star"), (r"boutique|commer|magasin|vend", "store"),
    (r"famille|enfant|parent|maman|papa|m[èe]re", "family"), (r"maison|immobil|logement|loyer", "home"), (r"voiture|auto|transport", "car"),
    (r"livr|colis|exp[ée]di", "truck"), (r"formation|cours|apprend|[ée]tudi|[ée]cole", "graduation"),
    (r"argent|revenu|salaire|profit|gain|[ée]pargn", "coin"), (r"imp[ôo]t|tax|frais", "percent"),
    (r"prot[èe]g|s[ée]curit|assuranc|garant", "shield"), (r"temps|minute|heure|rapide|vite", "clock"),
    (r"croiss|grandi|fructif|augment|multipli", "trendUp"), (r"client|prospect|vente|achet", "users"),
    (r"t[ée]l[ée]phone|appel|whatsapp|message", "message"), (r"retraite|avenir|futur", "sparkle"),
    (r"restaurant|cuisine|repas|nourrit|g[âa]teau|p[âa]tiss|boulang", "food"), (r"voyage|avion|visa|immigr", "plane"), (r"beaut[ée]|cosm[ée]t|soin", "heart"),
]


def guess_icon(text: str) -> str:
    t = (text or "").lower()
    for pat, ic in _ICON_HINTS:
        if re.search(pat, t):
            return ic
    return "sparkle"


def _you(b: Brief) -> dict[str, str]:
    if b.tone == "tu":
        return {"vous": "tu", "votre": "ton", "vos": "tes", "Vous": "Tu", "Votre": "Ton", "Cliquez": "Clique", "Protégez": "Protège", "voulez-vous": "veux-tu", "êtes": "es"}
    return {"vous": "vous", "votre": "votre", "vos": "vos", "Vous": "Vous", "Votre": "Votre", "Cliquez": "Cliquez", "Protégez": "Protégez", "voulez-vous": "voulez-vous", "êtes": "êtes"}


_STOP_END = {"de", "d'", "du", "des", "un", "une", "le", "la", "les", "l'", "à", "au", "aux", "pour", "et", "ou", "en", "avec", "sans", "sur", "dans", "par", "vos", "votre", "tes", "ton", "ta", "ses", "son", "sa", "mes", "mon", "ma", "qui", "que"}


def _short(s: str, n: int = 4) -> str:
    """n premiers mots, sans finir sur un mot-outil (« Pas le temps de préparer un » → « Pas le temps »)."""
    w = str(s or "").replace(",", "").split()[:n]
    while len(w) > 1 and (w[-1].lower() in _STOP_END or w[-1].lower().endswith("'")):
        w.pop()
    return " ".join(w)


_BREAK = {"à", "a", "de", "du", "des", "et", "pour", "sans", "avec", "en", "dans", "quoi", "qui", "est", "sont"}


def _split_benefit(x: str) -> tuple[str, str]:
    """« Votre argent fructifie à l'abri de l'impôt » → (« Votre argent fructifie », « à l'abri de l'impôt »)."""
    w = str(x or "").rstrip(" .").split()
    if len(w) <= 3:
        return " ".join(w), ""
    mid = len(w) // 2
    for d in range(0, len(w)):
        for i in (mid + d, mid - d):
            if 2 <= i < len(w) and w[i].lower().split("'")[0] in _BREAK:
                return " ".join(w[:i]), " ".join(w[i:i + 6])
    return " ".join(w[:mid]), " ".join(w[mid:mid + 6])


def _sentence(s: str) -> str:
    s = " ".join(str(s or "").split()).strip()
    if not s:
        return s
    s = s[0].upper() + s[1:]
    return s if s[-1] in ".!?…" else s + "."


# --------------------------------------------------------------------------- #
# Repli sans IA
# --------------------------------------------------------------------------- #
def fallback_storyboard(b: Brief) -> Storyboard:
    y = _you(b)
    aud = [a.strip() for a in re.split(r",|\bet\b|/|;", b.audience or "") if a.strip()][:3] or ["Entrepreneurs"]
    offer = b.offer or b.business or "notre solution"
    benefits = [x for x in (b.benefits or []) if x.strip()][:3] or [b.promise or "Des résultats concrets"]
    cta = b.cta_action or f"{y['Cliquez']} sur le bouton juste en bas de cette vidéo"
    if b.tone == "tu":
        cta = cta.replace("Cliquez", "Clique").replace("Écrivez-nous", "Écris-nous").replace("Appelez-nous", "Appelle-nous")
    beats: list[Beat] = []
    angle = b.angle if b.angle in ANGLES else "douleur"

    def add(text, scene, pause=0.35):
        beats.append(Beat(_sentence(text), scene, pause))

    if angle == "histoire":
        a_lab, b_lab = f"{_short(aud[0], 2)} 1", f"{_short(aud[0], 2)} 2"
        add(f"Deux {aud[0].lower()}. Même métier. Même ambition.", {"type": "title_slam", "kicker": "Histoire vraie ?", "title": f"Deux {aud[0]}", "highlight": ["deux"]}, 0.45)
        add("Le premier continue comme tout le monde, sans stratégie.", {"type": "split_compare", "a": {"label": a_lab, "tag": "Sans stratégie", "loss": "− PERTES", "at": "premier"}, "b": {"label": b_lab, "tag": _short(offer, 3), "at": "second"}})
        add(f"Le second fait un autre choix : {offer}.", {"type": "continue"})
        add(f"Pour lui : {b.promise or 'des résultats concrets'}.", {"type": "continue"}, 0.5)
        add("Même point de départ. Deux résultats très différents.", {"type": "bars_compare", "title": "Le résultat", "caption": "Deux résultats très différents", "caption_at": "résultats", "a_label": a_lab, "b_label": b_lab, "disclaimer": b.disclaimer or "Illustration."}, 0.45)
        add("La différence ? Une seule décision, prise à temps.", {"type": "toggle_decision", "kicker": "La différence :", "title": "Une seule décision", "on_at": "décision", "caption": "Prise à temps", "caption_at": "temps"}, 0.45)
        add(f"Alors, lequel des deux {y['voulez-vous']} être ?", {"type": "choice_cards", "title": f"Lequel {y['voulez-vous']} être ?", "a": {"label": a_lab, "sub": "Sans stratégie"}, "b": {"label": b_lab, "sub": _short(offer, 3)}, "pick_at": "être"}, 0.4)
    elif angle == "exclusivite":
        add(f"Ce n'est pas pour tout le monde.", {"type": "crowd_select", "title": "Pas pour tout le monde", "select_at": "monde"}, 0.4)
        add(f"C'est pour {', '.join(a.lower() for a in aud)}.", {"type": "icon_cards", "items": [{"icon": guess_icon(a), "label": _short(a, 3), "at": _short(a, 1)} for a in aud]})
        add(f"Avec {offer}, {y['vous']} obtenez enfin {b.promise or 'des résultats'}.", {"type": "hero_reveal", "kicker": "La solution", "name": offer, "at": _short(offer, 1)}, 0.4)
    elif angle == "protection":
        add(f"Et si demain, tout s'arrêtait ?", {"type": "title_slam", "kicker": "Question", "title": "Et si demain…", "highlight": ["demain"]}, 0.45)
        add(f"{b.problem or 'Sans protection, tout ce que vous avez construit peut disparaître'}.", {"type": "loss_drain", "tag": "Sans protection", "label": "Perte", "drain_at": _short(b.problem, 1) or "tout"})
        add(f"{offer} protège ce qui compte.", {"type": "hero_reveal", "kicker": "La protection", "name": offer, "at": _short(offer, 1)}, 0.4)
    else:  # douleur / mythe / attente / conversation → structure douleur
        add(", ".join(aud) + ".", {"type": "icon_cards", "items": [{"icon": guess_icon(a), "label": _short(a, 3), "at": _short(a, 1)} for a in aud]}, 0.3)
        q = b.problem or "vous perdez du temps et de l'argent"
        money = re.search(r"imp[ôo]t|argent|revenu|frais|perd|co[ûu]t|d[ée]pens|tax", q, re.I)
        if money:
            lab = "Impôt" if re.search(r"imp[ôo]t|tax", q, re.I) else ("Frais" if re.search(r"frais|co[ûu]t|d[ée]pens", q, re.I) else "Pertes")
            add(f"{q[0].upper() + q[1:]}", {"type": "loss_drain", "tag": "Sans stratégie" if "strat" in q.lower() else "Le problème",
                                              "chips": [c for c in ["Vos revenus", "Vos biens"]], "label": lab, "drain_at": "part", "label_at": lab.lower()[:4]}, 0.4)
        else:
            add(f"{q[0].upper() + q[1:]}", {"type": "title_slam", "kicker": "Le problème", "title": _short(q, 6), "at": _short(q, 1)}, 0.4)
        if b.promise:
            add(f"{offer[0].upper() + offer[1:]} : {b.promise}.", {"type": "hero_reveal", "kicker": "La solution", "name": offer, "sub": _short(b.promise, 6), "at": _short(offer, 1)}, 0.4)
        else:
            add(f"La solution : {offer}.", {"type": "hero_reveal", "kicker": "La solution", "name": offer, "at": _short(offer, 1)}, 0.4)
    # bénéfices (tous les angles)
    if angle not in ("histoire",):
        items = [dict(zip(("label", "detail"), _split_benefit(x)), icon=guess_icon(x), at=_short(x, 1)) for x in benefits]
        add(benefits[0], {"type": "checklist", "title": "Vos avantages" if b.tone != "tu" else "Tes avantages", "items": items})
        for x in benefits[1:]:
            add(x, {"type": "continue"})
    if b.proof:
        m = re.search(r"\d+[\d.,]*\s*%?", b.proof)
        if m:
            add(b.proof, {"type": "stat_number", "value": m.group(0).strip(), "label": _short(b.proof.replace(m.group(0), ""), 6), "at": m.group(0).split()[0]})
    add(cta, {"type": "cta_button", "title": f"{y['Cliquez']} sur le bouton", "button": f"{y['Cliquez']} ici", "click_at": "bouton", "down_at": "bas"}, 0.35)
    if b.cta_detail:
        mm = re.search(r"(\d+)\s*(minutes?|min|heures?|jours?)", b.cta_detail)
        if mm:
            add(b.cta_detail, {"type": "timer_ring", "value": int(mm.group(1)), "unit": mm.group(2), "at": mm.group(1), "caption": b.cta_detail})
        else:
            add(b.cta_detail, {"type": "title_slam", "title": _short(b.cta_detail, 6)})
    slogan = _short(b.promise, 4) or f"{y['Protégez']} votre avenir"
    add(f"{slogan}. Dès aujourd'hui.", {"type": "end_card", "brand": b.business, "slogan": slogan, "button": f"{y['Cliquez']} sur le bouton", "disclaimer": b.disclaimer, "at": _short(slogan, 1)}, 0.3)
    return Storyboard(angle=angle, template=b.template, beats=beats, title=f"{b.business} — {ANGLES[angle]['name']}",
                      notes=["Script généré sans IA (mode secours)."])


# --------------------------------------------------------------------------- #
# IA
# --------------------------------------------------------------------------- #
def build_prompt(b: Brief) -> str:
    angle = ANGLES.get(b.angle, ANGLES["douleur"])
    catalog = {k: {"desc": v["desc"], "params": v["params"]} for k, v in SCENE_CATALOG.items()}
    words = int(b.duration * 3.0)
    return f"""Tu es un directeur de création de publicités vidéo verticales en motion design (TikTok/Reels) pour l'Afrique francophone et le Canada.
Écris le script de voix off ET choisis l'animation de chaque phrase pour cette pub.

BRIEF CLIENT (JSON): {json.dumps(b.to_dict(), ensure_ascii=False)}

ANGLE IMPOSÉ: « {angle['name']} » — structure: {angle['structure']}

RÈGLES:
- Langue: {b.language}. {"Tutoiement" if b.tone == "tu" else "Vouvoiement"}. Phrases courtes et parlées, percutantes, émotion d'abord.
- Environ {words} mots au total (≈ 3 mots/seconde pour {b.duration} s), 9 à 13 phrases, chaque phrase ≤ 16 mots.
- La 1re phrase accroche en moins de 3 secondes. La fin: appel à l'action ({b.cta_action}) {('+ ' + b.cta_detail) if b.cta_detail else ''}, puis une carte de fin (end_card).
- INTERDIT d'inventer des chiffres, statistiques, prix, remises, témoignages ou résultats garantis. Utilise stat_number UNIQUEMENT avec un chiffre présent dans le brief (champ proof). Promesses fiscales/financières/santé: formulations prudentes.
- Si une mention est nécessaire, mets-la dans end_card.disclaimer (courte).
- Une phrase = une scène. Pour prolonger la scène précédente sur la phrase suivante: {{"type":"continue"}} (utile pour split_compare, checklist, icon_cards).
- Varie les scènes: jamais deux fois la même scène de suite (sauf continue). Utilise au moins 6 types différents.
- Les champs « at » / « *_at » contiennent UN mot exact de la phrase, prononcé au moment où l'animation doit se déclencher.
- Textes à l'écran très courts (1 à 5 mots), mots-clés, pas des phrases entières.
- Icônes autorisées: {', '.join(ICON_NAMES)}.

CATALOGUE DES SCÈNES: {json.dumps(catalog, ensure_ascii=False)}

Réponds UNIQUEMENT avec du JSON valide:
{{"title": "...", "beats": [{{"text": "phrase de voix off", "scene": {{"type": "...", ...}}}}]}}"""


def _extract_json(text: str) -> dict[str, Any]:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S)
    m = re.search(r"\{.*\}", t, re.S)
    return json.loads(m.group(0) if m else t)


def llm_endpoints(api_key: Optional[str] = None) -> list[dict[str, Any]]:
    """Passerelles LLM disponibles, dans l'ordre d'essai.

    1. Passerelle compatible OpenAI (LLM_BASE_URL — ex. FreeLLMAPI: niveaux gratuits
       officiels de ~30 fournisseurs, bascule automatique entre eux).
    2. OpenRouter (OPENROUTER_API_KEY).
    Liste vide = aucune IA: les moteurs utilisent leurs règles locales.
    """
    out = []
    base = (setting("LLM_BASE_URL", "") or "").rstrip("/")
    if base:
        out.append({"name": "passerelle", "url": base + "/chat/completions", "key": setting("LLM_API_KEY", "") or "",
                    "model": setting("LLM_MODEL", "auto:smart") or "auto:smart", "headers": {}})
    key = api_key or setting("OPENROUTER_API_KEY")
    if key:
        out.append({"name": "openrouter", "url": OPENROUTER_CHAT_URL, "key": key, "model": LLM_MODEL,
                    "headers": {"HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "https://cutforge.app"), "X-Title": "CutForge Pub"}})
    return out


def llm_available(api_key: Optional[str] = None) -> bool:
    return bool(llm_endpoints(api_key))


def chat(prompt: str, api_key: Optional[str] = None, model: Optional[str] = None, timeout: int = 90, temperature: float = 0.8) -> str:
    """Un appel de chat; essaie chaque passerelle dans l'ordre, lève si toutes échouent."""
    import httpx
    errors = []
    for ep in llm_endpoints(api_key):
        try:
            with httpx.Client(timeout=timeout) as cl:
                headers = {"Content-Type": "application/json", **ep["headers"]}
                if ep["key"]:
                    headers["Authorization"] = f"Bearer {ep['key']}"
                r = cl.post(ep["url"], headers=headers, json={"model": model if (model and ep["name"] == "openrouter") else ep["model"],
                                                                "temperature": temperature,
                                                                "messages": [{"role": "user", "content": prompt}]})
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
            content = ((r.json().get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            if content.strip():
                logger.info("LLM via %s (%s)", ep["name"], r.headers.get("X-Routed-Via", ep["model"]))
                return content
            raise RuntimeError("réponse vide")
        except Exception as e:  # passerelle suivante
            errors.append(f"{ep['name']}: {e}")
            logger.warning("LLM %s indisponible: %s", ep["name"], e)
    raise RuntimeError("aucune passerelle LLM disponible — " + " | ".join(errors) if errors else "aucune passerelle LLM configurée")


def write_storyboard(b: Brief, api_key: Optional[str] = None) -> Storyboard:
    if llm_available(api_key):
        for attempt in range(2):
            try:
                data = _extract_json(chat(build_prompt(b), api_key))
                board = Storyboard.from_dict({"angle": b.angle, "template": b.template, **data})
                board = sanitize(board, b)
                if len(board.beats) >= 5:
                    board.notes.append("Script écrit par l'IA.")
                    return board
            except Exception as e:  # repli
                logger.warning("storyboard IA échoué (tentative %s): %s", attempt + 1, e)
    return sanitize(fallback_storyboard(b), b)


# --------------------------------------------------------------------------- #
# Garde-fous
# --------------------------------------------------------------------------- #
_NUM = re.compile(r"\d")


def sanitize(board: Storyboard, b: Brief) -> Storyboard:
    allowed_numbers = set(re.findall(r"\d+", " ".join([b.proof or "", b.cta_detail or "", b.offer or "", b.promise or ""])))
    prev = None
    for beat in board.beats:
        sc = beat.scene if isinstance(beat.scene, dict) else {"type": "continue"}
        typ = sc.get("type", "continue")
        if typ not in SCENE_CATALOG and typ != "continue":
            sc = {"type": "title_slam", "title": _short(beat.text, 5)}; typ = "title_slam"
        if typ == "stat_number":
            nums = set(re.findall(r"\d+", str(sc.get("value", ""))))
            if not nums or not nums <= allowed_numbers:
                sc = {"type": "title_slam", "title": sc.get("label") or _short(beat.text, 5)}; typ = "title_slam"
                board.notes.append("Chiffre non fourni par le client retiré.")
        if typ == "timer_ring":
            v = re.findall(r"\d+", str(sc.get("value", "")))
            if not v or v[0] not in allowed_numbers | set(re.findall(r"\d+", beat.text)):
                sc = {"type": "title_slam", "title": _short(beat.text, 5)}; typ = "title_slam"
        if typ == prev and typ != "continue":
            sc["type"] = "continue"; typ = "continue"
        for item in sc.get("items", []) if isinstance(sc.get("items"), list) else []:
            if isinstance(item, dict) and item.get("icon") not in ICON_NAMES:
                item["icon"] = guess_icon(item.get("label", ""))
        beat.scene = sc
        prev = typ if typ != "continue" else prev
        # voix: chiffres en toutes lettres gardés tels quels; rien d'autre
    if not board.beats or board.beats[-1].scene.get("type") != "end_card":
        board.beats.append(Beat(_sentence(_short(b.promise, 5) or "Dès aujourd'hui"),
                                {"type": "end_card", "brand": b.business, "slogan": _short(b.promise, 4) or b.business,
                                 "button": "Cliquez sur le bouton", "disclaimer": b.disclaimer}, 0.3))
    if b.disclaimer:
        board.beats[-1].scene.setdefault("disclaimer", b.disclaimer)
    if board.beats and board.beats[0].scene.get("type") == "continue":
        board.beats[0].scene = {"type": "title_slam", "title": _short(board.beats[0].text, 5)}
    board.template = b.template
    return board
