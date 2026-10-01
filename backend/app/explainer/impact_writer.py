"""Brief → storyboard du montage « Impact » (méthode problème → agitation → solution → action).

Ordre narratif imposé (c'est ce qui fait vendre) :
  1. ACCROCHE      la douleur de la cible, en question ou en constat choc
  2. AGITATION     les symptômes concrets, ce que ça coûte, le concurrent qui gagne, « ça fait mal »
  3. BASCULE       « c'est exactement pour ça que… » (plein écran, couleur de la marque)
  4. SOLUTION      le produit révélé, ce qu'il apporte, les bénéfices
  5. RÉSULTAT      le téléphone qui sonne, l'offre / le prix (seulement s'il est fourni)
  6. ACTION        lien / bouton + numéro prononcé et affiché chiffre par chiffre

IA (passerelles configurées) avec catalogue de scènes + exemple validé ;
sinon gabarit rempli avec les réponses de l'entretien. Toujours nettoyé par sanitize_impact().
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from .montages import resolve_domain
from .schema import Beat, Brief, Storyboard

logger = logging.getLogger(__name__)

PHASES = ["accroche", "agitation", "bascule", "solution", "resultat", "action"]

IMPACT_SCENES: dict[str, dict[str, Any]] = {
    "hook_question": {"phase": "accroche", "desc": "Lignes géantes qui claquent une à une + grand emoji OU le produit sur un socle; étiquette rouge qui tombe (ex: « 0 VENTE »).",
                      "params": {"lines": ["2-4 lignes de 1-4 mots, reprennent la phrase"], "highlight": ["mots en couleur"], "emoji": "1 emoji", "product": "true pour montrer le produit", "stamp": "optionnel, 1-2 mots", "stamp_at": "mot"}},
    "pain_stack": {"phase": "agitation", "desc": "3 douleurs/symptômes sur cartes rouges barrées une par une, sur un fil d'actualité qui défile.",
                   "params": {"lead": "ex: Une pub qui…", "items": [{"emoji": "1 emoji", "text": "2-5 mots", "at": "mot déclencheur"}]}},
    "counter_rows": {"phase": "agitation", "desc": "Compteurs qui montent (vues, likes…) puis une ligne rouge à 0 (ventes, clients…). Chiffres purement illustratifs de la situation de la cible.",
                     "params": {"title": "ex: Résultat ?", "rows": [{"emoji": "", "label": "", "value": "nombre ou 0", "bad": "true pour la ligne rouge", "at": "mot"}], "bubbles": ["1-3 messages courts"], "bubbles_at": "mot"}},
    "versus": {"phase": "*", "desc": "Deux panneaux : ce qui va (vert, coché) / ce qui ne va pas (rouge, croix).",
               "params": {"title": "optionnel", "a": {"label": "", "text": "", "emoji": "", "product": "true", "at": "mot"}, "b": {"label": "", "text": "", "emoji": "", "at": "mot"}}},
    "rival_split": {"phase": "agitation", "desc": "Écran coupé : en haut « vous », silence ; en bas « votre concurrent », les messages de clients pleuvent.",
                    "params": {"top": {"label": "VOUS", "value": "ex: 0 client", "sub": "silence…"}, "bottom": {"label": "VOTRE CONCURRENT", "bubbles": ["3-4 messages clients"], "at": "mot"}, "bubbles_at": "mot"}},
    "punch": {"phase": "agitation", "desc": "Coup de poing rouge, l'écran se fissure (ex: « Et ça, ça fait mal. »).",
              "params": {"pre": "ex: Et ça,", "punch": "ex: ça fait mal.", "at": "mot"}},
    "pivot": {"phase": "bascule", "desc": "Plein écran couleur de marque, formes géométriques : « C'est exactement pour ça que… » + pastille noire.",
              "params": {"lines": ["1-2 lignes"], "pill": "2-4 mots (ex: on est là / nom de la marque)", "pill_at": "mot"}},
    "product_reveal": {"phase": "solution", "desc": "Le produit sur un socle, rayons lumineux, nom en grand, accroche courte, étoiles, badge optionnel.",
                       "params": {"kicker": "optionnel", "name": "nom du produit", "tagline": "promesse 2-5 mots", "badge": "optionnel (ex: NOUVEAU)", "at": "mot"}},
    "tiles": {"phase": "solution", "desc": "Grille de 3 à 8 cartes emoji + libellé qui apparaissent mot à mot (gamme, catégories, usages, cibles).",
              "params": {"kicker": "petit sur-titre", "title": "1-2 lignes", "items": [{"emoji": "", "label": "1-3 mots", "at": "mot"}]}},
    "phone_checks": {"phase": "solution", "desc": "Téléphone qui montre la pub/produit + 3 coches vertes (miroir positif des douleurs).",
                     "params": {"title": "2 lignes séparées par \\n", "badge": "optionnel", "button": "ex: COMMANDER", "at": "mot", "checks": [{"text": "2-4 mots", "at": "mot"}]}},
    "pillars": {"phase": "solution", "desc": "3 grandes cartes emoji + texte (3 bénéfices ou 3 piliers).",
                "params": {"kicker": "ex: CE QUE VOUS OBTENEZ", "items": [{"emoji": "", "text": "2-5 mots", "at": "mot"}]}},
    "phone_ring": {"phase": "resultat", "desc": "Le téléphone sonne, notifications de commandes/rendez-vous, compteur qui monte.",
                   "params": {"title": "ex: Vous lancez votre pub…", "notes": ["3-4 notifications"], "counter_label": "ex: commandes", "counter_to": 27, "at": "mot"}},
    "price_offer": {"phase": "resultat", "desc": "Prix / offre qui claque (UNIQUEMENT si le client a donné un prix), ancien prix barré optionnel.",
                    "params": {"kicker": "", "old_price": "optionnel", "price": "", "note": "optionnel", "at": "mot"}},
    "cta": {"phase": "action", "desc": "Bouton « Cliquez sur le lien », flèche, téléphone qui sonne, numéro chiffre par chiffre, slogan, logo.",
            "params": {"button": "", "sub": "ex: sous cette vidéo", "phone": "numéro avec espaces", "call_at": "mot (ex: appelez)", "tagline": "slogan final court"}},
    "title": {"phase": "*", "desc": "Repli : lignes géantes qui claquent.", "params": {"lines": [""], "highlight": [""]}},
}

EXAMPLE = [
    {"text": "Votre produit est bon.", "scene": {"type": "hook_question", "lines": ["Votre produit", "est bon."], "highlight": ["bon"], "product": True}},
    {"text": "Alors pourquoi personne ne l'achète ?", "scene": {"type": "title", "lines": ["Alors pourquoi", "personne", "ne l'achète ?"], "highlight": ["personne"]}},
    {"text": "Une pub qui n'arrête pas le regard. Qui ne convainc pas. Qui ne vend pas.", "scene": {"type": "pain_stack", "lead": "Une pub qui…", "items": [{"emoji": "👁️", "text": "n'arrête pas le regard", "at": "arrête"}, {"emoji": "🤷🏾‍♂️", "text": "ne convainc pas", "at": "convainc"}, {"emoji": "💸", "text": "ne vend pas", "at": "vend"}]}},
    {"text": "Résultat ? Des vues. Des likes. Quelques « c'est combien ? »… et zéro vente.", "scene": {"type": "counter_rows", "title": "Résultat ?", "rows": [{"emoji": "👁️", "label": "Vues", "value": 12480, "at": "vues"}, {"emoji": "❤️", "label": "Likes", "value": 356, "at": "likes"}, {"emoji": "🛒", "label": "Ventes", "value": 0, "bad": True, "at": "zéro"}], "bubbles": ["C'est combien ?", "Prix svp 🙏🏾"], "bubbles_at": "quelques"}},
    {"text": "Pendant ce temps, votre concurrent récupère vos clients.", "scene": {"type": "rival_split", "top": {"label": "Vous", "value": "0 client"}, "bottom": {"label": "Votre concurrent", "bubbles": ["Je commande ! 🛍️", "J'en veux 3 🔥"], "at": "concurrent"}, "bubbles_at": "récupère"}},
    {"text": "Et ça, ça fait mal.", "scene": {"type": "punch", "pre": "Et ça,", "punch": "ça fait mal.", "at": "fait"}},
    {"text": "C'est exactement pour ça que nous sommes là.", "scene": {"type": "pivot", "lines": ["C'est exactement", "pour ça que"], "pill": "on est là", "pill_at": "sommes"}},
    {"text": "Cliquez sur le lien sous cette vidéo, ou appelez le +228 93 70 81 78.", "scene": {"type": "cta", "button": "Cliquez sur le lien", "sub": "sous cette vidéo", "phone": "+228 93 70 81 78", "call_at": "appelez", "tagline": "Votre prochaine vente commence ici"}},
]

_EMOJI_HINTS = [
    (r"peau|cr[èe]me|cosm|beaut|maquill|soin", "💄"), (r"cheveu|coiff|perruque|m[èe]che", "💇🏾‍♀️"), (r"v[êe]tement|robe|pagne|mode|tenue|habit", "👗"),
    (r"chaussure|basket|sandale", "👟"), (r"parfum|odeur|senteur", "🌸"), (r"bijou|bague|collier|montre", "💍"), (r"t[ée]l[ée]phone|smartphone", "📱"),
    (r"meuble|canap|lit|table|d[ée]co", "🛋️"), (r"repas|plat|cuisine|nourrit|manger|faim|restau", "🍲"), (r"jus|boisson|eau", "🥤"),
    (r"g[âa]teau|p[âa]tiss|pain|boulang", "🎂"), (r"formation|cours|apprend|[ée]cole|[ée]tudi", "🎓"), (r"livre|e-?book|guide", "📘"),
    (r"logiciel|appli|site|digital|ordinateur", "💻"), (r"argent|prix|cher|co[ûu]t|budget|d[ée]pens|perd", "💸"), (r"temps|retard|attente|lent|heure", "⏳"),
    (r"stress|fatigu|[ée]puis|peur|inqui", "😩"), (r"client|vente|vend|commande", "🛒"), (r"livr|colis|exp[ée]d", "🚚"), (r"maison|terrain|immob|construct", "🏠"),
    (r"sant[ée]|douleur|mal ", "🩺"), (r"voiture|transport|d[ée]plac", "🚗"), (r"qualit|solide|dur", "💪"), (r"rapide|vite|instant", "⚡"),
    (r"naturel|bio|plante", "🌿"), (r"garanti|s[ée]curi|confian|prot[èe]g", "🛡️"), (r"[ée]conom|moins cher|pas cher|promo", "💰"), (r"style|[ée]l[ée]gan|beau", "✨"),
]


def emoji_for(text: str, default: str = "✨") -> str:
    low = (text or "").lower()
    for pat, e in _EMOJI_HINTS:
        if re.search(pat, low):
            return e
    return default


# --------------------------------------------------------------------------- nombres en lettres (voix)
_U = ["zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze", "douze", "treize", "quatorze",
      "quinze", "seize", "dix-sept", "dix-huit", "dix-neuf"]
_T = {20: "vingt", 30: "trente", 40: "quarante", 50: "cinquante", 60: "soixante"}


def fr_number(n: int) -> str:
    if n < 20:
        return _U[n]
    if n < 70:
        t, u = divmod(n, 10)
        return _T[t * 10] + ("" if u == 0 else (" et un" if u == 1 else "-" + _U[u])).replace(" et un", "-et-un")
    if n < 80:
        return "soixante" + ("-et-onze" if n == 71 else "-" + _U[n - 60])
    if n < 100:
        return "quatre-vingt" + ("s" if n == 80 else "-" + _U[n - 80])
    if n < 1000:
        h, r = divmod(n, 100)
        head = "cent" if h == 1 else _U[h] + "-cent" + ("s" if r == 0 else "")
        return head + ("" if r == 0 else "-" + fr_number(r))
    return str(n)


def format_phone(raw: str) -> str:
    """« +22893708178 » → « +228 93 70 81 78 » (affichage)."""
    s = re.sub(r"[^\d+]", "", raw or "")
    if not s:
        return ""
    plus = s.startswith("+"); d = s.lstrip("+")
    cc = ""
    if plus:
        for n in (3, 2, 1):  # indicatif le plus probable (Afrique de l'Ouest: 3 chiffres)
            if len(d) - n in (8, 9, 10):
                cc, d = d[:n], d[n:]
                break
    pairs = [d[i:i + 2] for i in range(0, len(d), 2)]
    return (("+" + cc + " ") if cc else ("+" if plus else "")) + " ".join(pairs)


def spoken_phone(display: str) -> str:
    """« +228 93 70 81 78 » → « plus deux-cent-vingt-huit, quatre-vingt-treize, … » (lecture sans ambiguïté)."""
    parts = []
    for tok in display.split():
        plus = tok.startswith("+"); t = tok.lstrip("+")
        if not t.isdigit():
            continue
        if t.startswith("0") and len(t) > 1:
            w = " ".join(fr_number(int(c)) for c in t)
        else:
            w = fr_number(int(t))
        parts.append(("plus " if plus else "") + w)
    return ", ".join(parts)


# --------------------------------------------------------------------------- repli sans IA
def _you(b: Brief) -> dict[str, str]:
    tu = (b.tone or "vous") == "tu"
    return {"vous": "tu" if tu else "vous", "votre": "ton" if tu else "votre", "vos": "tes" if tu else "vos",
            "cliquez": "Clique" if tu else "Cliquez", "appelez": "appelle" if tu else "appelez",
            "etes": "es" if tu else "êtes", "avez": "as" if tu else "avez"}


def _sent(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip()).rstrip(" .")
    return (s[:1].upper() + s[1:] + ".") if s else ""


def _lines(text: str, maxw: int = 3, maxl: int = 4) -> list[str]:
    ws = re.sub(r"[«»\"]", "", text).rstrip(".").split()
    out, cur = [], []
    for w in ws:
        cur.append(w)
        if len(cur) >= maxw:
            out.append(" ".join(cur)); cur = []
    if cur:
        out.append(" ".join(cur))
    if len(out) > maxl:
        out = out[:maxl - 1] + [" ".join(out[maxl - 1:])]
    return out


def _items(text: str, n: int = 3) -> list[str]:
    parts = [p.strip(" .;-•") for p in re.split(r",|;|\n| et |•", text or "") if p.strip(" .;-•")]
    return [p for p in parts if len(p.split()) <= 7][:n]


def _keyword(text: str) -> str:
    ws = [w for w in re.findall(r"[\wÀ-ÿ'-]+", text or "") if len(w) > 3]
    return max(ws, key=len) if ws else ""


def _is_pro(b: Brief) -> bool:
    """La cible est-elle un professionnel (vendeur, entreprise) plutôt qu'un consommateur ?"""
    txt = f"{b.audience} {b.problem}".lower()
    return bool(re.search(r"entrepr|commer[çc]ant|vendeu|boutique|business|pme|soci[ée]t[ée]|patron|marque|restaurat|g[ée]rant|clients?\b", txt))


