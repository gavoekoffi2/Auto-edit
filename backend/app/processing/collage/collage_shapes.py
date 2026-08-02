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
import hashlib
import math
import os
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
    """Pièces empilées — le coût, l'économie.

    Une pièce DEBOUT couronne la pile: trois ellipses seules se lisaient comme
    un empilement de galets, pas comme de la monnaie.
    """
    for i, y in enumerate((0.80, 0.68, 0.56)):
        p.ellipse((0.24, y - 0.072, 0.76, y + 0.072), accent if i % 2 else ink)
    p.circle(0.50, 0.30, 0.21, ink)
    p.circle(0.50, 0.30, 0.115, accent)


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
    """Flamme — ce qui cartonne, la tendance.

    Silhouette ASYMÉTRIQUE à langues latérales, pas une goutte inclinée: la
    version précédente réutilisait le même `_teardrop` que `drop`, si bien que
    « ça cartonne » et « hydratation » produisaient exactement la même pièce.
    Deux idées différentes ne doivent jamais tomber sur le même dessin.
    """
    p.poly([(0.50, 0.04), (0.63, 0.25), (0.60, 0.37), (0.73, 0.31),
            (0.79, 0.52), (0.73, 0.72), (0.58, 0.88), (0.40, 0.88),
            (0.25, 0.71), (0.23, 0.48), (0.34, 0.33), (0.41, 0.44),
            (0.42, 0.22)], ink)
    p.poly([(0.50, 0.40), (0.61, 0.57), (0.57, 0.75), (0.44, 0.80),
            (0.37, 0.62), (0.46, 0.52)], accent)


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


# --------------------------------------------------------------------------- #
# Vocabulaire ÉLARGI — le monde dont les gens parlent vraiment
#
# La première version couvrait le discours e-commerce (colis, prix, avis…).
# Dès que quelqu'un parlait d'une voiture, d'une maison, d'un ordinateur ou
# d'un rendez-vous, aucune découpe ne correspondait et le résolveur retombait
# sur une forme ARBITRAIRE: on parlait d'une voiture, la scène montrait un
# flacon. Ces pictogrammes ferment ce trou, avec deux priorités:
#
#   * les objets du quotidien les plus prononcés en français parlé;
#   * les objets nommés par les bibliothèques de métaphores (`collage_profiles`)
#     qui n'avaient encore aucune découpe (pont, graine, engrenage, sablier…).
# --------------------------------------------------------------------------- #
def _car(p: Pen, ink, accent) -> None:
    """Voiture — trajet, transport, achat automobile."""
    p.poly([(0.06, 0.62), (0.18, 0.62), (0.30, 0.40), (0.68, 0.40),
            (0.82, 0.62), (0.94, 0.62), (0.94, 0.76), (0.06, 0.76)], ink)
    p.poly([(0.33, 0.44), (0.48, 0.44), (0.48, 0.60), (0.26, 0.60)], accent)
    p.poly([(0.52, 0.44), (0.66, 0.44), (0.76, 0.60), (0.52, 0.60)], accent)
    p.circle(0.28, 0.78, 0.095, ink)
    p.circle(0.72, 0.78, 0.095, ink)
    p.circle(0.28, 0.78, 0.040, accent)
    p.circle(0.72, 0.78, 0.040, accent)


def _house(p: Pen, ink, accent) -> None:
    """Maison — logement, loyer, chez soi, famille."""
    p.poly([(0.50, 0.10), (0.94, 0.46), (0.06, 0.46)], accent)
    p.rect((0.16, 0.46, 0.84, 0.90), ink, 0.02)
    p.rect((0.42, 0.62, 0.58, 0.90), accent, 0.01)
    p.rect((0.24, 0.54, 0.36, 0.66), accent, 0.01)


def _building(p: Pen, ink, accent) -> None:
    """Immeuble / boutique / entreprise — le local, la société."""
    p.rect((0.14, 0.18, 0.56, 0.90), ink, 0.02)
    p.rect((0.58, 0.44, 0.88, 0.90), accent, 0.02)
    for y in (0.28, 0.44, 0.60, 0.74):
        for x in (0.20, 0.32, 0.44):
            p.rect((x, y, x + 0.07, y + 0.08), accent, 0.01)


