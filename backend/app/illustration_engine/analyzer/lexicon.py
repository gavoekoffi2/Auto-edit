"""Bilingual (FR/EN) marker vocabulary used by the analyzer.

Kept apart from the detection logic so the vocabulary can grow without
touching the scoring, and so tests can assert on it directly.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Tuple


def fold(text: str) -> str:
    """Lowercase and strip accents — matching form, never display form."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFD", str(text).lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


# --------------------------------------------------------------------------- #
# ordinal / sequence markers -> steps & process
# --------------------------------------------------------------------------- #
ORDINALS: Dict[str, int] = {
    "premierement": 1, "premier": 1, "premiere": 1, "d'abord": 1, "dabord": 1,
    "tout d'abord": 1, "pour commencer": 1, "en premier": 1,
    "first": 1, "firstly": 1, "to start": 1, "step one": 1,
    "deuxiemement": 2, "deuxieme": 2, "second": 2, "seconde": 2, "secondly": 2,
    "en deuxieme": 2, "step two": 2,
    "troisiemement": 3, "troisieme": 3, "third": 3, "thirdly": 3, "step three": 3,
    "quatriemement": 4, "quatrieme": 4, "fourth": 4,
    "cinquiemement": 5, "cinquieme": 5, "fifth": 5,
}

SEQUENCE_MARKERS: Tuple[str, ...] = (
    "ensuite", "puis", "apres ca", "apres cela", "par la suite", "enfin",
    "finalement", "pour finir", "en dernier", "et pour terminer",
    "then", "next", "after that", "finally", "lastly", "at the end",
)

STEP_WORDS: Tuple[str, ...] = ("etape", "phase", "step", "stage")

# --------------------------------------------------------------------------- #
# quantity announcements -> lists
# --------------------------------------------------------------------------- #
NUMBER_WORDS: Dict[str, int] = {
    "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7,
    "two": 2, "three": 3, "four": 4, "five": 5, "six_en": 6, "seven": 7,
}

# "il y a trois choses", "les 4 piliers", "there are three things"
COUNT_NOUNS: Tuple[str, ...] = (
    "chose", "choses", "point", "points", "pilier", "piliers", "raison",
    "raisons", "element", "elements", "cle", "cles", "regle", "regles",
    "erreur", "erreurs", "facon", "facons", "maniere", "manieres",
    "critere", "criteres", "avantage", "avantages", "type", "types",
    "categorie", "categories", "etape", "etapes", "conseil", "conseils",
    "astuce", "astuces", "secret", "secrets", "principe", "principes",
    "habitude", "habitudes", "qualite", "qualites", "competence",
    "competences", "outil", "outils", "methode", "methodes", "technique",
    "techniques", "strategie", "strategies", "levier", "leviers", "axe",
    "axes", "option", "options", "choix", "niveau", "niveaux", "priorite",
    "priorites", "obstacle", "obstacles", "defi", "defis", "ingredient",
    "ingredients", "condition", "conditions", "benefice", "benefices",
    "thing", "things", "point", "pillar", "pillars", "reason", "reasons",
    "key", "keys", "rule", "rules", "mistake", "mistakes", "way", "ways",
    "step", "steps", "tip", "tips", "secret", "secrets", "habit", "habits",
    "skill", "skills", "tool", "tools", "method", "methods", "option",
    "options", "level", "levels", "priority", "priorities",
)

LIST_INTROS: Tuple[str, ...] = (
    "il y a", "il existe", "voici", "vous avez", "on a", "ce sont",
    "les trois", "les quatre", "les deux", "il faut maitriser",
    "there are", "here are", "you have", "you need", "these are",
)

# --------------------------------------------------------------------------- #
# comparison / opposition
# --------------------------------------------------------------------------- #
COMPARISON_PAIRS: Tuple[Tuple[str, str], ...] = (
    ("avant", "maintenant"), ("avant", "aujourd'hui"), ("avant", "apres"),
    ("hier", "aujourd'hui"), ("autrefois", "desormais"),
    ("before", "now"), ("before", "after"), ("then", "today"),
    ("old way", "new way"),
)

