"""Bibliothèque de PICTOGRAMMES « papier découpé » — illustrer sans image IA.

Les moteurs UGC (`collage_ugc_product`, `collage_ugc_motion`) n'appellent
AUCUNE API d'image: tout ce qui illustre le discours est dessiné ici, en
vectoriel, avec le même vocabulaire visuel que le Collage Premium (aplat de
papier coloré, bord déchiré, contour crème, trame, ombre courte).

Pourquoi maison plutôt qu'IA — même raisonnement que `autoedit_engine.silhouettes`:

  * coût nul et hors-ligne: c'est la raison d'être des moteurs UGC;
  * déterministe: la même phrase donne toujours la même pièce, donc un montage
    est reproductible et deux scènes voisines restent cohérentes;
  * pas de typographie parasite: un modèle d'image glisse presque toujours des
    pseudo-lettres dans une découpe, ce que le verrou de style interdit.

Un pictogramme est décrit en coordonnées NORMALISÉES (0..1) dans sa boîte, donc
il se rend proprement à n'importe quelle taille.

Usage:
    python -m app.processing.collage.collage_shapes --preview planche.png
"""
from __future__ import annotations

import argparse
import math
import os
import re
import sys
from typing import Callable, Optional, Sequence

from PIL import Image, ImageDraw, ImageFilter

Box = tuple[float, float, float, float]
Point = tuple[float, float]

try:  # Pillow >= 9.1
    _RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:  # pragma: no cover - Pillow ancien
    _RESAMPLE = Image.LANCZOS


# --------------------------------------------------------------------------- #
# Helpers de dessin (coordonnées normalisées -> pixels)
# --------------------------------------------------------------------------- #
class Pen:
    """Petit traceur normalisé: 0..1 sur la boîte, épaisseurs relatives."""

    def __init__(self, draw: ImageDraw.ImageDraw, w: int, h: int):
        self.d = draw
        self.w = w
        self.h = h
        self.span = min(w, h)

    def px(self, p: Point) -> Point:
        return (p[0] * self.w, p[1] * self.h)

    def stroke(self, unit: float) -> int:
        return max(2, int(self.span * unit))

    def poly(self, pts: Sequence[Point], fill) -> None:
        self.d.polygon([self.px(p) for p in pts], fill=fill)

    def line(self, pts: Sequence[Point], fill, width: float = 0.055) -> None:
        self.d.line([self.px(p) for p in pts], fill=fill,
                    width=self.stroke(width), joint="curve")

    def rect(self, box: Box, fill, radius: float = 0.0) -> None:
        a, b = self.px((box[0], box[1])), self.px((box[2], box[3]))
        if radius > 0:
            self.d.rounded_rectangle((*a, *b), radius=int(self.span * radius), fill=fill)
        else:
            self.d.rectangle((*a, *b), fill=fill)

    def ellipse(self, box: Box, fill) -> None:
        a, b = self.px((box[0], box[1])), self.px((box[2], box[3]))
        self.d.ellipse((*a, *b), fill=fill)

    def arc(self, box: Box, start: float, end: float, fill, width: float = 0.06) -> None:
        a, b = self.px((box[0], box[1])), self.px((box[2], box[3]))
        self.d.arc((*a, *b), start, end, fill=fill, width=self.stroke(width))

    def circle(self, cx: float, cy: float, r: float, fill) -> None:
        self.ellipse((cx - r, cy - r * self.w / self.h,
                      cx + r, cy + r * self.w / self.h), fill)


# --------------------------------------------------------------------------- #
# Pictogrammes
#
# Chaque fonction dessine UNE idée concrète. `ink` = la découpe principale
# (photo tramée dans le style d'origine), `accent` = le détail chaud qui
# empêche la forme d'être un aplat mort.
# --------------------------------------------------------------------------- #
def _box(p: Pen, ink, accent) -> None:
    """Carton / colis — le produit tel qu'il arrive."""
    p.poly([(0.14, 0.36), (0.50, 0.20), (0.86, 0.36), (0.50, 0.52)], accent)
    p.poly([(0.14, 0.36), (0.50, 0.52), (0.50, 0.86), (0.14, 0.70)], ink)
    p.poly([(0.86, 0.36), (0.50, 0.52), (0.50, 0.86), (0.86, 0.70)], ink)
    p.line([(0.50, 0.52), (0.50, 0.86)], accent, 0.022)


def _bottle(p: Pen, ink, accent) -> None:
    """Flacon / bouteille — cosmétique, boisson, complément."""
    p.rect((0.42, 0.12, 0.58, 0.26), accent, 0.02)
    p.poly([(0.44, 0.26), (0.56, 0.26), (0.70, 0.42), (0.70, 0.88),
            (0.30, 0.88), (0.30, 0.42)], ink)
    p.rect((0.36, 0.54, 0.64, 0.70), accent, 0.02)