def _key(p: Pen, ink, accent) -> None:
    """Clé — accès, solution, ce qui débloque."""
    p.circle(0.28, 0.34, 0.21, ink)
    p.circle(0.28, 0.34, 0.085, accent)
    p.line([(0.40, 0.46), (0.86, 0.88)], ink, 0.080)
    p.line([(0.64, 0.58), (0.54, 0.72)], accent, 0.050)
    p.line([(0.76, 0.69), (0.66, 0.83)], accent, 0.050)


def _laptop(p: Pen, ink, accent) -> None:
    """Ordinateur — le site, le travail, la formation en ligne."""
    p.rect((0.22, 0.16, 0.78, 0.64), ink, 0.02)
    p.rect((0.27, 0.22, 0.73, 0.58), accent, 0.015)
    p.poly([(0.10, 0.66), (0.90, 0.66), (0.96, 0.80), (0.04, 0.80)], ink)
    p.rect((0.42, 0.69, 0.58, 0.74), accent, 0.01)


def _cup(p: Pen, ink, accent) -> None:
    """Tasse — café, pause, boisson chaude."""
    p.poly([(0.22, 0.36), (0.68, 0.36), (0.61, 0.86), (0.29, 0.86)], ink)
    p.rect((0.22, 0.36, 0.68, 0.45), accent, 0.02)
    p.arc((0.64, 0.42, 0.92, 0.68), 300, 60, accent, 0.050)
    p.line([(0.38, 0.26), (0.38, 0.14)], accent, 0.030)
    p.line([(0.52, 0.24), (0.52, 0.10)], accent, 0.030)


def _plate(p: Pen, ink, accent) -> None:
    """Assiette — repas, cuisine, restaurant, alimentation."""
    p.circle(0.52, 0.54, 0.34, ink)
    p.circle(0.52, 0.54, 0.21, accent)
    p.rect((0.04, 0.18, 0.10, 0.88), accent, 0.02)
    p.rect((0.92, 0.18, 0.98, 0.88), accent, 0.02)


def _plane(p: Pen, ink, accent) -> None:
    """Avion en papier — voyage, départ, expédition lointaine."""
    p.poly([(0.06, 0.46), (0.94, 0.10), (0.54, 0.90), (0.44, 0.58)], ink)
    p.poly([(0.44, 0.58), (0.94, 0.10), (0.62, 0.68)], accent)


def _wallet(p: Pen, ink, accent) -> None:
    """Portefeuille — budget, dépense, ce qu'on sort de sa poche."""
    p.rect((0.10, 0.26, 0.90, 0.80), ink, 0.05)
    p.rect((0.10, 0.26, 0.90, 0.40), accent, 0.05)
    p.rect((0.56, 0.46, 0.94, 0.64), accent, 0.03)
    p.circle(0.75, 0.55, 0.048, ink)


def _book(p: Pen, ink, accent) -> None:
    """Livre ouvert — formation, méthode, savoir."""
    p.poly([(0.08, 0.24), (0.48, 0.34), (0.48, 0.86), (0.08, 0.76)], ink)
    p.poly([(0.92, 0.24), (0.52, 0.34), (0.52, 0.86), (0.92, 0.76)], accent)
    p.line([(0.50, 0.34), (0.50, 0.86)], accent, 0.022)


def _camera(p: Pen, ink, accent) -> None:
    """Caméra — la vidéo, le tournage, le contenu."""
    p.rect((0.08, 0.30, 0.86, 0.80), ink, 0.05)
    p.rect((0.32, 0.20, 0.56, 0.32), ink, 0.03)
    p.circle(0.47, 0.55, 0.18, accent)
    p.circle(0.47, 0.55, 0.085, ink)
    p.circle(0.76, 0.41, 0.038, accent)


def _envelope(p: Pen, ink, accent) -> None:
    """Enveloppe — message, courrier, contact."""
    p.rect((0.08, 0.28, 0.92, 0.76), ink, 0.02)
    p.poly([(0.08, 0.28), (0.92, 0.28), (0.50, 0.60)], accent)


def _sun(p: Pen, ink, accent) -> None:
    """Soleil — la journée, l'été, l'énergie."""
    p.circle(0.50, 0.50, 0.25, ink)
    for i in range(8):
        angle = i * math.pi / 4
        p.line([(0.50 + 0.33 * math.cos(angle), 0.50 + 0.33 * math.sin(angle)),
                (0.50 + 0.45 * math.cos(angle), 0.50 + 0.45 * math.sin(angle))],
               accent, 0.042)


