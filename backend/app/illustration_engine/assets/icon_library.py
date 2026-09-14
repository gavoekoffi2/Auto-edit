"""Procedural vector icon library.

Every icon is a list of polylines in a normalised 0..1 box, so the same
definition scales to any canvas, exports to SVG, and can be drawn
stroke-by-stroke by the whiteboard renderer.

The vocabulary is deliberately built around what CutForge's audience talks
about — commerce, mobile money, delivery, phones, business, AI, agriculture,
education, finance — and stays symbolic: objects and tools, never caricatured
depictions of people.
"""
from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

Point = Tuple[float, float]
Stroke = List[Point]
Icon = List[Stroke]


# --------------------------------------------------------------------------- #
# primitive builders (all in 0..1 space)
# --------------------------------------------------------------------------- #
def circle(cx: float, cy: float, r: float, n: int = 32) -> Stroke:
    return [(cx + r * math.cos(2 * math.pi * i / n),
             cy + r * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]


def ellipse(cx: float, cy: float, rx: float, ry: float, n: int = 32) -> Stroke:
    return [(cx + rx * math.cos(2 * math.pi * i / n),
             cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]


def arc(cx: float, cy: float, r: float, a0: float, a1: float, n: int = 20) -> Stroke:
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n),
             cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def rect(x0: float, y0: float, x1: float, y1: float) -> Stroke:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]


def line(x0: float, y0: float, x1: float, y1: float) -> Stroke:
    return [(x0, y0), (x1, y1)]


def poly(*points: Point) -> Stroke:
    return list(points)


def arrow(x0: float, y0: float, x1: float, y1: float, head: float = 0.12) -> Icon:
    """Shaft plus a two-line head, as three separate strokes."""
    angle = math.atan2(y1 - y0, x1 - x0)
    left = (x1 - head * math.cos(angle - 0.45), y1 - head * math.sin(angle - 0.45))
    right = (x1 - head * math.cos(angle + 0.45), y1 - head * math.sin(angle + 0.45))
    return [line(x0, y0, x1, y1), line(x1, y1, *left), line(x1, y1, *right)]


# --------------------------------------------------------------------------- #
# the library
# --------------------------------------------------------------------------- #
def _phone() -> Icon:
    return [rect(0.30, 0.08, 0.70, 0.92), line(0.44, 0.15, 0.56, 0.15),
            circle(0.50, 0.85, 0.04, 16), rect(0.35, 0.22, 0.65, 0.76)]


def _mobile_money() -> Icon:
    return (_phone() +
            [circle(0.50, 0.46, 0.13, 24),
             line(0.50, 0.36, 0.50, 0.56),
             arc(0.50, 0.42, 0.07, math.pi, 2 * math.pi, 12),
             arc(0.50, 0.50, 0.07, 0.0, math.pi, 12)])


def _cart() -> Icon:
    return [poly((0.10, 0.22), (0.24, 0.22), (0.34, 0.62), (0.80, 0.62)),
            line(0.28, 0.34, 0.86, 0.34), line(0.86, 0.34, 0.80, 0.62),
            circle(0.40, 0.78, 0.07, 18), circle(0.72, 0.78, 0.07, 18)]


def _shop() -> Icon:
    return [poly((0.12, 0.40), (0.20, 0.20), (0.80, 0.20), (0.88, 0.40)),
            rect(0.16, 0.40, 0.84, 0.88), rect(0.36, 0.58, 0.64, 0.88),
            line(0.12, 0.40, 0.88, 0.40)]


def _parcel() -> Icon:
    return [rect(0.18, 0.30, 0.82, 0.86), line(0.18, 0.46, 0.82, 0.46),
            line(0.50, 0.30, 0.50, 0.86),
            poly((0.38, 0.30), (0.50, 0.18), (0.62, 0.30))]


def _truck() -> Icon:
    return [rect(0.08, 0.34, 0.56, 0.70), poly((0.56, 0.44), (0.76, 0.44),
            (0.90, 0.58), (0.90, 0.70), (0.56, 0.70)),
            circle(0.26, 0.78, 0.08, 18), circle(0.74, 0.78, 0.08, 18),
            line(0.08, 0.70, 0.90, 0.70)]