def _jar(p: Pen, ink, accent) -> None:
    """Pot de crème — soin, texture, contenance."""
    p.rect((0.26, 0.30, 0.74, 0.42), accent, 0.03)
    p.poly([(0.28, 0.42), (0.72, 0.42), (0.68, 0.84), (0.32, 0.84)], ink)
    p.arc((0.34, 0.50, 0.66, 0.66), 200, 340, accent, 0.035)


def _tube(p: Pen, ink, accent) -> None:
    """Tube — dentifrice, gel, sérum."""
    p.rect((0.44, 0.10, 0.56, 0.22), accent, 0.02)
    p.poly([(0.36, 0.22), (0.64, 0.22), (0.68, 0.80), (0.32, 0.80)], ink)
    p.poly([(0.32, 0.80), (0.68, 0.80), (0.60, 0.90), (0.40, 0.90)], accent)


def _bag(p: Pen, ink, accent) -> None:
    """Sac / sachet — achat, packaging souple."""
    p.arc((0.34, 0.16, 0.66, 0.46), 180, 360, accent, 0.045)
    p.poly([(0.22, 0.34), (0.78, 0.34), (0.72, 0.88), (0.28, 0.88)], ink)


def _cart(p: Pen, ink, accent) -> None:
    """Panier / caddie — la commande."""
    p.poly([(0.18, 0.30), (0.82, 0.30), (0.70, 0.64), (0.30, 0.64)], ink)
    p.line([(0.10, 0.20), (0.22, 0.20), (0.30, 0.64)], accent, 0.045)
    p.circle(0.36, 0.80, 0.062, accent)
    p.circle(0.66, 0.80, 0.062, accent)


def _tag(p: Pen, ink, accent) -> None:
    """Étiquette — le prix, l'offre."""
    p.poly([(0.20, 0.18), (0.62, 0.18), (0.86, 0.50), (0.62, 0.82),
            (0.20, 0.82)], ink)
    p.circle(0.70, 0.50, 0.070, accent)


def _coins(p: Pen, ink, accent) -> None:
    """Pièces empilées — le coût, l'économie."""
    for i, y in enumerate((0.74, 0.60, 0.46)):
        p.ellipse((0.26, y - 0.07, 0.74, y + 0.07), accent if i == 2 else ink)
    p.ellipse((0.30, 0.30, 0.70, 0.44), accent)


def _hand(p: Pen, ink, accent) -> None:
    """Main ouverte — « tiens, regarde »: le geste UGC par excellence."""
    p.rect((0.30, 0.46, 0.70, 0.86), ink, 0.06)
    for x in (0.34, 0.45, 0.56):
        p.rect((x, 0.20, x + 0.09, 0.52), ink, 0.05)
    p.rect((0.66, 0.34, 0.76, 0.60), accent, 0.05)


def _thumb_up(p: Pen, ink, accent) -> None:
    """Pouce levé — validation, recommandation."""
    p.rect((0.16, 0.46, 0.34, 0.86), accent, 0.04)
    p.poly([(0.38, 0.50), (0.50, 0.16), (0.62, 0.20), (0.56, 0.44),
            (0.84, 0.44), (0.84, 0.86), (0.38, 0.86)], ink)


def _star(p: Pen, ink, accent) -> None:
    """Étoile — l'avis client, la note."""
    pts: list[Point] = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        r = 0.40 if i % 2 == 0 else 0.17
        pts.append((0.5 + r * math.cos(angle), 0.5 + r * math.sin(angle) * 1.0))
    p.poly(pts, ink)
    p.circle(0.5, 0.5, 0.085, accent)


def _heart(p: Pen, ink, accent) -> None:
    """Cœur — le coup de cœur, la préférence."""
    p.ellipse((0.16, 0.22, 0.52, 0.58), ink)
    p.ellipse((0.48, 0.22, 0.84, 0.58), ink)
    p.poly([(0.16, 0.44), (0.84, 0.44), (0.50, 0.88)], ink)
    p.ellipse((0.28, 0.32, 0.40, 0.44), accent)


def _check(p: Pen, ink, accent) -> None:
    """Coche — c'est réglé, c'est inclus."""
    p.circle(0.5, 0.5, 0.40, accent)
    p.line([(0.30, 0.52), (0.44, 0.68), (0.72, 0.32)], ink, 0.095)


def _cross(p: Pen, ink, accent) -> None:
    """Croix — le problème, ce qu'on évite."""
    p.circle(0.5, 0.5, 0.40, accent)
    p.line([(0.32, 0.32), (0.68, 0.68)], ink, 0.085)
    p.line([(0.68, 0.32), (0.32, 0.68)], ink, 0.085)