COMPARISON_MARKERS: Tuple[str, ...] = (
    "au lieu de", "plutot que", "alors que", "tandis que", "contrairement a",
    "a l'inverse", "d'un cote", "de l'autre cote", "par contre",
    "la difference", "versus", " vs ", "mieux que", "pire que",
    "la plupart des gens", "les debutants", "les pros",
    "instead of", "rather than", "whereas", "while", "on the other hand",
    "the difference", "better than", "worse than", "most people",
)

# --------------------------------------------------------------------------- #
# cause / consequence
# --------------------------------------------------------------------------- #
CAUSE_MARKERS: Tuple[str, ...] = (
    "parce que", "car ", "puisque", "etant donne", "grace a", "a cause de",
    "because", "since ", "thanks to", "due to",
)
EFFECT_MARKERS: Tuple[str, ...] = (
    "donc", "du coup", "resultat", "c'est pour ca", "c'est pourquoi",
    "par consequent", "ce qui fait que", "alors ", "ainsi ",
    "so ", "therefore", "as a result", "that's why", "which means",
)

# --------------------------------------------------------------------------- #
# problem / solution
# --------------------------------------------------------------------------- #
PROBLEM_MARKERS: Tuple[str, ...] = (
    "le probleme", "un probleme", "l'erreur", "une erreur", "le piege",
    "ce qui bloque", "ca ne marche pas", "echouent", "echoue", "difficulte",
    "the problem", "the mistake", "the trap", "fails", "doesn't work",
)
SOLUTION_MARKERS: Tuple[str, ...] = (
    "la solution", "il suffit de", "ce qu'il faut faire", "la bonne methode",
    "voici comment", "pour regler", "pour resoudre", "la reponse",
    "the solution", "the fix", "here's how", "what you should do", "the answer",
)

# --------------------------------------------------------------------------- #
# definition
# --------------------------------------------------------------------------- #
DEFINITION_MARKERS: Tuple[str, ...] = (
    "c'est-a-dire", "ca veut dire", "c'est quoi", "qu'est-ce que",
    "par definition", "on appelle ca", "ce qu'on appelle", "autrement dit",
    "signifie", "consiste a", "se definit",
    "which means", "that means", "is defined as", "in other words",
    "what we call", "stands for",
)
# Accent-aware: French definitions are full of "système", "modèle", "données".
DEFINITION_COPULA = re.compile(
    r"([\w\u00c0-\u024f'’ \-]{3,40}?)\s*,?\s*"
    r"(?:c'est|c’est|ce sont|est un|est une|est le|est la|sont des|sont les|"
    r"is a|is an|is the|are the)\s+"
    r"([\w\u00c0-\u024f'’ \-]{3,60})", re.IGNORECASE | re.UNICODE)

# --------------------------------------------------------------------------- #
# process / architecture
# --------------------------------------------------------------------------- #
FLOW_VERBS: Tuple[str, ...] = (
    "envoie", "envoyer", "recoit", "recevoir", "traite", "traiter",
    "genere", "generer", "transforme", "transmet", "passe par", "arrive",
    "declenche", "valide", "stocke", "renvoie", "retourne", "circule",
    "sends", "receives", "processes", "generates", "transforms", "goes through",
    "triggers", "validates", "stores", "returns", "flows",
)
ARCHITECTURE_NOUNS: Tuple[str, ...] = (
    "serveur", "serveurs", "base de donnees", "api", "backend", "frontend",
    "client", "module", "modules", "service", "services", "couche", "couches",
    "composant", "composants", "systeme", "architecture", "infrastructure",
    "pipeline", "workflow", "tunnel", "entrepot", "plateforme",
    "server", "database", "layer", "layers", "component", "components",
    "system", "warehouse", "platform",
)