def _customer() -> Icon:
    return [circle(0.50, 0.28, 0.15, 24),
            arc(0.50, 0.86, 0.30, math.pi, 2 * math.pi, 24),
            line(0.20, 0.86, 0.80, 0.86)]


def _people() -> Icon:
    return [circle(0.32, 0.30, 0.12, 20), arc(0.32, 0.80, 0.22, math.pi, 2 * math.pi, 18),
            circle(0.68, 0.30, 0.12, 20), arc(0.68, 0.80, 0.22, math.pi, 2 * math.pi, 18)]


def _money() -> Icon:
    return [rect(0.10, 0.30, 0.90, 0.72), ellipse(0.50, 0.51, 0.13, 0.13, 24),
            line(0.50, 0.36, 0.50, 0.66), line(0.20, 0.51, 0.26, 0.51),
            line(0.74, 0.51, 0.80, 0.51)]


def _coin() -> Icon:
    return [circle(0.50, 0.50, 0.34, 32), circle(0.50, 0.50, 0.26, 28),
            line(0.50, 0.32, 0.50, 0.68),
            arc(0.50, 0.42, 0.10, math.pi, 2 * math.pi, 14),
            arc(0.50, 0.56, 0.10, 0.0, math.pi, 14)]


def _bank() -> Icon:
    return [poly((0.08, 0.36), (0.50, 0.14), (0.92, 0.36)),
            line(0.10, 0.36, 0.90, 0.36), line(0.10, 0.84, 0.90, 0.84),
            line(0.24, 0.40, 0.24, 0.80), line(0.42, 0.40, 0.42, 0.80),
            line(0.58, 0.40, 0.58, 0.80), line(0.76, 0.40, 0.76, 0.80)]


def _growth() -> Icon:
    return [line(0.12, 0.86, 0.12, 0.14), line(0.12, 0.86, 0.90, 0.86),
            poly((0.22, 0.70), (0.42, 0.52), (0.58, 0.60), (0.84, 0.26))] + \
        arrow(0.78, 0.32, 0.86, 0.24, 0.08)


def _chart() -> Icon:
    return [line(0.14, 0.86, 0.14, 0.14), line(0.14, 0.86, 0.90, 0.86),
            rect(0.24, 0.62, 0.38, 0.86), rect(0.44, 0.44, 0.58, 0.86),
            rect(0.64, 0.26, 0.78, 0.86)]


def _target() -> Icon:
    return [circle(0.50, 0.50, 0.36, 32), circle(0.50, 0.50, 0.23, 26),
            circle(0.50, 0.50, 0.10, 18)] + arrow(0.14, 0.88, 0.48, 0.52, 0.10)


def _idea() -> Icon:
    return [circle(0.50, 0.38, 0.24, 28), line(0.38, 0.62, 0.38, 0.74),
            line(0.62, 0.62, 0.62, 0.74), line(0.38, 0.74, 0.62, 0.74),
            line(0.42, 0.84, 0.58, 0.84),
            line(0.50, 0.06, 0.50, 0.00), line(0.14, 0.22, 0.06, 0.16),
            line(0.86, 0.22, 0.94, 0.16)]


def _gear() -> Icon:
    icon: Icon = [circle(0.50, 0.50, 0.24, 28), circle(0.50, 0.50, 0.10, 16)]
    for i in range(8):
        a = 2 * math.pi * i / 8
        icon.append(line(0.50 + 0.26 * math.cos(a), 0.50 + 0.26 * math.sin(a),
                         0.50 + 0.40 * math.cos(a), 0.50 + 0.40 * math.sin(a)))
    return icon


def _server() -> Icon:
    return [rect(0.18, 0.14, 0.82, 0.38), rect(0.18, 0.42, 0.82, 0.66),
            rect(0.18, 0.70, 0.82, 0.94),
            circle(0.28, 0.26, 0.035, 12), circle(0.28, 0.54, 0.035, 12),
            circle(0.28, 0.82, 0.035, 12),
            line(0.44, 0.26, 0.72, 0.26), line(0.44, 0.54, 0.72, 0.54),
            line(0.44, 0.82, 0.72, 0.82)]