def _clock(p: Pen, ink, accent) -> None:
    """Horloge — le temps gagné, l'urgence."""
    p.circle(0.5, 0.5, 0.40, ink)
    p.circle(0.5, 0.5, 0.31, accent)
    p.line([(0.50, 0.50), (0.50, 0.28)], ink, 0.045)
    p.line([(0.50, 0.50), (0.68, 0.58)], ink, 0.045)


def _calendar(p: Pen, ink, accent) -> None:
    """Calendrier — la date, la routine."""
    p.rect((0.16, 0.22, 0.84, 0.84), ink, 0.035)
    p.rect((0.16, 0.22, 0.84, 0.40), accent, 0.035)
    for row in (0.50, 0.64, 0.78):
        for col in (0.28, 0.46, 0.64):
            p.rect((col, row, col + 0.10, row + 0.08), accent, 0.012)


def _truck(p: Pen, ink, accent) -> None:
    """Camion — la livraison."""
    p.rect((0.10, 0.34, 0.56, 0.68), ink, 0.03)
    p.poly([(0.58, 0.44), (0.78, 0.44), (0.90, 0.58), (0.90, 0.68), (0.58, 0.68)], accent)
    p.circle(0.28, 0.74, 0.085, accent)
    p.circle(0.74, 0.74, 0.085, ink)


def _phone(p: Pen, ink, accent) -> None:
    """Téléphone — la commande en ligne, le message."""
    p.rect((0.30, 0.12, 0.70, 0.88), ink, 0.055)
    p.rect((0.35, 0.22, 0.65, 0.74), accent, 0.02)


def _chat(p: Pen, ink, accent) -> None:
    """Bulle — l'avis, la question qu'on pose souvent."""
    p.rect((0.12, 0.22, 0.88, 0.66), ink, 0.09)
    p.poly([(0.30, 0.64), (0.48, 0.64), (0.30, 0.86)], ink)
    p.rect((0.24, 0.36, 0.66, 0.44), accent, 0.02)
    p.rect((0.24, 0.50, 0.52, 0.58), accent, 0.02)


def _lens(tip: Point, base: Point, bulge: float, steps: int = 22) -> list[Point]:
    """Contour « lentille »: deux arcs symétriques entre *tip* et *base*.

    Un polygone à 4 sommets donne un LOSANGE, pas une feuille ni une goutte.
    On échantillonne donc de vraies courbes: c'est ce qui fait lire la forme.
    """
    dx, dy = base[0] - tip[0], base[1] - tip[1]
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    left, right = [], []
    for i in range(steps + 1):
        f = i / steps
        # sin() -> ventre au milieu, pointes nettes aux deux extrémités.
        width = bulge * math.sin(math.pi * f) ** 0.85
        cx, cy = tip[0] + dx * f, tip[1] + dy * f
        left.append((cx + nx * width, cy + ny * width))
        right.append((cx - nx * width, cy - ny * width))
    return left + list(reversed(right))


def _teardrop(cx: float, top: float, bottom: float, radius: float,
              steps: int = 30, lean: float = 0.0) -> list[Point]:
    """Contour d'une goutte: pointe en haut, ventre circulaire en bas.

    Les deux flancs sont les TANGENTES du cercle passant par la pointe — c'est
    ce raccord tangent qui donne une goutte et pas un losange à sommets mous.
    *lean* décale la pointe horizontalement (flamme qui vacille).
    """
    center_y = bottom - radius
    depth = center_y - top
    if depth <= radius:                       # dégénéré: un simple cercle
        depth = radius * 1.35
        top = center_y - depth
    phi0 = math.acos(max(-1.0, min(1.0, radius / depth)))
    pts: list[Point] = [(cx + lean, top)]
    for i in range(steps + 1):
        phi = phi0 + (2 * math.pi - 2 * phi0) * i / steps
        pts.append((cx + radius * math.sin(phi), center_y - radius * math.cos(phi)))
    return pts


def _leaf(p: Pen, ink, accent) -> None:
    """Feuille — naturel, composition, ingrédient."""
    p.poly(_lens((0.50, 0.10), (0.50, 0.90), 0.30), ink)
    p.line([(0.50, 0.16), (0.50, 0.86)], accent, 0.030)
    for y in (0.34, 0.50, 0.66):
        p.line([(0.50, y), (0.50 + 0.16, y - 0.07)], accent, 0.020)
        p.line([(0.50, y), (0.50 - 0.16, y - 0.07)], accent, 0.020)


