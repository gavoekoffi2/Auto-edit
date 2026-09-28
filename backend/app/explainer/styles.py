"""ADN de style du Studio face caméra — pour que deux montages ne se ressemblent jamais.

Un style n'est pas une palette: c'est un ensemble de GÈNES indépendants qui
changent tout ce que l'œil perçoit d'une vidéo à l'autre :

    palette      couleurs des panneaux sombres / clairs, encre, accents
    head_font    typo des titres (Anton, Bebas, DMSerif) + casse
    panel        texture des panneaux plein écran (papier, grille, points, trame…)
    chrome       habillage des cartes flottantes (carte postale, dossier, notification…)
    transition   entrée/sortie des panneaux (iris, raclette, feuille, déchirure…)
    captions     sous-titres karaoké (boîte, surligneur, contour, serif…) + position
    badge        présentation du logo (carte blanche, pastille, rond…) + coin
    motion       caractère du mouvement (raideur/amortissement des ressorts, secousse)
    text_fx      apparition des textes (chute, masque, machine à écrire, zoom)
    sound        humeur musicale, tempo, tonalité, sons signature

14 styles sont écrits à la main (dont les 9 validés en production). Pour chaque
nouvelle vidéo, `choose_style` :
  1. mesure l'affinité thématique de chaque style avec le discours (voyage,
     finance, santé, tech…);
  2. écarte les styles trop proches des derniers montages de l'utilisateur
     (distance entre empreintes de gènes);
  3. si tous les styles écrits ont déjà servi récemment, INVENTE un style :
     tirage seedé des gènes + palette harmonique générée, rejeté tant qu'il
     ressemble à un style de l'historique.
Chaque style choisi est en plus légèrement MUTÉ (seed de la vidéo) pour que
même un style réutilisé ne produise jamais deux fois la même image.
"""
from __future__ import annotations

import colorsys
import hashlib
import random
import re
from copy import deepcopy
from typing import Any, Iterable, Optional

# --------------------------------------------------------------------------- #
# Pools de gènes (contrat avec web/studio.js)
# --------------------------------------------------------------------------- #
PANELS = ["radial", "paper", "grid", "dots", "lines", "halftone", "mesh", "blueprint", "scan", "stripes"]
CHROMES = ["postcard", "dossier", "notification", "glass", "sticker", "ticket", "polaroid", "terminal",
           "magazine", "neon", "clean", "tape"]
TRANSITIONS = ["iris", "squeegee", "slide", "paper", "tear", "zoom", "shutter", "whip", "glitch", "blinds"]
CAPTIONS = ["box", "pill", "underline", "highlight", "outline", "bounce", "serif", "ticker"]
BADGES = ["card", "bare", "pill", "round"]
TEXT_FX = ["drop", "mask", "type", "scale"]
HEAD_FONTS = ["Anton", "Bebas", "DMSerif"]
MOODS = ["hopeful", "energetic", "calm"]
# MODE DE MONTAGE: la grammaire de l'image (où est le visage, comment les idées
# s'écrivent, comment on passe aux démonstrations). C'est le gène principal:
# deux montages de modes différents ne se ressemblent pas, quelles que soient
# les couleurs.
MONTAGES = ["plein_cadre", "presentateur", "fenetre", "telephone", "kinetique", "ecran_scinde",
            "zoom_rythme", "mur_polaroid", "journal_tv", "magazine",
            "stories", "jeu_video", "podcast", "documentaire", "bento", "voyage"]
MONTAGE_NAMES = {
    "plein_cadre": "Plein cadre", "presentateur": "Présentateur", "fenetre": "Fenêtre", "telephone": "Téléphone",
    "kinetique": "Typo cinétique", "ecran_scinde": "Écran scindé", "zoom_rythme": "Zoom rythmé",
    "mur_polaroid": "Mur de polaroids", "journal_tv": "Journal TV", "magazine": "Couverture magazine",
    "stories": "Story Instagram", "jeu_video": "Jeu vidéo", "podcast": "Podcast", "documentaire": "Documentaire",
    "bento": "Bento", "voyage": "Voyage plan-séquence",
}
MONTAGE_DESC = {
    "plein_cadre": "Visage plein écran, cartes habillées posées sur l'image.",
    "presentateur": "Pendant les démonstrations, le visage devient une bulle dans un coin.",
    "fenetre": "Le visage dans un cadre sur un décor, gros titres écrits au-dessus.",
    "telephone": "Le visage dans un téléphone incliné, les idées sortent en bulles de discussion.",
    "kinetique": "Pas de cartes: les phrases clés tombent en typographie géante sur l'image.",
    "ecran_scinde": "Visage en haut, bande de texte en bas où s'écrivent titres et sous-titres.",
    "zoom_rythme": "La caméra zoome et pivote sur chaque idée; graphisme minimal, mots-clés géants.",
    "mur_polaroid": "Le visage dans un polaroid épinglé, les idées en notes collées autour.",
    "journal_tv": "Bandeaux d'information, titres qui glissent, bande défilante.",
    "magazine": "Le visage en couverture de magazine, idées en accroches de une.",
    "stories": "Barres de story, idées en stickers (question, sondage, hashtag), profil à suivre à la fin.",
    "jeu_video": "Interface de jeu: niveau, barres PV/XP, dialogues façon RPG, quête, succès débloqués.",
    "podcast": "Le visage dans un cercle entouré d'une onde qui suit la voix, idées en chapitres d'épisode.",
    "documentaire": "Bandes cinéma, image étalonnée, cartons de chapitre, titres fins, générique de fin.",
    "bento": "L'écran en tuiles: le visage, les idées et les sous-titres se partagent une grille qui se réorganise.",
    "voyage": "Une carte géante: chaque idée est une étape sur la route, la caméra voyage de l'une à l'autre et révèle tout le chemin à la fin.",
}