# --------------------------------------------------------------------------- #
# emphasis -> importance
# --------------------------------------------------------------------------- #
EMPHASIS_MARKERS: Tuple[str, ...] = (
    "important", "essentiel", "crucial", "fondamental", "retenez",
    "le plus important", "attention", "surtout", "le secret", "la cle",
    "ne faites jamais", "il faut absolument", "souvenez-vous", "notez bien",
    "la verite", "ce que personne ne dit", "le point cle",
    "important", "essential", "crucial", "remember", "the key", "the secret",
    "never", "always", "the truth", "pay attention",
)

# Discourse filler that adds no visual value.
LOW_VALUE_MARKERS: Tuple[str, ...] = (
    "bonjour", "salut", "bienvenue", "abonnez-vous", "likez", "commentez",
    "on se retrouve", "dans cette video", "comme je disais", "bref",
    "voila", "euh", "hum", "subscribe", "like and", "welcome back",
)

# --------------------------------------------------------------------------- #
# numbers
# --------------------------------------------------------------------------- #
NUMBER_RE = re.compile(
    r"(\d[\d\s.,]{0,12}\d|\d)\s*"
    r"(%|pour ?cent|percent|euros?|€|\$|dollars?|fcfa|cfa|k\b|"
    r"millions?|milliards?|millions|billion|fois|times|x\b)?",
    re.IGNORECASE)

_MULTIPLIERS = {
    "k": 1_000.0, "million": 1e6, "millions": 1e6, "milliard": 1e9,
    "milliards": 1e9, "billion": 1e9,
}


def parse_numbers(text: str) -> List[Tuple[str, float]]:
    """Extract (display, value) pairs. Skips bare small ordinals like "1.".

    Only numbers that carry a unit, or are large enough to be a real figure,
    survive — "trois choses" is a list announcement, not a statistic.
    """
    out: List[Tuple[str, float]] = []
    for match in NUMBER_RE.finditer(text or ""):
        raw_num, unit = match.group(1), (match.group(2) or "").strip().lower()
        cleaned = raw_num.replace(" ", "").replace(",", ".")
        # A dot used as a thousands separator ("1.500") must not become 1.5.
        if cleaned.count(".") > 1:
            cleaned = cleaned.replace(".", "")
        try:
            value = float(cleaned)
        except ValueError:
            continue
        mult = _MULTIPLIERS.get(unit)
        if mult:
            value *= mult
        elif not unit and value < 10:
            continue          # "3 choses" — handled by the list detector
        display = match.group(0).strip()
        out.append((display, value))
    return out


# A sentence that announces a count AND then enumerates. Separators are what
# distinguish "trois habitudes : la répétition, la pratique et le repos" from
# "j'ai trois enfants".
_ENUMERATES = re.compile(r":|,[^,]+\bet\b|\bet\b[^,]+,|;")

_COUNT_TOKENS = {**NUMBER_WORDS, **{str(n): n for n in range(2, 8)}}


def count_announcement(folded: str) -> int:
    """"il y a trois choses" / "les 4 piliers" / "trois habitudes :" -> the count.

    Two passes: a curated noun list first (precise), then a generic rule for
    any plural noun when the sentence goes on to enumerate. The generic pass
    is what stops the detector from silently missing every noun nobody thought
    to add to the list.
    """
    for word, n in NUMBER_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", folded):
            for noun in COUNT_NOUNS:
                if re.search(rf"\b{re.escape(word)}\s+(?:\w+\s+){{0,2}}"
                             rf"{re.escape(noun)}\b", folded):
                    return n
    match = re.search(r"\b([2-7])\s+(?:\w+\s+){0,2}(" +
                      "|".join(re.escape(n) for n in COUNT_NOUNS) + r")\b", folded)
    if match:
        return int(match.group(1))

    for token, n in _COUNT_TOKENS.items():
        generic = re.search(rf"\b{re.escape(token)}\s+(?:\w+\s+){{0,2}}"
                            rf"(\w{{4,}}s)\b", folded)
        if generic and _ENUMERATES.search(folded[generic.end():]):
            return n
    return 0


def has_any(folded: str, markers) -> bool:
    return any(m in folded for m in markers)


def first_hit(folded: str, markers) -> str:
    for m in markers:
        if m in folded:
            return m.strip()
    return ""