def fallback_impact(b: Brief) -> Storyboard:
    y = _you(b); dom = resolve_domain(b.domain)
    name = (b.offer or b.business or "Notre offre").strip()
    beats: list[Beat] = []
    add = lambda text, scene, pause=0.22: beats.append(Beat(text=text, scene=scene, pause_after=pause))  # noqa: E731

    # 1. accroche : la douleur
    prob = _sent(b.problem) or _sent(f"{y['vous'].capitalize()} cherchez une solution qui marche vraiment")
    add(prob, {"type": "hook_question", "lines": _lines(prob), "highlight": [_keyword(prob)], "emoji": emoji_for(b.problem, "😩")})
    # 2. agitation : symptômes / coût
    cons = _items(b.consequences) or _items(b.problem)
    if len(cons) < 2:
        cons = ["Du temps perdu", "De l'argent gaspillé", "Toujours le même problème"]
    cons = cons[:3]
    lead = "Résultat :"
    low = lambda c: c[:1].lower() + c[1:] if c[1:2].islower() or len(c) < 2 else c  # noqa: E731
    add(f"{lead} " + ", ".join(low(c) for c in cons) + ".",
        {"type": "pain_stack", "lead": lead, "items": [{"emoji": emoji_for(c, "❌"), "text": c, "at": _keyword(c)} for c in cons]})
    pro = _is_pro(b)
    if pro:
        add("Pendant ce temps, votre concurrent récupère vos clients." if y["vous"] == "vous" else "Pendant ce temps, ton concurrent récupère tes clients.",
            {"type": "rival_split", "top": {"label": "Vous" if y["vous"] == "vous" else "Toi", "value": f"0 {dom['result']}", "sub": "silence…"},
             "bottom": {"label": "Le concurrent", "bubbles": dom["bubbles"][:3], "at": "concurrent"}, "bubbles_at": "récupère"})
    add("Et ça, ça fait mal.", {"type": "punch", "pre": "Et ça,", "punch": "ça fait mal.", "at": "fait"}, 0.35)
    # 3. bascule
    brand = (b.business or name).strip()
    add(f"C'est exactement pour ça que {brand} existe.", {"type": "pivot", "lines": ["C'est exactement", "pour ça que"], "pill": brand[:24], "pill_at": _keyword(brand) or "existe"})
    # 4. solution
    desc = _sent(b.product_desc) if b.product_desc and len(b.product_desc.split()) <= 18 else ""
    tag = " ".join((b.promise or "").split()[:5])
    add(f"Voici {name}. {desc}".strip(), {"type": "product_reveal", "name": name[:28], "tagline": tag, "badge": "NOUVEAU" if not b.price else "", "at": _keyword(name) or "voici"})
    add(f"La différence ? Avec {name}, ça marche vraiment.",
        {"type": "versus", "a": {"label": name[:18], "text": "ça marche vraiment", "product": True, "at": "avec"},
         "b": {"label": "Les autres", "text": "des promesses", "emoji": "🙄", "at": "difference"}})
    bens = [x for x in (b.benefits or []) if x][:3]
    if bens:
        add(" ".join(_sent(x) for x in bens), {"type": "pillars", "kicker": "Ce que " + y["vous"] + " obtenez" if y["vous"] == "vous" else "Ce que tu obtiens",
                                                "items": [{"emoji": emoji_for(x, "✅"), "text": x, "at": _keyword(x)} for x in bens]})
    if b.promise:
        prom = _sent(b.promise)
        if pro:
            add(prom, {"type": "phone_ring", "title": "Et le résultat…", "notes": dom["notes"], "counter_label": dom["result"] + "s", "counter_to": 27, "at": _keyword(prom)})
        else:
            add(f"Résultat : {prom[:1].lower() + prom[1:]}", {"type": "title", "lines": _lines(prom), "highlight": [_keyword(prom)]})
    if b.price:
        add(f"Et tout ça pour seulement {b.price.strip().rstrip('.')}.", {"type": "price_offer", "kicker": "Seulement", "price": b.price.strip()[:18], "note": "", "at": "seulement"})
    # 6. action
    phone = format_phone(b.contact_phone)
    cta_txt = f"{y['cliquez']} sur le lien sous cette vidéo"
    if phone:
        cta_txt += f", ou {y['appelez']} dès maintenant le {spoken_phone(phone)}."
    else:
        cta_txt += f", et {('commandez' if y['vous'] == 'vous' else 'commande')} dès maintenant."
    add(cta_txt, {"type": "cta", "button": f"{y['cliquez']} sur le lien", "sub": "sous cette vidéo", "phone": phone, "call_at": y["appelez"],
                  "tagline": (b.cta_detail or brand)[:40]}, 0.3)
    return Storyboard(angle="pas", template=b.template, beats=beats, title=f"{brand} — Impact", notes=["Script écrit sans IA (gabarit)."])


