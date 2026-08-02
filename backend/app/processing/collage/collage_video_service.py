"""ÉTAPE 5 — `CollageVideoService`: le mouvement `collage_assemble`.

Nouveau type de mouvement du produit, à côté du Ken Burns existant:

    le clip DÉMARRE sur un fond vide
    → les éléments arrivent un par un, dans l'ordre décidé par le planner
    → chaque pose « claque » en quelques paliers stop-motion
    → l'image finale est exactement le visuel généré
    → la scène respire à peine (ce n'est pas un zoom, c'est un assemblage)

Deux moteurs de rendu, un seul contrat (`CollageVideoRenderer`):

  * **local** (défaut) — compositeur déterministe PIL/NumPy → ProRes 4444 RGBA.
    Gratuit, hors-ligne, reproductible, et surtout: il respecte l'ordre
    d'apparition à la frame près, ce qu'un modèle vidéo ne garantit jamais.
  * **http** — image→vidéo par API, entièrement piloté par configuration
    (URL, en-têtes, chemins de réponse). Aucun fournisseur codé en dur.

L'astuce du rendu local: le prompt image a placé chaque objet dans une zone
connue du cadre (`collage_types.LAYOUT_TEMPLATES`). On repartitionne donc
l'image finale selon ces mêmes zones et on révèle chaque région comme une
pièce de papier posée. Prompt et animation partagent une seule source de
vérité — pas besoin de segmentation sémantique.
"""
from __future__ import annotations

import logging
import math
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional, Protocol, Sequence, runtime_checkable

import numpy as np
from PIL import Image, ImageFilter

from . import collage_config as ccfg
from .collage_types import (
    CollageClip,
    CollageConcept,
    CollagePrompts,
    hex_to_rgb,
    layout_for,
)

logger = logging.getLogger(__name__)

#: Taille d'une feuille de papier, en multiples du rayon de sa cellule de
#: layout. Au-delà d'environ 1,7 les pièces voisines du gabarit à 4 éléments se
#: recouvrent et la scène devient un empilement illisible.
PIECE_SPREAD = 1.60

try:  # Pillow >= 9.1
    _RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:  # pragma: no cover - Pillow ancien
    _RESAMPLE = Image.LANCZOS


# --------------------------------------------------------------------------- #
# Contrat de rendu
# --------------------------------------------------------------------------- #
@runtime_checkable
class CollageVideoRenderer(Protocol):
    name: str

    def render(self, concept: CollageConcept, image_path: Optional[str],
               out_path: str, *, duration: float, prompts: Optional[CollagePrompts]
               ) -> float:
        """Écrit le clip et renvoie sa durée réelle (secondes)."""


RendererFactory = Callable[[], CollageVideoRenderer]
RENDERERS: dict[str, RendererFactory] = {}


def register_renderer(name: str, factory: RendererFactory) -> None:
    RENDERERS[name.strip().lower()] = factory


# --------------------------------------------------------------------------- #
# Rendu local déterministe
# --------------------------------------------------------------------------- #
class _Piece:
    """Une pièce de papier prête à poser (layer RGBA + position cible)."""

    __slots__ = ("layer", "x", "y", "entrance", "order")

    def __init__(self, layer: Image.Image, x: int, y: int, entrance: str, order: int):
        self.layer = layer
        self.x = x
        self.y = y
        self.entrance = entrance
        self.order = order


