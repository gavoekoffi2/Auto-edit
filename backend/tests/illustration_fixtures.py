"""Shared helpers for the illustration-engine test suite."""
from __future__ import annotations

import shutil
from typing import List

WPS = 2.5   # words per second, roughly conversational French


def build_vu(script: List[str], wps: float = WPS, gap: float = 0.35) -> dict:
    """A word-level transcript in the shape the transcription step produces."""
    t, segments = 0.0, []
    for sentence in script:
        words = []
        for word in sentence.split():
            duration = 1.0 / wps
            words.append({"word": word, "start": round(t, 3),
                          "end": round(t + duration, 3)})
            t += duration
        if not words:
            continue
        segments.append({"text": sentence, "start": words[0]["start"],
                         "end": words[-1]["end"], "words": words})
        t += gap
    return {"language": "fr", "duration": round(t, 3), "segments": segments}


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


# A script that exercises every discourse pattern the analyzer knows.
DEMO_SCRIPT = [
    "Salut à tous et bienvenue dans cette nouvelle vidéo.",
    "Aujourd'hui je vous explique comment lancer une boutique en ligne rentable.",
    "Pour réussir en e-commerce, vous devez maîtriser trois choses : "
    "le produit, le trafic et la livraison.",
    "Beaucoup de gens se lancent sans réfléchir et ils perdent leur argent.",
    "Premièrement vous trouvez un bon produit, ensuite vous attirez du trafic, "
    "enfin vous assurez la livraison.",
    "C'est vraiment la base de tout le système.",
    "Avant, les vendeurs perdaient des heures à encaisser ; maintenant, "
    "le mobile money règle le paiement en dix secondes.",
    "Et ça change absolument tout pour les commerçants africains.",
    "87% des boutiques en ligne échouent pendant la première année.",
    "La raison est simple et je vais vous l'expliquer.",
    "Le problème, c'est que personne ne suit ses marges. "
    "La solution est un tableau de bord hebdomadaire.",
    "Prenez le temps de le mettre en place dès le départ.",
    "Le client envoie sa commande, le serveur traite le paiement, "
    "puis l'entrepôt expédie le colis.",
    "Voilà comment fonctionne une vraie chaîne logistique.",
    "Merci d'avoir regardé, abonnez-vous et à très vite.",
]

# The mission's end-to-end acceptance script.
MISSION_SCRIPT = [
    "Bonjour et bienvenue sur la chaîne.",
    "Pour réussir en e-commerce, vous devez maîtriser trois choses : "
    "le produit, le trafic et la livraison.",
    "Je vais détailler chacun de ces trois points avec vous maintenant.",
]