# Gènes comptés dans l'empreinte (ce qui se VOIT d'une vidéo à l'autre).
FINGERPRINT_GENES = ("montage", "montage", "panel", "chrome", "transition", "captions", "head_font", "hue", "tone", "badge")
MIN_DISTANCE = 4          # gènes différents exigés vs chaque style récent
HISTORY_WINDOW = 8        # nombre de montages récents à ne pas imiter


def _style(sid: str, name: str, desc: str, *, palette: dict[str, str], head_font: str, caps: bool,
           panel: str, chrome: str, transition: str, captions: str, cap_y: float, badge: str,
           corner: str, text_fx: str, motion: tuple[float, float, float, float], mood: str, bpm: int,
           transpose: int, radius: int, grain: float, topics: Iterable[str], validated: bool = False,
           whoosh: str = "whoosh", impact: str = "impact", tone: str = "dark", montage: str = "plein_cadre") -> dict[str, Any]:
    stiff, damp, shake, push = motion
    return {
        "id": sid, "name": name, "description": desc, "validated": validated, "invented": False, "montage": montage,
        "palette": palette, "head_font": head_font, "caps": caps, "panel": panel, "chrome": chrome,
        "transition": transition, "captions": {"style": captions, "y": cap_y}, "badge": {"kind": badge, "corner": corner},
        "text_fx": text_fx, "motion": {"stiff": stiff, "damp": damp, "shake": shake, "push": push},
        "sound": {"mood": mood, "bpm": bpm, "transpose": transpose, "whoosh": whoosh, "impact": impact},
        "radius": radius, "grain": grain, "topics": list(topics), "tone": tone,
    }


def _pal(dark: str, dark2: str, light: str, light2: str, ink: str, accent: str, accent2: str,
         bad: str = "#E23A3A", good: str = "#2DBE6C") -> dict[str, str]:
    return {"dark": dark, "dark2": dark2, "light": light, "light2": light2, "ink": ink,
            "accent": accent, "accent2": accent2, "bad": bad, "good": good}


