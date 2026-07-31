"""PROFILS du moteur de collage — une seule mécanique, trois directions.

Le moteur `collage_assemble` (analyse du sens → concept → pièces → assemblage)
est le même pour les trois moteurs produit. Ce qui change tient dans un profil:

  ``editorial``    Collage Premium historique. Métaphores abstraites de
                   discours business, images IA autorisées.
  ``ugc_product``  Présentation de produit (UGC). Le collage papier illustre ce
                   que la personne dit de SON produit: prix, livraison,
                   ingrédients, avant/après, avis… AUCUN appel d'image payante:
                   toutes les pièces sont découpées en vectoriel
                   (`collage_shapes`).
  ``ugc_motion``   Identique à ``ugc_product``, mais le montage garde en plus
                   les scènes de motion design du moteur Auto Edit.

Un profil est une DONNÉE, pas une branche de code: ajouter une quatrième
direction ne demande aucune modification du pipeline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .collage_types import Emotion

#: (métaphore, objets dans l'ordre d'apparition, émotion par défaut)
MetaphorEntry = tuple[str, list[str], Emotion]


@dataclass(frozen=True)
class CollageProfile:
    """Direction artistique + politique de coût d'un moteur de collage."""

    id: str
    label: str
    #: False = aucune image générée par API, jamais. Les pièces sont dessinées.
    allow_ai_images: bool
    #: Le planner TEXTE (un seul appel, modèle bon marché) est ce qui rend le
    #: collage pertinent avec le discours. Séparé de l'image: un moteur peut
    #: comprendre la phrase sans payer la moindre génération visuelle.
    allow_planner_llm: bool
    #: Consigne envoyée au planner texte (direction artistique du profil).
    llm_instruction: str
    #: Bibliothèque de repli, sans aucun appel réseau.
    metaphor_library: dict[str, MetaphorEntry]
    default_metaphor: MetaphorEntry
    #: Détecteur d'intention utilisé pour choisir dans la bibliothèque.
    intent_rules: list[tuple[str, str]] = field(default_factory=list)
    #: Part maximale des beats B-roll routés vers le collage (1.0 = tous).
    share_of_broll: float = 0.5
    #: Plafond de scènes de collage par vidéo.
    max_scenes: int = 4

    def intent_for(self, text: str) -> Optional[str]:
        """Intention dominante du texte, ou None (repli sur les icônes moteur)."""
        for intent, pattern in _compiled(self):
            if pattern.search(text or ""):
                return intent
        return None

    def metaphor_for(self, key: Optional[str]) -> MetaphorEntry:
        return self.metaphor_library.get(key or "", self.default_metaphor)


_RULE_CACHE: dict[str, list[tuple[str, re.Pattern[str]]]] = {}


def _compiled(profile: CollageProfile) -> list[tuple[str, re.Pattern[str]]]:
    cached = _RULE_CACHE.get(profile.id)
    if cached is None:
        cached = [(intent, re.compile(pattern, re.I))
                  for intent, pattern in profile.intent_rules]
        _RULE_CACHE[profile.id] = cached
    return cached


# --------------------------------------------------------------------------- #
# Profil 1 — éditorial (Collage Premium historique)
# --------------------------------------------------------------------------- #
_EDITORIAL_INSTRUCTION = (
    "Tu es directeur artistique d'un studio de motion design éditorial. "
    "Pour CHAQUE extrait parlé ci-dessous, conçois UNE scène de collage papier "
    "qui raconte visuellement l'idée (jamais une illustration littérale de mots).\n"
    "Contraintes strictes:\n"
    "- 3 à 6 objets MAXIMUM, tous concrets et découpables en papier;\n"
    "- aucun objet ne doit être du texte, un logo, un chiffre ou une lettre;\n"
    "- la métaphore doit être compréhensible en 2 secondes, sans légende;\n"
    "- l'ordre des objets = ordre d'apparition qui construit le sens "
    "(le sujet d'abord, la conséquence en dernier);\n"
    "- couleurs = aplats de papier saturés, une couleur de fond + 2 ou 3 accents.\n"
    "Réponds UNIQUEMENT par un tableau JSON de {n} objets, dans le MÊME ORDRE, "
    "chaque objet ayant exactement ces clés:\n"
    '{"meaning": str, "emotion": "urgency|hope|warning|pride|curiosity|trust|'
    'frustration|neutral", "metaphor": str, "objects": [{"name": str, '
    '"order": int, "note": str}], "background_color": "#RRGGBB", '
    '"palette": ["#RRGGBB", ...], "label": str}\n'
    "`label` = UN mot-clé en majuscules (max 12 caractères).\n\n"
    "Extraits:\n{items}"
)

