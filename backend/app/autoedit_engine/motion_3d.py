"""
STEP 6ter — MOTION DESIGN 3D PROCÉDURAL (aucun crédit image, aucun asset).

Le repli historique des scènes de motion design était un DESSIN AU TRAIT: des
lignes blanches tracées à l'écran. Sur un montage réel, ça ne « lit » pas —
c'est ce que le produit appelait « du motion design qui ne fonctionne pas ».

Ce module remplace ce repli par un vrai petit MOTEUR 3D logiciel:

  * primitives ombrées — prisme extrudé (polygone 2D extrudé en Z, faces
    latérales éclairées par leur normale) et sphère (normale par pixel,
    lambert + spéculaire + rim light);
  * une caméra (yaw/pitch + perspective faible) qui TOURNE légèrement pendant
    la scène: c'est la rotation qui fait lire le volume;
  * un studio (dégradé, halo, sol, ombre de contact floutée) par style;
  * une bibliothèque de MODÈLES (argent, croissance, fusée, bouclier…) composés
    à partir des primitives, indexés sur les icônes que le moteur détecte déjà
    dans le discours (``content.icon_for_text``) — donc l'objet 3D illustre ce
    que la personne dit, sans le moindre appel réseau;
  * plusieurs STYLES 3D (pâte à modeler, verre néon, chrome, isométrique,
    papier en relief) choisis par graine stable: deux vidéos différentes ne
    rendent pas le même 3D, un même job reste reproductible.

API publique:

    render_plate(icon, w, h, t=..., dur=..., style=..., accent=..., gold=...)
        -> Image RGBA de taille (w, h), prête à être posée par
           ``motion_design._paste_illustration`` exactement comme une
           illustration IA.

    select_style(seed_text)            -> nom de style 3D (stable par graine)
    style_for_family(family)           -> style 3D associé à une famille de preset
    has_model(icon) / model_names()    -> introspection de la bibliothèque
"""
from __future__ import annotations

import argparse
import hashlib
import math
import os
import sys
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

RGB = Tuple[int, int, int]
RGBA = Tuple[int, int, int, int]
Vec3 = Tuple[float, float, float]
Poly = List[Tuple[float, float]]

#: Suréchantillonnage du rendu (anti-aliasing). 2 = qualité/coût équilibrés.
SS = 2

#: Distance focale de la caméra (perspective faible: on veut du volume, pas du
#: fish-eye). Plus la valeur est grande, plus la projection est orthographique.
FOCAL = 4.2


# --------------------------------------------------------------------------- #
# Matériaux et styles
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Material:
    """Réponse lumineuse d'une surface (modèle Blinn-Phong simplifié)."""
    ambient: float = 0.34
    diffuse: float = 0.72
    spec: float = 0.22
    shininess: float = 24.0
    rim: float = 0.18
    rim_color: RGB = (255, 255, 255)
    #: Éclaircissement des arêtes vues de face (donne le « bord ciselé »).
    edge_light: float = 0.30


@dataclass(frozen=True)
class Style3D:
    """Une direction artistique 3D complète (studio + matériau + caméra)."""
    name: str
    label: str
    bg_top: RGB
    bg_bottom: RGB
    floor: RGB
    halo: RGB
    material: Material
    light: Vec3 = (-0.42, 0.62, 0.66)
    #: Caméra — yaw de base, amplitude et vitesse de la rotation, inclinaison.
    yaw_base: float = 0.0
    yaw_amp: float = 0.30
    yaw_speed: float = 0.24
    pitch: float = -0.16
    #: Ombre portée au sol.
    shadow_alpha: float = 96
    shadow_blur: float = 0.055
    #: Post-traitement.
    bloom: float = 0.0
    grain: float = 0.0
    #: Saturation appliquée aux couleurs de la palette (1.0 = telle quelle).
    saturate: float = 1.0
    #: Éclaircissement global des aplats (pâte à modeler = pastel).
    lift: float = 0.0
    #: Le halo derrière l'objet (0 = pas de halo).
    halo_strength: float = 0.55


_CLAY = Material(ambient=0.46, diffuse=0.66, spec=0.10, shininess=10.0,
                 rim=0.14, rim_color=(255, 246, 235), edge_light=0.22)
_GLASS = Material(ambient=0.38, diffuse=0.70, spec=0.50, shininess=44.0,
                  rim=0.42, rim_color=(150, 245, 255), edge_light=0.42)
_CHROME = Material(ambient=0.32, diffuse=0.64, spec=0.80, shininess=80.0,
                   rim=0.34, rim_color=(255, 255, 255), edge_light=0.52)
_ISO = Material(ambient=0.40, diffuse=0.80, spec=0.06, shininess=8.0,
                rim=0.06, rim_color=(255, 255, 255), edge_light=0.16)
_PAPER = Material(ambient=0.52, diffuse=0.56, spec=0.05, shininess=6.0,
                  rim=0.08, rim_color=(255, 250, 240), edge_light=0.18)


STYLES: List[Style3D] = [
    # 1. Pâte à modeler — le look « 3D publicitaire » doux et chaleureux.
    Style3D(
        name="clay_studio", label="Pâte à modeler",
        bg_top=(28, 32, 52), bg_bottom=(14, 16, 30),
        floor=(38, 42, 64), halo=(255, 214, 170),
        material=_CLAY, light=(-0.40, 0.66, 0.64),
        yaw_amp=0.34, yaw_speed=0.22, pitch=-0.17,
        shadow_alpha=108, shadow_blur=0.065, lift=0.12, saturate=0.92,
        halo_strength=0.60,
    ),
    # 2. Verre néon — studio sombre, arêtes qui brillent, très « tech ».
    Style3D(
        name="glass_neon", label="Verre néon",
        bg_top=(12, 14, 34), bg_bottom=(6, 8, 18),
        floor=(18, 22, 48), halo=(90, 210, 255),
        material=_GLASS, light=(-0.50, 0.55, 0.67),
        yaw_amp=0.42, yaw_speed=0.28, pitch=-0.14,
        shadow_alpha=120, shadow_blur=0.05, bloom=0.38, saturate=1.18,
        halo_strength=0.50,
    ),
    # 3. Chrome — métal poli, spéculaire dur, premium/finance.
    Style3D(
        name="chrome_metal", label="Chrome",
        bg_top=(22, 24, 30), bg_bottom=(9, 10, 14),
        floor=(30, 33, 42), halo=(200, 220, 255),
        material=_CHROME, light=(-0.55, 0.60, 0.58),
        yaw_amp=0.46, yaw_speed=0.30, pitch=-0.12,
        shadow_alpha=132, shadow_blur=0.045, bloom=0.35, saturate=1.05,
        halo_strength=0.50,
    ),
    # 4. Isométrique — caméra fixe à 35°, aplats francs, lecture immédiate.
    Style3D(
        name="iso_blocks", label="Isométrique",
        bg_top=(24, 30, 46), bg_bottom=(13, 17, 28),
        floor=(32, 40, 60), halo=(255, 235, 190),
        material=_ISO, light=(-0.46, 0.68, 0.57),
        yaw_base=0.52, yaw_amp=0.10, yaw_speed=0.16, pitch=-0.30,
        shadow_alpha=118, shadow_blur=0.035, saturate=1.10,
        halo_strength=0.35,
    ),
    # 5. Papier en relief — passerelle assumée avec le moteur de collage.
    Style3D(
        name="paper_relief", label="Papier en relief",
        bg_top=(244, 238, 226), bg_bottom=(226, 217, 200),
        floor=(214, 205, 188), halo=(255, 252, 244),
        material=_PAPER, light=(-0.38, 0.70, 0.60),
        yaw_amp=0.26, yaw_speed=0.18, pitch=-0.13,
        shadow_alpha=74, shadow_blur=0.075, grain=0.05, saturate=0.96,
        lift=0.06, halo_strength=0.30,
    ),
]

STYLES_BY_NAME: Dict[str, Style3D] = {s.name: s for s in STYLES}
DEFAULT_STYLE = STYLES[0].name