# --------------------------------------------------------------------------- IA
def build_prompt(b: Brief) -> str:
    dom = resolve_domain(b.domain)
    phone = format_phone(b.contact_phone)
    cat = {k: {"phase": v["phase"], "desc": v["desc"], "params": v["params"]} for k, v in IMPACT_SCENES.items()}
    brief = {k: v for k, v in b.to_dict().items() if v and k not in ("product_image_path", "logo_path", "product_asset", "logo_asset", "template", "angle", "montage", "voice")}
    return f"""Tu es un copywriter publicitaire francophone d'élite (20 ans de réponse directe) ET un motion designer.
Écris le script d'une pub vidéo verticale de 45 à 70 secondes pour le client ci-dessous, scène par scène.

BRIEF (réponses du client) : {json.dumps(brief, ensure_ascii=False)}
DOMAINE : {dom['name']}

MÉTHODE OBLIGATOIRE, dans cet ordre (ne jamais commencer par le produit) :
1. ACCROCHE (1-2 phrases) : la douleur de la cible, avec SES mots, en question ou en constat qui pique.
2. AGITATION (3-4 phrases) : symptômes concrets, ce que ça leur coûte (temps, argent, image, stress), la comparaison avec ceux qui ont déjà trouvé la solution, puis un coup de poing court (« Et ça, ça fait mal. » ou équivalent).
3. BASCULE (1 phrase) : « C'est exactement pour ça que… » + la marque.
4. SOLUTION (2-4 phrases) : le produit révélé, ce qui le rend différent, 3 bénéfices concrets (miroir des douleurs).
5. RÉSULTAT (1-2 phrases) : ce qui change concrètement ; le prix/l'offre UNIQUEMENT s'il est dans le brief.
6. ACTION (1 phrase, la dernière) : « {_you(b)['cliquez']} sur le lien sous cette vidéo »{', ou appelez le numéro (écris-le EN LETTRES dans le texte : « ' + spoken_phone(phone) + ' » et mets « ' + phone + ' » dans params.phone)' if phone else ''}.

RÈGLES :
- Français naturel, oral, phrases courtes (3 à 14 mots), rythme rapide ; {'tutoiement' if (b.tone == 'tu') else 'vouvoiement'}.
- 10 à 15 phrases au total. Chaque phrase = une scène (type choisi dans le catalogue, adapté à la phase).
- N'invente AUCUN chiffre sur l'entreprise (clients, années, résultats). Les compteurs de counter_rows ne font qu'illustrer la situation de la cible.
- Les valeurs « at » sont des mots EXACTS de la phrase (déclencheurs d'animation).
- Textes à l'écran très courts (1 à 5 mots), en français. Emojis pertinents pour le domaine.
- Varie les scènes : au moins 7 types différents, jamais deux fois la même scène d'affilée.
- La dernière scène est « cta ».

CATALOGUE DE SCÈNES (type, phase, description, paramètres) :
{json.dumps(cat, ensure_ascii=False)}

EXEMPLE validé (pub d'une agence vidéo — imite la mécanique, pas le texte) :
{json.dumps(EXAMPLE, ensure_ascii=False)}

Réponds UNIQUEMENT en JSON : {{"title": "...", "beats": [{{"text": "...", "scene": {{"type": "...", ...}}}}]}}"""