#: Bibliothèque historique, indexée sur les icônes déjà détectées par le moteur
#: (`autoedit_engine.content.icon_for_text`) — aucune règle dupliquée.
EDITORIAL_LIBRARY: dict[str, MetaphorEntry] = {
    "money": ("value flowing from one hand to another",
              ["open hand", "folded banknote", "coin stack", "arrow"], Emotion.TRUST),
    "growth": ("a small seed becoming a rising staircase",
               ["seed", "sprout", "rising bar", "upward arrow"], Emotion.HOPE),
    "transfer": ("a bridge carrying a parcel across a gap",
                 ["hand with phone", "bridge", "parcel", "receiving hand"], Emotion.TRUST),
    "crypto": ("a locked block joining an endless chain",
               ["chain link", "padlock", "coin", "network node"], Emotion.CURIOSITY),
    "bank": ("two currencies balancing on a scale",
             ["balance scale", "banknote", "coin", "arrow"], Emotion.TRUST),
    "card": ("a card unlocking a closed shutter",
             ["bank card", "shutter", "key", "open door"], Emotion.TRUST),
    "check": ("a key finally matching its lock",
              ["key", "padlock", "check mark", "shield"], Emotion.TRUST),
    "warning": ("a crack spreading across a smooth surface",
                ["cracked plate", "warning triangle", "falling piece"], Emotion.WARNING),
    "phone": ("a hand holding a window onto the world",
              ["hand", "phone screen", "signal waves", "small globe"], Emotion.CURIOSITY),
    "people": ("separate silhouettes converging into one circle",
               ["silhouette", "second silhouette", "circle", "handshake"], Emotion.PRIDE),
    "cart": ("a shelf emptying into a customer's basket",
             ["shelf", "product box", "basket", "arrow"], Emotion.HOPE),
    "idea": ("a struck match lighting a dark room",
             ["match", "flame", "light beam", "open book"], Emotion.CURIOSITY),
    "target": ("an arrow finding the exact centre",
               ["bow", "arrow", "target rings", "flag"], Emotion.PRIDE),
    "gear": ("loose gears clicking into one mechanism",
             ["gear", "second gear", "belt", "lever"], Emotion.NEUTRAL),
    "book": ("a closed book opening into a staircase",
             ["closed book", "open book", "staircase", "graduation cap"], Emotion.HOPE),
    "megaphone": ("one voice multiplying into many ears",
                  ["megaphone", "sound waves", "ear", "crowd silhouette"], Emotion.URGENCY),
    "shield": ("a shield absorbing an incoming arrow",
               ["shield", "incoming arrow", "padlock", "safe hands"], Emotion.TRUST),
    "clock": ("sand running out of an hourglass",
              ["hourglass", "falling sand", "clock face", "hand"], Emotion.URGENCY),
    "rocket": ("a rocket leaving its launch pad",
               ["rocket", "launch pad", "smoke plume", "star"], Emotion.HOPE),
    "map": ("a pin dropping onto a folded map",
            ["folded map", "location pin", "route line", "parcel"], Emotion.NEUTRAL),
    "chart": ("scattered dots aligning into a rising line",
              ["scattered dots", "rising line", "axis", "magnifier"], Emotion.CURIOSITY),
    "star": ("one shape lifted above a row of identical shapes",
             ["row of squares", "lifted star", "pedestal", "sparkle"], Emotion.PRIDE),
    "heart": ("two hands protecting a small flame",
              ["hand", "second hand", "flame", "heart"], Emotion.HOPE),
    "globe": ("threads stitching distant points together",
              ["globe", "thread", "pin", "envelope"], Emotion.CURIOSITY),
    "chat": ("two speech bubbles overlapping into one",
             ["speech bubble", "second bubble", "overlap shape", "pen"], Emotion.NEUTRAL),
    "lock": ("a padlock closing over a folder",
             ["folder", "padlock", "key", "shield"], Emotion.TRUST),
    "handshake": ("two hands meeting over a signed sheet",
                  ["hand", "second hand", "signed sheet", "seal"], Emotion.TRUST),
    "calendar": ("a single date circled on a wall of days",
                 ["calendar grid", "circled date", "pen", "clock"], Emotion.URGENCY),
}