def _tree(p: Pen, ink, accent) -> None:
    """Arbre — la nature, la durée, ce qui pousse."""
    p.rect((0.44, 0.58, 0.56, 0.92), accent, 0.02)
    p.circle(0.50, 0.38, 0.29, ink)
    p.circle(0.32, 0.52, 0.16, ink)
    p.circle(0.68, 0.52, 0.16, ink)


def _pill(p: Pen, ink, accent) -> None:
    """Gélule — complément, médicament, cure."""
    p.rect((0.08, 0.36, 0.92, 0.64), ink, 0.14)
    p.rect((0.50, 0.36, 0.88, 0.64), accent, 0.14)
    p.rect((0.50, 0.36, 0.64, 0.64), accent)
    p.line([(0.50, 0.36), (0.50, 0.64)], ink, 0.022)


def _glasses(p: Pen, ink, accent) -> None:
    """Lunettes — la vue, le détail qu'on remarque."""
    p.circle(0.27, 0.52, 0.21, ink)
    p.circle(0.27, 0.52, 0.135, accent)
    p.circle(0.73, 0.52, 0.21, ink)
    p.circle(0.73, 0.52, 0.135, accent)
    p.line([(0.46, 0.50), (0.54, 0.50)], ink, 0.050)
    p.line([(0.07, 0.44), (0.02, 0.34)], ink, 0.035)
    p.line([(0.93, 0.44), (0.98, 0.34)], ink, 0.035)


def _watch(p: Pen, ink, accent) -> None:
    """Montre — le rendez-vous, le temps qu'on suit."""
    p.rect((0.38, 0.06, 0.62, 0.32), accent, 0.03)
    p.rect((0.38, 0.68, 0.62, 0.94), accent, 0.03)
    p.circle(0.50, 0.50, 0.27, ink)
    p.circle(0.50, 0.50, 0.185, accent)
    p.line([(0.50, 0.50), (0.50, 0.37)], ink, 0.035)
    p.line([(0.50, 0.50), (0.61, 0.56)], ink, 0.035)


def _ring(p: Pen, ink, accent) -> None:
    """Bague — bijou, mariage, engagement."""
    p.circle(0.50, 0.66, 0.25, ink)
    p.circle(0.50, 0.66, 0.155, accent)
    p.poly([(0.50, 0.06), (0.68, 0.26), (0.50, 0.44), (0.32, 0.26)], accent)
    p.poly([(0.32, 0.26), (0.68, 0.26), (0.50, 0.44)], ink)


def _scissors(p: Pen, ink, accent) -> None:
    """Ciseaux — la coupe, le montage, ce qu'on retire."""
    p.line([(0.24, 0.10), (0.68, 0.60)], ink, 0.055)
    p.line([(0.76, 0.10), (0.32, 0.60)], ink, 0.055)
    p.circle(0.30, 0.76, 0.125, accent)
    p.circle(0.30, 0.76, 0.058, ink)
    p.circle(0.70, 0.76, 0.125, accent)
    p.circle(0.70, 0.76, 0.058, ink)


def _bulb(p: Pen, ink, accent) -> None:
    """Ampoule — l'idée, la solution, l'électricité."""
    p.circle(0.50, 0.40, 0.28, ink)
    p.rect((0.40, 0.64, 0.60, 0.80), accent, 0.02)
    p.rect((0.42, 0.80, 0.58, 0.90), accent, 0.02)
    # Filament en zigzag, pas en V: un chevron isolé se lit comme une LETTRE,
    # et le verrou de style interdit toute typographie dans une découpe.
    p.line([(0.38, 0.40), (0.45, 0.50), (0.53, 0.38), (0.61, 0.49)], accent, 0.032)


def _brain(p: Pen, ink, accent) -> None:
    """Cerveau — le mental, la compréhension, l'apprentissage."""
    p.circle(0.35, 0.40, 0.22, ink)
    p.circle(0.63, 0.38, 0.20, ink)
    p.circle(0.42, 0.62, 0.22, ink)
    p.circle(0.66, 0.62, 0.19, ink)
    p.line([(0.50, 0.24), (0.50, 0.80)], accent, 0.030)


def _eye(p: Pen, ink, accent) -> None:
    """Œil — la visibilité, ce qu'on remarque, l'attention."""
    p.poly(_lens((0.04, 0.50), (0.96, 0.50), 0.24), ink)
    p.circle(0.50, 0.50, 0.17, accent)
    p.circle(0.50, 0.50, 0.080, ink)