def write_impact(b: Brief, api_key: Optional[str] = None) -> Storyboard:
    from .writer import _extract_json, chat, llm_available
    if llm_available(api_key):
        try:
            data = _extract_json(chat(build_prompt(b), api_key, temperature=0.8, timeout=120))
            beats = [Beat(text=str(x.get("text", "")).strip(), scene=dict(x.get("scene") or {}), pause_after=0.22)
                     for x in data.get("beats", []) if str(x.get("text", "")).strip()]
            if len(beats) >= 6:
                board = Storyboard(angle="pas", template=b.template, beats=beats, title=str(data.get("title") or b.business), notes=["Script écrit par l'IA."])
                return sanitize_impact(board, b)
        except Exception as e:  # noqa: BLE001
            logger.warning("script IA Impact indisponible (%s) — gabarit", e)
    return sanitize_impact(fallback_impact(b), b)


def sanitize_impact(board: Storyboard, b: Brief) -> Storyboard:
    """Garde-fous : types valides, pas de doublon consécutif, fin sur cta avec le vrai numéro, longueur raisonnable."""
    phone = format_phone(b.contact_phone)
    out: list[Beat] = []
    for beat in board.beats[:18]:
        sc = dict(beat.scene or {})
        t = sc.get("type")
        if t not in IMPACT_SCENES:
            sc = {"type": "title", "lines": _lines(beat.text)}
        if t == "price_offer" and not b.price:
            sc = {"type": "title", "lines": _lines(beat.text)}
        if out and out[-1].scene.get("type") == sc["type"] and sc["type"] not in ("title",):
            sc = {"type": "title", "lines": _lines(beat.text)}
        text = re.sub(r"\s+", " ", beat.text).strip()
        if len(text) > 260:
            text = text[:257].rsplit(" ", 1)[0] + "…"
        out.append(Beat(text=text, scene=sc, pause_after=min(0.45, max(0.12, float(beat.pause_after or 0.22)))))
    if not out or out[-1].scene.get("type") != "cta":
        y = _you(b)
        txt = f"{y['cliquez']} sur le lien sous cette vidéo" + (f", ou {y['appelez']} le {spoken_phone(phone)}." if phone else ".")
        out.append(Beat(text=txt, scene={"type": "cta", "button": f"{y['cliquez']} sur le lien", "sub": "sous cette vidéo", "phone": phone, "call_at": y["appelez"]}))
    cta = out[-1].scene
    cta["phone"] = phone  # toujours le numéro fourni, jamais un numéro inventé
    if phone and spoken_phone(phone).split(",")[0] not in out[-1].text:
        y = _you(b)
        out[-1].text = re.sub(r"[.!]*$", "", out[-1].text) + f", ou {y['appelez']} le {spoken_phone(phone)}."
    if out[0].scene.get("type") not in ("hook_question", "title"):
        out[0].scene = {"type": "hook_question", "lines": _lines(out[0].text), "emoji": emoji_for(out[0].text, "🤔")}
    return Storyboard(angle="pas", template=board.template, beats=out, title=board.title, notes=board.notes)
