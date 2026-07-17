"""Détection & suppression des sous-titres DÉJÀ incrustés dans la source.

Beaucoup de vidéos importées portent déjà des sous-titres gravés (TikTok,
reels re-téléchargés…). Le montage ajoute SES sous-titres animés — sans
nettoyage on obtient un double sous-titrage illisible.

Approche MVP (fiable, sans inpainting):
  1. Échantillonne quelques frames réparties sur la vidéo.
  2. Sur la bande BASSE de l'image (les sous-titres gravés y vivent presque
     toujours), détecte les lignes « texte »: forte densité de contours +
     alternance claire/sombre caractéristique des lettres à contour.
  3. Si la même bande ressort sur une majorité de frames (le texte change,
     la POSITION reste), la bande est déclarée « sous-titres incrustés ».
  4. Le rendu RECADRE la source pour exclure cette bande (crop bas avant la
     conversion cover 9:16) — les anciens sous-titres disparaissent, les
     nouveaux sont brûlés proprement.

Garde-fous:
  * bande plafonnée à MAX_BAND_FRAC de la hauteur (jamais de recadrage
    mutilant) — au-delà, on ne touche à rien et on le journalise;
  * sans OpenCV ou en cas d'erreur, aucune modification (fallback contrôlé);
  * décision et bande retenue tracées dans le report du job
    (``source_subtitles``).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from typing import List, Optional, Tuple

SEARCH_REGION_FRAC = 0.32     # on cherche du texte dans le tiers bas de l'image
MAX_BAND_FRAC = 0.26          # jamais plus de 26 % de la hauteur recadrée
                              # (couvre les sous-titres gravés à DEUX lignes)
MIN_BAND_FRAC = 0.04          # bande plus fine = bruit, on ignore
_N_SAMPLES = 7                # frames analysées
_MIN_HITS_RATIO = 0.5         # la bande doit ressortir sur >= 50 % des frames
_EDGE_ROW_THRESHOLD = 0.045   # densité de contours minimale d'une ligne "texte"
_PAD_FRAC = 0.015             # marge au-dessus de la bande détectée


def _cv2():
    try:
        import cv2  # noqa: PLC0415 - optional dependency
        return cv2
    except Exception:  # noqa: BLE001
        return None


def _sample_frames(source: str, outdir: str, n: int = _N_SAMPLES) -> List[str]:
    try:
        dur_s = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", source],
            check=True, capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        duration = float(dur_s)
    except Exception:  # noqa: BLE001
        return []
    paths: List[str] = []
    for i in range(n):
        t = duration * (0.12 + 0.76 * i / max(1, n - 1))
        out = os.path.join(outdir, f"s_{i}.png")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", source,
                 "-frames:v", "1", "-vf", "scale=540:-2", out],
                check=True, timeout=60,
            )
            if os.path.exists(out):
                paths.append(out)
        except Exception:  # noqa: BLE001
            continue
    return paths


def _row_edge_profile(cv2, image_path: str) -> Optional["object"]:
    """Densité de contours par rangée dans la zone de recherche (tableau numpy)."""
    img = cv2.imread(image_path)
    if img is None:
        return None
    h = img.shape[0]
    y0 = int(h * (1.0 - SEARCH_REGION_FRAC))
    region = cv2.cvtColor(img[y0:, :], cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(region, 80, 200)
    return edges.mean(axis=1) / 255.0


def detect_burned_subtitles(source: str) -> Tuple[Optional[float], dict]:
    """Retourne (bottom_crop_frac, report).

    ``bottom_crop_frac`` = fraction de la hauteur à retirer EN BAS (0..1),
    ou None si aucun sous-titre incrusté fiable n'est détecté.

    Robustesse: le profil de contours par rangée est agrégé en MÉDIANE sur
    plusieurs frames — les lettres des sous-titres restent aux MÊMES rangées
    pendant toute la vidéo (le texte change, la position non), alors que les
    contours du décor bougent et se moyennent. Le seuil est ADAPTATIF: une
    rangée « texte » doit dominer nettement le fond de SA vidéo, pas un seuil
    absolu qui prend les décors chargés pour du texte.
    """
    report = {"detected": False, "band_frac": 0.0, "frames_hit": 0,
              "frames_checked": 0, "skipped": None}
    cv2 = _cv2()
    if cv2 is None:
        report["skipped"] = "opencv_unavailable"
        return None, report
    import numpy as np
    with tempfile.TemporaryDirectory(prefix="subscrub_") as tmp:
        frames = _sample_frames(source, tmp)
        report["frames_checked"] = len(frames)
        if len(frames) < 3:
            report["skipped"] = "not_enough_frames"
            return None, report
        profiles = [p for p in (_row_edge_profile(cv2, f) for f in frames)
                    if p is not None]
    if len(profiles) < 3:
        report["skipped"] = "not_enough_frames"
        return None, report
    n = min(len(p) for p in profiles)
    stack = np.stack([p[:n] for p in profiles])
    median_profile = np.median(stack, axis=0)          # structure STATIQUE
    baseline = float(np.median(median_profile))        # fond de CETTE vidéo

    threshold = max(_EDGE_ROW_THRESHOLD, baseline * 2.5 + 0.01)
    text_rows = np.where(median_profile > threshold)[0]
    report["frames_hit"] = len(profiles)
    if len(text_rows) < max(4, int(n * 0.06)):
        return None, report                    # pas de bande texte stable

    # Bande compacte: au moins 30 % des rangées denses entre top et bottom.
    top, bottom = int(text_rows[0]), int(text_rows[-1])
    if len(text_rows) / max(1, bottom - top + 1) < 0.30:
        return None, report

    region_frac = SEARCH_REGION_FRAC
    band_top_frac = (1.0 - region_frac) + (top / n) * region_frac - _PAD_FRAC
    band_frac = 1.0 - band_top_frac
    if band_frac < MIN_BAND_FRAC:
        return None, report
    if band_frac > MAX_BAND_FRAC:
        report["skipped"] = "band_too_tall"    # on ne mutile pas l'image
        print(f"[subtitle_scrub] bande texte trop haute ({band_frac:.0%}) — "
              "recadrage refusé, la vidéo reste intacte", file=sys.stderr)
        return None, report
    report["detected"] = True
    report["band_frac"] = round(band_frac, 4)
    print(f"[subtitle_scrub] sous-titres incrustés détectés "
          f"({len(profiles)} frames) — recadrage bas de {band_frac:.0%}")
    return band_frac, report


def bottom_crop_filter(band_frac: float) -> str:
    """Filtre ffmpeg qui retire la bande basse AVANT la conversion 9:16."""
    keep = max(0.5, 1.0 - float(band_frac))
    return f"crop=iw:trunc(ih*{keep:.4f}/2)*2:0:0"