def _music(p: Pen, ink, accent) -> None:
    """Note — la musique, le son, l'ambiance."""
    p.rect((0.54, 0.12, 0.64, 0.72), ink)
    p.poly([(0.54, 0.12), (0.90, 0.04), (0.90, 0.24), (0.54, 0.32)], accent)
    p.circle(0.42, 0.74, 0.155, ink)


def _document(p: Pen, ink, accent) -> None:
    """Feuille — le contrat, la facture, le papier administratif."""
    p.poly([(0.18, 0.08), (0.64, 0.08), (0.84, 0.28), (0.84, 0.92),
            (0.18, 0.92)], ink)
    p.poly([(0.64, 0.08), (0.84, 0.28), (0.64, 0.28)], accent)
    for y in (0.46, 0.60, 0.74):
        p.rect((0.28, y, 0.72, y + 0.055), accent, 0.01)


def _folder(p: Pen, ink, accent) -> None:
    """Dossier — le classement, le projet, les fichiers."""
    p.poly([(0.08, 0.24), (0.40, 0.24), (0.48, 0.36), (0.92, 0.36),
            (0.92, 0.86), (0.08, 0.86)], ink)
    p.rect((0.16, 0.48, 0.84, 0.56), accent, 0.02)


def _graduation(p: Pen, ink, accent) -> None:
    """Toque — l'école, le diplôme, la formation validée."""
    p.poly([(0.50, 0.18), (0.96, 0.40), (0.50, 0.62), (0.04, 0.40)], ink)
    p.poly([(0.28, 0.50), (0.72, 0.50), (0.72, 0.74), (0.50, 0.82),
            (0.28, 0.74)], accent)
    p.line([(0.90, 0.44), (0.90, 0.74)], accent, 0.030)


def _briefcase(p: Pen, ink, accent) -> None:
    """Mallette — le travail, le business, le professionnel."""
    p.rect((0.08, 0.32, 0.92, 0.86), ink, 0.04)
    p.rect((0.08, 0.52, 0.92, 0.61), accent)
    p.arc((0.34, 0.14, 0.66, 0.44), 180, 360, accent, 0.050)
    p.rect((0.44, 0.50, 0.56, 0.63), accent, 0.02)


def _trophy(p: Pen, ink, accent) -> None:
    """Coupe — gagner, le meilleur, la récompense."""
    p.poly([(0.28, 0.12), (0.72, 0.12), (0.67, 0.50), (0.33, 0.50)], ink)
    p.arc((0.08, 0.14, 0.32, 0.46), 90, 270, accent, 0.048)
    p.arc((0.68, 0.14, 0.92, 0.46), 270, 90, accent, 0.048)
    p.rect((0.44, 0.50, 0.56, 0.70), ink)
    p.rect((0.26, 0.70, 0.74, 0.84), accent, 0.02)


def _dumbbell(p: Pen, ink, accent) -> None:
    """Haltère — le sport, l'effort, la salle."""
    p.rect((0.20, 0.43, 0.80, 0.57), ink, 0.03)
    p.rect((0.06, 0.28, 0.24, 0.72), accent, 0.04)
    p.rect((0.76, 0.28, 0.94, 0.72), accent, 0.04)


def _ball(p: Pen, ink, accent) -> None:
    """Ballon — le sport, le match, l'équipe."""
    p.circle(0.50, 0.50, 0.38, ink)
    p.poly([(0.50, 0.26), (0.70, 0.41), (0.62, 0.66), (0.38, 0.66),
            (0.30, 0.41)], accent)


def _wifi(p: Pen, ink, accent) -> None:
    """Ondes — le réseau, la connexion, internet."""
    p.arc((0.02, 0.20, 0.98, 1.16), 200, 340, ink, 0.055)
    p.arc((0.20, 0.40, 0.80, 1.00), 200, 340, ink, 0.060)
    p.arc((0.36, 0.58, 0.64, 0.86), 200, 340, accent, 0.070)
    p.circle(0.50, 0.84, 0.062, accent)


def _battery(p: Pen, ink, accent) -> None:
    """Batterie — l'autonomie, l'énergie qui reste."""
    p.rect((0.08, 0.32, 0.82, 0.68), ink, 0.04)
    p.rect((0.84, 0.44, 0.94, 0.56), ink, 0.02)
    p.rect((0.14, 0.38, 0.48, 0.62), accent, 0.02)