def _database() -> Icon:
    return [ellipse(0.50, 0.22, 0.32, 0.12, 28),
            line(0.18, 0.22, 0.18, 0.78), line(0.82, 0.22, 0.82, 0.78),
            arc(0.50, 0.78, 0.32, 0.0, math.pi, 20),
            arc(0.50, 0.46, 0.32, 0.0, math.pi, 20),
            arc(0.50, 0.62, 0.32, 0.0, math.pi, 20)]


def _cloud() -> Icon:
    return [arc(0.34, 0.58, 0.18, math.pi, 2 * math.pi, 18),
            arc(0.58, 0.52, 0.24, math.pi, 2 * math.pi, 20),
            arc(0.76, 0.60, 0.14, math.pi * 1.2, 2 * math.pi, 14),
            line(0.16, 0.58, 0.90, 0.60)]


def _ai() -> Icon:
    icon: Icon = [rect(0.26, 0.26, 0.74, 0.74), circle(0.50, 0.50, 0.10, 18)]
    for x in (0.38, 0.50, 0.62):
        icon.append(line(x, 0.26, x, 0.12))
        icon.append(line(x, 0.74, x, 0.88))
    for y in (0.38, 0.50, 0.62):
        icon.append(line(0.26, y, 0.12, y))
        icon.append(line(0.74, y, 0.88, y))
    return icon


def _social() -> Icon:
    return [circle(0.24, 0.30, 0.10, 18), circle(0.76, 0.24, 0.10, 18),
            circle(0.50, 0.76, 0.10, 18), circle(0.50, 0.44, 0.10, 18),
            line(0.32, 0.34, 0.42, 0.42), line(0.68, 0.28, 0.58, 0.40),
            line(0.50, 0.54, 0.50, 0.66)]


def _megaphone() -> Icon:
    return [poly((0.16, 0.42), (0.16, 0.62), (0.56, 0.78), (0.56, 0.26)),
            rect(0.56, 0.32, 0.68, 0.72),
            arc(0.68, 0.52, 0.14, -1.0, 1.0, 12),
            arc(0.68, 0.52, 0.24, -0.9, 0.9, 14),
            rect(0.20, 0.62, 0.32, 0.90)]


def _clock() -> Icon:
    return [circle(0.50, 0.50, 0.36, 32), line(0.50, 0.50, 0.50, 0.26),
            line(0.50, 0.50, 0.68, 0.58), line(0.50, 0.10, 0.50, 0.16),
            line(0.50, 0.84, 0.50, 0.90)]


def _calendar() -> Icon:
    icon: Icon = [rect(0.12, 0.20, 0.88, 0.88), line(0.12, 0.38, 0.88, 0.38),
                  line(0.30, 0.12, 0.30, 0.26), line(0.70, 0.12, 0.70, 0.26)]
    for i in range(1, 3):
        icon.append(line(0.12, 0.38 + i * 0.17, 0.88, 0.38 + i * 0.17))
    for i in range(1, 3):
        icon.append(line(0.12 + i * 0.253, 0.38, 0.12 + i * 0.253, 0.88))
    return icon


def _check() -> Icon:
    return [circle(0.50, 0.50, 0.38, 32),
            poly((0.30, 0.52), (0.44, 0.66), (0.72, 0.36))]


def _warning() -> Icon:
    return [poly((0.50, 0.10), (0.94, 0.86), (0.06, 0.86), (0.50, 0.10)),
            line(0.50, 0.38, 0.50, 0.62), circle(0.50, 0.74, 0.035, 12)]


def _cross() -> Icon:
    return [circle(0.50, 0.50, 0.38, 32), line(0.34, 0.34, 0.66, 0.66),
            line(0.66, 0.34, 0.34, 0.66)]