#: Style 3D par famille de preset motion design (`motion_presets.PRESETS`).
#: Chaque famille garde ainsi son identité couleur ET reçoit un rendu 3D
#: cohérent avec elle — pas de 3D « générique » plaqué sur tout.
FAMILY_STYLE: Dict[str, str] = {
    "clean_fintech": "chrome_metal",
    "neon_social": "glass_neon",
    "african_premium": "clay_studio",
    "minimal_creator": "glass_neon",
    "kinetic_education": "iso_blocks",
    "sunset_vibes": "clay_studio",
    "electric_lime": "glass_neon",
    "editorial_paper": "paper_relief",
    "board_pitch": "clay_studio",
    # Familles 3D natives (voir motion_presets).
    "clay_3d": "clay_studio",
    "glass_3d": "glass_neon",
    "chrome_3d": "chrome_metal",
    "iso_3d": "iso_blocks",
    "paper_3d": "paper_relief",
}


def style_for(name: Optional[str]) -> Style3D:
    """Style 3D par nom, avec repli sur le style signature."""
    if name and name in STYLES_BY_NAME:
        return STYLES_BY_NAME[name]
    return STYLES_BY_NAME[DEFAULT_STYLE]


def style_for_family(family: Optional[str]) -> Optional[str]:
    """Nom du style 3D associé à une famille de preset (None si inconnue)."""
    return FAMILY_STYLE.get(family or "")


def select_style(seed_text: Optional[str]) -> str:
    """Style 3D stable par graine — deux vidéos, deux rendus différents."""
    if not seed_text:
        return DEFAULT_STYLE
    digest = hashlib.md5(str(seed_text).encode("utf-8")).hexdigest()
    return STYLES[int(digest, 16) % len(STYLES)].name


# --------------------------------------------------------------------------- #
# Palette d'un plan — les modèles nomment des RÔLES, pas des couleurs
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Palette3D:
    primary: RGB
    secondary: RGB
    light: RGB
    dark: RGB
    shade: RGB

    def get(self, role: str) -> RGB:
        return getattr(self, role, self.primary)


def _mix(a: RGB, b: RGB, k: float) -> RGB:
    return (int(a[0] + (b[0] - a[0]) * k),
            int(a[1] + (b[1] - a[1]) * k),
            int(a[2] + (b[2] - a[2]) * k))


def _saturate(c: RGB, k: float) -> RGB:
    if abs(k - 1.0) < 1e-3:
        return c
    lum = 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
    return tuple(int(max(0, min(255, lum + (v - lum) * k))) for v in c)  # type: ignore[return-value]


def build_palette(style: Style3D, accent: Sequence[int],
                  gold: Sequence[int]) -> Palette3D:
    """Palette d'objets dérivée des couleurs d'encre de la famille de preset."""
    acc = _saturate((int(accent[0]), int(accent[1]), int(accent[2])), style.saturate)
    gld = _saturate((int(gold[0]), int(gold[1]), int(gold[2])), style.saturate)
    if style.lift > 0:
        acc = _mix(acc, (255, 255, 255), style.lift)
        gld = _mix(gld, (255, 255, 255), style.lift)
    light_on_dark = sum(style.bg_top) < 330
    return Palette3D(
        primary=acc,
        secondary=gld,
        light=(246, 243, 236) if light_on_dark else (255, 253, 248),
        dark=(28, 30, 40) if light_on_dark else (44, 42, 52),
        shade=_mix(acc, (18, 20, 30) if light_on_dark else (120, 112, 100), 0.55),
    )


# --------------------------------------------------------------------------- #
# Géométrie: polygones unitaires (repère objet, ~[-1, 1], y vers le HAUT)
# --------------------------------------------------------------------------- #
def circle_poly(cx: float, cy: float, r: float, n: int = 40,
                start: float = 0.0) -> Poly:
    return [(cx + r * math.cos(start + 2 * math.pi * i / n),
             cy + r * math.sin(start + 2 * math.pi * i / n)) for i in range(n)]


def rrect_poly(cx: float, cy: float, w: float, h: float,
               r: float = 0.08, steps: int = 5) -> Poly:
    """Rectangle à coins arrondis, sens horaire écran (y haut)."""
    hw, hh = w / 2.0, h / 2.0
    r = max(0.0, min(r, hw, hh))
    pts: Poly = []
    corners = (
        (cx + hw - r, cy + hh - r, 0.0),
        (cx - hw + r, cy + hh - r, math.pi / 2),
        (cx - hw + r, cy - hh + r, math.pi),
        (cx + hw - r, cy - hh + r, 3 * math.pi / 2),
    )
    for ox, oy, a0 in corners:
        for i in range(steps + 1):
            a = a0 + (math.pi / 2) * i / steps
            pts.append((ox + r * math.cos(a), oy + r * math.sin(a)))
    return pts


def star_poly(cx: float, cy: float, r_out: float, r_in: float,
              points: int = 5, rot: float = math.pi / 2) -> Poly:
    pts: Poly = []
    for i in range(points * 2):
        r = r_out if i % 2 == 0 else r_in
        a = rot + math.pi * i / points
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def heart_poly(cx: float, cy: float, s: float, n: int = 40) -> Poly:
    pts: Poly = []
    for i in range(n):
        a = 2 * math.pi * i / n
        x = 16 * math.sin(a) ** 3
        y = 13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)
        pts.append((cx + s * x / 17.0, cy + s * y / 17.0))
    return pts


def arrow_up_poly(cx: float, cy: float, w: float, h: float,
                  head: float = 0.55) -> Poly:
    hw, hh = w / 2.0, h / 2.0
    sw = hw * 0.44
    hy = cy + hh - h * head
    return [(cx, cy + hh), (cx + hw, hy), (cx + sw, hy),
            (cx + sw, cy - hh), (cx - sw, cy - hh), (cx - sw, hy), (cx - hw, hy)]


def arrow_right_poly(cx: float, cy: float, w: float, h: float,
                     head: float = 0.5) -> Poly:
    hw, hh = w / 2.0, h / 2.0
    sh = hh * 0.44
    hx = cx + hw - w * head
    return [(cx + hw, cy), (hx, cy + hh), (hx, cy + sh),
            (cx - hw, cy + sh), (cx - hw, cy - sh), (hx, cy - sh), (hx, cy - hh)]


def check_poly(cx: float, cy: float, s: float) -> Poly:
    w = 0.20 * s
    return [(cx - 0.62 * s, cy + 0.02 * s), (cx - 0.30 * s, cy - 0.34 * s),
            (cx + 0.60 * s, cy + 0.52 * s), (cx + 0.60 * s - w, cy + 0.52 * s + w),
            (cx - 0.30 * s, cy - 0.10 * s), (cx - 0.62 * s + w, cy + 0.02 * s + w)]


def shield_poly(cx: float, cy: float, w: float, h: float, n: int = 12) -> Poly:
    hw, hh = w / 2.0, h / 2.0
    pts: Poly = [(cx - hw, cy + hh), (cx + hw, cy + hh), (cx + hw, cy - hh * 0.10)]
    for i in range(1, n):
        k = i / n
        pts.append((cx + hw * (1 - k) ** 0.65, cy - hh * (0.10 + 0.90 * k)))
    pts.append((cx, cy - hh))
    for i in range(1, n):
        k = 1 - i / n
        pts.append((cx - hw * (1 - k) ** 0.65, cy - hh * (0.10 + 0.90 * k)))
    pts.append((cx - hw, cy - hh * 0.10))
    return pts


def triangle_poly(cx: float, cy: float, w: float, h: float) -> Poly:
    return [(cx, cy + h / 2), (cx + w / 2, cy - h / 2), (cx - w / 2, cy - h / 2)]


def gear_poly(cx: float, cy: float, r: float, teeth: int = 8,
              tooth: float = 0.22) -> Poly:
    pts: Poly = []
    for i in range(teeth * 4):
        a = 2 * math.pi * i / (teeth * 4)
        rr = r * (1.0 + tooth) if (i % 4) in (1, 2) else r
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


def hex_poly(cx: float, cy: float, r: float) -> Poly:
    return [(cx + r * math.cos(math.pi / 6 + math.pi * i / 3),
             cy + r * math.sin(math.pi / 6 + math.pi * i / 3)) for i in range(6)]