def _ladder(p: Pen, ink, accent) -> None:
    """Échelle — les étapes, la montée, la méthode."""
    p.rect((0.22, 0.06, 0.33, 0.94), ink, 0.02)
    p.rect((0.67, 0.06, 0.78, 0.94), ink, 0.02)
    for y in (0.20, 0.40, 0.60, 0.78):
        p.rect((0.22, y, 0.78, y + 0.07), accent, 0.01)


def _stairs(p: Pen, ink, accent) -> None:
    """Escalier — la progression par paliers."""
    p.poly([(0.08, 0.90), (0.08, 0.66), (0.36, 0.66), (0.36, 0.46),
            (0.64, 0.46), (0.64, 0.24), (0.92, 0.24), (0.92, 0.90)], ink)
    p.poly([(0.64, 0.24), (0.92, 0.24), (0.92, 0.40), (0.64, 0.40)], accent)


def _target(p: Pen, ink, accent) -> None:
    """Cible — l'objectif, le but visé."""
    p.circle(0.50, 0.50, 0.41, ink)
    p.circle(0.50, 0.50, 0.28, accent)
    p.circle(0.50, 0.50, 0.15, ink)
    p.circle(0.50, 0.50, 0.055, accent)


def _handshake(p: Pen, ink, accent) -> None:
    """Poignée de main — l'accord, le partenariat, la confiance."""
    p.rect((0.00, 0.44, 0.40, 0.56), ink, 0.03)
    p.rect((0.60, 0.44, 1.00, 0.56), accent, 0.03)
    p.poly([(0.50, 0.20), (0.80, 0.50), (0.50, 0.80), (0.20, 0.50)], ink)
    p.line([(0.36, 0.44), (0.54, 0.26)], accent, 0.030)
    p.line([(0.46, 0.74), (0.64, 0.56)], accent, 0.030)


def _rocket(p: Pen, ink, accent) -> None:
    """Fusée — le lancement, le décollage, la croissance rapide."""
    p.poly([(0.50, 0.04), (0.67, 0.32), (0.67, 0.70), (0.33, 0.70),
            (0.33, 0.32)], ink)
    p.poly([(0.33, 0.44), (0.14, 0.74), (0.33, 0.70)], accent)
    p.poly([(0.67, 0.44), (0.86, 0.74), (0.67, 0.70)], accent)
    p.circle(0.50, 0.36, 0.095, accent)
    p.poly([(0.40, 0.70), (0.60, 0.70), (0.50, 0.96)], accent)


def _gear(p: Pen, ink, accent) -> None:
    """Engrenage — le système, le fonctionnement, le réglage."""
    pts: list[Point] = []
    for i in range(16):
        angle = -math.pi / 2 + i * math.pi / 8
        r = 0.45 if i % 2 == 0 else 0.33
        pts.append((0.50 + r * math.cos(angle), 0.50 + r * math.sin(angle)))
    p.poly(pts, ink)
    p.circle(0.50, 0.50, 0.145, accent)


def _chain(p: Pen, ink, accent) -> None:
    """Maillons — le lien, la chaîne, ce qui tient ensemble."""
    p.arc((0.04, 0.30, 0.56, 0.70), 0, 360, ink, 0.070)
    p.arc((0.44, 0.30, 0.96, 0.70), 0, 360, accent, 0.070)


def _bridge(p: Pen, ink, accent) -> None:
    """Pont — le passage, ce qui relie deux côtés."""
    p.arc((0.08, 0.28, 0.92, 0.94), 180, 360, accent, 0.048)
    p.rect((0.02, 0.56, 0.98, 0.65), ink, 0.01)
    for x in (0.26, 0.50, 0.74):
        p.line([(x, 0.56), (x, 0.38)], accent, 0.028)
    p.rect((0.12, 0.65, 0.21, 0.92), ink)
    p.rect((0.79, 0.65, 0.88, 0.92), ink)


def _sprout(p: Pen, ink, accent) -> None:
    """Pousse — le début, la graine, ce qui commence à grandir."""
    p.line([(0.50, 0.86), (0.50, 0.40)], ink, 0.045)
    p.poly(_lens((0.20, 0.26), (0.50, 0.54), 0.11), accent)
    p.poly(_lens((0.80, 0.26), (0.50, 0.54), 0.11), ink)
    p.arc((0.28, 0.76, 0.72, 0.98), 180, 360, accent, 0.055)


