"""Templates (packs de style), angles publicitaires et catalogue de scènes.

Un template n'est pas qu'une palette: il fixe la typo des titres, le type de
transition, l'intensité du mouvement, la musique et le grain. Combiné à
l'angle choisi et aux couleurs de marque, deux clients n'obtiennent jamais la
même vidéo.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def _rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    return ",".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def _shade(hex_color: str, factor: float) -> str:
    """factor < 1 assombrit, > 1 éclaircit (vers le blanc)."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    if factor <= 1:
        r, g, b = (int(c * factor) for c in (r, g, b))
    else:
        f = factor - 1
        r, g, b = (int(c + (255 - c) * f) for c in (r, g, b))
    return "#%02x%02x%02x" % (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


def _luma(hex_color: str) -> float:
    r, g, b = (int(hex_color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


TEMPLATES: dict[str, dict[str, Any]] = {
    "prestige": {
        "id": "prestige",
        "name": "Prestige",
        "description": "Bleu nuit et or, bouclier 3D, rythme posé. Finance, santé, conseil, immobilier.",
        "head_font": "Anton",
        "transition": "whip",
        "textCase": "upper",
        "radius": 36,
        "grain": 0.07,
        "pushIn": 0.04,
        "shake": 1.0,
        "music": "hopeful",
        "bpm": 96,
        "colors": {
            "dark0": "#040914", "dark1": "#0B1B3A", "dark2": "#1d3a7a",
            "light1": "#ffffff", "light2": "#f1f3f8", "light3": "#d3d9e7",
            "alarm1": "#4a0f18", "alarm2": "#1e060b",
            "ink": "#0B1B3A", "inkSoft": "#5d6b88", "paper": "#ffffff", "paperSoft": "#b9c4dc",
            "accent": "#F5B82E", "bad": "#E23A3A", "onDark": "#ffffff",
        },
    },
    "neon": {
        "id": "neon",
        "name": "Néon énergie",
        "description": "Violet profond, cyan électrique, transitions zoom, rythme rapide. Tech, apps, e-commerce, jeunes.",
        "head_font": "Bebas",
        "transition": "zoom",
        "textCase": "upper",
        "radius": 28,
        "grain": 0.05,
        "pushIn": 0.06,
        "shake": 1.3,
        "music": "energetic",
        "bpm": 118,
        "colors": {
            "dark0": "#05020f", "dark1": "#140a33", "dark2": "#3a1a7a",
            "light1": "#f7f5ff", "light2": "#ece8ff", "light3": "#cfc6f3",
            "alarm1": "#4d0b3a", "alarm2": "#1c0416",
            "ink": "#140a33", "inkSoft": "#6b5aa3", "paper": "#ffffff", "paperSoft": "#b8aee6",
            "accent": "#22E3FF", "bad": "#FF3D8B", "onDark": "#ffffff",
        },
    },
    "editorial": {
        "id": "editorial",
        "name": "Éditorial papier",
        "description": "Crème et encre, rouge vif, titres serif élégants, glissés horizontaux. Mode, beauté, formation, marques premium.",
        "head_font": "DMSerif",
        "transition": "slide",
        "textCase": "none",
        "radius": 18,
        "grain": 0.10,
        "pushIn": 0.03,
        "shake": 0.7,
        "music": "calm",
        "bpm": 88,
        "colors": {
            "dark0": "#0d0d0d", "dark1": "#1a1a1a", "dark2": "#3a3530",
            "light1": "#fbf8f2", "light2": "#f3ede2", "light3": "#e2d7c3",
            "alarm1": "#5a1712", "alarm2": "#220806",
            "ink": "#141414", "inkSoft": "#6e665b", "paper": "#fbf8f2", "paperSoft": "#c9bfae",
            "accent": "#E63B2E", "bad": "#B8261C", "onDark": "#fbf8f2",
        },
    },
    "minimal": {
        "id": "minimal",
        "name": "Minimal clair",
        "description": "Blanc, noir et bleu franc, style tech épuré, glissés rapides. SaaS, formation, consultants.",
        "head_font": "Anton",
        "transition": "slide",
        "textCase": "upper",
        "radius": 30,
        "grain": 0.03,
        "pushIn": 0.035,
        "shake": 0.8,
        "music": "calm",
        "bpm": 100,
        "colors": {
            "dark0": "#05070d", "dark1": "#0f172a", "dark2": "#1e293b",
            "light1": "#ffffff", "light2": "#f5f7fb", "light3": "#dfe5ef",
            "alarm1": "#3b0d12", "alarm2": "#16050a",
            "ink": "#0f172a", "inkSoft": "#64748b", "paper": "#ffffff", "paperSoft": "#94a3b8",
            "accent": "#2563EB", "bad": "#E11D48", "onDark": "#ffffff",
        },
    },
    "solaire": {
        "id": "solaire",
        "name": "Solaire",
        "description": "Orange soleil et brun chaud, titres condensés, énergie positive. Commerce, food, beauté, événementiel.",
        "head_font": "Bebas",
        "transition": "whip",
        "textCase": "upper",
        "radius": 40,
        "grain": 0.08,
        "pushIn": 0.05,
        "shake": 1.15,
        "music": "energetic",
        "bpm": 110,
        "colors": {
            "dark0": "#120502", "dark1": "#2a0f06", "dark2": "#6b2a10",
            "light1": "#fffaf3", "light2": "#fff0de", "light3": "#f6d6b4",
            "alarm1": "#4a0f0f", "alarm2": "#1c0505",
            "ink": "#2a0f06", "inkSoft": "#8a5a3c", "paper": "#fffaf3", "paperSoft": "#e9c3a0",
            "accent": "#FF7A1A", "bad": "#D7263D", "onDark": "#fffaf3",
        },
    },
}

DEFAULT_TEMPLATE = "prestige"


def resolve_template(template_id: str | None, brand_color: str | None = None) -> dict[str, Any]:
    """Template complet (couleurs dérivées calculées), avec la couleur de marque
    éventuelle en guise d'accent."""
    tpl = deepcopy(TEMPLATES.get(template_id or "", TEMPLATES[DEFAULT_TEMPLATE]))
    c = tpl["colors"]
    if brand_color and isinstance(brand_color, str) and len(brand_color.lstrip("#")) == 6:
        try:
            _rgb(brand_color)
            c["accent"] = "#" + brand_color.lstrip("#")
        except ValueError:
            pass
    acc = c["accent"]
    c["accentLight"] = _shade(acc, 1.45)
    c["accentDark"] = _shade(acc, 0.78)
    c["accentDeep"] = _shade(acc, 0.62)
    c["accentRGB"] = _rgb(acc)
    c["onAccent"] = "#0B1B3A" if _luma(acc) > 0.55 else "#ffffff"
    return tpl


# --------------------------------------------------------------------------- #
# Angles publicitaires: chacun impose une structure narrative différente.
# --------------------------------------------------------------------------- #
ANGLES: dict[str, dict[str, str]] = {
    "douleur": {
        "name": "Douleur → solution",
        "structure": "accroche sur la douleur de la cible → 2-3 symptômes concrets → basculement « pendant ce temps / c'est pour ça » → révélation de la solution → 3 bénéfices → exclusivité ou preuve → appel à l'action → carte de fin",
    },
    "histoire": {
        "name": "Histoire comparée",
        "structure": "deux personnes identiques (même métier, même revenu) → la première sans solution perd, la seconde avec la solution gagne (split_compare) → le résultat (bars_compare) → « une seule décision prise à temps » (toggle_decision) → « lequel voulez-vous être ? » (choice_cards) → appel à l'action → carte de fin",
    },
    "protection": {
        "name": "Peur de perdre / protection",
        "structure": "« Et si demain… » (risque concret pour la famille ou l'entreprise) → ce qui arrive sans protection (loss_drain) → la solution protège (hero_reveal) → ce qui est protégé (checklist) → appel à l'action → carte de fin",
    },
    "exclusivite": {
        "name": "Exclusivité / statut",
        "structure": "« Ce n'est pas pour tout le monde » → pour qui c'est (icon_cards) → ce que ces personnes obtiennent (checklist) → sélection (crowd_select) → appel à l'action → carte de fin",
    },
    "mythe": {
        "name": "Mythe vs réalité",
        "structure": "« On vous a dit que… » (croyance répandue) → FAUX / la réalité → la solution → 3 bénéfices → appel à l'action → carte de fin",
    },
    "attente": {
        "name": "Coût de l'attente",
        "structure": "chaque mois qui passe coûte (timer / loss_drain) → pourquoi on repousse → la solution simple → une décision prise à temps (toggle_decision) → appel à l'action → carte de fin",
    },
    "conversation": {
        "name": "Conversation client",
        "structure": "une conversation réelle type (chat_bubbles) qui pose la question du client → la réponse / la solution → bénéfices → appel à l'action → carte de fin",
    },
}

DEFAULT_ANGLE = "douleur"

# --------------------------------------------------------------------------- #
# Catalogue des scènes (contrat entre le rédacteur IA et le moteur web).
# « at » = un mot prononcé dans la phrase qui déclenche l'animation.
# --------------------------------------------------------------------------- #
SCENE_CATALOG: dict[str, dict[str, Any]] = {
    "title_slam": {"tone": "dark", "desc": "Gros titre qui tombe lettre par lettre (accroche, question, affirmation forte).",
                   "params": {"kicker": "petit sur-titre (optionnel)", "title": "2-6 mots", "highlight": ["mots en couleur"], "sub": "phrase secondaire (optionnel)", "sub_at": "mot"}},
    "icon_cards": {"tone": "dark", "desc": "1 à 5 cartes icône + libellé qui basculent une par une (cibles, catégories, étapes).",
                   "params": {"title": "optionnel", "items": [{"icon": "nom d'icône", "label": "1-3 mots", "at": "mot déclencheur"}]}},
    "checklist": {"tone": "light", "desc": "2 à 4 avantages cochés sur cartes blanches.",
                  "params": {"title": "ex: VOS AVANTAGES", "items": [{"icon": "nom", "label": "début de phrase", "detail": "fin surlignée", "at": "mot"}]}},
    "loss_drain": {"tone": "alarm", "desc": "Des piles de pièces aspirées vers un tampon rouge (perte, gaspillage, impôt, frais).",
                   "params": {"tag": "ex: SANS STRATÉGIE", "chips": ["2 libellés max"], "label": "mot du tampon (ex: IMPÔT)", "drain_at": "mot", "label_at": "mot"}},
    "hero_reveal": {"tone": "light", "desc": "Révélation de la solution: emblème 3D doré qui tourne + nom du produit.",
                    "params": {"kicker": "optionnel", "name": "nom de la solution", "sub": "promesse courte", "emblem": "shield|star|bolt|circle|crown", "at": "mot"}},
    "split_compare": {"tone": "split", "desc": "Écran partagé haut/bas: A sans la solution perd de l'argent, B avec la solution est protégé et grandit. Durée idéale: 2-3 phrases (utiliser continue).",
                      "params": {"a": {"label": "ex: MÉDECIN 1", "tag": "ex: SANS STRATÉGIE", "loss": "ex: − IMPÔT", "at": "mot"}, "b": {"label": "ex: MÉDECIN 2", "tag": "nom de la solution", "at": "mot où B entre en scène"}, "emblem": "shield"}},
    "bars_compare": {"tone": "light", "desc": "Deux barres qui montent (résultat illustratif sans chiffres).",
                     "params": {"title": "ex: À LA RETRAITE", "caption": "ex: DEUX RÉSULTATS TRÈS DIFFÉRENTS", "a_label": "", "b_label": "", "a_value": 0.35, "b_value": 1.0}},
    "crowd_select": {"tone": "dark", "desc": "Une foule grise, seuls 5 personnages s'allument (exclusivité).",
                     "params": {"title": "ex: PAS POUR TOUT LE MONDE", "select_at": "mot", "caption": "optionnel", "highlight": "ex: CEUX QUI BÂTISSENT"}},
    "toggle_decision": {"tone": "dark", "desc": "Un interrupteur passe sur ON: la décision.",
                        "params": {"kicker": "ex: La différence :", "title": "ex: UNE SEULE DÉCISION", "on_at": "mot", "caption": "ex: PRISE À TEMPS"}},
    "choice_cards": {"tone": "light", "desc": "Deux profils; le curseur choisit le bon.",
                     "params": {"title": "question", "a": {"label": "", "sub": ""}, "b": {"label": "", "sub": ""}, "pick_at": "mot"}},
    "timer_ring": {"tone": "light", "desc": "Anneau horloge qui se remplit (durée d'un rendez-vous, d'un délai).",
                   "params": {"value": 30, "unit": "MINUTES", "caption": "phrase", "caption_highlight": "partie surlignée", "at": "mot"}},
    "cta_button": {"tone": "light", "desc": "Appel à l'action: bouton, main qui clique, chevrons vers le bas.",
                   "params": {"title": "ex: CLIQUEZ SUR LE BOUTON", "button": "ex: CLIQUEZ ICI", "click_at": "mot", "down_at": "mot", "caption": "optionnel"}},
    "chat_bubbles": {"tone": "light", "desc": "Téléphone avec une conversation (question client / réponse).",
                     "params": {"contact": "nom affiché", "messages": [{"from": "them|me", "text": "court", "at": "mot"}]}},
    "stat_number": {"tone": "dark", "desc": "Chiffre clé animé — UNIQUEMENT si le chiffre est fourni par le client.",
                    "params": {"value": "ex: 80%", "label": "ce que mesure le chiffre", "source": "source"}},
    "plan_to_3d": {"tone": "dark", "desc": "Plan 2D dessiné trait par trait, scanné par l'IA, qui bascule en maquette 3D (murs qui sortent du sol). Architecture, immobilier, construction, aménagement, décoration.",
                   "params": {"title": "ex: DU PLAN 2D À LA 3D", "title_at": "mot", "at": "mot où le plan commence", "to3d_at": "mot où ça passe en 3D", "label_2d": "ex: PLAN 2D", "label_3d": "ex: MODÈLE 3D", "ai_label": "ex: IA"}},
    "end_card": {"tone": "dark", "desc": "Carte de fin: emblème, slogan, bouton pulsant, mention légale.",
                 "params": {"brand": "nom", "slogan": "2-4 mots", "button": "texte du bouton", "disclaimer": "mention courte", "emblem": "shield"}},
}

ICON_NAMES = [
    "user", "users", "family", "briefcase", "building", "store", "scale", "stethoscope", "heart", "hospital",
    "shield", "check", "coin", "wallet", "trendUp", "trendDown", "chart", "percent", "clock", "calendar",
    "phone", "message", "cart", "truck", "home", "car", "graduation", "book", "rocket", "target", "bulb",
    "lock", "key", "star", "gift", "sparkle", "globe", "bell", "camera", "video", "mic", "tool", "leaf",
    "food", "plane", "school", "alert", "hourglass", "handshake", "crown", "bolt",
]


def public_templates() -> list[dict[str, str]]:
    return [{"id": t["id"], "name": t["name"], "description": t["description"],
             "accent": t["colors"]["accent"], "dark": t["colors"]["dark1"]} for t in TEMPLATES.values()]


def public_angles() -> list[dict[str, str]]:
    return [{"id": k, "name": v["name"], "structure": v["structure"]} for k, v in ANGLES.items()]