class LocalAssembleRenderer:
    """Compositeur `collage_assemble` — 100 % local, 100 % déterministe."""

    name = "local"

    def __init__(self, width: Optional[int] = None, height: Optional[int] = None,
                 fps: Optional[int] = None):
        from app.autoedit_engine import config as engine_config
        self.width = width or engine_config.WIDTH
        self.height = height or engine_config.HEIGHT
        self.fps = fps or engine_config.FPS

    # ------------------------------------------------------------------ #
    def render(self, concept: CollageConcept, image_path: Optional[str],
               out_path: str, *, duration: float,
               prompts: Optional[CollagePrompts] = None) -> float:
        from app.autoedit_engine.render_utils import ProResPipe

        duration = max(ccfg.CLIP_DURATION_MIN,
                       min(ccfg.CLIP_DURATION_MAX, float(duration or ccfg.CLIP_DURATION)))
        background = self._background_plate(concept)
        source = self._load_ai_image(image_path)
        if source is not None:
            # Une image générée existe: on la découpe selon les zones que le
            # prompt lui a imposées (l'union des pièces reconstitue l'image).
            pieces = self._slice_pieces(concept, source)
        else:
            # Chemin des moteurs UGC (et repli du moteur éditorial sans crédit):
            # chaque objet du concept devient une VRAIE pièce de papier découpée,
            # dessinée en vectoriel. Bien meilleur qu'une partition d'un aplat:
            # la forme est reconnaissable et chaque élément a sa propre entrée.
            pieces = self._pictogram_pieces(concept)
        n_frames = max(2, int(round(duration * self.fps)))

        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
        with ProResPipe(out_path, width=self.width, height=self.height, fps=self.fps) as pipe:
            for index in range(n_frames):
                t = index / self.fps
                pipe.write(self._compose(background, pieces, t, duration))
        return duration

    # ------------------------------------------------------------------ #
    def _load_ai_image(self, image_path: Optional[str]) -> Optional[Image.Image]:
        """L'image générée, cadrée — ou None s'il n'y en a pas d'exploitable."""
        if not image_path or not os.path.exists(image_path):
            return None
        try:
            return _cover(Image.open(image_path).convert("RGBA"),
                          self.width, self.height)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[collage_video] image illisible (%s) — pièces dessinées",
                           str(exc)[:120])
            return None

    # ------------------------------------------------------------------ #
    def _pictogram_pieces(self, concept: CollageConcept) -> list[_Piece]:
        """Une pièce de papier découpée PAR OBJET du concept, sans aucune IA.

        C'est le moteur d'illustration des profils UGC. Chaque objet nommé par
        le planner est traduit en découpe vectorielle (`collage_shapes`), posée
        sur son papier coloré, avec contour crème et ombre courte — exactement
        le même vocabulaire visuel que les pièces issues d'une image générée,
        pour que les trois moteurs restent cohérents entre eux.

        L'ancien repli dessinait des ellipses et des rectangles de couleur: la
        scène existait mais n'illustrait RIEN. Ici la forme porte le sens.
        """
        from . import collage_shapes

        objects = concept.ordered_objects()
        cells = concept.layout()
        count = min(len(objects), len(cells))
        pieces: list[_Piece] = []
        ink = hex_to_rgb("#1D1D1B") + (255,)
        for i in range(count):
            obj = objects[i]
            _, cx, cy, radius = cells[i]
            # La feuille déborde du pictogramme (c'est ce qui fait « élément
            # collé » et pas « icône »), mais elle doit rester DANS sa zone:
            # au-delà, les pièces voisines se recouvrent et la scène devient
            # illisible. PIECE_SPREAD est calibré sur le gabarit le plus serré.
            size = max(48, int(radius * self.width * PIECE_SPREAD))
            w = h = size
            paper = hex_to_rgb(obj.paper_color) + (255,)
            # Un papier très sombre a besoin d'une encre claire pour rester lisible.
            glyph_ink = ink if _luma(paper) > 110 else hex_to_rgb("#F7F1E3") + (255,)
            accent = hex_to_rgb(
                _accent_for(concept, obj.paper_color, glyph_ink)) + (255,)
            seed = (abs(hash((concept.id, obj.name, obj.order))) % 99991) + 1
            # Résolution STRICTE: un objet que le vocabulaire ne connaît pas ne
            # doit pas être remplacé par une découpe tirée au hasard de son nom
            # — on parlerait d'une voiture et la scène montrerait un flacon. Le
            # planner a normalement déjà écarté ces objets (ancrage lexical);
            # ce garde-fou couvre les appels directs au renderer.
            pictogram = collage_shapes.resolve_strict(obj.name)
            if pictogram is None:
                logger.info("[collage_video] « %s » hors vocabulaire — forme neutre",
                            obj.name[:40])
                pictogram = collage_shapes.DEFAULT_PICTOGRAM
            layer = collage_shapes.render_cutout(
                pictogram, w, h,
                paper_color=paper, ink_color=glyph_ink, accent_color=accent,
                seed=seed, tilt=(-4.5 if i % 2 else 4.0),
            )
            layer = _add_keyline(layer, layer.split()[3])
            layer = _add_shadow(layer)
            x = int(cx * self.width - layer.width / 2)
            y = int(cy * self.height - layer.height / 2)
            pieces.append(_Piece(layer, x, y, obj.entrance, obj.order))
        pieces.sort(key=lambda p: p.order)
        return pieces

    # ------------------------------------------------------------------ #
    def _background_plate(self, concept: CollageConcept) -> Image.Image:
        """Le fond VIDE sur lequel tout se pose: aplat + grain de papier."""
        plate = Image.new("RGBA", (self.width, self.height),
                          hex_to_rgb(concept.background_color) + (255,))
        return _apply_paper_grain(plate, ccfg.PAPER_GRAIN_STRENGTH)

    # ------------------------------------------------------------------ #
    def _slice_pieces(self, concept: CollageConcept,
                      source: Image.Image) -> list[_Piece]:
        """Découpe l'image finale en pièces, une par objet du concept.

        Partition par plus proche centre de cellule (pondéré par le rayon) →
        chaque pixel appartient à exactement une pièce, donc l'union des pièces
        reconstitue l'image finale au pixel près.
        """
        objects = concept.ordered_objects()
        cells = concept.layout()
        count = min(len(objects), len(cells))
        if count == 0:
            return []

        ys, xs = np.mgrid[0:self.height, 0:self.width]
        xs_n = xs / float(self.width)
        ys_n = ys / float(self.height)
        # Distance normalisée au centre de chaque cellule (l'aspect vertical est
        # compensé pour que les zones restent visuellement circulaires).
        aspect = self.height / float(self.width)
        scores = np.stack([
            np.sqrt(((xs_n - cx) ** 2) + ((ys_n - cy) * aspect) ** 2) / max(0.08, radius)
            for _, cx, cy, radius in cells[:count]
        ])
        owner = np.argmin(scores, axis=0)

        rgba = np.array(source.convert("RGBA"), dtype=np.uint8)
        pieces: list[_Piece] = []
        for i in range(count):
            mask_arr = (owner == i).astype(np.uint8) * 255
            mask = Image.fromarray(mask_arr, "L").filter(ImageFilter.GaussianBlur(2.5))
            bbox = mask.getbbox()
            if not bbox:
                continue
            layer = Image.fromarray(rgba, "RGBA").copy()
            layer.putalpha(mask)
            layer = layer.crop(bbox)
            layer = _add_keyline(layer, mask.crop(bbox))
            layer = _add_shadow(layer)
            pieces.append(_Piece(layer, bbox[0] - ccfg.SHADOW_OFFSET,
                                 bbox[1] - ccfg.SHADOW_OFFSET,
                                 objects[i].entrance, objects[i].order))
        pieces.sort(key=lambda p: p.order)
        return pieces

    # ------------------------------------------------------------------ #
    def _compose(self, background: Image.Image, pieces: Sequence[_Piece],
                 t: float, duration: float) -> Image.Image:
        canvas = background.copy()
        if not pieces:
            return canvas

        hold = duration * ccfg.EMPTY_HOLD_RATIO           # fond vide au départ
        assembly = max(0.6, duration * ccfg.ASSEMBLY_RATIO - hold)
        step = assembly / max(1, len(pieces))

        for index, piece in enumerate(pieces):
            start = hold + index * step
            progress = (t - start) / max(0.05, ccfg.ELEMENT_ENTRANCE_DUR)
            if progress <= 0.0:
                continue                                   # pas encore posée
            progress = _stop_motion(min(1.0, progress))
            self._place(canvas, piece, progress)

        breath = 1.0 + ccfg.BREATH_AMOUNT * (t / max(0.01, duration))
        return _scale_about_center(canvas, breath) if breath > 1.001 else canvas

    # ------------------------------------------------------------------ #
    def _place(self, canvas: Image.Image, piece: _Piece, progress: float) -> None:
        eased = 1.0 - (1.0 - progress) ** 3               # ease-out cubique
        layer = piece.layer
        x, y = piece.x, piece.y
        travel = 1.0 - eased

        if piece.entrance == "drop":
            y -= int(travel * 0.42 * self.height)
        elif piece.entrance == "rise":
            y += int(travel * 0.38 * self.height)
        elif piece.entrance == "slide_left":
            x -= int(travel * 0.55 * self.width)
        elif piece.entrance == "slide_right":
            x += int(travel * 0.55 * self.width)
        elif piece.entrance == "rotate_in" and travel > 0.02:
            layer = layer.rotate(travel * 14.0, expand=True, resample=Image.BICUBIC)
            x -= (layer.width - piece.layer.width) // 2
            y -= (layer.height - piece.layer.height) // 2
        elif piece.entrance == "scale_pop":
            # Léger dépassement puis retour: la pièce est « pressée » en place.
            overshoot = 1.0 + 0.14 * math.sin(math.pi * min(1.0, progress))
            layer = _scaled(layer, overshoot)
            x -= (layer.width - piece.layer.width) // 2
            y -= (layer.height - piece.layer.height) // 2

        if progress < 0.999:
            layer = _with_opacity(layer, 0.35 + 0.65 * eased)
        canvas.alpha_composite(layer, (x, y))