EDITORIAL_DEFAULT: MetaphorEntry = (
    "a closed door opening onto a bright path",
    ["closed door", "turning key", "open path", "silhouette"],
    Emotion.CURIOSITY,
)


# --------------------------------------------------------------------------- #
# Profil 2 & 3 — UGC produit
#
# Ici la personne parle d'un PRODUIT face caméra. Le collage ne doit pas partir
# dans la métaphore abstraite: il doit montrer ce dont elle parle à l'instant
# précis (le prix, la livraison, la texture, le résultat, les avis…). Les
# objets sont volontairement nommés avec le vocabulaire de `collage_shapes`
# pour que la découpe corresponde exactement à l'idée.
# --------------------------------------------------------------------------- #
_UGC_INSTRUCTION = (
    "Tu es directeur artistique d'un studio spécialisé dans la vidéo UGC de "
    "présentation de produit. Une personne parle face caméra de son produit. "
    "Pour CHAQUE extrait ci-dessous, conçois UNE scène de collage papier qui "
    "ILLUSTRE CONCRÈTEMENT ce qu'elle dit à cet instant (le prix, la livraison, "
    "la texture, la façon de l'utiliser, le résultat, les avis, la garantie…).\n"
    "Contraintes strictes:\n"
    "- 3 à 5 objets MAXIMUM, tous des objets du quotidien, découpables en papier;\n"
    "- reste LITTÉRAL et lisible: on doit reconnaître l'objet en une seconde, "
    "ce n'est pas une métaphore poétique mais une démonstration produit;\n"
    "- aucun objet ne doit être du texte, un logo, un chiffre, une marque;\n"
    "- l'ordre des objets raconte la petite scène: le produit d'abord, le "
    "bénéfice ou la preuve en dernier;\n"
    "- privilégie ce vocabulaire quand il colle: flacon, pot, tube, carton, "
    "sachet, panier, étiquette, pièces, main, pouce levé, étoile, cœur, coche, "
    "croix, horloge, calendrier, camion, téléphone, bulle, feuille, goutte, "
    "flamme, éclat, bouclier, loupe, flèche montante, barres, cadeau, "
    "personne, avant/après, vêtement, chaussure, cadenas;\n"
    "- couleurs = aplats de papier saturés, une couleur de fond + 2 accents.\n"
    "Réponds UNIQUEMENT par un tableau JSON de {n} objets, dans le MÊME ORDRE, "
    "chaque objet ayant exactement ces clés:\n"
    '{"meaning": str, "emotion": "urgency|hope|warning|pride|curiosity|trust|'
    'frustration|neutral", "metaphor": str, "objects": [{"name": str, '
    '"order": int, "note": str}], "background_color": "#RRGGBB", '
    '"palette": ["#RRGGBB", ...], "label": str}\n'
    "`label` = UN mot-clé en majuscules (max 12 caractères).\n\n"
    "Extraits:\n{items}"
)