def _brick(p: Pen, ink, accent) -> None:
    """Mur de briques — ce qui se construit pièce par pièce (ou s'écroule).

    Les joints verticaux ne sont pas décoratifs: des rangées pleines et
    régulières se lisent comme des LIGNES DE TEXTE, ce que le contrôle qualité
    rejette (et il a raison — le verrou de style interdit toute typographie).
    """
    for index, (top, shift) in enumerate(((0.20, 0.0), (0.44, 0.15), (0.68, 0.0))):
        fill = ink if index % 2 == 0 else accent
        x = 0.05 + shift
        while x < 0.93:
            p.rect((x, top, min(0.93, x + 0.25), top + 0.19), fill, 0.015)
            x += 0.29


def _megaphone(p: Pen, ink, accent) -> None:
    """Mégaphone — l'annonce, la communication, la portée."""
    p.poly([(0.08, 0.40), (0.42, 0.26), (0.42, 0.76), (0.08, 0.62)], ink)
    p.poly([(0.42, 0.18), (0.60, 0.12), (0.60, 0.90), (0.42, 0.84)], ink)
    p.arc((0.62, 0.30, 0.86, 0.72), 300, 60, accent, 0.045)
    p.arc((0.72, 0.18, 1.00, 0.84), 300, 60, accent, 0.038)


def _hourglass(p: Pen, ink, accent) -> None:
    """Sablier — le temps qui s'écoule, la fenêtre qui se ferme."""
    p.poly([(0.16, 0.08), (0.84, 0.08), (0.54, 0.50), (0.84, 0.92),
            (0.16, 0.92), (0.46, 0.50)], ink)
    p.poly([(0.26, 0.16), (0.74, 0.16), (0.52, 0.46), (0.48, 0.46)], accent)
    p.poly([(0.34, 0.86), (0.66, 0.86), (0.56, 0.66), (0.44, 0.66)], accent)


def _flag(p: Pen, ink, accent) -> None:
    """Drapeau — le repère atteint, le pays, l'étape franchie."""
    p.rect((0.18, 0.06, 0.28, 0.94), ink, 0.01)
    p.poly([(0.28, 0.14), (0.88, 0.26), (0.88, 0.58), (0.28, 0.46)], accent)


def _crown(p: Pen, ink, accent) -> None:
    """Couronne — le premium, le haut de gamme, le numéro un."""
    p.poly([(0.08, 0.72), (0.14, 0.24), (0.34, 0.52), (0.50, 0.16),
            (0.66, 0.52), (0.86, 0.24), (0.92, 0.72)], ink)
    p.rect((0.08, 0.72, 0.92, 0.88), accent, 0.02)


def _banknote(p: Pen, ink, accent) -> None:
    """Billet — l'argent liquide, le salaire, le paiement."""
    p.rect((0.04, 0.30, 0.96, 0.70), ink, 0.03)
    p.circle(0.50, 0.50, 0.135, accent)
    p.rect((0.10, 0.36, 0.19, 0.64), accent, 0.01)
    p.rect((0.81, 0.36, 0.90, 0.64), accent, 0.01)


def _card(p: Pen, ink, accent) -> None:
    """Carte bancaire — le paiement, l'abonnement, le compte."""
    p.rect((0.04, 0.28, 0.96, 0.74), ink, 0.05)
    p.rect((0.04, 0.36, 0.96, 0.48), accent)
    p.rect((0.12, 0.56, 0.32, 0.66), accent, 0.02)


def _globe(p: Pen, ink, accent) -> None:
    """Globe — l'international, l'ailleurs, le web."""
    p.circle(0.50, 0.50, 0.40, ink)
    p.arc((0.30, 0.10, 0.70, 0.90), 0, 360, accent, 0.038)
    p.line([(0.11, 0.50), (0.89, 0.50)], accent, 0.038)


def _pin(p: Pen, ink, accent) -> None:
    """Épingle — le lieu, l'adresse, l'endroit précis."""
    p.circle(0.50, 0.38, 0.29, ink)
    p.poly([(0.26, 0.54), (0.74, 0.54), (0.50, 0.94)], ink)
    p.circle(0.50, 0.38, 0.115, accent)