register_renderer("local", LocalAssembleRenderer)


# --------------------------------------------------------------------------- #
# Rendu par API image→vidéo — 100 % piloté par configuration
# --------------------------------------------------------------------------- #
class HttpImageToVideoRenderer:
    """Renderer générique image→vidéo.

    Aucun fournisseur n'est codé en dur: l'URL, l'en-tête d'authentification, le
    nom du modèle et le chemin de la vidéo dans la réponse sont des variables
    d'environnement. Brancher un fournisseur = renseigner la configuration.
    """

    name = "http"

    def __init__(self) -> None:
        self.url = os.environ.get("COLLAGE_VIDEO_API_URL", "")
        self.api_key = os.environ.get("COLLAGE_VIDEO_API_KEY", "")
        self.auth_header = os.environ.get("COLLAGE_VIDEO_AUTH_HEADER", "Authorization")
        self.auth_prefix = os.environ.get("COLLAGE_VIDEO_AUTH_PREFIX", "Bearer ")
        self.model = os.environ.get("COLLAGE_VIDEO_MODEL", ccfg.MAXFUSION_VIDEO_MODEL)
        # Chemin pointé dans le JSON de réponse, ex: "data.0.url".
        self.result_path = os.environ.get("COLLAGE_VIDEO_RESULT_PATH", "data.0.url")

    def render(self, concept: CollageConcept, image_path: Optional[str],
               out_path: str, *, duration: float,
               prompts: Optional[CollagePrompts] = None) -> float:
        import base64
        import httpx

        if not self.url or not self.api_key:
            raise RuntimeError("COLLAGE_VIDEO_API_URL/KEY manquants")
        payload = {
            "model": self.model,
            "prompt": (prompts.video_prompt if prompts else concept.metaphor),
            "duration": round(duration, 2),
            "aspect_ratio": (prompts.aspect_ratio if prompts else ccfg.ASPECT_RATIO),
        }
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as fh:
                payload["image"] = base64.b64encode(fh.read()).decode("ascii")

        headers = {self.auth_header: f"{self.auth_prefix}{self.api_key}",
                   "Content-Type": "application/json"}
        with httpx.Client(timeout=ccfg.VIDEO_TIMEOUT_S) as client:
            resp = client.post(self.url, headers=headers, json=payload)
            if resp.status_code >= 400:
                raise RuntimeError(f"video api {resp.status_code}: {resp.text[:160]}")
            url = _dig(resp.json() or {}, self.result_path)
            if not isinstance(url, str) or not url:
                raise RuntimeError("video api: aucune vidéo dans la réponse")
            video = client.get(url)
            if video.status_code >= 400 or not video.content:
                raise RuntimeError(f"video download {video.status_code}")
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
        with open(out_path, "wb") as fh:
            fh.write(video.content)
        return duration


