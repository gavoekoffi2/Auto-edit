"""
Bibliothèque de SILHOUETTES vectorielles (style « papercut lumineux »).

Pourquoi maison plutôt qu'IA: une silhouette générée par un modèle d'image
coûte un crédit, change de proportions à chaque appel et ne se pose jamais deux
fois pareil. Ici chaque pose est un petit SQUELETTE de points normalisés, donc:

  * gratuit et hors-ligne — aucune API, aucun asset propriétaire;
  * strictement identique d'un rendu à l'autre (montage reproductible);
  * animable (respiration, balancement) puisque les points sont calculés;
  * exportable en SVG (`--export-svg`) pour être ouvert/retouché dans un outil
    vectoriel, puis réimporté via `assets/silhouettes/*.svg`.

Le look reproduit celui des boards de motion design: corps quasi noir, col et
revers en or, liseré froid sur une arête, halo doux — jamais de visage.

Usage:
    python -m app.autoedit_engine.silhouettes --export-svg out_svg/
    python -m app.autoedit_engine.silhouettes --preview preview.png
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFilter

Point = Tuple[float, float]

# Couleurs par défaut (surchargées par la palette du style appelant).
BODY = (13, 13, 16, 255)
ACCENT = (255, 199, 64, 255)      # col / revers — chaud
RIM = (0, 220, 255, 255)          # liseré froid sur une arête
PLATE = (238, 239, 237, 255)      # fond clair quand on rend une « plaque »


# --------------------------------------------------------------------------- #
# squelette
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Figure:
    """Un personnage: des articulations normalisées + un placement."""
    joints: Dict[str, Point]
    offset: Point = (0.0, 0.0)
    scale: float = 1.0
    flip: bool = False
    sway: float = 1.0             # amplitude du mouvement d'inactivité


@dataclass(frozen=True)
class Prop:
    """Un accessoire simple (table, socle, téléphone, mur…).

    *front* le dessine PAR-DESSUS les personnages: une table doit masquer les
    jambes de ceux qui sont assis derrière, sinon la scène se lit mal.
    """
    kind: str                     # "rect" | "accent" | "round"
    box: Tuple[float, float, float, float]
    front: bool = False


@dataclass(frozen=True)
class Pose:
    figures: List[Figure]
    props: List[Prop] = field(default_factory=list)
    label: str = ""


# Squelette debout de référence. Les poses n'en surchargent que quelques points,
# ce qui garde la bibliothèque courte et cohérente.
_BASE: Dict[str, Point] = {
    "head": (0.500, 0.152), "neck": (0.500, 0.216),
    "sh_l": (0.378, 0.248), "sh_r": (0.622, 0.248),
    "el_l": (0.318, 0.378), "el_r": (0.682, 0.378),
    "hd_l": (0.262, 0.492), "hd_r": (0.738, 0.492),
    "hip_l": (0.424, 0.580), "hip_r": (0.576, 0.580),
    "kn_l": (0.420, 0.758), "kn_r": (0.580, 0.758),
    "ft_l": (0.414, 0.930), "ft_r": (0.586, 0.930),
}


def _j(**overrides: Point) -> Dict[str, Point]:
    return {**_BASE, **overrides}


# --------------------------------------------------------------------------- #
# poses
# --------------------------------------------------------------------------- #
POSES: Dict[str, Pose] = {
    # Présente, paumes ouvertes — la pose « explique une idée ».
    "presenter": Pose([Figure(_j(
        el_l=(0.315, 0.365), el_r=(0.685, 0.365),
        hd_l=(0.232, 0.452), hd_r=(0.768, 0.452)))], label="Présente"),

    # Montre du doigt vers le haut — « regarde ça ».
    "pointing": Pose([Figure(_j(
        el_r=(0.690, 0.300), hd_r=(0.790, 0.170),
        el_l=(0.352, 0.380), hd_l=(0.352, 0.500)))], label="Montre"),

    # Main au menton — question, hésitation, objection.
    "thinking": Pose([Figure(_j(
        el_r=(0.660, 0.380), hd_r=(0.552, 0.205),
        el_l=(0.360, 0.390), hd_l=(0.430, 0.470)))], label="Réfléchit"),

    # Tient un téléphone — contact, message, WhatsApp.
    "phone": Pose([Figure(_j(
        el_r=(0.650, 0.360), hd_r=(0.575, 0.265),
        el_l=(0.355, 0.385), hd_l=(0.400, 0.495)))],
        [Prop("accent", (0.545, 0.185, 0.625, 0.290), front=True)], label="Téléphone"),

    # Marche — progression, mise en action.
    "walking": Pose([Figure(_j(
        el_l=(0.318, 0.352), hd_l=(0.300, 0.480),
        el_r=(0.678, 0.352), hd_r=(0.700, 0.455),
        kn_l=(0.372, 0.742), ft_l=(0.318, 0.940),
        kn_r=(0.612, 0.748), ft_r=(0.678, 0.940)))], label="Avance"),

    # Bras levés sur un socle — résultat, réussite, palier atteint.
    "podium": Pose([Figure(_j(
        el_l=(0.318, 0.300), hd_l=(0.268, 0.168),
        el_r=(0.682, 0.300), hd_r=(0.732, 0.168),
        kn_l=(0.420, 0.700), kn_r=(0.580, 0.700),
        ft_l=(0.414, 0.845), ft_r=(0.586, 0.845)), scale=0.90,
        offset=(0.0, -0.060))],
        [Prop("rect", (0.286, 0.820, 0.714, 0.958))], label="Réussite"),

    # Poignée de main — les mains intérieures se rejoignent au CENTRE du cadre.
    "handshake": Pose([
        Figure(_j(el_r=(0.632, 0.400), hd_r=(0.694, 0.436),
                  el_l=(0.340, 0.392), hd_l=(0.322, 0.520)),
               offset=(-0.175, 0.0), scale=0.90),
        Figure(_j(el_r=(0.632, 0.400), hd_r=(0.694, 0.436),
                  el_l=(0.340, 0.392), hd_l=(0.322, 0.520)),
               offset=(0.175, 0.0), scale=0.90, flip=True),
    ], label="Accord"),

    # Deux personnes assises face à une table — négociation, rendez-vous.
    # Les jambes descendent droit sous le bassin: la table (au premier plan)
    # les masque, ce qui donne une assise lisible.
    "table_meeting": Pose([
        Figure(_j(el_r=(0.648, 0.432), hd_r=(0.586, 0.548),
                  el_l=(0.352, 0.424), hd_l=(0.396, 0.548),
                  hip_l=(0.436, 0.596), hip_r=(0.564, 0.596),
                  kn_l=(0.436, 0.716), kn_r=(0.564, 0.716),
                  ft_l=(0.436, 0.876), ft_r=(0.564, 0.876)),
               offset=(-0.182, 0.040), scale=0.84),
        Figure(_j(el_r=(0.648, 0.432), hd_r=(0.586, 0.548),
                  el_l=(0.352, 0.424), hd_l=(0.396, 0.548),
                  hip_l=(0.436, 0.596), hip_r=(0.564, 0.596),
                  kn_l=(0.436, 0.716), kn_r=(0.564, 0.716),
                  ft_l=(0.436, 0.876), ft_r=(0.564, 0.876)),
               offset=(0.182, 0.040), scale=0.84, flip=True),
    ], [Prop("rect", (0.296, 0.628, 0.704, 0.700), front=True),
        Prop("rect", (0.466, 0.700, 0.534, 0.900), front=True)], label="Rendez-vous"),

    # Bras levés devant un mur — blocage, objection, obstacle.
    "blocked": Pose([Figure(_j(
        el_l=(0.330, 0.336), hd_l=(0.398, 0.256),
        el_r=(0.670, 0.336), hd_r=(0.602, 0.256)), offset=(-0.098, 0.0))],
        [Prop("rect", (0.716, 0.170, 0.868, 0.944))], label="Blocage"),
}

DEFAULT_POSE = "presenter"

# Passerelle depuis le vocabulaire d'icônes déjà utilisé par le moteur, pour
# qu'une scène choisisse une silhouette qui COLLE au propos.
_ICON_TO_POSE: Dict[str, str] = {
    "money": "presenter", "crypto": "presenter", "bank": "presenter",
    "card": "phone", "transfer": "phone", "phone": "phone", "chat": "phone",
    "megaphone": "pointing", "target": "pointing", "rocket": "podium",
    "growth": "podium", "chart": "podium", "star": "podium", "check": "podium",
    "people": "handshake", "handshake": "handshake",
    "idea": "thinking", "book": "thinking", "globe": "walking",
    "clock": "table_meeting", "calendar": "table_meeting", "cart": "walking",
    "map": "walking", "gear": "thinking", "heart": "presenter",
    "warning": "blocked", "shield": "blocked", "lock": "blocked",
}


def pose_for_icon(icon: Optional[str]) -> str:
    """Silhouette la plus proche du sens porté par *icon*."""
    return _ICON_TO_POSE.get((icon or "").strip().lower(), DEFAULT_POSE)


def pose_names() -> List[str]:
    return list(POSES)


# --------------------------------------------------------------------------- #
# géométrie
# --------------------------------------------------------------------------- #
def _place(p: Point, fig: Figure, sway: float) -> Point:
    x, y = p
    if fig.flip:
        x = 1.0 - x
    x = 0.5 + (x - 0.5) * fig.scale + fig.offset[0]
    y = 0.5 + (y - 0.5) * fig.scale + fig.offset[1]
    return (x + sway, y)


def _figure_parts(fig: Figure, t: float, phase: float
                  ) -> Tuple[List[Sequence[Point]], List[Point], Point, float]:
    """Retourne (membres, polygone du buste, centre de tête, rayon de tête)."""
    breathe = 0.004 * math.sin(2 * math.pi * 0.45 * t + phase) * fig.sway
    arm_sway = 0.010 * math.sin(2 * math.pi * 0.30 * t + phase) * fig.sway
    j = fig.joints

    def P(name: str, extra: float = 0.0) -> Point:
        x, y = j[name]
        return _place((x + extra, y - (breathe if name != "ft_l" and name != "ft_r" else 0.0)),
                      fig, 0.0)

    limbs = [
        [P("sh_l"), P("el_l", -arm_sway), P("hd_l", -arm_sway * 1.6)],
        [P("sh_r"), P("el_r", arm_sway), P("hd_r", arm_sway * 1.6)],
        [P("hip_l"), P("kn_l"), P("ft_l")],
        [P("hip_r"), P("kn_r"), P("ft_r")],
    ]
    torso = [P("sh_l"), P("sh_r"), P("hip_r"), P("hip_l")]
    head_c = P("head")
    head_r = 0.052 * fig.scale
    return limbs, torso, head_c, head_r


def _to_px(p: Point, box: Tuple[int, int, int, int]) -> Point:
    x0, y0, x1, y1 = box
    return (x0 + p[0] * (x1 - x0), y0 + p[1] * (y1 - y0))


def _draw_figure(d: ImageDraw.ImageDraw, fig: Figure, box: Tuple[int, int, int, int],
                 t: float, phase: float, color, dx: int = 0, dy: int = 0):
    x0, y0, x1, y1 = box
    span = min(x1 - x0, y1 - y0)
    limbs, torso, head_c, head_r = _figure_parts(fig, t, phase)
    arm_w = max(4, int(span * 0.062 * fig.scale))
    leg_w = max(4, int(span * 0.082 * fig.scale))

    for i, limb in enumerate(limbs):
        pts = [(px + dx, py + dy) for px, py in (_to_px(p, box) for p in limb)]
        w = arm_w if i < 2 else leg_w
        d.line(pts, fill=color, width=w, joint="curve")
        for cap in (pts[0], pts[-1]):
            d.ellipse((cap[0] - w / 2, cap[1] - w / 2, cap[0] + w / 2, cap[1] + w / 2),
                      fill=color)

    tp = [(px + dx, py + dy) for px, py in (_to_px(p, box) for p in torso)]
    # épaules débordantes + taille resserrée -> veste, pas un bâton
    flare = span * 0.030 * fig.scale
    tp[0] = (tp[0][0] - flare, tp[0][1] - flare * 0.45)
    tp[1] = (tp[1][0] + flare, tp[1][1] - flare * 0.45)
    d.polygon(tp, fill=color)

    hx, hy = _to_px(head_c, box)
    hr = head_r * span
    # cou: relie la tête au buste (sinon la tête flotte)
    neck_w = hr * 0.52
    d.rectangle((hx - neck_w + dx, hy + dy, hx + neck_w + dx,
                 (tp[0][1] + tp[1][1]) / 2 + dy), fill=color)
    d.rounded_rectangle((hx - hr * 0.86 + dx, hy - hr * 1.20 + dy,
                         hx + hr * 0.86 + dx, hy + hr * 1.05 + dy),
                        radius=int(hr * 0.40), fill=color)


def _draw_collar(d: ImageDraw.ImageDraw, fig: Figure, box: Tuple[int, int, int, int],
                 t: float, phase: float, accent):
    """Le col/plastron clair — le seul éclat chaud de la silhouette."""
    _, torso, _, _ = _figure_parts(fig, t, phase)
    sh_l, sh_r = torso[0], torso[1]
    mid = ((sh_l[0] + sh_r[0]) / 2, (sh_l[1] + sh_r[1]) / 2)
    depth = 0.115 * fig.scale
    pts = [
        (mid[0] - (sh_r[0] - sh_l[0]) * 0.20, mid[1] + 0.004),
        (mid[0], mid[1] + depth),
        (mid[0] + (sh_r[0] - sh_l[0]) * 0.20, mid[1] + 0.004),
    ]
    d.polygon([_to_px(p, box) for p in pts], fill=accent)


def _draw_props(d: ImageDraw.ImageDraw, props: Sequence[Prop],
                box: Tuple[int, int, int, int], color, accent, dx: int = 0, dy: int = 0,
                front: bool = False):
    for prop in props:
        if prop.front != front:
            continue
        a = _to_px((prop.box[0], prop.box[1]), box)
        b = _to_px((prop.box[2], prop.box[3]), box)
        rect = (a[0] + dx, a[1] + dy, b[0] + dx, b[1] + dy)
        if prop.kind == "accent":
            d.rounded_rectangle(rect, radius=int((b[0] - a[0]) * 0.18), fill=accent)
        elif prop.kind == "round":
            d.ellipse(rect, fill=color)
        else:
            d.rectangle(rect, fill=color)


# --------------------------------------------------------------------------- #
# rendu
# --------------------------------------------------------------------------- #
def render_silhouette(name: str, width: int, height: int, *, t: float = 0.0,
                      body=BODY, accent=ACCENT, rim=RIM,
                      reveal: float = 1.0) -> Image.Image:
    """Rend la pose *name* sur un calque RGBA transparent.

    *reveal* (0..1) fait monter la silhouette depuis le bas avec un fondu —
    l'entrée utilisée quand elle arrive dans une carte.
    """
    pose = POSES.get(name) or POSES[DEFAULT_POSE]
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    box = (0, 0, width, height)
    span = min(width, height)

    # 1) liseré froid: mêmes formes décalées, sous le corps
    rim_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    dr = ImageDraw.Draw(rim_layer)
    off = max(2, int(span * 0.012))
    _draw_props(dr, pose.props, box, rim, rim, dx=-off)
    for i, fig in enumerate(pose.figures):
        _draw_figure(dr, fig, box, t, i * 1.7, rim, dx=-off)
    _draw_props(dr, pose.props, box, rim, rim, dx=-off, front=True)
    layer.alpha_composite(rim_layer.filter(ImageFilter.GaussianBlur(max(1, off // 2))))

    # 2) corps (accessoires d'arrière-plan, personnages, puis premier plan)
    body_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    db = ImageDraw.Draw(body_layer)
    _draw_props(db, pose.props, box, body, accent)
    for i, fig in enumerate(pose.figures):
        _draw_figure(db, fig, box, t, i * 1.7, body)
    _draw_props(db, pose.props, box, body, accent, front=True)
    layer.alpha_composite(body_layer)

    # 3) col chaud + halo
    warm = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    dw = ImageDraw.Draw(warm)
    for i, fig in enumerate(pose.figures):
        _draw_collar(dw, fig, box, t, i * 1.7, accent)
    layer.alpha_composite(warm.filter(ImageFilter.GaussianBlur(max(1, span // 260))))
    layer.alpha_composite(warm)

    if reveal < 0.999:
        rise = int((1.0 - max(0.0, reveal)) * height * 0.10)
        shifted = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        shifted.paste(layer, (0, rise))
        r, g, b, a = shifted.split()
        layer = Image.merge("RGBA", (r, g, b, a.point(
            lambda v: int(v * max(0.0, min(1.0, reveal))))))
    return layer


def render_plate(name: str, width: int, height: int, *, t: float = 0.0,
                 plate=PLATE, body=BODY, accent=ACCENT, rim=RIM,
                 reveal: float = 1.0) -> Image.Image:
    """La même silhouette posée sur un fond clair dégradé — une « plaque »
    opaque directement utilisable comme illustration par le moteur."""
    grad = Image.new("RGB", (1, height))
    px = grad.load()
    for y in range(height):
        f = abs(y / max(1, height - 1) - 0.38) * 2.0
        v = int(plate[0] - 26 * min(1.0, f) ** 1.3)
        px[0, y] = (v, v + 1, v)
    out = grad.resize((width, height)).convert("RGBA")
    inset = (int(width * 0.10), int(height * 0.06))
    fig = render_silhouette(name, width - 2 * inset[0], height - 2 * inset[1],
                            t=t, body=body, accent=accent, rim=rim, reveal=reveal)
    out.alpha_composite(fig, inset)
    return out


# --------------------------------------------------------------------------- #
# export SVG (pour ouvrir/retoucher les poses dans un outil vectoriel)
# --------------------------------------------------------------------------- #
def to_svg(name: str, width: int = 600, height: int = 900, *,
           body=BODY, accent=ACCENT, rim=RIM) -> str:
    pose = POSES.get(name) or POSES[DEFAULT_POSE]
    box = (0, 0, width, height)
    span = min(width, height)

    def hexa(c) -> str:
        return "#%02x%02x%02x" % (c[0], c[1], c[2])

    parts: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'  <title>{name}</title>',
    ]
    for shift, color, opacity in ((-max(2, int(span * 0.012)), rim, 0.85), (0, body, 1.0)):
        parts.append(f'  <g fill="{hexa(color)}" stroke="{hexa(color)}" '
                     f'stroke-linecap="round" stroke-linejoin="round" opacity="{opacity}">')
        for prop in pose.props:
            a = _to_px((prop.box[0], prop.box[1]), box)
            b = _to_px((prop.box[2], prop.box[3]), box)
            parts.append(f'    <rect x="{a[0] + shift:.1f}" y="{a[1]:.1f}" '
                         f'width="{b[0] - a[0]:.1f}" height="{b[1] - a[1]:.1f}"/>')
        for i, fig in enumerate(pose.figures):
            limbs, torso, head_c, head_r = _figure_parts(fig, 0.0, i * 1.7)
            arm_w = max(3, int(span * 0.042 * fig.scale))
            leg_w = max(3, int(span * 0.055 * fig.scale))
            for k, limb in enumerate(limbs):
                pts = " ".join(f"{x + shift:.1f},{y:.1f}"
                               for x, y in (_to_px(p, box) for p in limb))
                parts.append(f'    <polyline points="{pts}" fill="none" '
                             f'stroke-width="{arm_w if k < 2 else leg_w}"/>')
            tp = " ".join(f"{x + shift:.1f},{y:.1f}"
                          for x, y in (_to_px(p, box) for p in torso))
            parts.append(f'    <polygon points="{tp}" stroke="none"/>')
            hx, hy = _to_px(head_c, box)
            hr = head_r * span
            parts.append(f'    <rect x="{hx - hr * 0.82 + shift:.1f}" y="{hy - hr * 1.12:.1f}" '
                         f'width="{hr * 1.64:.1f}" height="{hr * 2.24:.1f}" '
                         f'rx="{hr * 0.42:.1f}" stroke="none"/>')
        parts.append('  </g>')

    parts.append(f'  <g fill="{hexa(accent)}" stroke="none">')
    for i, fig in enumerate(pose.figures):
        _, torso, _, _ = _figure_parts(fig, 0.0, i * 1.7)
        sh_l, sh_r = torso[0], torso[1]
        mid = ((sh_l[0] + sh_r[0]) / 2, (sh_l[1] + sh_r[1]) / 2)
        depth = 0.115 * fig.scale
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (
            _to_px(p, box) for p in (
                (mid[0] - (sh_r[0] - sh_l[0]) * 0.20, mid[1] + 0.004),
                (mid[0], mid[1] + depth),
                (mid[0] + (sh_r[0] - sh_l[0]) * 0.20, mid[1] + 0.004))))
        parts.append(f'    <polygon points="{pts}"/>')
    parts.append('  </g>')
    parts.append('</svg>')
    return "\n".join(parts)


def export_svgs(outdir: str, width: int = 600, height: int = 900) -> List[str]:
    os.makedirs(outdir, exist_ok=True)
    written: List[str] = []
    for name in POSES:
        path = os.path.join(outdir, f"{name}.svg")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(to_svg(name, width, height))
        written.append(path)
    return written


# --------------------------------------------------------------------------- #
# SVG personnalisés déposés par l'utilisateur
# --------------------------------------------------------------------------- #
CUSTOM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "assets", "silhouettes")


def custom_pose_names() -> List[str]:
    """Les .svg déposés dans assets/silhouettes/ (repliés silencieusement si le
    rasteriseur n'est pas installé — le moteur ne doit jamais casser pour ça)."""
    if not os.path.isdir(CUSTOM_DIR):
        return []
    return sorted(f[:-4] for f in os.listdir(CUSTOM_DIR) if f.lower().endswith(".svg"))


def load_custom_svg(name: str, width: int, height: int) -> Optional[Image.Image]:
    path = os.path.join(CUSTOM_DIR, f"{name}.svg")
    if not os.path.exists(path):
        return None
    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPM
    except ImportError:
        print("[silhouettes] svglib absent — SVG personnalisés ignorés",
              file=sys.stderr)
        return None
    try:
        drawing = svg2rlg(path)
        if drawing is None or not drawing.width or not drawing.height:
            return None
        scale = min(width / drawing.width, height / drawing.height)
        drawing.scale(scale, scale)
        drawing.width, drawing.height = drawing.width * scale, drawing.height * scale
        pil = renderPM.drawToPIL(drawing, bg=0xFFFFFF, configPIL={"transparent": True})
        img = pil.convert("RGBA")
        out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        out.alpha_composite(img, ((width - img.width) // 2, (height - img.height) // 2))
        return out
    except Exception as exc:  # noqa: BLE001 - un SVG bancal ne casse pas le rendu
        print(f"[silhouettes] SVG '{name}' illisible: {exc}", file=sys.stderr)
        return None


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Bibliothèque de silhouettes vectorielles")
    ap.add_argument("--export-svg", metavar="DIR", help="écrit un .svg par pose")
    ap.add_argument("--preview", metavar="PNG", help="planche PNG de toutes les poses")
    ap.add_argument("--list", action="store_true", help="liste les poses")
    args = ap.parse_args(argv)

    if args.list or not (args.export_svg or args.preview):
        for name, pose in POSES.items():
            print(f"{name:16s} {pose.label}")
        for name in custom_pose_names():
            print(f"{name:16s} (SVG personnalisé)")
        return 0
    if args.export_svg:
        paths = export_svgs(args.export_svg)
        print(f"[silhouettes] {len(paths)} SVG -> {args.export_svg}")
    if args.preview:
        names = list(POSES)
        cols, tw, th = 5, 300, 450
        rows = (len(names) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * tw, rows * th), (236, 237, 235))
        for i, name in enumerate(names):
            r, c = divmod(i, cols)
            sheet.paste(render_plate(name, tw, th).convert("RGB"), (c * tw, r * th))
        sheet.save(args.preview)
        print(f"[silhouettes] planche -> {args.preview}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