def _scale(p: Pen, ink, accent) -> None:
    """Balance — la comparaison, l'équilibre, le choix."""
    p.rect((0.46, 0.14, 0.54, 0.82), ink, 0.01)
    p.rect((0.26, 0.82, 0.74, 0.92), ink, 0.02)
    p.line([(0.08, 0.28), (0.92, 0.28)], ink, 0.035)
    p.arc((0.00, 0.24, 0.32, 0.56), 0, 180, accent, 0.048)
    p.arc((0.68, 0.24, 1.00, 0.56), 0, 180, accent, 0.048)


def _umbrella(p: Pen, ink, accent) -> None:
    """Parapluie — la protection, l'imprévu couvert."""
    p.poly([(0.04, 0.54), (0.12, 0.28), (0.30, 0.14), (0.50, 0.10),
            (0.70, 0.14), (0.88, 0.28), (0.96, 0.54)], ink)
    p.line([(0.50, 0.54), (0.50, 0.84)], accent, 0.045)
    p.arc((0.28, 0.76, 0.52, 0.94), 0, 180, accent, 0.045)


def _lightning(p: Pen, ink, accent) -> None:
    """Éclair — la rapidité, le choc, le déclic."""
    p.poly([(0.62, 0.04), (0.24, 0.56), (0.46, 0.56), (0.36, 0.96),
            (0.76, 0.44), (0.52, 0.44)], ink)


def _tools(p: Pen, ink, accent) -> None:
    """Marteau — les travaux, la réparation, le concret.

    Tête volontairement ASYMÉTRIQUE (panne fendue d'un côté): un marteau
    parfaitement symétrique sur un manche vertical se lit comme un « T ».
    """
    p.rect((0.44, 0.32, 0.58, 0.94), ink, 0.02)
    p.poly([(0.34, 0.10), (0.70, 0.10), (0.88, 0.20), (0.88, 0.32),
            (0.70, 0.38), (0.34, 0.38)], accent)
    p.poly([(0.34, 0.10), (0.34, 0.38), (0.12, 0.32), (0.20, 0.22),
            (0.12, 0.14)], accent)


def _pen(p: Pen, ink, accent) -> None:
    """Stylo — signer, écrire, décider noir sur blanc."""
    p.poly([(0.06, 0.94), (0.16, 0.66), (0.72, 0.06), (0.94, 0.26),
            (0.36, 0.86)], ink)
    p.poly([(0.06, 0.94), (0.16, 0.66), (0.36, 0.86)], accent)


def _mountain(p: Pen, ink, accent) -> None:
    """Montagne — l'objectif lointain, l'obstacle à franchir."""
    p.poly([(0.02, 0.86), (0.34, 0.26), (0.56, 0.60), (0.66, 0.42),
            (0.98, 0.86)], ink)
    p.poly([(0.34, 0.26), (0.47, 0.50), (0.21, 0.50)], accent)
    p.circle(0.78, 0.22, 0.10, accent)


def _road(p: Pen, ink, accent) -> None:
    """Route — le parcours, le chemin, la distance."""
    p.poly([(0.30, 0.06), (0.70, 0.06), (0.96, 0.94), (0.04, 0.94)], ink)
    for y in (0.16, 0.42, 0.70):
        p.rect((0.46, y, 0.54, y + 0.13), accent, 0.01)


def _cloud(p: Pen, ink, accent) -> None:
    """Nuage — le stockage en ligne, la météo, le flou."""
    p.circle(0.34, 0.52, 0.20, ink)
    p.circle(0.56, 0.44, 0.26, ink)
    p.circle(0.74, 0.56, 0.17, ink)
    p.rect((0.28, 0.52, 0.78, 0.72), ink, 0.06)
    p.circle(0.50, 0.58, 0.095, accent)