def _drop(p: Pen, ink, accent) -> None:
    """Goutte — hydratation, texture, concentration."""
    p.poly(_teardrop(0.50, 0.08, 0.92, 0.30), ink)
    p.circle(0.41, 0.66, 0.070, accent)


def _flame(p: Pen, ink, accent) -> None:
    """Flamme — ce qui cartonne, la tendance."""
    p.poly(_teardrop(0.50, 0.06, 0.92, 0.31, lean=0.06), ink)
    p.poly(_teardrop(0.50, 0.44, 0.86, 0.15, lean=-0.03), accent)


def _sparkle(p: Pen, ink, accent) -> None:
    """Éclat — le résultat, l'effet « waouh »."""
    p.poly([(0.50, 0.06), (0.60, 0.40), (0.94, 0.50), (0.60, 0.60),
            (0.50, 0.94), (0.40, 0.60), (0.06, 0.50), (0.40, 0.40)], ink)
    p.circle(0.50, 0.50, 0.085, accent)


def _shield(p: Pen, ink, accent) -> None:
    """Bouclier — garantie, sécurité, sans risque."""
    p.poly([(0.50, 0.10), (0.86, 0.26), (0.86, 0.56), (0.50, 0.90),
            (0.14, 0.56), (0.14, 0.26)], ink)
    p.line([(0.36, 0.48), (0.47, 0.62), (0.68, 0.36)], accent, 0.075)


def _magnifier(p: Pen, ink, accent) -> None:
    """Loupe — le détail, la comparaison."""
    p.circle(0.44, 0.42, 0.30, ink)
    p.circle(0.44, 0.42, 0.21, accent)
    p.line([(0.64, 0.64), (0.86, 0.88)], ink, 0.085)


def _arrow_up(p: Pen, ink, accent) -> None:
    """Flèche montante — le résultat, la progression."""
    p.poly([(0.50, 0.08), (0.86, 0.46), (0.64, 0.46), (0.64, 0.90),
            (0.36, 0.90), (0.36, 0.46), (0.14, 0.46)], ink)
    p.rect((0.36, 0.62, 0.64, 0.72), accent)


def _chart(p: Pen, ink, accent) -> None:
    """Barres croissantes — la preuve chiffrée, sans chiffre écrit."""
    p.rect((0.16, 0.62, 0.34, 0.88), ink)
    p.rect((0.41, 0.44, 0.59, 0.88), ink)
    p.rect((0.66, 0.20, 0.84, 0.88), accent)


def _gift(p: Pen, ink, accent) -> None:
    """Cadeau — l'offre, le bonus."""
    p.rect((0.14, 0.36, 0.86, 0.88), ink, 0.03)
    p.rect((0.10, 0.26, 0.90, 0.40), accent, 0.03)
    p.rect((0.44, 0.26, 0.56, 0.88), accent)
    p.arc((0.20, 0.10, 0.52, 0.32), 0, 200, accent, 0.045)
    p.arc((0.48, 0.10, 0.80, 0.32), 340, 180, accent, 0.045)


def _person(p: Pen, ink, accent) -> None:
    """Buste — la personne qui parle, le client."""
    p.circle(0.50, 0.30, 0.18, ink)
    p.poly([(0.18, 0.92), (0.26, 0.62), (0.74, 0.62), (0.82, 0.92)], ink)
    p.poly([(0.42, 0.62), (0.58, 0.62), (0.50, 0.80)], accent)


def _mirror(p: Pen, ink, accent) -> None:
    """Avant / après — deux moitiés séparées par une arête franche."""
    p.poly([(0.12, 0.16), (0.48, 0.16), (0.48, 0.88), (0.12, 0.88)], ink)
    p.poly([(0.52, 0.16), (0.88, 0.16), (0.88, 0.88), (0.52, 0.88)], accent)
    p.circle(0.30, 0.42, 0.11, accent)
    p.circle(0.70, 0.42, 0.11, ink)


def _shirt(p: Pen, ink, accent) -> None:
    """Vêtement — mode, taille, matière."""
    p.poly([(0.30, 0.18), (0.42, 0.14), (0.58, 0.14), (0.70, 0.18),
            (0.88, 0.34), (0.76, 0.46), (0.74, 0.88), (0.26, 0.88),
            (0.24, 0.46), (0.12, 0.34)], ink)
    p.poly([(0.42, 0.14), (0.50, 0.30), (0.58, 0.14)], accent)


def _shoe(p: Pen, ink, accent) -> None:
    """Chaussure — confort, usage quotidien."""
    p.poly([(0.10, 0.44), (0.36, 0.44), (0.56, 0.60), (0.88, 0.64),
            (0.90, 0.78), (0.10, 0.78)], ink)
    p.rect((0.10, 0.78, 0.90, 0.86), accent, 0.02)


