"""Modes de montage du Studio Pub, domaines d'activité et voix proposées.

Un MODE DE MONTAGE n'est pas une palette de couleurs : c'est une grammaire
complète (composition des scènes, place du produit, widgets, rythme des
coupes, transitions, sound design). Chaque mode a son moteur d'animation.

Chaque mode est tiré de pubs de référence validées par l'équipe. Les modes du
moteur « kit » s'adaptent à tous les formats (9:16, 4:5, 1:1, 16:9) ; « Impact »
et « Explicatif illustré » restent verticaux.
"""
from __future__ import annotations

import os
from typing import Any

MONTAGES: dict[str, dict[str, Any]] = {
    "impact": {
        "id": "impact", "name": "Impact produit", "engine": "impact", "available": True, "formats": ["9:16"],
        "description": "Accroche choc, douleur martelée (barres rouges, compteurs à zéro, écran qui se fissure), "
                       "bascule plein écran, produit révélé sur socle, téléphone qui sonne, numéro chiffre par chiffre.",
        "rhythm": "rapide", "music": "energetic", "bpm": 100, "voice_rate": "+6%", "pause": 0.22,
        "best_for": ["ecommerce", "physique", "beaute", "food"],
        "keywords": ["produit", "cosmétique", "crème", "savon", "parfum", "vêtement", "chaussure", "sac", "montre", "gadget", "commande"],
    },
    "studio": {
        "id": "studio", "name": "Studio blanc", "engine": "kit", "available": True, "formats": ["9:16", "4:5", "1:1", "16:9"],
        "description": "Fond blanc épuré, ordinateur, silhouettes, titres tapés lettre par lettre, étiquettes inclinées, "
                       "ruptures noires et rouges, coffret produit et bouclier « accès exclusif ». Infoproduits, formations, digital.",
        "rhythm": "rapide", "music": "energetic", "bpm": 104, "voice_rate": "+6%", "pause": 0.22,
        "best_for": ["digital", "education"],
        "keywords": ["formation", "cours", "coaching", "ebook", "e-book", "programme", "masterclass", "méthode", "en ligne", "vidéo", "module", "template"],
        "refs": ["Slide IA", "Motion Mastery", "The WhatsApp Closer"],
    },
    "dossier": {
        "id": "dossier", "name": "Dossier résultat", "engine": "kit", "available": True, "formats": ["9:16", "4:5", "1:1", "16:9"],
        "description": "Compte à rebours, enveloppe « REFUSÉ », bascule dans un monde rouge, coffret qui tombe, dossiers colorés, "
                       "livre ouvert, bonus et enveloppe « VALIDÉ ». Examens, concours, visas, certifications.",
        "rhythm": "tendu", "music": "energetic", "bpm": 98, "voice_rate": "+6%", "pause": 0.22,
        "best_for": ["education"],
        "keywords": ["examen", "tcf", "tef", "ielts", "toefl", "bac", "bepc", "visa", "immigration", "canada", "certification", "permis", "admission", "dossier", "réussir", "note", "score"],
        "refs": ["TCF Canada"],
    },
    "app": {
        "id": "app", "name": "App 3D", "engine": "kit", "available": True, "formats": ["9:16", "4:5", "1:1", "16:9"],
        "description": "Téléphone 3D qui pivote, pilules 3D qui basculent, étapes numérotées, trio d'écrans en perspective, "
                       "puces en verre, numéro qui se tape. Applications, assurance, banque, services en ligne.",
        "rhythm": "fluide", "music": "hopeful", "bpm": 100, "voice_rate": "+5%", "pause": 0.25,
        "best_for": ["appli", "services"],
        "keywords": ["application", "appli", "app ", "télécharg", "assurance", "banque", "mobile money", "paiement", "fintech", "logiciel", "plateforme", "site web", "budget", "épargne", "cv"],
        "refs": ["Budget (P2)", "AFG Assurances (P3)", "CV (P5)"],
    },
    "lifestyle": {
        "id": "lifestyle", "name": "Lifestyle offre", "engine": "kit", "available": True, "formats": ["9:16", "4:5", "1:1", "16:9"],
        "description": "Monde plein écran à la couleur de marque, personne heureuse, téléphone couché, gros titres condensés, "
                       "le fond change de couleur à chaque offre, prix 3D. Abonnements, promos, mode, restauration.",
        "rhythm": "pop", "music": "energetic", "bpm": 108, "voice_rate": "+6%", "pause": 0.2,
        "best_for": ["ecommerce", "food", "beaute", "physique"],
        "keywords": ["abonnement", "par mois", "illimité", "promo", "réduction", "soldes", "collection", "mode", "restaurant", "menu", "livraison", "netflix", "musique", "film", "série", "forfait", "pack"],
        "refs": ["Spotify / Netflix (P4)"],
    },
    "event": {
        "id": "event", "name": "Événement", "engine": "kit", "available": True, "formats": ["9:16", "4:5", "1:1", "16:9"],
        "description": "Dégradé orange avec structures de scène, photos assombries, mots encadrés, « À la clé ? » et montant géant, "
                       "date, affiche finale. Événements, concours, soirées, inscriptions, ouvertures.",
        "rhythm": "festif", "music": "energetic", "bpm": 110, "voice_rate": "+7%", "pause": 0.2,
        "best_for": ["evenement"],
        "keywords": ["événement", "evenement", "soirée", "concert", "festival", "concours", "talent", "gala", "salon", "foire", "ouverture", "inauguration", "tournoi", "match", "billet", "ticket", "date", "édition"],
        "refs": ["Concours de talents (P7)"],
    },
    "classique": {
        "id": "classique", "name": "Explicatif illustré", "engine": "classique", "available": True, "formats": ["9:16"],
        "description": "Scènes illustrées pédagogiques : cartes icônes, bouclier 3D, écran partagé, barres comparées, "
                       "minuteur, conversation. Idéal pour expliquer un service (finance, santé, conseil).",
        "rhythm": "posé", "music": "hopeful", "bpm": 96, "voice_rate": "+5%", "pause": 0.35,
        "best_for": ["services", "immobilier"],
        "keywords": ["conseil", "santé", "clinique", "cabinet", "avocat", "comptab", "agence", "immobilier", "terrain"],
    },
}
DEFAULT_MONTAGE = "impact"