PICTOGRAMS: dict[str, Callable[[Pen, tuple, tuple], None]] = {
    # vocabulaire d'origine (discours e-commerce)
    "box": _box, "bottle": _bottle, "jar": _jar, "tube": _tube, "bag": _bag,
    "cart": _cart, "tag": _tag, "coins": _coins, "hand": _hand,
    "thumb_up": _thumb_up, "star": _star, "heart": _heart, "check": _check,
    "cross": _cross, "clock": _clock, "calendar": _calendar, "truck": _truck,
    "phone": _phone, "chat": _chat, "leaf": _leaf, "drop": _drop,
    "flame": _flame, "sparkle": _sparkle, "shield": _shield,
    "magnifier": _magnifier, "arrow_up": _arrow_up, "chart": _chart,
    "gift": _gift, "person": _person, "mirror": _mirror, "shirt": _shirt,
    "shoe": _shoe, "lock": _lock, "door": _door,
    # vocabulaire élargi (le monde dont les gens parlent vraiment)
    "car": _car, "house": _house, "building": _building, "key": _key,
    "laptop": _laptop, "cup": _cup, "plate": _plate, "plane": _plane,
    "wallet": _wallet, "book": _book, "camera": _camera, "envelope": _envelope,
    "sun": _sun, "tree": _tree, "pill": _pill, "glasses": _glasses,
    "watch": _watch, "ring": _ring, "scissors": _scissors, "bulb": _bulb,
    "brain": _brain, "eye": _eye, "music": _music, "document": _document,
    "folder": _folder, "graduation": _graduation, "briefcase": _briefcase,
    "trophy": _trophy, "dumbbell": _dumbbell, "ball": _ball, "wifi": _wifi,
    "battery": _battery, "ladder": _ladder, "stairs": _stairs,
    "target": _target, "handshake": _handshake, "rocket": _rocket,
    "gear": _gear, "chain": _chain, "bridge": _bridge, "sprout": _sprout,
    "brick": _brick, "megaphone": _megaphone, "hourglass": _hourglass,
    "flag": _flag, "crown": _crown, "banknote": _banknote, "card": _card,
    "globe": _globe, "pin": _pin, "scale": _scale, "umbrella": _umbrella,
    "lightning": _lightning, "tools": _tools, "pen": _pen,
    "mountain": _mountain, "road": _road, "cloud": _cloud,
}

DEFAULT_PICTOGRAM = "sparkle"


# --------------------------------------------------------------------------- #
# Résolution nom d'objet -> pictogramme
#
# Les règles mot → découpe vivent dans `collage_lexicon`: c'est le MÊME tableau
# qui sert à résoudre un nom d'objet et à repérer les choses nommées dans le
# transcript. Une seule table, donc aucune divergence possible entre « ce que
# le moteur sait dessiner » et « ce qu'il sait reconnaître dans le discours ».
# --------------------------------------------------------------------------- #
def resolve_strict(name: str) -> Optional[str]:
    """Découpe correspondant à *name*, ou **None** si aucune ne correspond.

    C'est la fonction que le moteur utilise. Un None n'est pas un échec: c'est
    l'information « je ne sais pas dessiner ça », qui permet au planner de
    remplacer l'objet par quelque chose qui, lui, illustre vraiment le propos.
    """
    from . import collage_lexicon

    pictogram = collage_lexicon.resolve(name)
    return pictogram if pictogram in PICTOGRAMS else None


def resolve_pictogram(name: str) -> str:
    """Pictogramme le plus proche de *name*, avec repli garanti (FR ou EN).

    Conservé pour les appelants qui ont besoin d'une forme quoi qu'il arrive.
    Le repli est STABLE (même mot → même forme) mais reste arbitraire: le
    pipeline passe par `resolve_strict` et ne s'y expose jamais.
    """
    text = (name or "").strip()
    if not text:
        return DEFAULT_PICTOGRAM
    pictogram = resolve_strict(text)
    if pictogram:
        return pictogram
    digest = hashlib.sha1(text.lower().encode("utf-8")).digest()[0]
    names = sorted(PICTOGRAMS)
    return names[digest % len(names)]


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
    """Trame de points — le rappel « photo noir & blanc tramée » du style.

    La période suit la TAILLE de la feuille au lieu d'être fixée en pixels. À
    période constante, une petite pièce recevait une trame fine (correcte) et
    une grande pièce une trame de gros pois: ça ne se lisait plus comme une
    impression tramée mais comme un motif à pois. Ici, toute pièce porte le
    même nombre de points d'un bord à l'autre — c'est ce qui fait « imprimé ».
    """
    import numpy as np

    if strength <= 0:
        return img
    arr = np.array(img, dtype=np.float32)
    ys, xs = np.mgrid[0:img.height, 0:img.width]
    span = min(img.width, img.height)
    #: ~52 points sur la largeur d'une pièce, borné pour rester visible sans
    #: virer au moiré sur les très petites découpes.
    period = max(3.4, min(9.0, span / 52.0))
    freq = 2.0 * math.pi / period
    phase = (seed % 7) * 0.4
    dots = ((np.sin(xs * freq + phase) * np.sin(ys * freq + phase)) > 0.40
            ).astype(np.float32)
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
