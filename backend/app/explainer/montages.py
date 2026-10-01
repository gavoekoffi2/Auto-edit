"""Modes de montage du Studio Pub, domaines d'activité et voix proposées.

Un MODE DE MONTAGE n'est pas une palette de couleurs : c'est une grammaire
complète (composition des scènes, place du produit, widgets, rythme des
coupes, transitions, sound design). Chaque mode a son moteur d'animation.

Les modes « disponible: False » sont réservés : ils seront construits à partir
de vidéos de référence fournies par l'équipe (même principe que « Impact »,
tiré d'une pub validée).
"""
from __future__ import annotations

import os
from typing import Any

MONTAGES: dict[str, dict[str, Any]] = {
    "impact": {
        "id": "impact", "name": "Impact produit", "engine": "impact", "available": True,
        "description": "Accroche choc, douleur martelée (barres rouges, compteurs à zéro, écran qui se fissure), "
                       "bascule plein écran, produit révélé sur socle, téléphone qui sonne, numéro chiffre par chiffre.",
        "rhythm": "rapide", "music": "energetic", "bpm": 100, "voice_rate": "+6%", "pause": 0.22,
        "best_for": ["ecommerce", "physique", "digital", "services", "food", "beaute"],
    },
    "classique": {
        "id": "classique", "name": "Explicatif illustré", "engine": "classique", "available": True,
        "description": "Scènes illustrées pédagogiques : cartes icônes, bouclier 3D, écran partagé, barres comparées, "
                       "minuteur, conversation. Idéal pour expliquer un service (finance, santé, conseil).",
        "rhythm": "posé", "music": "hopeful", "bpm": 96, "voice_rate": "+5%", "pause": 0.35,
        "best_for": ["services", "immobilier", "education"],
    },
    "cinema": {
        "id": "cinema", "name": "Bande-annonce", "engine": None, "available": False,
        "description": "Format bande-annonce : bandes noires, titres monumentaux, coupes au rythme des percussions.",
        "rhythm": "épique",
    },
    "conversation": {
        "id": "conversation", "name": "Conversation WhatsApp", "engine": None, "available": False,
        "description": "Toute la pub racontée dans un fil de discussion : questions du client, réponses, vocaux, preuve.",
        "rhythm": "naturel",
    },
    "magazine": {
        "id": "magazine", "name": "Magazine", "engine": None, "available": False,
        "description": "Mise en page éditoriale : colonnes, photos produit en grand, typographie de couverture.",
        "rhythm": "élégant",
    },
    "kinetic": {
        "id": "kinetic", "name": "Typo cinétique", "engine": None, "available": False,
        "description": "Uniquement des mots géants qui volent, se cassent et se recomposent sur la voix.",
        "rhythm": "très rapide",
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


def resolve_montage(mid: str | None) -> dict[str, Any]:
    m = MONTAGES.get(mid or "", MONTAGES[DEFAULT_MONTAGE])
    return m if m.get("available") else MONTAGES[DEFAULT_MONTAGE]


def resolve_domain(did: str | None) -> dict[str, Any]:
    return DOMAINS.get(did or "", DOMAINS[DEFAULT_DOMAIN])


def public_montages() -> list[dict[str, Any]]:
    return [{k: m.get(k) for k in ("id", "name", "description", "available", "rhythm")} for m in MONTAGES.values()]


def public_domains() -> list[dict[str, str]]:
    return [{"id": k, "name": d["name"], "emoji": d["emoji"]} for k, d in DOMAINS.items()]


def match_domain(text: str) -> str:
    low = (text or "").lower()
    for k, d in DOMAINS.items():
        if d["name"].lower() in low or k in low:
            return k
    rules = [(r"ligne|e-?commerce|internet|livraison", "ecommerce"), (r"digital|num[ée]rique|e-?book|logiciel|appli|formation en ligne", "digital"),
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