register_renderer("http", HttpImageToVideoRenderer)


# --------------------------------------------------------------------------- #
class CollageVideoService:
    """Anime les scènes de collage (`collage_assemble`)."""

    def __init__(self, renderer: Optional[CollageVideoRenderer] = None,
                 max_workers: Optional[int] = None):
        self.renderer = renderer or self._build_renderer()
        self.max_workers = max(1, int(max_workers or ccfg.RENDER_WORKERS))

    @staticmethod
    def _build_renderer() -> CollageVideoRenderer:
        name = (ccfg.VIDEO_PROVIDER or "local").strip().lower()
        factory = RENDERERS.get(name)
        if not factory:
            logger.warning("[collage_video] renderer '%s' inconnu — local", name)
            factory = RENDERERS["local"]
        try:
            return factory()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[collage_video] renderer '%s' indisponible (%s) — local",
                           name, str(exc)[:140])
            return LocalAssembleRenderer()

    # ------------------------------------------------------------------ #
    def animate(self, concept: CollageConcept, image_path: Optional[str],
                out_dir: str, *, prompts: Optional[CollagePrompts] = None,
                duration: Optional[float] = None) -> Optional[CollageClip]:
        """Rend UNE scène. Renvoie None si le rendu échoue (jamais d'exception)."""
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"cg_{concept.id}.mov")
        target = duration or _duration_for(concept)
        try:
            real = self.renderer.render(concept, image_path, out_path,
                                        duration=target, prompts=prompts)
        except Exception as exc:  # noqa: BLE001 - jamais bloquant
            logger.warning("[collage_video] %s: rendu échoué (%s)",
                           concept.id, str(exc)[:180])
            return None
        if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            logger.warning("[collage_video] %s: clip vide", concept.id)
            return None
        return CollageClip(
            concept_id=concept.id, clip_path=out_path, duration=real,
            source_start=concept.source_start,
            source_end=concept.source_start + real,
            label=concept.label, renderer=self.renderer.name,
        )

    # ------------------------------------------------------------------ #
    def animate_many(
        self,
        items: Sequence[tuple[CollageConcept, Optional[str], Optional[CollagePrompts]]],
        out_dir: str,
    ) -> list[CollageClip]:
        """Rend N scènes. Le rendu local est CPU-bound: parallélisme modéré."""
        if not items:
            return []
        if len(items) == 1 or self.max_workers == 1:
            results = [self.animate(c, img, out_dir, prompts=p) for c, img, p in items]
        else:
            with ThreadPoolExecutor(max_workers=min(self.max_workers, len(items))) as pool:
                futures = [pool.submit(self.animate, c, img, out_dir, prompts=p)
                           for c, img, p in items]
                results = [f.result() for f in futures]
        return [clip for clip in results if clip is not None]