def _lock(p: Pen, ink, accent) -> None:
    """Cadenas — exclusivité, accès, paiement sécurisé."""
    p.arc((0.30, 0.14, 0.70, 0.54), 180, 360, ink, 0.075)
    p.rect((0.20, 0.44, 0.80, 0.86), ink, 0.05)
    p.circle(0.50, 0.64, 0.085, accent)


def _door(p: Pen, ink, accent) -> None:
    """Porte qui s'ouvre — l'opportunité (repli générique)."""
    p.rect((0.16, 0.12, 0.84, 0.90), ink, 0.02)
    p.poly([(0.52, 0.18), (0.80, 0.26), (0.80, 0.84), (0.52, 0.90)], accent)
    p.circle(0.58, 0.56, 0.045, ink)


PICTOGRAMS: dict[str, Callable[[Pen, tuple, tuple], None]] = {
    "box": _box, "bottle": _bottle, "jar": _jar, "tube": _tube, "bag": _bag,
    "cart": _cart, "tag": _tag, "coins": _coins, "hand": _hand,
    "thumb_up": _thumb_up, "star": _star, "heart": _heart, "check": _check,
    "cross": _cross, "clock": _clock, "calendar": _calendar, "truck": _truck,
    "phone": _phone, "chat": _chat, "leaf": _leaf, "drop": _drop,
    "flame": _flame, "sparkle": _sparkle, "shield": _shield,
    "magnifier": _magnifier, "arrow_up": _arrow_up, "chart": _chart,
    "gift": _gift, "person": _person, "mirror": _mirror, "shirt": _shirt,
    "shoe": _shoe, "lock": _lock, "door": _door,
}

DEFAULT_PICTOGRAM = "sparkle"