DOMAINS: dict[str, dict[str, Any]] = {
    "ecommerce": {"name": "Vente en ligne", "emoji": "🛒", "noun": "produit", "result": "commande",
                  "bubbles": ["Je commande ! 🛍️", "Vous livrez aujourd'hui ?", "J'en veux 2 🔥", "Paiement envoyé ✅"],
                  "notes": ["🛍️ Nouvelle commande", "💬 « C'est disponible ? »", "🛍️ Nouvelle commande", "🚚 Livraison demandée"]},
    "physique": {"name": "Produits physiques / boutique", "emoji": "🛍️", "noun": "produit", "result": "vente",
                 "bubbles": ["Vous êtes où exactement ?", "Il vous en reste ?", "Je passe ce soir 👍", "Mettez-m'en 3"],
                 "notes": ["🛍️ Nouvelle vente", "📍 « Vous êtes où ? »", "🛍️ Nouvelle vente", "📞 Appel manqué (2)"]},
    "digital": {"name": "Produits digitaux", "emoji": "💻", "noun": "programme", "result": "inscription",
                "bubbles": ["Comment je m'inscris ?", "C'est accessible à vie ?", "Paiement fait ✅", "Je commence quand ?"],
                "notes": ["💳 Nouvel achat", "📩 « Comment j'accède ? »", "💳 Nouvel achat", "🎓 Nouvelle inscription"]},
    "services": {"name": "Services", "emoji": "🤝", "noun": "service", "result": "rendez-vous",
                 "bubbles": ["Vous êtes dispo demain ?", "C'est combien le forfait ?", "Je réserve ✅", "On peut se voir ?"],
                 "notes": ["📅 Nouveau rendez-vous", "💬 « Vous êtes dispo ? »", "📅 Nouveau rendez-vous", "📞 Appel manqué (2)"]},
    "food": {"name": "Restauration & alimentation", "emoji": "🍲", "noun": "plat", "result": "commande",
             "bubbles": ["Une portion pour midi 😋", "Vous livrez au bureau ?", "Deux plats svp", "C'était trop bon !"],
             "notes": ["🍽️ Nouvelle commande", "🛵 Livraison demandée", "🍽️ Nouvelle commande", "⭐ Nouvel avis 5/5"]},
    "beaute": {"name": "Beauté & bien-être", "emoji": "💄", "noun": "soin", "result": "réservation",
               "bubbles": ["Il reste une place samedi ?", "Je veux le même résultat 😍", "Je réserve ✅", "Vous livrez ?"],
               "notes": ["💅 Nouvelle réservation", "💬 « C'est quel produit ? »", "🛍️ Nouvelle commande", "⭐ Nouvel avis 5/5"]},
    "immobilier": {"name": "Immobilier & construction", "emoji": "🏠", "noun": "projet", "result": "visite",
                   "bubbles": ["Je peux visiter quand ?", "C'est encore disponible ?", "Envoyez-moi le plan", "On signe 🤝"],
                   "notes": ["🏠 Demande de visite", "📩 « Encore disponible ? »", "🏠 Demande de visite", "📞 Appel manqué (2)"]},
    "education": {"name": "École & formation", "emoji": "🎓", "noun": "formation", "result": "inscription",
                  "bubbles": ["Les inscriptions sont ouvertes ?", "C'est combien la rentrée ?", "Je m'inscris ✅", "Il reste des places ?"],
                  "notes": ["🎓 Nouvelle inscription", "📩 « Il reste des places ? »", "🎓 Nouvelle inscription", "📞 Appel manqué (2)"]},
    "appli": {"name": "Applications & services en ligne", "emoji": "📱", "noun": "application", "result": "téléchargement",
              "bubbles": ["Je l'ai téléchargée ✅", "C'est gratuit ?", "Trop pratique 👌", "Ça marche sur Android ?"],
              "notes": ["📲 Nouveau téléchargement", "💬 « C'est gratuit ? »", "📲 Nouveau téléchargement", "⭐ Nouvel avis 5/5"]},
    "evenement": {"name": "Événements & concours", "emoji": "🎉", "noun": "événement", "result": "inscription",
                  "bubbles": ["Je m'inscris ✅", "C'est où exactement ?", "Il reste des places ?", "On sera là 🔥"],
                  "notes": ["🎟️ Nouvelle inscription", "💬 « C'est où ? »", "🎟️ Nouvelle inscription", "📞 Appel manqué (2)"]},
    "autre": {"name": "Autre", "emoji": "✨", "noun": "offre", "result": "client",
              "bubbles": ["C'est combien ?", "Je suis intéressé 👍", "Comment on fait ?", "Je prends ✅"],
              "notes": ["🔔 Nouveau client", "💬 « C'est combien ? »", "🔔 Nouveau client", "📞 Appel manqué (2)"]},
}
DEFAULT_DOMAIN = "autre"