def _lock() -> Icon:
    return [rect(0.24, 0.44, 0.76, 0.88),
            arc(0.50, 0.44, 0.18, math.pi, 2 * math.pi, 18),
            circle(0.50, 0.64, 0.05, 14), line(0.50, 0.66, 0.50, 0.76)]


def _book() -> Icon:
    return [poly((0.10, 0.22), (0.48, 0.30), (0.48, 0.86), (0.10, 0.78)),
            poly((0.90, 0.22), (0.52, 0.30), (0.52, 0.86), (0.90, 0.78)),
            line(0.48, 0.30, 0.52, 0.30)]


def _graduation() -> Icon:
    return [poly((0.50, 0.22), (0.94, 0.42), (0.50, 0.62), (0.06, 0.42), (0.50, 0.22)),
            poly((0.22, 0.50), (0.22, 0.74), (0.50, 0.84), (0.78, 0.74), (0.78, 0.50)),
            line(0.88, 0.46, 0.88, 0.74)]


def _plant() -> Icon:
    return [line(0.50, 0.92, 0.50, 0.38),
            arc(0.32, 0.50, 0.20, -1.4, 0.4, 14),
            arc(0.68, 0.42, 0.20, 2.6, 4.6, 14),
            poly((0.30, 0.92), (0.70, 0.92))]


def _handshake() -> Icon:
    return [poly((0.06, 0.50), (0.28, 0.38), (0.50, 0.52), (0.72, 0.38), (0.94, 0.50)),
            poly((0.28, 0.38), (0.34, 0.62), (0.50, 0.70), (0.66, 0.62), (0.72, 0.38)),
            line(0.50, 0.52, 0.50, 0.70)]


def _document() -> Icon:
    icon: Icon = [poly((0.22, 0.10), (0.62, 0.10), (0.78, 0.28), (0.78, 0.90),
                       (0.22, 0.90), (0.22, 0.10)),
                  poly((0.62, 0.10), (0.62, 0.28), (0.78, 0.28))]
    for i in range(4):
        icon.append(line(0.32, 0.42 + i * 0.12, 0.68, 0.42 + i * 0.12))
    return icon


def _search() -> Icon:
    return [circle(0.42, 0.42, 0.26, 28), line(0.61, 0.61, 0.86, 0.86)]


def _globe() -> Icon:
    return [circle(0.50, 0.50, 0.38, 32), ellipse(0.50, 0.50, 0.16, 0.38, 28),
            line(0.12, 0.50, 0.88, 0.50),
            arc(0.50, 0.14, 0.42, 0.5, 2.64, 16),
            arc(0.50, 0.86, 0.42, 3.64, 5.78, 16)]


def _chat() -> Icon:
    return [poly((0.10, 0.18), (0.90, 0.18), (0.90, 0.66), (0.42, 0.66),
                 (0.26, 0.86), (0.26, 0.66), (0.10, 0.66), (0.10, 0.18)),
            circle(0.34, 0.42, 0.04, 12), circle(0.50, 0.42, 0.04, 12),
            circle(0.66, 0.42, 0.04, 12)]


def _rocket() -> Icon:
    return [poly((0.50, 0.06), (0.68, 0.36), (0.68, 0.70), (0.32, 0.70),
                 (0.32, 0.36), (0.50, 0.06)),
            circle(0.50, 0.36, 0.09, 18),
            poly((0.32, 0.52), (0.16, 0.74), (0.32, 0.70)),
            poly((0.68, 0.52), (0.84, 0.74), (0.68, 0.70)),
            poly((0.42, 0.70), (0.50, 0.94), (0.58, 0.70))]


def _key() -> Icon:
    return [circle(0.26, 0.42, 0.18, 24), line(0.40, 0.54, 0.86, 0.86),
            line(0.72, 0.74, 0.64, 0.86), line(0.80, 0.80, 0.72, 0.92)]


def _shield() -> Icon:
    return [poly((0.50, 0.08), (0.86, 0.24), (0.86, 0.56), (0.50, 0.92),
                 (0.14, 0.56), (0.14, 0.24), (0.50, 0.08)),
            poly((0.34, 0.48), (0.46, 0.60), (0.68, 0.36))]