# --------------------------------------------------------------------------- #
# Résolution nom d'objet -> pictogramme
#
# Le planner (LLM ou heuristique) décrit ses objets en langage naturel, en
# anglais comme en français. On mappe ces mots vers la découpe la plus proche.
# L'ordre compte: les règles les plus spécifiques d'abord.
# --------------------------------------------------------------------------- #
_KEYWORD_RULES: list[tuple[str, str]] = [
    ("thumb_up", r"thumb|pouce|like|approv|recommand|satisfait|content"),
    ("truck", r"truck|van|deliver|livrais|livré|livre[rz]|colis en route|shipping|"
              r"courier|transport|exp[ée]di|acheminement|logistique|fret|camion|"
              r"livreur|coursier"),
    ("box", r"\bbox\b|carton|parcel|package|colis|packaging|emballage|coffret|"
            r"stock|inventaire|entrep[ôo]t|r[ée]serve"),
    ("bottle", r"bottle|flacon|bouteille|spray|vaporis|parfum|shampo|serum|sérum|"
               r"boisson|jus\b|sirop"),
    ("jar", r"\bjar\b|\bpot\b|crème|creme|cream|baume|balm|masque|mask|beurre|"
            r"pommade|gommage"),
    ("tube", r"tube|dentifrice|gel\b|lotion|mascara|rouge à lèvres|pommade"),
    ("bag", r"\bbag\b|sachet|pouch|sac\b|poche|valise|bagage|cabas"),
    ("cart", r"\bcarts?\b|basket|panier|caddie|trolley|commande|checkout|achat|acheter|"
             r"boutique|magasin|shop|vendre|vente"),
    ("tag", r"tag\b|étiquette|etiquette|label|price|prix|tarif|promo|réduction|"
            r"reduction|discount|solde|co[ûu]t|abonnement|forfait|frais"),
    ("coins", r"coin|money|argent|banknote|billet|cash|budget|euro|dollar|franc|"
              r"payer|paiement|économ|econom|salaire|revenu|gain|marge|"
              r"b[ée]n[ée]fice|capital|investi|[ée]pargne|virement|transf[eè]r|"
              r"facture|monnaie|fcfa|cfa|mobile money|portefeuille|wallet|"
              r"cagnotte|richesse|riche|fortune|\bcartes?\b|\bcards?\b|bancaire|"
              r"banques?\b|\bbank\b|ch[èe]que"),
    ("hand", r"hand|main\b|paume|palm|geste|tenir|holding|grasp|doigt|donner|"
             r"recevoir|re[çc]oit|partager"),
    ("star", r"star|étoile|etoile|avis|review|note\b|rating|témoign|temoign|"
             r"client satisfait|r[ée]putation|qualit[ée]|excellence|premium|"
             r"meilleur|top\b|champion|r[ée]compense"),
    ("heart", r"heart|cœur|coeur|love|adore|favori|préfér|prefer|kiff|passion|"
              r"[ée]motion|bienveill|fid[èe]l"),
    ("check", r"check|coche|tick|valid|inclus|garanti ok|réussi|reussi|done|"
              r"resolved|solution|r[ée]soudre|corrig|conforme|approuv|certifi|"
              r"v[ée]rifi|ok\b|c'est bon|termin[ée]"),
    ("cross", r"cross|croix|erreur|problem|problème|probleme|éviter|eviter|jamais|"
              r"arnaque|fail|[ée]chec|refus|interdit|faux|piège|piege|danger|"
              r"perte|perdre|attention"),
    ("clock", r"clock|montre|horloge|temps|time|minute|heure|rapide|vite|urgence|"
              r"dernier jour|d[ée]lai|attente|imm[ée]diat|instantan|maintenant|"
              r"secondes?"),
    ("calendar", r"calendar|calendrier|date|jour\b|semaine|mois\b|ann[ée]e|routine|"
                 r"planning|agenda|[ée]ch[ée]ance|rendez-vous|programme"),
    ("phone", r"phone|smartphone|téléphone|telephone|mobile|écran|ecran|whatsapp|"
              r"\bdm\b|insta|application|\bapp\b|sms|appel|num[ée]ro|en ligne|"
              r"internet|site|plateforme|r[ée]seau"),
    ("chat", r"chat|bubble|bulle|message|question|commentaire|comment|discussion|"
             r"témoignage|conversation|parler|\bdire\b|expliqu|[ée]change|r[ée]ponse|"
             r"support|conseil"),
    ("leaf", r"leaf|feuille|plant|plante|natur|bio|végét|veget|ingrédient|"
             r"ingredient|composition|[ée]colo|durable|croissance naturelle|graine"),
    ("drop", r"drop|goutte|water|\beau\b|hydrat|liquid|liquide|huile|\boil\b|"
             r"texture|essence|source|peau|sueur"),
    ("flame", r"flame|feu|flamme|hot|chaud|tendance|trend|viral|cartonne|explos|"
              r"énergie|energie|motivation|urgent|buzz"),
    ("sparkle", r"sparkle|shine|éclat|eclat|brill|glow|résultat|resultat|effet|"
                r"magic|waouh|wow|transformation r[ée]ussie|nouveau|surprise"),
    ("shield", r"shield|bouclier|garantie|guarantee|sécur|secur|protect|risque|"
               r"rembours|assurance|confiance|fiable|s[ûu]r\b|sain|d[ée]fense|"
               r"conformit[ée]|kyc"),
    ("magnifier", r"magnif|loupe|zoom|détail|detail|compar|analys|inspect|"
                  r"regarde de près|recherche|trouver|examin|audit|d[ée]couvr"),
    ("arrow_up", r"arrow|flèche|fleche|\bup\b|monte|augment|progress|croissance|"
                 r"growth|améliore|ameliore|d[ée]colle|doubl|tripl|scale|"
                 r"[ée]volu|d[ée]velopp|objectif atteint"),
    ("chart", r"chart|graph|barre|courbe|stat|chiffre|donn[ée]e|"
              r"résultats mesur|performance|pourcentage|%|taux|mesure|bilan|"
              r"rapport|tableau"),
    ("gift", r"gift|cadeau|bonus|offert|free|gratuit|surprise|ruban|ribbon|"
             r"parrainage|avantage"),
    ("person", r"person|people|silhouette|client|utilisateur|user|femme|homme|"
               r"visage|face|customer|\bmoi\b|[ée]quipe|communaut[ée]|public|"
               r"abonn[ée]|audience|gens|monde|patron|entrepreneur"),
    ("mirror", r"mirror|miroir|avant|before|après|apres|after|transformation|"
               r"changement|comparaison|diff[ée]rence|contraste"),
    ("shirt", r"shirt|vêtement|vetement|robe|tshirt|t-shirt|pull|veste|clothes|"
              r"mode\b|taille|tissu|couture"),
    ("shoe", r"shoe|chaussure|basket\b|sneaker|semelle|\bpieds?\b"),
    ("lock", r"lock|cadenas|padlock|secret|exclusi|accès|acces|privé|prive|"
             r"verrou|mot de passe|code\b|otp|bloqu|ferm[ée]|confidentiel"),
    ("door", r"door|porte|opportunit|entrée|entree|ouvre|open path|seuil|"
             r"acc[ée]der|d[ée]marrer|commencer|d[ée]but|lancer"),
]

_COMPILED_RULES = [(name, re.compile(pattern, re.I)) for name, pattern in _KEYWORD_RULES]