EDGE_VOICE_LABELS = [
    ("henri", "Henri — voix d'homme posée (France)"),
    ("remy", "Rémy — voix d'homme dynamique"),
    ("thierry_ca", "Thierry — voix d'homme (Canada)"),
    ("denise", "Denise — voix de femme (France)"),
    ("vivienne", "Vivienne — voix de femme chaleureuse"),
]


def public_voices() -> list[dict[str, str]]:
    from .conf import setting
    out = [{"id": k, "name": n} for k, n in EDGE_VOICE_LABELS]
    if setting("ELEVENLABS_API_KEY"):
        vid = setting("ELEVENLABS_VOICE_ID") or ""
        label = setting("ELEVENLABS_VOICE_NAME") or "Voix premium (ElevenLabs)"
        out.insert(0, {"id": f"eleven:{vid}" if vid else "eleven:", "name": label})
    return out


FORMATS: list[dict[str, str]] = [
    {"id": "9:16", "name": "Vertical 9:16", "hint": "TikTok, Reels, Shorts, Statut WhatsApp", "size": "1080×1920"},
    {"id": "4:5", "name": "Portrait 4:5", "hint": "Fil Facebook et Instagram", "size": "1080×1350"},
    {"id": "1:1", "name": "Carré 1:1", "hint": "Facebook, Instagram, WhatsApp", "size": "1080×1080"},
    {"id": "16:9", "name": "Horizontal 16:9", "hint": "YouTube, site web, écran", "size": "1920×1080"},
]
FORMAT_IDS = [f["id"] for f in FORMATS]
DEFAULT_FORMAT = "9:16"
AUTO = "auto"


def resolve_format(fid: str | None) -> str:
    return fid if fid in FORMAT_IDS else DEFAULT_FORMAT


def match_format(text: str) -> str:
    import re
    low = (text or "").lower().replace(" ", "")
    if re.search(r"16[:/x]9|youtube|horizontal|paysage|[ée]cran|site", low):
        return "16:9"
    if re.search(r"1[:/x]1|carr[ée]", low):
        return "1:1"
    if re.search(r"4[:/x]5|filfacebook|filinstagram|feed", low):
        return "4:5"
    if re.search(r"9[:/x]16|tiktok|reel|short|statut|story|vertical", low):
        return "9:16"
    if "facebook" in low or "instagram" in low:
        return "4:5"
    return DEFAULT_FORMAT