#: Intentions du discours produit. Ordre = priorité (la plus spécifique d'abord).
#:
#: Les mots courts sont ANCRÉS sur des limites de mot. Sans ancrage, le français
#: piège en permanence: « franc » attrapait « franchement », « coute » attrapait
#: « écoute », « avis » attrapait « ravis », « vite » attrapait « évite » — une
#: phrase sur le résultat produit se retrouvait illustrée par une étiquette de
#: prix.
UGC_INTENT_RULES: list[tuple[str, str]] = [
    ("delivery", r"livrais|livré|livre en |expédi|expedi|colis|réception|reception|"
                 r"\bdélai|\bdelai|deliver|shipping|à domicile|a domicile|"
                 r"\b24 ?h\b|\b48 ?h\b"),
    ("price", r"\bprix\b|\bcoûte|\bcoute\b|\btarif|\beuros?\b|\bfrancs?\b|\bcfa\b|"
              r"\bpayer\b|\bpromo|réduction|reduction|\bsoldes?\b|moins cher|"
              r"\bprice\b|discount|offre spéciale|pas cher"),
    ("proof", r"\bavis\b|témoign|temoign|\bclients?\b|\bnotes?\b|étoiles?\b|"
              r"etoiles?\b|recommand|\breviews?\b|satisfait|commentaire|"
              r"des milliers|tout le monde"),
    ("guarantee", r"garanti|rembours|sans risque|sécuris|securis|authentique|"
                  r"certifi|guarantee|\bessai\b|satisfait ou"),
    ("result", r"résultat|resultat|avant.{0,12}après|avant.{0,12}apres|transform|"
               r"différence|difference|change tout|en une semaine|\beffets?\b|"
               r"\bresults?\b|\bglow\b|\béclat|\beclat"),
    # « lien en bio » (le lien Instagram) n'a rien à voir avec le bio agricole:
    # sans cette exclusion, une phrase d'appel à l'achat était illustrée par des
    # feuilles et des gouttes.
    ("ingredients", r"ingrédient|ingredient|composi|naturel|(?<!en )\bbio\b|formule|"
                    r"sans paraben|\bactifs?\b|extrait de|matière|matiere|"
                    r"\bcoton\b|texture|parfum"),
    ("usage", r"utilis|appliqu|s'en sert|routine|\bmatin|\bsoir\b|chaque jour|"
              r"il suffit de|comment (le|la|l')|mode d'emploi|étapes?\b|etapes?\b"),
    ("order", r"command|acheter|achète|achete|\bpanier\b|lien en bio|clique|"
              r"\bdispo|boutique|\bsite\b|\bdm\b|whatsapp|\border\b|checkout"),
    ("problem", r"problème|probleme|galère|galere|\bmarre\b|jamais réussi|"
                r"ça marchait pas|ca marchait pas|difficile|arnaque|déçu|\bdecu\b|"
                r"perte de temps"),
    ("urgency", r"\bstocks?\b|dernières|dernieres|plus que|\bvite\b|dépêche|"
                r"depeche|aujourd'hui seulement|limité|\blimite\b|rupture|"
                r"ça part|ca part"),
    ("unboxing", r"emballage|packaging|\bboîte\b|\bboite\b|\bcarton\b|j'ouvre|"
                 r"déballe|deballe|coffret|à l'intérieur|a l'interieur|unboxing"),
    ("comparison", r"compar|versus|\bvs\b|mieux que|contrairement|l'autre marque|"
                   r"la différence entre|d'un côté"),
    ("product", r"\bproduits?\b|\barticles?\b|référence|reference|modèle|modele|"
                r"ce truc|cette crème|ce flacon|celui-ci|celle-ci"),
]

UGC_LIBRARY: dict[str, MetaphorEntry] = {
    "delivery": ("le colis part de l'entrepôt et arrive chez le client",
                 ["box", "truck", "calendar", "check"], Emotion.TRUST),
    "price": ("une étiquette de prix posée à côté de quelques pièces",
              ["tag", "coins", "hand", "check"], Emotion.HOPE),
    "proof": ("des avis qui s'empilent autour du produit",
              ["star", "chat", "person", "thumb_up"], Emotion.PRIDE),
    "guarantee": ("un bouclier refermé sur le produit",
                  ["shield", "lock", "check", "hand"], Emotion.TRUST),
    "result": ("le côté « avant » qui bascule vers le côté « après »",
               ["mirror", "arrow_up", "sparkle", "star"], Emotion.PRIDE),
    "ingredients": ("la formule décomposée en ses éléments",
                    ["bottle", "leaf", "drop", "magnifier"], Emotion.CURIOSITY),
    "usage": ("le geste quotidien, du produit à la main",
              ["jar", "hand", "drop", "clock"], Emotion.NEUTRAL),
    "order": ("la commande passée depuis le téléphone",
              ["phone", "cart", "bag", "check"], Emotion.HOPE),
    "problem": ("ce qui ne marchait pas, barré",
                ["cross", "clock", "magnifier", "check"], Emotion.FRUSTRATION),
    "urgency": ("le stock qui fond pendant que la demande grimpe",
                ["flame", "chart", "clock", "cart"], Emotion.URGENCY),
    "unboxing": ("le carton s'ouvre et révèle ce qu'il contient",
                 ["box", "gift", "bottle", "sparkle"], Emotion.CURIOSITY),
    "comparison": ("deux options mises côte à côte, une seule cochée",
                   ["mirror", "magnifier", "cross", "check"], Emotion.CURIOSITY),
    "product": ("le produit présenté, tenu en main",
                ["bottle", "hand", "star", "sparkle"], Emotion.PRIDE),
}