def pin_poly(cx: float, cy: float, w: float, h: float, n: int = 22) -> Poly:
    """Goutte / punaise de carte: rond en haut, pointe en bas."""
    r = w / 2.0
    top = cy + h / 2 - r
    pts: Poly = [(cx, cy - h / 2)]
    for i in range(n + 1):
        a = -math.pi / 2.6 + (math.pi + 2 * math.pi / 2.6) * i / n
        pts.append((cx + r * math.cos(a - math.pi / 2 + math.pi),
                    top + r * math.sin(a - math.pi / 2 + math.pi)))
    return pts


def bubble_tail_poly(cx: float, cy: float, w: float, h: float,
                     flip: bool = False) -> Poly:
    """Queue de bulle — pièce SÉPARÉE du corps: cousue au polygone du corps,
    elle créerait un contour auto-sécant que le remplissage annulerait."""
    s = -1.0 if flip else 1.0
    base = cy - h / 2 + 0.02
    return [(cx + s * w * 0.24, base), (cx + s * w * 0.06, base),
            (cx + s * w * 0.30, base - h * 0.42)]


def annulus_poly(cx: float, cy: float, r_out: float, r_in: float,
                 n: int = 44, a0: float = 0.0, a1: float = 2 * math.pi) -> Poly:
    """Anneau (ou arc épais) en UN seul contour: bord extérieur puis retour par
    le bord intérieur. Pas de booléen 3D nécessaire — la couronne se remplit
    correctement et s'extrude comme n'importe quel autre polygone."""
    outer = [(cx + r_out * math.cos(a0 + (a1 - a0) * i / n),
              cy + r_out * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
    inner = [(cx + r_in * math.cos(a0 + (a1 - a0) * i / n),
              cy + r_in * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n, -1, -1)]
    return outer + inner


def rotate_poly(poly: Poly, angle: float,
                cx: float = 0.0, cy: float = 0.0) -> Poly:
    """Rotation DANS LE PLAN de l'objet (le yaw caméra, lui, tourne en 3D)."""
    ca, sa = math.cos(angle), math.sin(angle)
    return [(cx + (x - cx) * ca - (y - cy) * sa,
             cy + (x - cx) * sa + (y - cy) * ca) for x, y in poly]


def scale_poly(poly: Poly, k: float, cx: float = 0.0, cy: float = 0.0) -> Poly:
    return [(cx + (x - cx) * k, cy + (y - cy) * k) for x, y in poly]


# --------------------------------------------------------------------------- #
# Parts — description déclarative d'un modèle 3D
# --------------------------------------------------------------------------- #
@dataclass
class Part:
    kind: str                  # "prism" | "sphere"
    color: str = "primary"     # rôle dans Palette3D
    poly: Optional[Poly] = None
    z: float = 0.0             # face ARRIÈRE (prisme) / centre (sphère)
    depth: float = 0.18
    pos: Tuple[float, float] = (0.0, 0.0)
    r: float = 0.25
    order: int = 0             # index d'apparition (pop-in décalé)
    yaw_bias: float = 0.0      # rotation propre (rend la scène moins figée)
    float_amp: float = 0.0     # flottement vertical propre
    float_phase: float = 0.0
    alpha: float = 1.0


def prism(poly: Poly, *, color: str = "primary", z: float = 0.0,
          depth: float = 0.18, order: int = 0, yaw_bias: float = 0.0,
          float_amp: float = 0.0, float_phase: float = 0.0,
          alpha: float = 1.0) -> Part:
    return Part(kind="prism", poly=poly, color=color, z=z, depth=depth,
                order=order, yaw_bias=yaw_bias, float_amp=float_amp,
                float_phase=float_phase, alpha=alpha)


def sphere(x: float, y: float, z: float = 0.0, *, r: float = 0.25,
           color: str = "primary", order: int = 0, float_amp: float = 0.0,
           float_phase: float = 0.0, alpha: float = 1.0) -> Part:
    return Part(kind="sphere", pos=(x, y), z=z, r=r, color=color, order=order,
                float_amp=float_amp, float_phase=float_phase, alpha=alpha)


def disc(x: float, y: float, z: float = 0.0, *, r: float = 0.3,
         depth: float = 0.09, color: str = "primary", order: int = 0,
         yaw_bias: float = 0.0, float_amp: float = 0.0,
         float_phase: float = 0.0) -> Part:
    """Cylindre court vu de face (pièce de monnaie, cadran, jeton)."""
    return prism(circle_poly(x, y, r), color=color, z=z, depth=depth,
                 order=order, yaw_bias=yaw_bias, float_amp=float_amp,
                 float_phase=float_phase)


def plate(x: float, y: float, w: float, h: float, *, z: float = 0.0,
          radius: float = 0.06, color: str = "light", depth: float = 0.05,
          order: int = 0, yaw_bias: float = 0.0, float_amp: float = 0.0,
          float_phase: float = 0.0) -> Part:
    return prism(rrect_poly(x, y, w, h, radius), color=color, z=z, depth=depth,
                 order=order, yaw_bias=yaw_bias, float_amp=float_amp,
                 float_phase=float_phase)


def bar(x: float, y0: float, y1: float, w: float, *, z: float = 0.0,
        color: str = "primary", depth: float = 0.16, order: int = 0) -> Part:
    """Barre verticale (histogramme) définie par sa base et son sommet."""
    return prism(rrect_poly(x, (y0 + y1) / 2, w, abs(y1 - y0), min(w, abs(y1 - y0)) * 0.28),
                 color=color, z=z, depth=depth, order=order)


# --------------------------------------------------------------------------- #
# Bibliothèque de MODÈLES — indexée sur les icônes du moteur
#
# Un modèle = fonction sans argument -> liste de Part. Les couleurs sont des
# RÔLES (primary/secondary/light/dark/shade) résolus par le style, donc un même
# modèle s'habille correctement dans les cinq directions artistiques.
# --------------------------------------------------------------------------- #
def _m_money() -> List[Part]:
    return [
        plate(0.02, -0.10, 1.24, 0.62, z=-0.26, radius=0.08, color="light",
              depth=0.05, order=0, yaw_bias=-0.10),
        disc(-0.34, -0.30, 0.02, r=0.30, depth=0.10, color="secondary", order=1),
        disc(-0.06, -0.06, 0.14, r=0.30, depth=0.10, color="primary", order=2),
        disc(0.24, 0.20, 0.26, r=0.30, depth=0.10, color="secondary", order=3,
             float_amp=0.03),
        prism(arrow_up_poly(0.62, 0.42, 0.34, 0.52), color="light", z=0.34,
              depth=0.10, order=4, float_amp=0.04, float_phase=1.1),
    ]


def _m_growth() -> List[Part]:
    return [
        plate(0.0, -0.68, 1.42, 0.10, z=-0.10, radius=0.04, color="shade",
              depth=0.22, order=0),
        bar(-0.44, -0.62, -0.18, 0.30, z=0.0, color="shade", order=1),
        bar(-0.02, -0.62, 0.12, 0.30, z=0.06, color="primary", order=2),
        bar(0.40, -0.62, 0.44, 0.30, z=0.12, color="secondary", order=3),
        prism(arrow_up_poly(0.44, 0.72, 0.34, 0.44), color="light", z=0.30,
              depth=0.10, order=4, float_amp=0.05),
    ]


def _m_chart() -> List[Part]:
    return [
        plate(0.0, 0.0, 1.44, 1.24, z=-0.22, radius=0.10, color="light",
              depth=0.06, order=0),
        bar(-0.42, -0.46, -0.02, 0.26, z=0.02, color="primary", order=1),
        bar(0.0, -0.46, 0.30, 0.26, z=0.02, color="secondary", order=2),
        bar(0.42, -0.46, 0.56, 0.26, z=0.02, color="primary", order=3),
        prism(arrow_right_poly(0.0, 0.62, 0.90, 0.20), color="dark", z=0.16,
              depth=0.07, order=4),
    ]


def _m_rocket() -> List[Part]:
    return [
        prism(triangle_poly(0.0, 0.62, 0.46, 0.44), color="secondary", z=0.06,
              depth=0.22, order=1),
        prism(rrect_poly(0.0, 0.06, 0.46, 0.90, 0.22), color="light", z=0.0,
              depth=0.26, order=0),
        disc(0.0, 0.18, 0.28, r=0.14, depth=0.06, color="primary", order=2),
        prism(triangle_poly(-0.40, -0.34, 0.34, 0.44), color="primary", z=-0.02,
              depth=0.12, order=3),
        prism(triangle_poly(0.40, -0.34, 0.34, 0.44), color="primary", z=-0.02,
              depth=0.12, order=3),
        prism(triangle_poly(0.0, -0.70, 0.34, 0.42), color="secondary", z=0.04,
              depth=0.14, order=4, float_amp=0.04, float_phase=0.6),
    ]


def _m_idea() -> List[Part]:
    return [
        sphere(0.0, 0.22, 0.10, r=0.46, color="secondary", order=0),
        prism(rrect_poly(0.0, -0.34, 0.34, 0.26, 0.08), color="shade", z=0.0,
              depth=0.20, order=1),
        prism(rrect_poly(0.0, -0.58, 0.28, 0.16, 0.06), color="dark", z=0.0,
              depth=0.18, order=2),
        prism(rrect_poly(-0.72, 0.52, 0.30, 0.09, 0.04), color="light", z=0.22,
              depth=0.06, order=3, yaw_bias=0.5, float_amp=0.04),
        prism(rrect_poly(0.72, 0.52, 0.30, 0.09, 0.04), color="light", z=0.22,
              depth=0.06, order=3, yaw_bias=-0.5, float_amp=0.04, float_phase=1.5),
    ]


def _m_target() -> List[Part]:
    return [
        disc(0.0, 0.0, 0.0, r=0.72, depth=0.10, color="light", order=0),
        disc(0.0, 0.0, 0.10, r=0.48, depth=0.08, color="primary", order=1),
        disc(0.0, 0.0, 0.18, r=0.24, depth=0.08, color="light", order=2),
        disc(0.0, 0.0, 0.26, r=0.10, depth=0.08, color="secondary", order=3),
        prism(arrow_right_poly(0.26, 0.02, 1.10, 0.16), color="dark", z=0.34,
              depth=0.09, order=4, float_amp=0.03),
    ]


def _m_shield() -> List[Part]:
    return [
        prism(shield_poly(0.0, 0.0, 1.14, 1.34), color="primary", z=0.0,
              depth=0.26, order=0),
        prism(shield_poly(0.0, 0.0, 0.86, 1.02), color="light", z=0.26,
              depth=0.05, order=1),
        prism(check_poly(0.0, -0.02, 0.66), color="secondary", z=0.31,
              depth=0.10, order=2),
    ]


def _m_lock() -> List[Part]:
    return [
        # Anse: demi-couronne ouverte vers le bas (vrai arceau de cadenas).
        prism(annulus_poly(0.0, 0.30, 0.44, 0.30, a0=0.0, a1=math.pi),
              color="secondary", z=-0.04, depth=0.16, order=0),
        prism(rrect_poly(0.0, -0.24, 1.10, 0.86, 0.16), color="primary", z=0.0,
              depth=0.26, order=1),
        disc(0.0, -0.20, 0.26, r=0.14, depth=0.07, color="light", order=2),
        prism(rrect_poly(0.0, -0.44, 0.11, 0.24, 0.05), color="light", z=0.26,
              depth=0.06, order=2),
    ]


def _m_clock() -> List[Part]:
    return [
        disc(0.0, 0.0, 0.0, r=0.76, depth=0.18, color="primary", order=0),
        disc(0.0, 0.0, 0.18, r=0.62, depth=0.06, color="light", order=1),
        prism(rrect_poly(0.0, 0.16, 0.09, 0.46, 0.04), color="dark", z=0.24,
              depth=0.05, order=2),
        prism(rrect_poly(0.14, -0.04, 0.34, 0.09, 0.04), color="secondary",
              z=0.26, depth=0.05, order=3),
        disc(0.0, 0.0, 0.30, r=0.07, depth=0.05, color="dark", order=3),
    ]


def _m_calendar() -> List[Part]:
    parts = [
        prism(rrect_poly(0.0, -0.06, 1.28, 1.16, 0.14), color="light", z=0.0,
              depth=0.20, order=0),
        prism(rrect_poly(0.0, 0.40, 1.28, 0.30, 0.10), color="primary", z=0.20,
              depth=0.05, order=1),
        prism(rrect_poly(-0.34, 0.60, 0.10, 0.26, 0.05), color="dark", z=0.14,
              depth=0.14, order=1),
        prism(rrect_poly(0.34, 0.60, 0.10, 0.26, 0.05), color="dark", z=0.14,
              depth=0.14, order=1),
    ]
    for i, (dx, dy) in enumerate([(-0.36, -0.02), (0.0, -0.02), (0.36, -0.02),
                                  (-0.36, -0.42), (0.0, -0.42)]):
        parts.append(disc(dx, dy, 0.20, r=0.10, depth=0.05,
                          color="secondary" if i == 4 else "shade", order=2 + i // 3))
    return parts


def _m_phone() -> List[Part]:
    return [
        prism(rrect_poly(0.0, 0.0, 0.86, 1.52, 0.18), color="dark", z=0.0,
              depth=0.20, order=0),
        prism(rrect_poly(0.0, 0.02, 0.70, 1.26, 0.10), color="light", z=0.20,
              depth=0.04, order=1),
        prism(rrect_poly(0.0, 0.30, 0.46, 0.36, 0.08), color="primary", z=0.24,
              depth=0.05, order=2),
        prism(rrect_poly(0.0, -0.18, 0.46, 0.10, 0.04), color="shade", z=0.24,
              depth=0.04, order=3),
        prism(rrect_poly(0.0, -0.40, 0.30, 0.10, 0.04), color="secondary",
              z=0.24, depth=0.04, order=3),
    ]


def _m_chat() -> List[Part]:
    return [
        prism(rrect_poly(-0.18, 0.30, 1.06, 0.72, 0.20), color="light", z=0.0,
              depth=0.16, order=0),
        prism(bubble_tail_poly(-0.18, 0.30, 1.06, 0.72, flip=True),
              color="light", z=0.0, depth=0.16, order=0),
        disc(-0.44, 0.32, 0.17, r=0.07, depth=0.04, color="dark", order=1),
        disc(-0.18, 0.32, 0.17, r=0.07, depth=0.04, color="dark", order=1),
        disc(0.08, 0.32, 0.17, r=0.07, depth=0.04, color="dark", order=1),
        prism(rrect_poly(0.28, -0.46, 0.88, 0.58, 0.18), color="primary",
              z=0.20, depth=0.16, order=2, float_amp=0.04, float_phase=1.0),
        prism(bubble_tail_poly(0.28, -0.46, 0.88, 0.58), color="primary",
              z=0.20, depth=0.16, order=2, float_amp=0.04, float_phase=1.0),
    ]


def _m_people() -> List[Part]:
    return [
        sphere(-0.40, 0.34, 0.10, r=0.24, color="secondary", order=0),
        prism(rrect_poly(-0.40, -0.30, 0.62, 0.66, 0.24), color="primary",
              z=0.0, depth=0.20, order=1),
        sphere(0.40, 0.42, 0.22, r=0.24, color="light", order=2),
        prism(rrect_poly(0.40, -0.24, 0.62, 0.66, 0.24), color="shade",
              z=0.12, depth=0.20, order=3),
    ]


def _m_person() -> List[Part]:
    return [
        sphere(0.0, 0.44, 0.12, r=0.30, color="secondary", order=0),
        prism(rrect_poly(0.0, -0.28, 0.78, 0.82, 0.28), color="primary", z=0.0,
              depth=0.24, order=1),
        prism(rrect_poly(0.0, -0.70, 0.96, 0.14, 0.06), color="shade", z=0.10,
              depth=0.16, order=2),
    ]


def _m_handshake() -> List[Part]:
    # Deux avant-bras qui montent en V et se serrent au centre — la rotation
    # DANS LE PLAN est ce qui fait lire « poignée de main » plutôt qu'haltère.
    left = rotate_poly(rrect_poly(-0.40, -0.30, 0.98, 0.34, 0.16), 0.40,
                       -0.40, -0.30)
    right = rotate_poly(rrect_poly(0.40, -0.30, 0.98, 0.34, 0.16), -0.40,
                        0.40, -0.30)
    cuff_l = rotate_poly(rrect_poly(-0.80, -0.48, 0.22, 0.42, 0.08), 0.40,
                         -0.40, -0.30)
    cuff_r = rotate_poly(rrect_poly(0.80, -0.48, 0.22, 0.42, 0.08), -0.40,
                         0.40, -0.30)
    return [
        prism(cuff_l, color="dark", z=-0.04, depth=0.26, order=0),
        prism(left, color="primary", z=0.0, depth=0.24, order=0),
        prism(cuff_r, color="dark", z=0.02, depth=0.26, order=1),
        prism(right, color="secondary", z=0.06, depth=0.24, order=1),
        # La POIGNE: un bloc large qui enjambe les deux avant-bras — c'est lui
        # qui fait lire « poignée de main » et pas « deux bâtons ».
        prism(rrect_poly(0.0, 0.14, 0.66, 0.46, 0.20), color="light", z=0.24,
              depth=0.22, order=2),
        prism(star_poly(-0.62, 0.66, 0.18, 0.08, 4, math.pi / 2), color="light",
              z=0.34, depth=0.06, order=3, float_amp=0.05),
        prism(star_poly(0.66, 0.58, 0.14, 0.06, 4, math.pi / 2), color="light",
              z=0.34, depth=0.06, order=3, float_amp=0.05, float_phase=1.3),
    ]


def _m_cart() -> List[Part]:
    return [
        prism([(-0.62, 0.30), (0.66, 0.30), (0.46, -0.28), (-0.42, -0.28)],
              color="primary", z=0.0, depth=0.26, order=0),
        prism(rrect_poly(-0.80, 0.44, 0.44, 0.11, 0.05), color="shade", z=0.06,
              depth=0.12, order=1, yaw_bias=0.22),
        disc(-0.30, -0.54, 0.10, r=0.16, depth=0.08, color="dark", order=2),
        disc(0.34, -0.54, 0.10, r=0.16, depth=0.08, color="dark", order=2),
        prism(rrect_poly(0.10, 0.62, 0.44, 0.34, 0.10), color="secondary",
              z=0.16, depth=0.16, order=3, float_amp=0.04),
    ]


def _m_box() -> List[Part]:
    return [
        prism(rrect_poly(0.0, -0.12, 1.16, 0.94, 0.06), color="secondary",
              z=0.0, depth=0.46, order=0),
        prism(rrect_poly(0.0, 0.44, 1.22, 0.24, 0.05), color="primary", z=-0.02,
              depth=0.50, order=1),
        prism(rrect_poly(0.0, -0.12, 0.16, 0.94, 0.04), color="light", z=0.46,
              depth=0.04, order=2),
    ]


def _m_gift() -> List[Part]:
    parts = _m_box()
    parts.append(prism(star_poly(0.0, 0.66, 0.24, 0.11, 5), color="light",
                       z=0.10, depth=0.14, order=3, float_amp=0.04))
    return parts


def _m_gear() -> List[Part]:
    return [
        prism(gear_poly(-0.22, 0.10, 0.60, 8), color="primary", z=0.0,
              depth=0.24, order=0),
        prism(circle_poly(-0.22, 0.10, 0.22), color="__cut", z=-0.02,
              depth=0.30, order=0),
        prism(gear_poly(0.48, -0.42, 0.38, 7), color="secondary", z=0.10,
              depth=0.20, order=1, yaw_bias=0.25),
        prism(circle_poly(0.48, -0.42, 0.14), color="__cut", z=0.08,
              depth=0.26, order=1),
    ]


def _m_globe() -> List[Part]:
    return [
        sphere(0.0, 0.0, 0.0, r=0.68, color="primary", order=0),
        # Orbites: deux couronnes fines inclinées autour de la sphère.
        prism(annulus_poly(0.0, 0.0, 0.90, 0.83), color="secondary", z=-0.03,
              depth=0.06, order=1, yaw_bias=0.95),
        prism(annulus_poly(0.0, 0.0, 0.84, 0.78), color="light", z=0.02,
              depth=0.05, order=2, yaw_bias=-0.75),
        sphere(0.62, 0.52, 0.55, r=0.11, color="secondary", order=3,
               float_amp=0.05),
    ]


def _m_map() -> List[Part]:
    return [
        plate(-0.02, -0.16, 1.36, 1.00, z=0.0, radius=0.05, color="light",
              depth=0.06, order=0, yaw_bias=-0.14),
        prism(rrect_poly(-0.02, -0.16, 1.36, 0.10, 0.03), color="shade",
              z=0.06, depth=0.03, order=1, yaw_bias=-0.14),
        prism(pin_poly(0.16, 0.42, 0.46, 0.74), color="primary", z=0.20,
              depth=0.14, order=2, float_amp=0.05),
        disc(0.16, 0.56, 0.34, r=0.12, depth=0.06, color="light", order=3),
    ]


def _m_book() -> List[Part]:
    return [
        plate(-0.36, 0.0, 0.86, 1.14, z=0.0, radius=0.05, color="light",
              depth=0.12, order=0, yaw_bias=0.26),
        plate(0.36, 0.0, 0.86, 1.14, z=0.0, radius=0.05, color="light",
              depth=0.12, order=1, yaw_bias=-0.26),
        prism(rrect_poly(0.0, 0.0, 0.14, 1.20, 0.05), color="primary", z=0.02,
              depth=0.18, order=2),
        prism(rrect_poly(0.0, 0.66, 0.30, 0.16, 0.05), color="secondary",
              z=0.14, depth=0.08, order=3, float_amp=0.04),
    ]


def _m_megaphone() -> List[Part]:
    return [
        prism([(-0.70, 0.34), (0.10, 0.74), (0.10, -0.66), (-0.70, -0.26)],
              color="primary", z=0.0, depth=0.26, order=0),
        prism(rrect_poly(-0.80, 0.04, 0.34, 0.44, 0.10), color="shade", z=0.02,
              depth=0.22, order=1),
        prism(rrect_poly(0.46, 0.44, 0.42, 0.10, 0.05), color="secondary",
              z=0.18, depth=0.06, order=2, float_amp=0.04),
        prism(rrect_poly(0.52, 0.06, 0.52, 0.10, 0.05), color="secondary",
              z=0.18, depth=0.06, order=2, float_amp=0.04, float_phase=0.8),
        prism(rrect_poly(0.46, -0.32, 0.42, 0.10, 0.05), color="secondary",
              z=0.18, depth=0.06, order=3, float_amp=0.04, float_phase=1.6),
    ]


def _m_star() -> List[Part]:
    return [
        prism(star_poly(0.0, 0.06, 0.86, 0.38), color="secondary", z=0.0,
              depth=0.28, order=0),
        prism(star_poly(0.0, 0.06, 0.52, 0.23), color="light", z=0.28,
              depth=0.05, order=1),
        prism(star_poly(-0.74, 0.66, 0.20, 0.09, 4), color="light", z=0.24,
              depth=0.05, order=2, float_amp=0.05),
        prism(star_poly(0.78, -0.48, 0.16, 0.07, 4), color="light", z=0.24,
              depth=0.05, order=3, float_amp=0.05, float_phase=1.3),
    ]


def _m_heart() -> List[Part]:
    return [
        prism(heart_poly(0.0, 0.0, 0.92), color="primary", z=0.0, depth=0.30,
              order=0),
        prism(heart_poly(-0.02, 0.06, 0.44), color="light", z=0.30, depth=0.05,
              order=1),
    ]


def _m_check() -> List[Part]:
    return [
        disc(0.0, 0.0, 0.0, r=0.78, depth=0.20, color="primary", order=0),
        prism(check_poly(0.0, -0.04, 0.86), color="light", z=0.20, depth=0.12,
              order=1),
    ]


def _m_warning() -> List[Part]:
    return [
        prism(triangle_poly(0.0, 0.0, 1.52, 1.32), color="secondary", z=0.0,
              depth=0.28, order=0),
        prism(triangle_poly(0.0, -0.02, 1.10, 0.96), color="light", z=0.28,
              depth=0.05, order=1),
        prism(rrect_poly(0.0, 0.02, 0.14, 0.44, 0.06), color="dark", z=0.33,
              depth=0.06, order=2),
        disc(0.0, -0.32, 0.33, r=0.09, depth=0.06, color="dark", order=3),
    ]


def _m_transfer() -> List[Part]:
    return [
        disc(-0.58, 0.02, 0.0, r=0.34, depth=0.12, color="secondary", order=0),
        disc(0.58, 0.02, 0.0, r=0.34, depth=0.12, color="primary", order=1),
        prism(arrow_right_poly(0.0, 0.30, 0.86, 0.20), color="light", z=0.18,
              depth=0.08, order=2, float_amp=0.03),
        prism(rotate_poly(arrow_right_poly(0.0, -0.30, 0.86, 0.20), math.pi,
                          0.0, -0.30),
              color="light", z=0.18, depth=0.08, order=3, float_amp=0.03,
              float_phase=1.4),
    ]


def _m_crypto() -> List[Part]:
    return [
        prism(hex_poly(0.0, 0.0, 0.78), color="primary", z=0.0, depth=0.30,
              order=0),
        prism(hex_poly(0.0, 0.0, 0.52), color="light", z=0.30, depth=0.06,
              order=1),
        disc(-0.72, 0.54, 0.14, r=0.18, depth=0.07, color="secondary", order=2,
             float_amp=0.05),
        disc(0.74, -0.50, 0.14, r=0.16, depth=0.07, color="secondary", order=3,
             float_amp=0.05, float_phase=1.2),
    ]


def _m_bank() -> List[Part]:
    parts = [
        prism(rrect_poly(0.0, -0.66, 1.50, 0.20, 0.05), color="shade", z=0.0,
              depth=0.34, order=0),
        prism(triangle_poly(0.0, 0.62, 1.50, 0.44), color="primary", z=0.0,
              depth=0.32, order=1),
    ]
    for i, x in enumerate((-0.50, 0.0, 0.50)):
        parts.append(prism(rrect_poly(x, -0.08, 0.24, 0.86, 0.08),
                           color="light", z=0.04, depth=0.24, order=2 + i % 2))
    return parts


def _m_card() -> List[Part]:
    return [
        plate(0.0, -0.06, 1.44, 0.92, z=0.0, radius=0.10, color="primary",
              depth=0.09, order=0),
        prism(rrect_poly(0.0, 0.16, 1.44, 0.22, 0.02), color="dark", z=0.09,
              depth=0.03, order=1),
        prism(rrect_poly(-0.44, -0.26, 0.42, 0.13, 0.04), color="light",
              z=0.09, depth=0.03, order=2),
        plate(0.30, 0.34, 1.00, 0.66, z=0.30, radius=0.09, color="secondary",
              depth=0.07, order=3, yaw_bias=-0.20, float_amp=0.04),
    ]


def _m_document() -> List[Part]:
    parts = [
        plate(0.0, 0.0, 1.10, 1.42, z=0.0, radius=0.05, color="light",
              depth=0.08, order=0),
    ]
    for i, (y, w) in enumerate(((0.44, 0.74), (0.18, 0.86), (-0.08, 0.86),
                                (-0.34, 0.54))):
        parts.append(prism(rrect_poly(-0.08 + (0.86 - w) / 2, y, w, 0.11, 0.05),
                           color="primary" if i == 0 else "shade",
                           z=0.08, depth=0.03, order=1 + i // 2))
    parts.append(prism(check_poly(0.42, -0.48, 0.42), color="secondary",
                       z=0.12, depth=0.08, order=3, float_amp=0.04))
    return parts


def _m_key() -> List[Part]:
    return [
        prism(annulus_poly(-0.44, 0.02, 0.44, 0.20), color="secondary", z=0.0,
              depth=0.16, order=0),
        prism(rrect_poly(0.30, 0.02, 1.06, 0.20, 0.07), color="secondary",
              z=0.02, depth=0.14, order=1),
        prism(rrect_poly(0.62, -0.20, 0.14, 0.28, 0.04), color="secondary",
              z=0.02, depth=0.14, order=2),
        prism(rrect_poly(0.88, -0.20, 0.14, 0.28, 0.04), color="secondary",
              z=0.02, depth=0.14, order=2),
    ]


def _m_spark() -> List[Part]:
    return [
        prism(star_poly(0.0, 0.04, 0.78, 0.24, 4, math.pi / 2), color="secondary",
              z=0.0, depth=0.26, order=0),
        prism(star_poly(-0.66, 0.62, 0.28, 0.09, 4, math.pi / 2), color="primary",
              z=0.16, depth=0.10, order=1, float_amp=0.05),
        prism(star_poly(0.70, -0.52, 0.22, 0.07, 4, math.pi / 2), color="light",
              z=0.16, depth=0.10, order=2, float_amp=0.05, float_phase=1.4),
        sphere(0.62, 0.58, 0.24, r=0.13, color="light", order=3, float_amp=0.05),
    ]


#: Modèle par icône du moteur (`content.ICON_RULES`). Toute icône absente
#: retombe sur `_m_spark`, qui reste une vraie scène 3D (jamais un trou).
MODELS: Dict[str, Callable[[], List[Part]]] = {
    "money": _m_money,
    "growth": _m_growth,
    "chart": _m_chart,
    "rocket": _m_rocket,
    "idea": _m_idea,
    "target": _m_target,
    "shield": _m_shield,
    "lock": _m_lock,
    "clock": _m_clock,
    "calendar": _m_calendar,
    "phone": _m_phone,
    "chat": _m_chat,
    "people": _m_people,
    "person": _m_person,
    "handshake": _m_handshake,
    "cart": _m_cart,
    "box": _m_box,
    "gift": _m_gift,
    "gear": _m_gear,
    "globe": _m_globe,
    "map": _m_map,
    "book": _m_book,
    "megaphone": _m_megaphone,
    "star": _m_star,
    "heart": _m_heart,
    "check": _m_check,
    "warning": _m_warning,
    "transfer": _m_transfer,
    "crypto": _m_crypto,
    "bank": _m_bank,
    "card": _m_card,
    "document": _m_document,
    "key": _m_key,
    "sparkle": _m_spark,
}

DEFAULT_MODEL = "sparkle"


def has_model(icon: Optional[str]) -> bool:
    return bool(icon) and icon in MODELS


def model_names() -> List[str]:
    return sorted(MODELS)


def model_for(icon: Optional[str]) -> List[Part]:
    return MODELS.get(icon or "", MODELS[DEFAULT_MODEL])()


# --------------------------------------------------------------------------- #
# Caméra / projection
# --------------------------------------------------------------------------- #
def _rotate(p: Vec3, yaw: float, pitch: float) -> Vec3:
    x, y, z = p
    ca, sa = math.cos(yaw), math.sin(yaw)
    xr = x * ca + z * sa
    zr = -x * sa + z * ca
    cb, sb = math.cos(pitch), math.sin(pitch)
    yr = y * cb - zr * sb
    zr2 = y * sb + zr * cb
    return (xr, yr, zr2)


class Camera:
    """Projection perspective faible, centrée sur la plaque."""

    def __init__(self, cx: float, cy: float, scale: float,
                 yaw: float, pitch: float):
        self.cx, self.cy, self.scale = cx, cy, scale
        self.yaw, self.pitch = yaw, pitch

    def project(self, p: Vec3, yaw_extra: float = 0.0) -> Tuple[float, float, float]:
        rx, ry, rz = _rotate(p, self.yaw + yaw_extra, self.pitch)
        f = FOCAL / max(0.6, FOCAL - rz)
        return (self.cx + rx * self.scale * f,
                self.cy - ry * self.scale * f,
                rz)

    def normal(self, n: Vec3, yaw_extra: float = 0.0) -> Vec3:
        return _rotate(n, self.yaw + yaw_extra, self.pitch)


def _norm(v: Vec3) -> Vec3:
    m = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / m, v[1] / m, v[2] / m)


def _shade(color: RGB, normal: Vec3, style: Style3D) -> RGB:
    """Blinn-Phong: ambiante + diffuse + spéculaire + rim light."""
    mat = style.material
    n = _norm(normal)
    light = _norm(style.light)
    lam = max(0.0, n[0] * light[0] + n[1] * light[1] + n[2] * light[2])
    half = _norm((light[0], light[1], light[2] + 1.0))
    spec_dot = max(0.0, n[0] * half[0] + n[1] * half[1] + n[2] * half[2])
    spec = mat.spec * (spec_dot ** mat.shininess)
    rim = mat.rim * (1.0 - abs(n[2])) ** 2
    k = mat.ambient + mat.diffuse * lam
    out = [min(255.0, c * k + 255.0 * spec) for c in color]
    out = [min(255.0, out[i] + mat.rim_color[i] * rim) for i in range(3)]
    return (int(out[0]), int(out[1]), int(out[2]))


# --------------------------------------------------------------------------- #
# Rendu des primitives
# --------------------------------------------------------------------------- #
def _draw_prism(draw: ImageDraw.ImageDraw, part: Part, cam: Camera,
                style: Style3D, palette: Palette3D, scale_k: float,
                dy: float) -> float:
    """Dessine un polygone extrudé. Retourne la profondeur moyenne (tri)."""
    poly = part.poly or []
    if len(poly) < 3:
        return -99.0
    z0, z1 = part.z, part.z + part.depth
    yaw = part.yaw_bias
    pts3 = [(x * scale_k, y * scale_k + dy) for x, y in poly]

    back = [cam.project((x, y, z0 * scale_k), yaw) for x, y in pts3]
    front = [cam.project((x, y, z1 * scale_k), yaw) for x, y in pts3]
    depth = sum(p[2] for p in front) / len(front)

    if part.color == "__cut":
        # Pièce « creusée » (moyeu d'engrenage, œil d'une clé…). ImageDraw
        # REMPLACE les pixels, alpha compris: peindre du transparent perce un
        # vrai trou dans la couche objet et laisse voir le studio derrière —
        # correct sur fond sombre COMME sur fond clair.
        draw.polygon([(p[0], p[1]) for p in front], fill=(0, 0, 0, 0))
        return depth

    base = palette.get(part.color)
    alpha = int(255 * max(0.0, min(1.0, part.alpha)))

    # --- faces latérales, triées de la plus lointaine à la plus proche ------
    n = len(pts3)
    faces: List[Tuple[float, list, RGB]] = []
    for i in range(n):
        j = (i + 1) % n
        ax, ay = pts3[i]
        bx, by = pts3[j]
        ex, ey = bx - ax, by - ay
        ln = math.hypot(ex, ey) or 1.0
        # Normale sortante du polygone (sens direct, y vers le haut).
        nrm = cam.normal((ey / ln, -ex / ln, 0.0), yaw)
        if nrm[2] <= 0.02:
            continue  # face cachée
        quad = [back[i], back[j], front[j], front[i]]
        faces.append((sum(p[2] for p in quad) / 4.0, quad,
                      _shade(_mix(base, (0, 0, 0), 0.10), nrm, style)))
    for _, quad, col in sorted(faces, key=lambda f: f[0]):
        draw.polygon([(p[0], p[1]) for p in quad], fill=(*col, alpha))

    # --- face avant ---------------------------------------------------------
    front_n = cam.normal((0.0, 0.0, 1.0), yaw)
    face_col = _shade(base, front_n, style)
    draw.polygon([(p[0], p[1]) for p in front], fill=(*face_col, alpha))

    # --- arête ciselée: liseré clair sur les bords orientés vers la lumière --
    if style.material.edge_light > 0:
        lit = _mix(face_col, (255, 255, 255), style.material.edge_light)
        width = max(1, int(2.2 * SS))
        for i in range(n):
            j = (i + 1) % n
            ax, ay = pts3[i]
            bx, by = pts3[j]
            ex, ey = bx - ax, by - ay
            ln = math.hypot(ex, ey) or 1.0
            nrm = cam.normal((ey / ln, -ex / ln, 0.0), yaw)
            light = _norm(style.light)
            if nrm[0] * light[0] + nrm[1] * light[1] < 0.25:
                continue
            draw.line([(front[i][0], front[i][1]), (front[j][0], front[j][1])],
                      fill=(*lit, alpha), width=width)
    return depth


def _sphere_tile(r_px: int, base: RGB, style: Style3D) -> Image.Image:
    """Sphère ombrée par pixel (normale analytique) — cache par (r, style)."""
    key = (r_px, base, style.name)
    cached = _SPHERE_CACHE.get(key)
    if cached is not None:
        return cached
    size = max(4, r_px * 2)
    yy, xx = np.mgrid[0:size, 0:size]
    nx = (xx - size / 2.0 + 0.5) / (size / 2.0)
    ny = -(yy - size / 2.0 + 0.5) / (size / 2.0)
    rr = nx * nx + ny * ny
    inside = rr <= 1.0
    nz = np.sqrt(np.clip(1.0 - rr, 0.0, 1.0))

    mat = style.material
    lx, ly, lz = _norm(style.light)
    lam = np.clip(nx * lx + ny * ly + nz * lz, 0.0, None)
    hx, hy, hz = _norm((lx, ly, lz + 1.0))
    spec = np.clip(nx * hx + ny * hy + nz * hz, 0.0, None) ** mat.shininess
    rim = mat.rim * (1.0 - nz) ** 2
    k = mat.ambient + mat.diffuse * lam

    rgb = np.zeros((size, size, 3), dtype=np.float32)
    for c in range(3):
        rgb[..., c] = (base[c] * k + 255.0 * mat.spec * spec
                       + mat.rim_color[c] * rim)
    rgb = np.clip(rgb, 0, 255)

    # Bord antialiasé: le masque s'adoucit sur ~1.5 px.
    edge = (1.0 - np.sqrt(np.clip(rr, 0.0, None))) * (size / 3.0)
    alpha = np.clip(edge, 0.0, 1.0) * inside
    out = np.dstack([rgb, alpha * 255.0]).astype(np.uint8)
    img = Image.fromarray(out, "RGBA")
    if len(_SPHERE_CACHE) > 96:
        _SPHERE_CACHE.clear()
    _SPHERE_CACHE[key] = img
    return img


_SPHERE_CACHE: Dict[tuple, Image.Image] = {}


def _draw_sphere(canvas: Image.Image, part: Part, cam: Camera, style: Style3D,
                 palette: Palette3D, scale_k: float, dy: float) -> float:
    x, y = part.pos
    sx, sy, depth = cam.project((x * scale_k, y * scale_k + dy, part.z * scale_k))
    f = FOCAL / max(0.6, FOCAL - depth)
    r_px = max(2, int(part.r * scale_k * cam.scale * f))
    tile = _sphere_tile(r_px, palette.get(part.color), style)
    if part.alpha < 1.0:
        a = tile.split()[3].point(lambda v: int(v * part.alpha))
        tile = Image.merge("RGBA", (*tile.split()[:3], a))
    canvas.alpha_composite(tile, (int(sx - r_px), int(sy - r_px)))
    return depth


# --------------------------------------------------------------------------- #
# Studio (fond) — mis en cache: il ne change pas d'une frame à l'autre
# --------------------------------------------------------------------------- #
_STAGE_CACHE: Dict[tuple, Image.Image] = {}


def _stage(w: int, h: int, style: Style3D) -> Image.Image:
    key = (w, h, style.name)
    cached = _STAGE_CACHE.get(key)
    if cached is not None:
        return cached.copy()

    grad = Image.new("RGB", (1, h))
    px = grad.load()
    for y in range(h):
        k = y / max(1, h - 1)
        px[0, y] = _mix(style.bg_top, style.bg_bottom, k)
    base = grad.resize((w, h)).convert("RGBA")

    # Sol: bande basse plus claire, horizon très adouci (un bord net ferait
    # « étagère » au lieu d'un studio infini).
    floor = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    fd = ImageDraw.Draw(floor)
    horizon = int(h * 0.74)
    fd.rectangle((0, horizon, w, h), fill=(*style.floor, 190))
    floor = floor.filter(ImageFilter.GaussianBlur(h * 0.11))
    base.alpha_composite(floor)

    # Halo derrière le sujet.
    if style.halo_strength > 0:
        halo = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        hd = ImageDraw.Draw(halo)
        rr = int(min(w, h) * 0.40)
        cx, cy = w // 2, int(h * 0.46)
        hd.ellipse((cx - rr, cy - rr, cx + rr, cy + rr),
                   fill=(*style.halo, int(120 * style.halo_strength)))
        halo = halo.filter(ImageFilter.GaussianBlur(min(w, h) * 0.16))
        base.alpha_composite(halo)

    # Vignette — recentre le regard sur l'objet.
    vig = Image.new("L", (w, h), 0)
    ImageDraw.Draw(vig).ellipse((-w * 0.25, -h * 0.18, w * 1.25, h * 1.18), fill=255)
    shade_a = vig.filter(ImageFilter.GaussianBlur(min(w, h) * 0.14)).point(
        lambda v: (255 - v) * 92 // 255)
    zero = Image.new("L", (w, h), 0)
    base.alpha_composite(Image.merge("RGBA", (zero, zero, zero, shade_a)))

    if len(_STAGE_CACHE) > 12:
        _STAGE_CACHE.clear()
    _STAGE_CACHE[key] = base
    return base.copy()


def _grain(w: int, h: int, strength: float, seed: int = 3) -> Image.Image:
    rng = np.random.default_rng(seed)
    noise = rng.integers(0, 255, size=(h // 2 + 1, w // 2 + 1), dtype=np.uint8)
    a = Image.fromarray(noise, "L").resize((w, h)).point(
        lambda v: int(abs(v - 128) * strength))
    grey = Image.new("L", (w, h), 128)
    return Image.merge("RGBA", (grey, grey, grey, a))


# --------------------------------------------------------------------------- #
# API principale
# --------------------------------------------------------------------------- #
def _ease_out_back(p: float, s: float = 1.70158) -> float:
    p = max(0.0, min(1.0, p))
    return 1.0 + (s + 1.0) * (p - 1.0) ** 3 + s * (p - 1.0) ** 2


def render_plate(icon: Optional[str], width: int, height: int, *,
                 t: float = 0.0, dur: float = 4.6,
                 style: Optional[str] = None,
                 accent: Sequence[int] = (0, 220, 255, 255),
                 gold: Sequence[int] = (255, 199, 64, 255),
                 seed: Optional[str] = None,
                 parts: Optional[List[Part]] = None) -> Image.Image:
    """Plaque RGBA (width x height) illustrant *icon* en 3D à l'instant *t*.

    Le résultat se pose exactement comme une illustration IA: même contrat,
    même taille, mais zéro appel réseau et zéro crédit consommé.
    """
    width = max(16, int(width))
    height = max(16, int(height))
    st = style_for(style or (select_style(seed) if seed else None))
    palette = build_palette(st, accent, gold)
    model = list(parts if parts is not None else model_for(icon))

    canvas = _stage(width, height, st)

    W2, H2 = width * SS, height * SS
    layer = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # --- caméra: rotation lente (c'est elle qui fait lire le volume) --------
    phase = 2 * math.pi * st.yaw_speed * t
    yaw = st.yaw_base + st.yaw_amp * math.sin(phase)
    pitch = st.pitch + 0.03 * math.sin(phase * 0.6)
    scale = min(W2, H2) * 0.30
    cam = Camera(W2 / 2.0, H2 * 0.47, scale, yaw, pitch)

    # --- respiration d'ensemble --------------------------------------------
    bob = 0.035 * math.sin(2 * math.pi * 0.33 * t)
    intro = _ease_out_back(min(1.0, t / 0.55)) if t < 0.55 else 1.0
    global_k = 0.86 + 0.14 * intro

    # --- ombre de contact ---------------------------------------------------
    sh = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sw, shh = int(W2 * 0.46), int(H2 * 0.075)
    scx, scy = W2 // 2, int(H2 * 0.80 - bob * scale * 0.4)
    sd.ellipse((scx - sw, scy - shh, scx + sw, scy + shh),
               fill=(0, 0, 0, int(st.shadow_alpha * intro)))
    sh = sh.filter(ImageFilter.GaussianBlur(max(2.0, H2 * st.shadow_blur)))
    layer.alpha_composite(sh)

    # --- pièces, triées par profondeur (peintre) ---------------------------
    n_parts = max(1, len(model))
    stagger = min(0.16, max(0.05, (dur * 0.30) / n_parts))
    renderables: List[Tuple[float, Part, float]] = []
    for part in model:
        appear = 0.10 + part.order * stagger
        p = _ease_out_back(min(1.0, max(0.0, (t - appear) / 0.42)))
        if p <= 0.005:
            continue
        k = global_k * (0.24 + 0.76 * min(1.15, p))
        renderables.append((0.0, part, k))

    # Tri « peintre ». La profondeur projetée seule ne suffit pas: une pièce de
    # DÉTAIL posée sur la face avant d'une autre (aiguilles d'une horloge,
    # barre d'un panneau) a un centre qui peut passer DERRIÈRE la grande pièce
    # dès que la caméra tourne — et le détail disparaît. On pondère donc la
    # profondeur d'auteur (le z du modèle, explicite) devant la profondeur
    # caméra, qui ne sert plus qu'à départager les pièces d'un même plan.
    ordered: List[Tuple[float, Part, float]] = []
    for _, part, k in renderables:
        if part.kind == "sphere":
            cz = part.z
            cx_, cy_ = part.pos
        else:
            poly = part.poly or [(0.0, 0.0)]
            cx_ = sum(p[0] for p in poly) / len(poly)
            cy_ = sum(p[1] for p in poly) / len(poly)
            cz = part.z + part.depth / 2.0
        _, _, d = cam.project((cx_ * k, cy_ * k, cz * k), part.yaw_bias)
        ordered.append((cz + 0.35 * d, part, k))
    ordered.sort(key=lambda item: item[0])

    for _, part, k in ordered:
        dy = bob + (part.float_amp * math.sin(2 * math.pi * 0.42 * t
                                              + part.float_phase) if part.float_amp else 0.0)
        if part.kind == "sphere":
            _draw_sphere(layer, part, cam, st, palette, k, dy)
        else:
            _draw_prism(draw, part, cam, st, palette, k, dy)

    if SS != 1:
        layer = layer.resize((width, height), Image.LANCZOS)

    # --- bloom (verre / chrome) --------------------------------------------
    if st.bloom > 0:
        glow = layer.filter(ImageFilter.GaussianBlur(min(width, height) * 0.035))
        glow.putalpha(glow.split()[3].point(lambda v: int(v * st.bloom)))
        canvas.alpha_composite(glow)

    canvas.alpha_composite(layer)

    # --- balayage de lumière à l'entrée ------------------------------------
    if t < 0.9:
        sweep = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        wd = ImageDraw.Draw(sweep)
        pos = int(-width * 0.4 + (width * 1.8) * (t / 0.9))
        wd.polygon([(pos, height), (pos + int(width * 0.22), height),
                    (pos + int(width * 0.42), 0), (pos + int(width * 0.20), 0)],
                   fill=(255, 255, 255, 42))
        canvas.alpha_composite(sweep.filter(ImageFilter.GaussianBlur(width * 0.03)))

    if st.grain > 0:
        canvas.alpha_composite(_grain(width, height, st.grain))
    return canvas


def render_still(icon: str, out_path: str, *, width: int = 620,
                 height: int = 800, style: Optional[str] = None,
                 t: float = 1.4) -> str:
    """Rend une image fixe (debug / planches de style)."""
    img = render_plate(icon, width, height, t=t, style=style)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    img.convert("RGB").save(out_path)
    return out_path


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Rendu 3D procédural des illustrations de motion design")
    ap.add_argument("icon", nargs="?", default="growth", help="nom du modèle")
    ap.add_argument("--style", default=None, help=f"un de: {', '.join(STYLES_BY_NAME)}")
    ap.add_argument("--out", default="motion_3d.png")
    ap.add_argument("--t", type=float, default=1.4)
    ap.add_argument("--list", action="store_true", help="liste les modèles")
    args = ap.parse_args(argv)
    if args.list:
        print("\n".join(model_names()))
        return 0
    print(render_still(args.icon, args.out, style=args.style, t=args.t))
    return 0


if __name__ == "__main__":
    sys.exit(main())