STYLES: dict[str, dict[str, Any]] = {s["id"]: s for s in [
    _style("canada_nuit", "Canada nuit & rouge",
           "Nuit profonde, rouge vif, cadenas et tampons. Révélations, secrets, finance.",
           palette=_pal("#070B18", "#16213E", "#F4F6FB", "#DDE3F0", "#0B1226", "#E63946", "#F1FAEE"),
           head_font="Anton", caps=True, panel="radial", chrome="clean", transition="whip", captions="box",
           cap_y=0.78, badge="card", corner="tl", text_fx="drop", motion=(16, 0.5, 1.2, 0.05),
           mood="hopeful", bpm=96, transpose=0, radius=28, grain=0.07,
           topics=["secret", "finance", "assurance", "canada", "révélation"], validated=True, impact="impact_big"),
    _style("dossier_confidentiel", "Dossier confidentiel",
           "Vert et crème, caviardage, tampon CONFIDENTIEL, fiches surlignées. Conseil, juridique, assurance.",
           palette=_pal("#12281E", "#1E3D2F", "#F6F1E3", "#E8DFC6", "#1B2A22", "#2F7D4F", "#F2C14E"),
           head_font="Anton", caps=True, panel="paper", chrome="dossier", transition="paper", captions="highlight",
           cap_y=0.76, badge="card", corner="tl", text_fx="mask", motion=(13, 0.62, 0.8, 0.03),
           mood="calm", bpm=90, transpose=-2, radius=14, grain=0.09,
           topics=["dossier", "juridique", "assurance", "conseil", "secret", "document"], validated=True,
           whoosh="whoosh", impact="stamp", tone="light"),
    _style("carte_postale", "Carte postale",
           "Crème vintage, marine, rouge et or, timbres et cachets. Voyage, immigration, études à l'étranger.",
           palette=_pal("#0A1628", "#1B2B45", "#FAF3E3", "#EFE3C8", "#1A1A2E", "#E63946", "#D4A843", good="#2D6A4F"),
           head_font="DMSerif", caps=False, panel="paper", chrome="postcard", transition="paper", captions="box",
           cap_y=0.79, badge="card", corner="tl", text_fx="scale", motion=(14, 0.55, 0.9, 0.035),
           mood="hopeful", bpm=92, transpose=2, radius=16, grain=0.08,
           topics=["voyage", "immigration", "visa", "canada", "étranger", "pays", "asile", "étudier"], validated=True,
           whoosh="whoosh", impact="stamp", tone="light"),
    _style("notification", "Notification",
           "Cartes façon notifications de téléphone, verre dépoli, bleu système. Relances, rappels, apps.",
           palette=_pal("#0B1020", "#1C2440", "#FFFFFF", "#EEF2F8", "#0F172A", "#2F7BFF", "#34C759"),
           head_font="Bebas", caps=True, panel="mesh", chrome="notification", transition="slide", captions="pill",
           cap_y=0.8, badge="pill", corner="tr", text_fx="mask", motion=(18, 0.62, 0.7, 0.03),
           mood="energetic", bpm=112, transpose=0, radius=34, grain=0.03,
           topics=["application", "rappel", "message", "téléphone", "digital", "notification"], validated=True,
           whoosh="whoosh", impact="blip"),
    _style("prestige_or", "Prestige or",
           "Bleu nuit et or, emblème 3D, rythme posé. Patrimoine, immobilier, santé, cabinets.",
           palette=_pal("#040914", "#0B1B3A", "#FFFFFF", "#F1F3F8", "#0B1B3A", "#F5B82E", "#FFE39A"),
           head_font="Anton", caps=True, panel="radial", chrome="glass", transition="zoom", captions="outline",
           cap_y=0.8, badge="bare", corner="tl", text_fx="drop", motion=(12, 0.62, 0.9, 0.04),
           mood="hopeful", bpm=88, transpose=-3, radius=32, grain=0.06,
           topics=["patrimoine", "retraite", "impôt", "investissement", "immobilier", "médecin", "richesse"],
           validated=True, impact="impact_big"),
    _style("neon_energie", "Néon énergie",
           "Violet profond, cyan électrique, glitch. Tech, e-commerce, jeunes, créateurs.",
           palette=_pal("#05020F", "#1A0B3D", "#F7F5FF", "#E4DEFF", "#140A33", "#22E3FF", "#FF3D8B", bad="#FF3D8B"),
           head_font="Bebas", caps=True, panel="mesh", chrome="neon", transition="zoom", captions="outline",
           cap_y=0.78, badge="round", corner="tr", text_fx="scale", motion=(19, 0.48, 1.4, 0.06),
           mood="energetic", bpm=124, transpose=3, radius=24, grain=0.05,
           topics=["tech", "ia", "application", "business en ligne", "argent en ligne", "tiktok", "crypto"],
           validated=True, whoosh="whoosh_deep", impact="impact"),
    _style("editorial_magazine", "Éditorial magazine",
           "Crème et encre, rouge vif, titres serif, mises en page de magazine. Formation, beauté, mode.",
           palette=_pal("#111111", "#262220", "#FBF8F2", "#F0E8DA", "#141414", "#E63B2E", "#141414", bad="#B8261C"),
           head_font="DMSerif", caps=False, panel="lines", chrome="magazine", transition="slide", captions="serif",
           cap_y=0.8, badge="bare", corner="tl", text_fx="mask", motion=(13, 0.66, 0.6, 0.025),
           mood="calm", bpm=84, transpose=1, radius=6, grain=0.1,
           topics=["formation", "beauté", "mode", "livre", "coaching", "éducation", "leçon"], validated=True, tone="light"),
    _style("table_dessin", "Table à dessin",
           "Plan bleu, traits de crayon, cotes et grille. Architecture, BTP, ingénierie, méthode.",
           palette=_pal("#0A2342", "#12386A", "#F4F8FF", "#DCE8F7", "#0A2342", "#FFB703", "#8ECAE6"),
           head_font="Bebas", caps=True, panel="blueprint", chrome="tape", transition="iris", captions="underline",
           cap_y=0.79, badge="card", corner="tl", text_fx="type", motion=(14, 0.6, 0.8, 0.035),
           mood="calm", bpm=94, transpose=-1, radius=10, grain=0.05,
           topics=["architecture", "plan", "construction", "maison", "ingénieur", "méthode", "étape"], validated=True,
           whoosh="whoosh", impact="thud"),
    _style("coup_raclette", "Coup de raclette",
           "Couleurs franches, raclette diagonale, autocollants. Services, nettoyage, commerce local.",
           palette=_pal("#0B019C", "#2A22C9", "#FFFFFF", "#EEF0FF", "#0B019C", "#D00A06", "#27D3F5", bad="#D00A06"),
           head_font="Anton", caps=True, panel="stripes", chrome="sticker", transition="squeegee", captions="bounce",
           cap_y=0.78, badge="card", corner="tl", text_fx="scale", motion=(17, 0.5, 1.1, 0.05),
           mood="energetic", bpm=116, transpose=2, radius=30, grain=0.04,
           topics=["nettoyage", "service", "entreprise", "maison", "hygiène", "commerce", "boutique"], validated=True,
           whoosh="whoosh", impact="impact"),
    _style("solaire", "Solaire",
           "Orange soleil et brun chaud, trame de points, énergie positive. Food, événementiel, beauté.",
           palette=_pal("#2A0F06", "#6B2A10", "#FFFAF3", "#FFE9CF", "#2A0F06", "#FF7A1A", "#FFD23F", bad="#D7263D"),
           head_font="Bebas", caps=True, panel="halftone", chrome="sticker", transition="zoom", captions="bounce",
           cap_y=0.78, badge="round", corner="tr", text_fx="scale", motion=(17, 0.46, 1.15, 0.05),
           mood="energetic", bpm=110, transpose=4, radius=40, grain=0.08,
           topics=["cuisine", "restaurant", "food", "événement", "beauté", "soleil", "vacances"]),
    _style("terminal_tech", "Terminal",
           "Noir profond, vert phosphore, lignes de balayage, machine à écrire. Tech, cybersécurité, data.",
           palette=_pal("#030805", "#0B1A10", "#EFFFF4", "#D5F5DF", "#04110A", "#3DFF8A", "#E6FF4F", bad="#FF4D4D"),
           head_font="Bebas", caps=True, panel="scan", chrome="terminal", transition="glitch", captions="ticker",
           cap_y=0.8, badge="pill", corner="tr", text_fx="type", motion=(20, 0.55, 1.0, 0.04),
           mood="energetic", bpm=120, transpose=-4, radius=12, grain=0.05,
           topics=["code", "tech", "données", "sécurité", "logiciel", "développeur", "ia", "automatisation"],
           whoosh="whoosh_deep", impact="blip"),
    _style("ticket_recu", "Ticket de caisse",
           "Papier thermique, encre noire, corail, bords dentelés. Prix, promos, budget, commerce.",
           palette=_pal("#1D1D1F", "#34343A", "#FFFFFF", "#F4F1EA", "#1D1D1F", "#FF5A4E", "#FFC857"),
           head_font="Anton", caps=True, panel="dots", chrome="ticket", transition="tear", captions="highlight",
           cap_y=0.79, badge="card", corner="tl", text_fx="type", motion=(15, 0.58, 0.9, 0.035),
           mood="hopeful", bpm=104, transpose=1, radius=8, grain=0.07,
           topics=["prix", "promo", "budget", "argent", "dépense", "économiser", "achat", "vente", "facture"],
           whoosh="whoosh", impact="stamp", tone="light"),
    _style("polaroid", "Album polaroid",
           "Photos instantanées, ruban adhésif, tons chauds de pellicule. Témoignages, famille, histoire.",
           palette=_pal("#1E1410", "#3B2A22", "#FFF8EE", "#F3E6D3", "#2B1D16", "#E07A5F", "#81B29A"),
           head_font="DMSerif", caps=False, panel="paper", chrome="polaroid", transition="shutter", captions="serif",
           cap_y=0.8, badge="round", corner="tl", text_fx="mask", motion=(12, 0.6, 0.7, 0.03),
           mood="calm", bpm=86, transpose=-2, radius=6, grain=0.12,
           topics=["histoire", "famille", "témoignage", "souvenir", "parcours", "enfant", "vie"], tone="light"),
    _style("suisse_minimal", "Minimal suisse",
           "Blanc pur, noir, un seul accent, grille stricte, volets. SaaS, consultants, B2B.",
           palette=_pal("#0A0A0A", "#1F1F1F", "#FFFFFF", "#F2F2F2", "#0A0A0A", "#2563EB", "#0A0A0A", bad="#E11D48"),
           head_font="Anton", caps=True, panel="grid", chrome="clean", transition="blinds", captions="underline",
           cap_y=0.8, badge="bare", corner="tr", text_fx="mask", motion=(18, 0.7, 0.5, 0.025),
           mood="calm", bpm=100, transpose=0, radius=0, grain=0.02,
           topics=["entreprise", "b2b", "consultant", "stratégie", "logiciel", "productivité", "business"], tone="light"),
    _style("story_gram", "Story", "Dégradé story, stickers blancs arrondis, rythme social. Créateurs, lifestyle, communauté.",
           palette=_pal("#1B0B2E", "#3B1466", "#FFFFFF", "#F6EEFF", "#262626", "#D62976", "#FEDA75", bad="#FF3B30"),
           head_font="Anton", caps=False, panel="mesh", chrome="sticker", transition="zoom", captions="pill",
           cap_y=0.8, badge="round", corner="tl", text_fx="scale", motion=(18, 0.5, 0.9, 0.04),
           mood="energetic", bpm=118, transpose=2, radius=40, grain=0.03,
           topics=["communauté", "abonnés", "instagram", "lifestyle", "créateur", "influence", "story"]),
    _style("arcade", "Arcade", "Écran de jeu, pixels, dialogues RPG, succès débloqués. Jeunes, défis, formation ludique.",
           palette=_pal("#0C0A28", "#231C66", "#F1F5FF", "#D8E0FF", "#0C0A28", "#34D399", "#FFD23F", bad="#FF2E63"),
           head_font="Bebas", caps=True, panel="halftone", chrome="neon", transition="glitch", captions="outline",
           cap_y=0.78, badge="round", corner="tr", text_fx="type", motion=(20, 0.45, 1.3, 0.05),
           mood="energetic", bpm=128, transpose=5, radius=16, grain=0.04,
           topics=["jeu", "défi", "niveau", "étape", "objectif", "challenge", "gagner"]),
    _style("studio_podcast", "Studio podcast", "Nuit chaude, orange micro, onde sonore vivante. Conseil, interviews, témoignages.",
           palette=_pal("#140D0A", "#2E1B12", "#FFF6EC", "#F3DFC9", "#140D0A", "#FF8A3D", "#FFC56B", bad="#E23A3A"),
           head_font="DMSerif", caps=False, panel="dots", chrome="glass", transition="iris", captions="serif",
           cap_y=0.81, badge="bare", corner="tl", text_fx="mask", motion=(12, 0.65, 0.5, 0.02),
           mood="calm", bpm=86, transpose=-3, radius=30, grain=0.06,
           topics=["conseil", "témoignage", "écoute", "parler", "discussion", "expérience", "histoire"]),
    _style("cinema_doc", "Cinéma", "Noir profond, crème et or, serif élégant, grain de pellicule. Histoires, causes, marques premium.",
           palette=_pal("#050505", "#1A1712", "#F4EFE6", "#E2D8C4", "#1A1712", "#C9A45C", "#F4EFE6", bad="#B3261E"),
           head_font="DMSerif", caps=False, panel="radial", chrome="clean", transition="shutter", captions="serif",
           cap_y=0.82, badge="bare", corner="tl", text_fx="mask", motion=(10, 0.7, 0.4, 0.02),
           mood="calm", bpm=78, transpose=-5, radius=0, grain=0.12,
           topics=["histoire", "parcours", "vie", "cause", "pays", "famille", "immigration", "espoir"]),
    _style("bento_grid", "Bento", "Tuiles arrondies, noir et citron vert, grille nette. Tech, produits, méthodes en étapes.",
           palette=_pal("#0B0C0F", "#1C1F26", "#F7F8FA", "#E6E9EF", "#0B0C0F", "#C6F432", "#7C5CFF", bad="#FF4D4D"),
           head_font="Anton", caps=True, panel="grid", chrome="clean", transition="blinds", captions="box",
           cap_y=0.78, badge="card", corner="tl", text_fx="drop", motion=(17, 0.6, 0.7, 0.03),
           mood="hopeful", bpm=104, transpose=1, radius=40, grain=0.02,
           topics=["produit", "méthode", "étape", "outil", "application", "tech", "fonctionnalité"]),
    _style("carnet_route", "Carnet de route", "Carte géante, route pointillée, étapes numérotées, caméra qui voyage. Parcours, voyage, méthodes pas à pas.",
           palette=_pal("#0E2A2F", "#17434A", "#FFF6E5", "#F2E3C4", "#10262A", "#FF7A45", "#FFD166", bad="#E63946"),
           head_font="Bebas", caps=True, panel="paper", chrome="ticket", transition="zoom", captions="highlight",
           cap_y=0.8, badge="card", corner="tl", text_fx="scale", motion=(15, 0.55, 0.9, 0.03),
           mood="hopeful", bpm=100, transpose=-1, radius=34, grain=0.05,
           topics=["voyage", "parcours", "étape", "chemin", "immigration", "destination", "méthode", "canada", "visa"]),
]}