# --------------------------------------------------------------------------- #
# helpers image
# --------------------------------------------------------------------------- #
def _luma(rgba: tuple) -> float:
    """Luminance perçue d'une couleur RGBA (0-255)."""
    return 0.299 * rgba[0] + 0.587 * rgba[1] + 0.114 * rgba[2]


def _accent_for(concept: CollageConcept, paper: str, ink: tuple) -> str:
    """Couleur du détail d'une pièce, prise dans la palette du concept.

    Elle doit se détacher de DEUX choses à la fois: du papier (sinon le détail
    disparaît dans le fond de la feuille) et de l'encre du pictogramme (sinon
    le détail fusionne avec la forme et le carton devient un hexagone noir, la
    coche un disque plein…). On maximise donc le contraste MINIMAL des deux.
    """
    candidates = [c for c in (list(concept.palette) + [concept.background_color])
                  if c and c.upper() != (paper or "").upper()]
    if not candidates:
        return "#F2B705"
    paper_luma = _luma(hex_to_rgb(paper or "#F7F1E3"))
    ink_luma = _luma(ink)

    def separation(color: str) -> float:
        luma = _luma(hex_to_rgb(color))
        return min(abs(luma - paper_luma), abs(luma - ink_luma))

    best = max(candidates, key=separation)
    # Aucune couleur de la palette ne se détache assez: on prend un jaune papier
    # neutre plutôt que de rendre une pièce illisible.
    return best if separation(best) >= 40 else "#F2B705"


def _duration_for(concept: CollageConcept) -> float:
    """Durée du clip: le temps du propos, borné par la configuration."""
    span = concept.duration or ccfg.CLIP_DURATION
    return max(ccfg.CLIP_DURATION_MIN, min(ccfg.CLIP_DURATION_MAX, span))