#: Mots vides: ils ne doivent JAMAIS décider d'une découpe.
_STOPWORDS = frozenset("""
le la les un une des du de d au aux et ou mais donc or ni car a à en dans sur
sous pour par avec sans vers chez que qui quoi dont ce cet cette ces mon ton
son notre votre leur mes tes ses nos vos leurs il elle ils elles on nous vous
je tu me te se y est sont était être avoir fait faire plus moins très trop
the a an of in on at to for with and or but from is are was were be been this
that these those it its my your his her our their
""".split())


#: Un mot isolé n'est reconnu que si la règle couvre l'essentiel du mot, DEPUIS
#: SON DÉBUT. Le français décline par la fin (livraison/livraisons, adore/
#: adorent), jamais par le début: un préfixe long est donc un vrai indice, alors
#: qu'un fragment interne est presque toujours un faux ami — « franc » dans
#: « franchement », « vite » dans « éviter », « port » dans « important ».
_TOKEN_COVERAGE = 0.62


def _match_single_word(word: str) -> Optional[str]:
    """Pictogramme d'un MOT isolé, ou None si aucune règle ne le couvre vraiment."""
    best: Optional[tuple[float, str]] = None
    for pictogram, pattern in _COMPILED_RULES:
        m = pattern.search(word)
        if not m or m.start() != 0:
            continue
        coverage = (m.end() - m.start()) / max(1, len(word))
        if coverage < _TOKEN_COVERAGE:
            continue
        if best is None or coverage > best[0]:
            best = (coverage, pictogram)
    return best[1] if best else None


def resolve_pictogram_ex(name: str) -> tuple[str, bool]:
    """(pictogramme, correspondance_réelle) pour le mot ou groupe de mots *name*.

    RÈGLE PRODUIT: une pièce de collage doit amener à l'écran CE QUE LA PERSONNE
    DIT. Tant qu'aucune règle ne reconnaît le mot, on ne doit pas inventer une
    découpe au hasard — l'ancien repli tirait une forme par empreinte du mot,
    et le montage affichait une chaussure pendant qu'on parlait de garantie.

    Le second membre du tuple dit si la découpe a un SENS: l'appelant peut alors
    écarter l'objet plutôt que de montrer n'importe quoi (voir
    `collage_concept_planner`).
    """
    text = (name or "").strip()
    if not text:
        return DEFAULT_PICTOGRAM, False
    lowered = text.lower()
    if lowered in PICTOGRAMS:
        return lowered, True
    tokens = [t for t in re.findall(r"[A-Za-zÀ-ÿ]{2,}", lowered)
              if t not in _STOPWORDS]

    # 1) MOT ISOLÉ — c'est le cas du texte prononcé: on exige que la règle
    #    couvre le mot depuis son début (voir _match_single_word).
    if len(tokens) <= 1:
        word = tokens[0] if tokens else lowered
        hit = _match_single_word(word)
        return (hit, True) if hit else (DEFAULT_PICTOGRAM, False)

    # 2) GROUPE DE MOTS ("bank card", "pot de crème") — c'est le cas des objets
    #    nommés par le planner: la règle la plus spécifique gagne sur l'ensemble.
    for pictogram, pattern in _COMPILED_RULES:
        if pattern.search(text):
            return pictogram, True
    # 3) Puis mot à mot, avec la même exigence de couverture. On garde le mot le
    #    plus LONG qui déclenche: c'est le plus porteur de sens.
    best: Optional[tuple[int, str]] = None
    for token in tokens:
        hit = _match_single_word(token)
        if hit and (best is None or len(token) > best[0]):
            best = (len(token), hit)
    if best is not None:
        return best[1], True
    return DEFAULT_PICTOGRAM, False


def resolve_pictogram(name: str) -> str:
    """Pictogramme le plus proche du mot *name* (FR ou EN).

    Sans correspondance, renvoie la découpe NEUTRE (`DEFAULT_PICTOGRAM`) et non
    une forme tirée au sort: mieux vaut un éclat abstrait qu'une chaussure sur
    une phrase qui parle de virement.
    """
    return resolve_pictogram_ex(name)[0]


# --------------------------------------------------------------------------- #
# Rendu « papier découpé »
# --------------------------------------------------------------------------- #
def _torn_mask(w: int, h: int, seed: int, roughness: float = 0.030) -> Image.Image:
    """Masque d'une feuille aux bords IRRÉGULIERS (découpe aux ciseaux).

    Un rectangle net fait « forme vectorielle »; le bord légèrement accidenté
    fait « papier réellement découpé ». Le bruit est déterministe (seed), donc
    la même pièce est identique d'un rendu à l'autre.
    """
    import numpy as np

    rng = np.random.default_rng(seed)
    steps = 26
    span = min(w, h)
    jitter = roughness * span
    pts: list[tuple[float, float]] = []
    inset = jitter * 1.4
    corners = [(inset, inset), (w - inset, inset), (w - inset, h - inset), (inset, h - inset)]
    for i in range(4):
        x0, y0 = corners[i]
        x1, y1 = corners[(i + 1) % 4]
        for s in range(steps):
            f = s / steps
            nx, ny = -(y1 - y0), (x1 - x0)
            norm = math.hypot(nx, ny) or 1.0
            off = float(rng.normal(0.0, jitter * 0.45))
            pts.append((x0 + (x1 - x0) * f + nx / norm * off,
                        y0 + (y1 - y0) * f + ny / norm * off))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(max(1.0, span * 0.004)))