# Mode de montage de chaque style écrit (le gène qui change la COMPOSITION de l'image)
for _sid, _m in {
    "canada_nuit": "zoom_rythme", "dossier_confidentiel": "fenetre", "carte_postale": "mur_polaroid",
    "notification": "telephone", "prestige_or": "presentateur", "neon_energie": "kinetique",
    "editorial_magazine": "magazine", "table_dessin": "ecran_scinde", "coup_raclette": "plein_cadre",
    "solaire": "kinetique", "terminal_tech": "journal_tv", "ticket_recu": "fenetre",
    "polaroid": "mur_polaroid", "suisse_minimal": "presentateur",
    "story_gram": "stories", "arcade": "jeu_video", "studio_podcast": "podcast", "cinema_doc": "documentaire",
    "bento_grid": "bento", "carnet_route": "voyage",
}.items():
    STYLES[_sid]["montage"] = _m

# --------------------------------------------------------------------------- #
# Affinité thématique
# --------------------------------------------------------------------------- #
_TOPIC_HINTS: list[tuple[str, str]] = [
    (r"canada|qu[ée]bec|visa|asile|immigr|[ée]tranger|voyage|pays|ambassade|passeport|[ée]tudier", "voyage"),
    (r"assurance|prot[èe]g|s[ée]curis|garanti", "assurance"),
    (r"imp[ôo]t|retraite|patrimoine|investi|placement|richesse|rente", "patrimoine"),
    (r"prix|promo|r[ée]duction|budget|d[ée]pens|[ée]conomis|acheter|achat|vendre|facture|payer", "prix"),
    (r"application|appli|t[ée]l[ée]phone|notification|message|whatsapp|rappel", "application"),
    (r"\bia\b|intelligence artificielle|logiciel|code|donn[ée]es|automatis|tech|digital|num[ée]rique", "tech"),
    (r"formation|cours|apprendre|le[çc]on|[ée]tudiant|coaching|m[ée]thode", "formation"),
    (r"maison|plan|construi|architect|chantier|terrain|immobili", "architecture"),
    (r"nettoy|hygi[èe]ne|entretien|m[ée]nage|d[ée]sinfect", "nettoyage"),
    (r"cuisine|restaurant|manger|plat|recette|food|g[âa]teau", "cuisine"),
    (r"beaut[ée]|cheveux|peau|maquillage|mode|v[êe]tement", "beauté"),
    (r"secret|personne ne|on ne vous dit|v[ée]rit[ée]|r[ée]v[ée]l", "secret"),
    (r"famille|enfant|parents|histoire|souvenir|t[ée]moign|parcours", "famille"),
    (r"entreprise|client|business|strat[ée]gie|b2b|consultant|productivit", "entreprise"),
]