def resolve_montage(mid: str | None, fmt: str | None = None) -> dict[str, Any]:
    m = MONTAGES.get(mid or "", MONTAGES[DEFAULT_MONTAGE])
    if not m.get("available"):
        m = MONTAGES[DEFAULT_MONTAGE]
    if fmt and fmt not in m.get("formats", ["9:16"]):
        m = MONTAGES["studio"]
    return m


def resolve_domain(did: str | None) -> dict[str, Any]:
    return DOMAINS.get(did or "", DOMAINS[DEFAULT_DOMAIN])


def auto_montage(brief: Any, recent: list[str] | None = None) -> tuple[str, str]:
    """Choisit le mode de montage le plus adapté à la pub (domaine, mots du brief, format) en évitant
    de redonner le même montage que les dernières pubs du client. Retourne (id, explication)."""
    get = (lambda k: getattr(brief, k, "") or "") if not isinstance(brief, dict) else (lambda k: brief.get(k) or "")
    fmt = resolve_format(get("format"))
    dom = get("domain")
    text = " ".join(str(get(k)) for k in ("business", "offer", "product_desc", "problem", "promise", "audience", "price", "cta_detail")).lower()
    recent = [r for r in (recent or []) if r][:3]
    scores: dict[str, float] = {}
    why: dict[str, list[str]] = {}
    for k, m in MONTAGES.items():
        if not m.get("available") or fmt not in m.get("formats", ["9:16"]):
            continue
        sc, w = 0.0, []
        if dom and dom in m.get("best_for", []):
            sc += 3; w.append(f"domaine « {resolve_domain(dom)['name']} »")
        hits = [kw.strip() for kw in m.get("keywords", []) if kw in text]
        if hits:
            sc += min(3, len(hits)) * 1.5; w.append("mots-clés : " + ", ".join(hits[:3]))
        if recent and k == recent[0]:
            sc -= 2.5; w.append("déjà utilisé pour la pub précédente")
        elif k in recent:
            sc -= 1
        scores[k] = sc + (0.1 if m["engine"] == "kit" else 0)  # à égalité : modes multi-formats
        why[k] = w
    if not scores:
        return "studio", "mode polyvalent"
    best = max(scores, key=lambda k: scores[k])
    reason = "; ".join(x for x in why[best] if not x.startswith("déjà")) or "mode polyvalent pour ce format"
    return best, reason


def public_montages() -> list[dict[str, Any]]:
    return [{k: m.get(k) for k in ("id", "name", "description", "available", "rhythm", "formats", "best_for")} for m in MONTAGES.values()]


def public_formats() -> list[dict[str, str]]:
    return list(FORMATS)


def public_domains() -> list[dict[str, str]]:
    return [{"id": k, "name": d["name"], "emoji": d["emoji"]} for k, d in DOMAINS.items()]


def match_domain(text: str) -> str:
    low = (text or "").lower()
    for k, d in DOMAINS.items():
        if d["name"].lower() in low or k in low:
            return k
    rules = [(r"[ée]v[ée]nement|concours de|soir[ée]e|concert|festival|gala|tournoi", "evenement"), (r"appli|application|t[ée]l[ée]charg|assurance|banque|fintech", "appli"),
             (r"ligne|e-?commerce|internet|livraison", "ecommerce"), (r"digital|num[ée]rique|e-?book|logiciel|formation en ligne", "digital"),
             (r"boutique|magasin|physique|v[êe]tement|chaussure|cosm", "physique"), (r"restau|food|cuisine|repas|alimen|traiteur|p[âa]tiss", "food"),
             (r"beaut|coiff|salon|spa|soin|onglerie|maquill", "beaute"), (r"immob|construct|archi|terrain|maison|appartement", "immobilier"),
             (r"[ée]cole|formation|cours|universit|coaching", "education"), (r"service|agence|consult|artisan|nettoyage|transport", "services")]
    import re
    for pat, k in rules:
        if re.search(pat, low):
            return k
    return DEFAULT_DOMAIN


def match_montage(text: str) -> str:
    low = (text or "").lower()
    if any(x in low for x in ("auto", "recommand", "choisis", "comme tu veux", "je ne sais pas")):
        return AUTO
    for k, m in MONTAGES.items():
        if m["available"] and (m["name"].lower() in low or k in low):
            return k
    return DEFAULT_MONTAGE


def match_voice(text: str) -> str:
    low = (text or "").lower()
    for v in public_voices():
        if v["name"].split(" — ")[0].lower() in low or v["id"] == low:
            return v["id"]
    return os.environ.get("EXPLAINER_DEFAULT_VOICE", "henri")