def _halftone(img: Image.Image, strength: float, seed: int) -> Image.Image:
    """Trame de points — le rappel « photo noir & blanc tramée » du style."""
    import numpy as np

    if strength <= 0:
        return img
    arr = np.array(img, dtype=np.float32)
    ys, xs = np.mgrid[0:img.height, 0:img.width]
    phase = (seed % 7) * 0.4
    dots = ((np.sin(xs / 3.0 + phase) * np.sin(ys / 3.0 + phase)) > 0.40).astype(np.float32)
    arr[..., :3] *= (1.0 - strength * dots[..., None])
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")


def render_cutout(pictogram: str, width: int, height: int, *,
                  paper_color: tuple, ink_color: tuple, accent_color: tuple,
                  seed: int = 0, halftone: float = 0.16,
                  tilt: float = 0.0) -> Image.Image:
    """Une pièce de collage: le pictogramme posé sur son papier déchiré.

    Renvoie un calque RGBA transparent hors de la découpe, directement
    composable par `CollageVideoService`.
    """
    width, height = max(8, int(width)), max(8, int(height))
    sheet = Image.new("RGBA", (width, height), tuple(paper_color))
    sheet = _halftone(sheet, halftone, seed)

    glyph = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pen = Pen(ImageDraw.Draw(glyph), width, height)
    inset = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    inset_pen = Pen(ImageDraw.Draw(inset), int(width * 0.74), int(height * 0.74))
    _ = inset_pen  # le tracé se fait dans la boîte pleine, marge gérée ci-dessous

    # Le pictogramme occupe 74 % de la feuille: la marge de papier autour est ce
    # qui donne l'impression d'un élément COLLÉ, pas d'une icône plein cadre.
    inner_w, inner_h = int(width * 0.74), int(height * 0.74)
    inner = Image.new("RGBA", (max(8, inner_w), max(8, inner_h)), (0, 0, 0, 0))
    draw_pictogram(pictogram, inner, ink_color, accent_color)
    glyph.alpha_composite(inner, ((width - inner.width) // 2, (height - inner.height) // 2))
    sheet.alpha_composite(glyph)

    sheet.putalpha(_torn_mask(width, height, seed or 1))
    if abs(tilt) > 0.01:
        sheet = sheet.rotate(tilt, expand=True, resample=Image.BICUBIC)
    return sheet


def draw_pictogram(name: str, canvas: Image.Image, ink_color: tuple,
                   accent_color: tuple) -> Image.Image:
    """Dessine *name* sur *canvas* (RGBA, modifié en place) et le renvoie."""
    fn = PICTOGRAMS.get(name) or PICTOGRAMS[DEFAULT_PICTOGRAM]
    pen = Pen(ImageDraw.Draw(canvas), canvas.width, canvas.height)
    fn(pen, tuple(ink_color), tuple(accent_color))
    return canvas


def pictogram_names() -> list[str]:
    return sorted(PICTOGRAMS)


# --------------------------------------------------------------------------- #
def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Planche des pictogrammes papier")
    ap.add_argument("--preview", metavar="PNG", help="écrit une planche de contrôle")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)

    if args.list or not args.preview:
        for name in pictogram_names():
            print(name)
        return 0

    names = pictogram_names()
    cols, tile = 6, 260
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tile, rows * tile), (232, 69, 44))
    for i, name in enumerate(names):
        r, c = divmod(i, cols)
        piece = render_cutout(name, int(tile * 0.86), int(tile * 0.86),
                              paper_color=(247, 241, 227, 255),
                              ink_color=(29, 29, 27, 255),
                              accent_color=(242, 183, 5, 255),
                              seed=i + 1, tilt=(-3 if i % 2 else 3))
        sheet.paste(piece.convert("RGB"), (c * tile + 16, r * tile + 16),
                    piece.split()[3])
    os.makedirs(os.path.dirname(os.path.abspath(args.preview)) or ".", exist_ok=True)
    sheet.save(args.preview)
    print(f"[collage_shapes] {len(names)} pictogrammes -> {args.preview}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