_MOTIFS: list[tuple[str, str]] = [
    (r"canada|qu[ée]bec|[ée]rable", "maple"),
    (r"argent|prix|payer|imp[ôo]t|[ée]conomis|francs?|cfa|budget", "coin"),
    (r"sant[ée]|m[ée]decin|h[ôo]pital|soin", "heart"),
    (r"maison|immobili|terrain|construi", "home"),
    (r"voyage|avion|pays|[ée]tranger|visa|asile", "plane"),
    (r"\bia\b|tech|logiciel|code|digital", "bolt"),
    (r"formation|apprendre|cours|[ée]cole", "graduation"),
]


def topics_of(text: str) -> list[str]:
    low = (text or "").lower()
    return [tag for pat, tag in _TOPIC_HINTS if re.search(pat, low)]


def motif_of(text: str) -> str:
    low = (text or "").lower()
    return next((m for pat, m in _MOTIFS if re.search(pat, low)), "sparkle")


def _affinity(style: dict[str, Any], topics: list[str]) -> float:
    if not topics:
        return 0.0
    st = " ".join(style.get("topics", [])).lower()
    return sum(1.0 for tp in topics if tp in st or any(tp[:5] in x for x in style.get("topics", [])))


# --------------------------------------------------------------------------- #
# Couleurs
# --------------------------------------------------------------------------- #
def _hex(rgb: tuple[float, float, float]) -> str:
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(c * 255))) for c in rgb)


