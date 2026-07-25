"""ÉTAPE 6 — `CollageQualityService`: le garde-fou automatique.

Le workflow de référence fait valider chaque étape par un humain. Ici il n'y a
personne: le contrôle qualité DOIT donc être exécutable par la machine, à coût
nul, sur chaque asset généré. Il vérifie:

  * lisibilité de la métaphore   (proxy: séparation + clarté + contraste)
  * absence de texte             (détection de bandes « glyphes »)
  * absence de watermark         (anomalie de détail dans les coins)
  * absence de faux caractères   (même détecteur que le texte, seuil bas)
  * cohérence graphique          (respect de la palette verrouillée, aplats)
  * bonne séparation des éléments (régions distinctes, pas une bouillie)
  * cohérence image finale ↔ vidéo (dernière frame vs image de référence)

Sortie: un `QualityReport` avec un score global, par exemple

    {"visual_clarity": 92, "style_consistency": 95, "usable": true}

Ces détecteurs sont **heuristiques et locaux** (NumPy/Pillow): ils coûtent
quelques millisecondes, ne dépendent d'aucune API et ne peuvent pas faire
échouer un rendu. Ils attrapent les défauts grossiers — lettrage baveux,
watermark de fournisseur, image plate ou saturée de détails — qui sont
précisément les modes d'échec des modèles image. Ils ne remplacent pas un
jugement esthétique humain, et c'est assumé: leur rôle est de décider s'il faut
RELANCER la génération, pas de noter une œuvre.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from typing import Optional, Sequence

import numpy as np
from PIL import Image

from . import collage_config as ccfg
from .collage_types import CollageConcept, QualityReport, hex_to_rgb

logger = logging.getLogger(__name__)

#: On analyse une version réduite: 10x plus rapide, mêmes verdicts.
_ANALYSIS_WIDTH = 512


class CollageQualityService:
    """Note un asset de collage et dit s'il faut relancer la génération."""

    def __init__(self, min_score: Optional[float] = None,
                 enabled: Optional[bool] = None):
        self.min_score = float(min_score if min_score is not None else ccfg.QUALITY_MIN_SCORE)
        self.enabled = ccfg.QUALITY_ENABLED if enabled is None else bool(enabled)

    # ------------------------------------------------------------------ #
    def review_image(self, image_path: Optional[str],
                     concept: CollageConcept) -> QualityReport:
        """Contrôle complet d'une image. Ne lève jamais."""
        report = QualityReport()
        if not image_path or not os.path.exists(image_path):
            report.issues.append("missing_image")
            return report
        if not self.enabled:
            # Contrôle désactivé: on ne bloque rien, on ne prétend rien mesurer.
            report.usable = True
            report.score = 100
            report.issues.append("quality_check_disabled")
            return report

        try:
            gray, rgb = _load_arrays(image_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[collage_quality] image illisible (%s)", str(exc)[:140])
            report.issues.append("unreadable_image")
            return report

        glyphs, corner_glyphs = _detect_glyph_bands(gray)
        watermark = _watermark_score(gray)
        separation = _element_separation(rgb, len(concept.ordered_objects()))
        clarity = _visual_clarity(gray)
        consistency = _style_consistency(rgb, concept)

        report.glyph_like_shapes = glyphs
        report.text_free = glyphs <= ccfg.QUALITY_TEXT_MAX_GLYPHS
        report.watermark_free = (watermark <= ccfg.QUALITY_WATERMARK_MAX_SCORE
                                 and corner_glyphs <= 6)
        report.element_separation = _pct(separation)
        report.visual_clarity = _pct(clarity)
        report.style_consistency = _pct(consistency)
        report.metaphor_readability = _pct(
            0.45 * separation + 0.35 * clarity + 0.20 * consistency)
        report.video_image_coherence = 0

        if not report.text_free:
            report.issues.append("text_detected")
        if not report.watermark_free:
            report.issues.append("watermark_suspected")
        if separation < ccfg.QUALITY_MIN_SEPARATION:
            report.issues.append("elements_not_separated")
        if clarity < 0.35:
            report.issues.append("low_visual_clarity")
        if consistency < 0.45:
            report.issues.append("style_drift")

        report.score = _pct(
            0.30 * (report.metaphor_readability / 100.0)
            + 0.28 * (report.style_consistency / 100.0)
            + 0.22 * (report.visual_clarity / 100.0)
            + 0.20 * (report.element_separation / 100.0)
        )
        # Le texte et le watermark sont ÉLIMINATOIRES: une belle image avec un
        # watermark reste inutilisable dans un montage livré à un client.
        report.usable = (report.text_free and report.watermark_free
                         and report.score >= self.min_score)
        return report

    # ------------------------------------------------------------------ #
    def review_clip(self, clip_path: Optional[str], image_path: Optional[str],
                    report: Optional[QualityReport] = None) -> QualityReport:
        """Vérifie que la dernière frame du clip correspond bien à l'image."""
        report = report or QualityReport(usable=True, score=100)
        if not self.enabled or not clip_path or not image_path:
            return report
        coherence = _video_image_coherence(clip_path, image_path)
        if coherence is None:
            return report                      # ffmpeg absent: on ne pénalise pas
        report.video_image_coherence = _pct(coherence)
        if coherence < ccfg.QUALITY_MIN_COHERENCE:
            report.issues.append("video_image_mismatch")
            report.usable = False
        return report

    # ------------------------------------------------------------------ #
    @staticmethod
    def retry_hints(report: QualityReport) -> list[str]:
        """Traduit les défauts en consignes concrètes pour la relance.

        Relancer un prompt identique redonne à peu près la même image: on
        renvoie donc au modèle CE QUI n'allait pas.
        """
        mapping = {
            "text_detected": "remove every letter, word, number and glyph — the "
                             "frame must contain zero typography",
            "watermark_suspected": "no watermark, no signature, no logo in any "
                                   "corner of the frame",
            "elements_not_separated": "space the paper pieces further apart, keep "
                                      "clear background between them",
            "low_visual_clarity": "simplify the composition, fewer details, "
                                  "stronger contrast between paper and background",
            "style_drift": "stay on the locked palette, flat paper cut-outs on a "
                           "single bold colour field",
            "video_image_mismatch": "the final frame must match the reference "
                                    "still exactly",
        }
        return [mapping[i] for i in report.issues if i in mapping]


# --------------------------------------------------------------------------- #
# détecteurs
# --------------------------------------------------------------------------- #
def _load_arrays(path: str) -> tuple[np.ndarray, np.ndarray]:
    img = Image.open(path).convert("RGB")
    if img.width > _ANALYSIS_WIDTH:
        ratio = _ANALYSIS_WIDTH / float(img.width)
        img = img.resize((_ANALYSIS_WIDTH, max(1, int(img.height * ratio))))
    rgb = np.asarray(img, dtype=np.float32)
    gray = rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    return gray, rgb


def _edge_mask(gray: np.ndarray, threshold: float = 26.0) -> np.ndarray:
    dx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
    dy = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
    return ((dx + dy) > threshold)


def _detect_glyph_bands(gray: np.ndarray) -> tuple[int, int]:
    """Compte les « glyphes » probables et ceux situés dans les coins.

    Signature du texte (vrai ou baveux): des lignes où l'on traverse BEAUCOUP
    de marques FINES et séparées, regroupées dans une bande horizontale courte.
    Trois filtres cumulés, qui écartent les deux faux positifs du style:

      * un grand aplat de papier => très peu de transitions par ligne;
      * une photo tramée (halftone) => beaucoup de transitions fines, mais sur
        une bande BIEN plus haute qu'une ligne de texte (rejetée par la borne
        de hauteur plus bas).
    """
    edges = _edge_mask(gray)
    height, width = edges.shape
    # Transitions 0 -> 1 par ligne = nombre de marques traversées.
    transitions = np.count_nonzero(edges[:, 1:] & ~edges[:, :-1], axis=1)
    density = edges.mean(axis=1)
    # Épaisseur moyenne d'une marque sur la ligne: fine => lettrage, épaisse =>
    # bord d'un aplat de papier.
    stroke = (density * width) / np.maximum(1, transitions)
    candidate = (transitions >= 10) & (stroke <= 14.0)
    if not candidate.any():
        return 0, 0

    # Une trame occupe une grande partie du cadre de façon RÉGULIÈRE. Dans ce
    # cas on ne retient que les bandes nettement plus chargées que la trame
    # ambiante — sinon la texture elle-même se ferait passer pour du lettrage.
    textured = float(candidate.mean()) > 0.50
    floor = 1.6 * float(np.median(transitions[candidate])) if textured else 0.0

    glyphs = 0
    corner_glyphs = 0
    run_start: Optional[int] = None
    for y in range(height + 1):
        active = bool(candidate[y]) if y < height else False
        if active and run_start is None:
            run_start = y
        elif not active and run_start is not None:
            band_h = y - run_start
            band = float(np.median(transitions[run_start:y]))
            # Une ligne de texte est FINE et POSÉE sur du calme: les lignes qui
            # l'encadrent sont nettement moins chargées qu'elle.
            neighbours = np.concatenate([transitions[max(0, run_start - 3):run_start],
                                         transitions[y:y + 3]])
            isolated = neighbours.size > 0 and float(neighbours.mean()) < 0.4 * band
            if 4 <= band_h <= 70 and isolated and band >= floor:
                glyphs += int(band)
                # Un watermark vit en marge (haut/bas 14 % du cadre).
                if run_start < height * 0.14 or y > height * 0.86:
                    corner_glyphs += int(band)
            run_start = None
    return glyphs, corner_glyphs


def _watermark_score(gray: np.ndarray) -> float:
    """Anomalie de détail dans un coin par rapport au reste du cadre (0..1)."""
    edges = _edge_mask(gray).astype(np.float32)
    height, width = edges.shape
    ch, cw = max(2, int(height * 0.13)), max(2, int(width * 0.24))
    corners = [
        edges[:ch, :cw], edges[:ch, -cw:],
        edges[-ch:, :cw], edges[-ch:, -cw:],
    ]
    overall = float(edges.mean()) + 1e-4
    worst = max(float(c.mean()) for c in corners)
    # Un coin 3x plus « chargé » que la moyenne d'un collage en aplats est
    # suspect; on borne à 1 pour garder un score lisible.
    return float(min(1.0, (worst / overall) / 3.0))


def _element_separation(rgb: np.ndarray, expected_objects: int) -> float:
    """Fraction 0..1: l'image montre-t-elle des régions bien distinctes ?"""
    # Quantification grossière: 4 niveaux par canal -> familles de couleurs.
    quant = (rgb // 64).astype(np.int32)
    codes = quant[..., 0] * 16 + quant[..., 1] * 4 + quant[..., 2]
    counts = np.bincount(codes.ravel(), minlength=64).astype(np.float32)
    share = counts / max(1.0, counts.sum())
    regions = int(np.count_nonzero(share > 0.02))
    target = max(3, min(ccfg.MAX_OBJECTS + 1, expected_objects + 1))
    if regions <= 1:
        return 0.0
    # Trop peu de régions = bouillie; beaucoup plus que prévu = fouillis.
    ratio = regions / float(target)
    return float(np.clip(1.0 - abs(1.0 - ratio) * 0.8, 0.0, 1.0))


def _visual_clarity(gray: np.ndarray) -> float:
    """Ni vide, ni saturé de détails, avec un vrai contraste."""
    edges = _edge_mask(gray)
    density = float(edges.mean())
    # Zone confortable pour un collage: 3 % à 16 % de pixels de contour.
    if density <= 0.0:
        occupancy = 0.0
    elif density < 0.03:
        occupancy = density / 0.03
    elif density <= 0.16:
        occupancy = 1.0
    else:
        occupancy = float(max(0.0, 1.0 - (density - 0.16) / 0.24))
    contrast = float(np.clip(gray.std() / 62.0, 0.0, 1.0))
    return float(np.clip(0.6 * occupancy + 0.4 * contrast, 0.0, 1.0))


def _style_consistency(rgb: np.ndarray, concept: CollageConcept) -> float:
    """Respect du verrou: aplats + palette du concept + crème présent."""
    palette = [concept.background_color, "#F7F1E3", *concept.palette]
    targets = np.array([hex_to_rgb(c) for c in palette], dtype=np.float32)
    pixels = rgb.reshape(-1, 3)
    if pixels.shape[0] > 40000:                      # échantillonnage: assez précis
        pixels = pixels[:: pixels.shape[0] // 40000 + 1]
    # Distance au plus proche papier de la palette.
    dist = np.sqrt(((pixels[:, None, :] - targets[None, :, :]) ** 2).sum(axis=2))
    nearest = dist.min(axis=1)
    on_palette = float((nearest < 95.0).mean())

    # « Aplat »: peu de couleurs distinctes dominent la surface.
    quant = (pixels // 48).astype(np.int32)
    codes = quant[:, 0] * 36 + quant[:, 1] * 6 + quant[:, 2]
    counts = np.bincount(codes, minlength=216).astype(np.float32)
    share = np.sort(counts / max(1.0, counts.sum()))[::-1]
    flatness = float(np.clip(share[:6].sum(), 0.0, 1.0))
    return float(np.clip(0.6 * on_palette + 0.4 * flatness, 0.0, 1.0))


def _video_image_coherence(clip_path: str, image_path: str) -> Optional[float]:
    """Corrélation entre la dernière frame du clip et l'image de référence."""
    frame = _extract_last_frame(clip_path)
    if frame is None:
        return None
    try:
        ref = Image.open(image_path).convert("RGB").resize((64, 112))
        got = frame.convert("RGB").resize((64, 112))
    except Exception:  # noqa: BLE001
        return None
    a = np.asarray(ref, dtype=np.float32).ravel()
    b = np.asarray(got, dtype=np.float32).ravel()
    if a.std() < 1e-3 or b.std() < 1e-3:
        return 0.0
    corr = float(np.corrcoef(a, b)[0, 1])
    return float(np.clip((corr + 1.0) / 2.0, 0.0, 1.0))


def _extract_last_frame(clip_path: str) -> Optional[Image.Image]:
    try:
        from app.autoedit_engine.ffmpeg_utils import FFMPEG
    except Exception:  # noqa: BLE001
        FFMPEG = "ffmpeg"  # noqa: N806
    tmp = os.path.join(tempfile.gettempdir(),
                       f"collage_qc_{os.getpid()}_{abs(hash(clip_path)) % 10**8}.png")
    cmd = [FFMPEG, "-y", "-v", "error", "-sseof", "-0.4", "-i", clip_path,
           "-frames:v", "1", "-update", "1", tmp]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=60)
        if proc.returncode != 0 or not os.path.exists(tmp):
            return None
        img = Image.open(tmp).copy()
        return img
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _pct(value: float) -> int:
    return int(round(float(np.clip(value, 0.0, 1.0)) * 100))


def best_asset(reports: Sequence[QualityReport]) -> int:
    """Index du meilleur rapport (utilisé quand tous les essais ont échoué)."""
    if not reports:
        return -1
    return max(range(len(reports)), key=lambda i: reports[i].score)