def _scale() -> Icon:
    return [line(0.50, 0.14, 0.50, 0.82), line(0.16, 0.30, 0.84, 0.30),
            line(0.30, 0.82, 0.70, 0.82),
            arc(0.16, 0.30, 0.14, 0.0, math.pi, 12),
            arc(0.84, 0.30, 0.14, 0.0, math.pi, 12)]


def _star() -> Icon:
    points: Stroke = []
    for i in range(11):
        angle = -math.pi / 2 + i * math.pi / 5
        radius = 0.40 if i % 2 == 0 else 0.17
        points.append((0.50 + radius * math.cos(angle), 0.50 + radius * math.sin(angle)))
    return [points]


def _percent() -> Icon:
    return [circle(0.28, 0.28, 0.16, 20), circle(0.72, 0.72, 0.16, 20),
            line(0.84, 0.16, 0.16, 0.84)]


ICONS: Dict[str, Icon] = {
    "phone": _phone(), "mobile_money": _mobile_money(), "cart": _cart(),
    "shop": _shop(), "parcel": _parcel(), "truck": _truck(),
    "customer": _customer(), "people": _people(), "money": _money(),
    "coin": _coin(), "bank": _bank(), "growth": _growth(), "chart": _chart(),
    "target": _target(), "idea": _idea(), "gear": _gear(), "server": _server(),
    "database": _database(), "cloud": _cloud(), "ai": _ai(), "social": _social(),
    "megaphone": _megaphone(), "clock": _clock(), "calendar": _calendar(),
    "check": _check(), "warning": _warning(), "cross": _cross(), "lock": _lock(),
    "book": _book(), "graduation": _graduation(), "plant": _plant(),
    "handshake": _handshake(), "document": _document(), "search": _search(),
    "globe": _globe(), "chat": _chat(), "rocket": _rocket(), "key": _key(),
    "shield": _shield(), "scale": _scale(), "star": _star(), "percent": _percent(),
}