def _hls(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(r, g, b)


def _from_hls(h: float, l: float, s: float) -> str:
    return _hex(colorsys.hls_to_rgb(h % 1.0, max(0.0, min(1.0, l)), max(0.0, min(1.0, s))))


def luma(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def hue_bucket(hex_color: str) -> int:
    """Teinte ramenée à 12 secteurs (les gris vont dans le secteur -1)."""
    h, l, s = _hls(hex_color)
    return -1 if s < 0.18 else int(h * 12) % 12


def harmonic_palette(rng: random.Random, tone: str) -> dict[str, str]:
    """Palette générée: une teinte de base + un accent (complémentaire,
    triadique ou analogue), contrastes garantis pour la lisibilité."""
    base_h = rng.random()
    scheme = rng.choice(["complement", "triad", "split", "analog"])
    off = {"complement": 0.5, "triad": 1 / 3, "split": 5 / 12, "analog": 1 / 12 * rng.choice([2, 3])}[scheme]
    acc_h = (base_h + off) % 1.0
    acc2_h = (acc_h + rng.choice([1 / 12, -1 / 12, 1 / 6])) % 1.0
    dark = _from_hls(base_h, rng.uniform(0.06, 0.11), rng.uniform(0.35, 0.7))
    dark2 = _from_hls(base_h, rng.uniform(0.16, 0.24), rng.uniform(0.35, 0.65))
    light = _from_hls(base_h, rng.uniform(0.95, 0.98), rng.uniform(0.25, 0.6))
    light2 = _from_hls(base_h, rng.uniform(0.86, 0.91), rng.uniform(0.2, 0.45))
    ink = _from_hls(base_h, rng.uniform(0.08, 0.14), rng.uniform(0.3, 0.6))
    accent = _from_hls(acc_h, rng.uniform(0.5, 0.6), rng.uniform(0.75, 0.95))
    accent2 = _from_hls(acc2_h, rng.uniform(0.55, 0.7), rng.uniform(0.6, 0.9))
    bad_h = 0.99 if abs(acc_h - 0.99) > 0.08 else 0.03
    return {"dark": dark, "dark2": dark2, "light": light, "light2": light2, "ink": ink, "accent": accent,
            "accent2": accent2, "bad": _from_hls(bad_h, 0.52, 0.78), "good": _from_hls(0.40, 0.42, 0.62)}


def _shade(hex_color: str, factor: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    if factor <= 1:
        r, g, b = (int(c * factor) for c in (r, g, b))
    else:
        f = factor - 1
        r, g, b = (int(c + (255 - c) * f) for c in (r, g, b))
    return "#%02x%02x%02x" % (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


# --------------------------------------------------------------------------- #
# Empreinte, distance, invention, mutation
# --------------------------------------------------------------------------- #
def fingerprint(style: dict[str, Any]) -> dict[str, Any]:
    return {"id": style.get("id"), "montage": style.get("montage", "plein_cadre"), "panel": style.get("panel"), "chrome": style.get("chrome"),
            "transition": style.get("transition"), "captions": (style.get("captions") or {}).get("style"),
            "head_font": style.get("head_font"), "hue": hue_bucket((style.get("palette") or {}).get("accent", "#888888")),
            "tone": style.get("tone", "dark"), "badge": (style.get("badge") or {}).get("kind")}


def distance(a: dict[str, Any], b: dict[str, Any]) -> int:
    """Nombre de gènes visibles qui diffèrent (0 = même allure)."""
    fa = a if "hue" in a and "palette" not in a else fingerprint(a)
    fb = b if "hue" in b and "palette" not in b else fingerprint(b)
    d = 0
    for g in FINGERPRINT_GENES:
        if g == "hue":
            ha, hb = fa.get("hue"), fb.get("hue")
            if ha is None or hb is None or ha == -1 or hb == -1:
                d += int(ha != hb)
            else:
                d += int(min((ha - hb) % 12, (hb - ha) % 12) > 1)
        else:
            d += int(fa.get(g) != fb.get(g))
    return d


def _seed_int(seed: Any) -> int:
    return int(hashlib.sha1(str(seed).encode()).hexdigest()[:12], 16)


def invent_style(seed: Any, history: Optional[list[dict[str, Any]]] = None, topics: Optional[list[str]] = None,
                 tries: int = 200) -> dict[str, Any]:
    """Un style NEUF: gènes tirés au sort (seedés) + palette harmonique, qui
    diffère d'au moins MIN_DISTANCE gènes de chaque style récent."""
    history = history or []
    rng = random.Random(_seed_int(seed))
    best, best_d = None, -1
    for _ in range(tries):
        tone = rng.choice(["dark", "dark", "light"])
        chrome = rng.choice(CHROMES)
        panel = rng.choice(PANELS)
        # cohérences de direction artistique (pas de terminal en serif, etc.)
        head = rng.choice(HEAD_FONTS)
        if chrome in ("terminal", "neon"):
            head = rng.choice(["Bebas", "Anton"])
        if chrome in ("magazine", "postcard", "polaroid") and rng.random() < 0.7:
            head = "DMSerif"
        caps = head != "DMSerif"
        cap = rng.choice(CAPTIONS)
        if cap == "serif" and head != "DMSerif":
            cap = rng.choice(["box", "highlight", "outline"])
        mood = rng.choice(MOODS)
        pal = harmonic_palette(rng, tone)
        st = _style(
            "invente_" + hashlib.sha1(str((seed, _)).encode()).hexdigest()[:6],
            _invented_name(rng, chrome, panel), "Style inventé pour cette vidéo : combinaison de gènes jamais utilisée récemment.",
            palette=pal, head_font=head, caps=caps, panel=panel, chrome=chrome, transition=rng.choice(TRANSITIONS),
            captions=cap, cap_y=round(rng.uniform(0.74, 0.81), 3), badge=rng.choice(BADGES), corner=rng.choice(["tl", "tr"]),
            text_fx=rng.choice(TEXT_FX),
            motion=(round(rng.uniform(12, 20), 1), round(rng.uniform(0.45, 0.7), 2), round(rng.uniform(0.5, 1.4), 2), round(rng.uniform(0.02, 0.06), 3)),
            mood=mood, bpm=rng.choice([84, 90, 96, 104, 110, 118, 124]), transpose=rng.randint(-5, 5),
            radius=rng.choice([0, 8, 14, 22, 30, 40]), grain=round(rng.uniform(0.02, 0.11), 3),
            topics=topics or [], whoosh=rng.choice(["whoosh", "whoosh_deep"]),
            impact=rng.choice(["impact", "impact_big", "stamp", "thud"]), tone=tone,
            montage=rng.choice([m for m in MONTAGES if m not in [h.get("montage") for h in history[:2]]] or MONTAGES))
        st["invented"] = True
        d = min([distance(st, h) for h in history] or [len(FINGERPRINT_GENES)])
        if d > best_d:
            best, best_d = st, d
        if d >= MIN_DISTANCE + 1:
            break
    assert best is not None
    return best


_NAME_A = {"postcard": "Courrier", "dossier": "Archive", "notification": "Signal", "glass": "Cristal", "sticker": "Pop",
           "ticket": "Reçu", "polaroid": "Instantané", "terminal": "Console", "magazine": "Une", "neon": "Néon",
           "clean": "Épure", "tape": "Atelier"}
_NAME_B = {"radial": "nocturne", "paper": "papier", "grid": "quadrillé", "dots": "pointillé", "lines": "ligné",
           "halftone": "tramé", "mesh": "aurore", "blueprint": "calque", "scan": "balayé", "stripes": "rayé"}


def _invented_name(rng: random.Random, chrome: str, panel: str) -> str:
    return f"{_NAME_A.get(chrome, 'Studio')} {_NAME_B.get(panel, 'libre')}"


def mutate(style: dict[str, Any], seed: Any, strength: float = 0.25) -> dict[str, Any]:
    """Variation légère et seedée: même famille, jamais la même image deux fois
    (teinte d'accent décalée de quelques degrés, position des sous-titres,
    tempo, tonalité musicale, rayon des cartes)."""
    st = deepcopy(style)
    rng = random.Random(_seed_int(("mut", seed)))
    p = st["palette"]
    h, l, s = _hls(p["accent"])
    p["accent"] = _from_hls(h + rng.uniform(-0.025, 0.025) * strength * 4, l + rng.uniform(-0.03, 0.03), s)
    st["captions"]["y"] = round(min(0.82, max(0.72, st["captions"]["y"] + rng.uniform(-0.02, 0.02))), 3)
    st["sound"]["bpm"] = int(st["sound"]["bpm"] + rng.choice([-6, -3, 0, 3, 6]))
    st["sound"]["transpose"] = int(st["sound"]["transpose"] + rng.choice([-2, 0, 0, 2]))
    st["radius"] = max(0, st["radius"] + rng.choice([-4, 0, 0, 4]))
    st["variant"] = rng.randint(0, 9999)  # graine visuelle (positions des motifs, rotations)
    return st


def with_brand(style: dict[str, Any], brand_color: Optional[str]) -> dict[str, Any]:
    st = deepcopy(style)
    if brand_color and re.fullmatch(r"#?[0-9A-Fa-f]{6}", brand_color or ""):
        st["palette"]["accent"] = "#" + brand_color.lstrip("#").upper()
    return st


# --------------------------------------------------------------------------- #
# Choix du style d'une vidéo
# --------------------------------------------------------------------------- #
def choose_style(transcript: str, *, requested: Optional[str] = None, history: Optional[list[dict[str, Any]]] = None,
                 seed: Any = "", brand_color: Optional[str] = None) -> dict[str, Any]:
    """Style final (résolu) d'une vidéo.

    requested: id d'un style écrit, « auto » (défaut: choisi selon le sujet et
    l'historique) ou « invent » (toujours un style neuf).
    history: empreintes des derniers montages de l'utilisateur (plus récent d'abord).
    """
    long_history = list(history or [])[:30]
    history = long_history[:HISTORY_WINDOW]
    topics = topics_of(transcript)
    reason = ""
    if requested and requested in STYLES:
        base, reason = STYLES[requested], "choisi par l'utilisateur"
    elif requested == "invent":
        base, reason = invent_style(seed, history, topics), "style inventé à la demande"
    else:
        rng = random.Random(_seed_int(("pick", seed)))
        long_ids = [h.get("id") for h in (long_history or history)]
        recent_ids = [h.get("id") for h in history]
        scored = []
        for st in STYLES.values():
            if st["id"] in recent_ids[:6]:
                continue  # jamais le même style que les 6 derniers montages
            if st.get("montage") in [h.get("montage") for h in history[:2]]:
                continue  # ni la même grammaire de montage que les 2 derniers
            dmin = min([distance(st, h) for h in history] or [len(FINGERPRINT_GENES)])
            if dmin < MIN_DISTANCE - 1:
                continue
            uses = long_ids.count(st["id"])
            score = (2.2 * _affinity(st, topics) + 0.35 * dmin + (0.4 if st.get("validated") else 0)
                     - 0.9 * uses + rng.random() * 1.1)
            scored.append((score, st))
        # un style neuf entre en concurrence dès que l'utilisateur a quelques montages
        invent_score = (3.0 + rng.random()) if len(long_ids) >= 4 else -1.0
        scored.sort(key=lambda x: -x[0])
        if scored and scored[0][0] >= invent_score:
            base, reason = scored[0][1], "adapté au sujet" + (" et différent des derniers montages" if history else "")
        else:
            base, reason = invent_style(seed, history, topics), "style inventé: combinaison jamais utilisée récemment"
    st = mutate(base, seed)
    st = with_brand(st, brand_color)
    st["motif"] = motif_of(transcript)
    st["topics_detected"] = topics
    st["reason"] = reason
    st["fingerprint"] = fingerprint(st)
    return st


def resolve_colors(style: dict[str, Any]) -> dict[str, str]:
    """Couleurs au format des scènes du moteur web (clé par clé)."""
    p = style["palette"]
    acc = p["accent"]
    dark, dark2 = p["dark"], p["dark2"]
    return {
        "dark0": _shade(dark, 0.6), "dark1": dark, "dark2": dark2,
        "light1": p["light"], "light2": _shade(p["light2"], 1.02), "light3": p["light2"],
        "alarm1": _shade(p["bad"], 0.35), "alarm2": _shade(p["bad"], 0.14),
        "ink": p["ink"], "inkSoft": _shade(p["ink"], 1.45), "paper": p["light"], "paperSoft": _shade(p["light2"], 0.85),
        "accent": acc, "accent2": p["accent2"], "bad": p["bad"], "good": p["good"], "onDark": p["light"],
        "accentLight": _shade(acc, 1.45), "accentDark": _shade(acc, 0.78), "accentDeep": _shade(acc, 0.62),
        "accentRGB": ",".join(str(int(acc.lstrip("#")[i:i + 2], 16)) for i in (0, 2, 4)),
        "onAccent": p["ink"] if luma(acc) > 0.55 else "#FFFFFF",
    }


def public_styles() -> list[dict[str, Any]]:
    """Catalogue pour l'interface (aperçus dessinés côté client à partir des gènes)."""
    out = []
    for st in STYLES.values():
        out.append({"id": st["id"], "name": st["name"], "description": st["description"], "validated": st["validated"],
                    "montage": st["montage"], "montage_name": MONTAGE_NAMES[st["montage"]], "montage_desc": MONTAGE_DESC[st["montage"]],
                    "palette": st["palette"], "head_font": st["head_font"], "chrome": st["chrome"], "panel": st["panel"],
                    "transition": st["transition"], "captions": st["captions"]["style"], "tone": st["tone"],
                    "mood": st["sound"]["mood"]})
    return out