def _stop_motion(progress: float) -> float:
    """Quantifie la progression en paliers — c'est ce qui fait « stop-motion »."""
    steps = ccfg.STOP_MOTION_STEPS
    if steps <= 0:
        return progress
    return min(1.0, math.ceil(progress * steps) / steps)


def _cover(img: Image.Image, w: int, h: int) -> Image.Image:
    src_ratio = img.width / max(1, img.height)
    dst_ratio = w / float(h)
    if src_ratio > dst_ratio:
        nh, nw = h, max(1, int(h * src_ratio))
    else:
        nw, nh = w, max(1, int(w / max(0.001, src_ratio)))
    img = img.resize((nw, nh), _RESAMPLE)
    left, top = (nw - w) // 2, (nh - h) // 2
    return img.crop((left, top, left + w, top + h))


def _scaled(img: Image.Image, factor: float) -> Image.Image:
    if abs(factor - 1.0) < 0.005:
        return img
    return img.resize((max(1, int(img.width * factor)),
                       max(1, int(img.height * factor))), _RESAMPLE)


def _scale_about_center(img: Image.Image, factor: float) -> Image.Image:
    """Respiration de la scène entière.

    Bilinéaire volontairement: c'est un agrandissement de 3 %, invisible à
    l'œil, mais le faire en LANCZOS sur un 1080x1920 à chaque frame double le
    temps de rendu du clip.
    """
    if abs(factor - 1.0) < 0.005:
        return img
    scaled = img.resize((max(1, int(img.width * factor)),
                         max(1, int(img.height * factor))), Image.BILINEAR)
    left = (scaled.width - img.width) // 2
    top = (scaled.height - img.height) // 2
    return scaled.crop((left, top, left + img.width, top + img.height))


def _with_opacity(img: Image.Image, opacity: float) -> Image.Image:
    if opacity >= 0.999:
        return img
    r, g, b, a = img.split()
    return Image.merge("RGBA", (r, g, b, a.point(lambda v: int(v * opacity))))


def _add_keyline(layer: Image.Image, mask: Image.Image) -> Image.Image:
    """Contour crème autour de la découpe — signature du style."""
    width = max(1, ccfg.KEYLINE_WIDTH)
    grown = mask.filter(ImageFilter.MaxFilter(_odd(width * 2 + 1)))
    edge = Image.fromarray(
        np.clip(np.array(grown, dtype=np.int16) - np.array(mask, dtype=np.int16),
                0, 255).astype(np.uint8), "L")
    keyline = Image.new("RGBA", layer.size, ccfg.KEYLINE_COLOR)
    keyline.putalpha(edge)
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    out.alpha_composite(keyline)
    out.alpha_composite(layer)
    return out


def _add_shadow(layer: Image.Image) -> Image.Image:
    """Ombre portée courte: la pièce est posée à quelques millimètres du fond."""
    offset = max(0, ccfg.SHADOW_OFFSET)
    pad = offset * 2
    canvas = Image.new("RGBA", (layer.width + pad, layer.height + pad), (0, 0, 0, 0))
    shadow = Image.new("RGBA", layer.size, (24, 18, 12, 0))
    shadow.putalpha(layer.split()[3].point(lambda v: int(v * ccfg.SHADOW_ALPHA / 255)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(1, offset * 0.55)))
    canvas.alpha_composite(shadow, (offset + offset // 2, offset + offset // 2))
    canvas.alpha_composite(layer, (offset, offset))
    return canvas


def _apply_paper_grain(img: Image.Image, strength: float) -> Image.Image:
    if strength <= 0:
        return img
    rng = np.random.default_rng(seed=1789)   # grain STABLE d'un rendu à l'autre
    noise = rng.normal(0.0, strength, size=(img.height, img.width, 1))
    arr = np.array(img, dtype=np.float32)
    arr[..., :3] = np.clip(arr[..., :3] + noise, 0, 255)
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def _odd(value: int) -> int:
    return value if value % 2 == 1 else value + 1


def _dig(payload: object, path: str) -> object:
    """Lit `data.0.url` dans un JSON arbitraire (configuration du provider)."""
    current = payload
    for token in path.split("."):
        if isinstance(current, list):
            try:
                current = current[int(token)]
            except (ValueError, IndexError):
                return None
        elif isinstance(current, dict):
            current = current.get(token)
        else:
            return None
    return current