UGC_DEFAULT: MetaphorEntry = (
    "le produit présenté et le bénéfice qu'il apporte",
    ["box", "hand", "check", "sparkle"],
    Emotion.TRUST,
)

#: Repli quand aucune intention produit ne se déclenche: on retombe sur le
#: vocabulaire d'icônes du moteur, mais traduit en objets CONCRETS (pas en
#: métaphores abstraites), pour rester dans la promesse du profil UGC.
UGC_ICON_FALLBACK: dict[str, str] = {
    "money": "price", "card": "price", "bank": "price",
    "cart": "order", "phone": "order", "chat": "proof", "people": "proof",
    "star": "proof", "heart": "proof", "check": "guarantee",
    "shield": "guarantee", "lock": "guarantee", "warning": "problem",
    "clock": "urgency", "calendar": "usage", "map": "delivery",
    "transfer": "delivery", "chart": "result", "growth": "result",
    "rocket": "result", "target": "result", "idea": "ingredients",
    "book": "usage", "gear": "usage", "globe": "delivery",
    "megaphone": "urgency", "handshake": "guarantee", "crypto": "price",
}


EDITORIAL = CollageProfile(
    id="editorial",
    label="Collage Premium éditorial",
    allow_ai_images=True,
    allow_planner_llm=True,
    llm_instruction=_EDITORIAL_INSTRUCTION,
    metaphor_library=EDITORIAL_LIBRARY,
    default_metaphor=EDITORIAL_DEFAULT,
    intent_rules=[],
    share_of_broll=0.5,
    max_scenes=4,
)

UGC_PRODUCT = CollageProfile(
    id="ugc_product",
    label="Collage UGC produit",
    allow_ai_images=False,
    allow_planner_llm=True,
    llm_instruction=_UGC_INSTRUCTION,
    metaphor_library=UGC_LIBRARY,
    default_metaphor=UGC_DEFAULT,
    intent_rules=UGC_INTENT_RULES,
    # Aucune image IA ne dispute les beats au collage: il les prend tous, et
    # c'est lui qui porte TOUTE l'illustration de la vidéo.
    share_of_broll=1.0,
    max_scenes=8,
)

#: Le profil « motion » partage exactement la direction artistique du profil
#: produit: la différence (scènes de motion design) se joue au niveau du
#: MONTAGE, pas du collage. Un profil distinct existe quand même pour que les
#: caches et les rapports de job restent lisibles moteur par moteur.
UGC_MOTION = CollageProfile(
    id="ugc_motion",
    label="Collage UGC produit + motion design",
    allow_ai_images=False,
    allow_planner_llm=True,
    llm_instruction=_UGC_INSTRUCTION,
    metaphor_library=UGC_LIBRARY,
    default_metaphor=UGC_DEFAULT,
    intent_rules=UGC_INTENT_RULES,
    # Le motion design occupe une partie des beats: le collage en prend moins,
    # sinon les deux familles se disputent les mêmes moments de parole.
    share_of_broll=0.7,
    max_scenes=6,
)

PROFILES: dict[str, CollageProfile] = {
    p.id: p for p in (EDITORIAL, UGC_PRODUCT, UGC_MOTION)
}

DEFAULT_PROFILE = EDITORIAL.id


def get(profile_id: Optional[str]) -> CollageProfile:
    """Profil demandé, ou le profil éditorial historique."""
    return PROFILES.get((profile_id or "").strip().lower(), EDITORIAL)