# Concept keyword -> icon. Checked as substrings against folded text, longest
# key first so "mobile money" beats "mobile".
KEYWORD_ICONS: Dict[str, str] = {
    "mobile money": "mobile_money", "orange money": "mobile_money",
    "momo": "mobile_money", "wave": "mobile_money", "transfert": "mobile_money",
    "portefeuille": "mobile_money", "wallet": "mobile_money",
    "livraison": "truck", "livreur": "truck", "transport": "truck",
    "expedition": "truck", "shipping": "truck", "delivery": "truck",
    "colis": "parcel", "paquet": "parcel", "parcel": "parcel",
    "commande": "cart", "panier": "cart", "achat": "cart", "cart": "cart",
    "vente": "cart", "vendre": "cart", "order": "cart",
    "boutique": "shop", "magasin": "shop", "shop": "shop", "store": "shop",
    "entrepot": "shop", "stock": "shop", "inventaire": "shop",
    "warehouse": "shop", "rayon": "shop",
    "paiement": "money", "payer": "money", "encaisser": "money",
    "facturation": "money", "payment": "money", "caisse": "money",
    "logistique": "truck", "chaine": "truck", "supply": "truck",
    "ecommerce": "shop", "e-commerce": "shop", "produit": "parcel",
    "client": "customer", "clients": "customer", "customer": "customer",
    "acheteur": "customer", "audience": "people", "communaute": "people",
    "equipe": "people", "team": "people", "gens": "people",
    "argent": "money", "prix": "money", "cout": "money", "revenu": "money",
    "chiffre d'affaires": "money", "benefice": "money", "money": "money",
    "marge": "coin", "budget": "coin", "epargne": "coin", "capital": "coin",
    "banque": "bank", "bank": "bank", "credit": "bank", "pret": "bank",
    "croissance": "growth", "augmenter": "growth", "scaler": "growth",
    "growth": "growth", "progression": "growth", "resultat": "growth",
    "statistique": "chart", "donnees": "chart", "data": "chart",
    "analyse": "chart", "metrique": "chart", "chart": "chart",
    "pourcent": "percent", "pourcentage": "percent", "percent": "percent",
    "objectif": "target", "but": "target", "cible": "target", "goal": "target",
    "strategie": "target", "target": "target",
    "idee": "idea", "concept": "idea", "astuce": "idea", "secret": "idea",
    "conseil": "idea", "idea": "idea", "solution": "idea",
    "methode": "gear", "processus": "gear", "systeme": "gear",
    "automatisation": "gear", "process": "gear", "outil": "gear",
    "serveur": "server", "server": "server", "backend": "server",
    "infrastructure": "server", "base de donnees": "database",
    "database": "database", "stockage": "database",
    "cloud": "cloud", "hebergement": "cloud", "internet": "cloud",
    "intelligence artificielle": "ai", "ia": "ai", "chatgpt": "ai",
    "algorithme": "ai", "modele": "ai", "machine learning": "ai",
    "reseaux sociaux": "social", "instagram": "social", "tiktok": "social",
    "facebook": "social", "social": "social", "abonnes": "social",
    "followers": "social", "whatsapp": "chat",
    "publicite": "megaphone", "marketing": "megaphone", "ads": "megaphone",
    "campagne": "megaphone", "promotion": "megaphone", "trafic": "megaphone",
    "temps": "clock", "heure": "clock", "delai": "clock", "rapide": "clock",
    "time": "clock", "duree": "clock",
    "planning": "calendar", "semaine": "calendar", "mois": "calendar",
    "calendrier": "calendar", "schedule": "calendar",
    "valide": "check", "correct": "check", "reussite": "check",
    "succes": "check", "bon": "check", "avantage": "check",
    "erreur": "warning", "probleme": "warning", "piege": "warning",
    "danger": "warning", "risque": "warning", "attention": "warning",
    "mistake": "warning", "arnaque": "warning",
    "mauvais": "cross", "echec": "cross", "interdit": "cross",
    "securite": "lock", "mot de passe": "lock", "prive": "lock",
    "formation": "book", "cours": "book", "apprendre": "graduation",
    "etudiant": "graduation", "ecole": "graduation", "education": "graduation",
    "diplome": "graduation", "learning": "graduation",
    "agriculture": "plant", "champ": "plant", "recolte": "plant",
    "culture": "plant", "ferme": "plant", "cacao": "plant",
    "partenaire": "handshake", "accord": "handshake", "contrat": "document",
    "deal": "handshake", "collaboration": "handshake",
    "document": "document", "facture": "document", "rapport": "document",
    "recherche": "search", "trouver": "search", "chercher": "search",
    "afrique": "globe", "monde": "globe", "international": "globe",
    "pays": "globe", "global": "globe", "export": "globe",
    "message": "chat", "communication": "chat", "discussion": "chat",
    "lancement": "rocket", "demarrer": "rocket", "startup": "rocket",
    "decoller": "rocket", "launch": "rocket", "acceleration": "rocket",
    "cle": "key", "acces": "key", "key": "key",
    "protection": "shield", "garantie": "shield", "assurance": "shield",
    "comparaison": "scale", "equilibre": "scale", "choix": "scale",
    "qualite": "star", "meilleur": "star", "premium": "star", "note": "star",
}

_SORTED_KEYWORDS = sorted(KEYWORD_ICONS, key=len, reverse=True)

DEFAULT_ICON = "idea"


def icon_for(text: str, exclude: Sequence[str] = ()) -> str:
    """Best icon for a phrase, avoiding names in *exclude* when possible."""
    from ..analyzer.lexicon import fold  # local import: avoids a cycle
    folded = " %s " % fold(text or "")
    excluded = set(exclude)
    fallback = ""
    for keyword in _SORTED_KEYWORDS:
        if keyword in folded:
            name = KEYWORD_ICONS[keyword]
            if name not in excluded:
                return name
            fallback = fallback or name
    return fallback or DEFAULT_ICON


def get(name: str) -> Icon:
    return ICONS.get(name or "", ICONS[DEFAULT_ICON])


def names() -> List[str]:
    return sorted(ICONS)
