"""Recadrage vertical intelligent — suivi de visage pour la conversion 9:16.

Une source 16:9 recadrée aveuglément au centre coupe régulièrement la tête de
la personne qui parle. Ce module calcule, PAR SEGMENT de l'EDL, un centre de
cadrage horizontal basé sur la détection de visages (OpenCV Haar), avec:

  * échantillonnage de quelques frames par segment (pas de tracking frame par
    frame: le centre est stable par segment, donc pas de tremblement);
  * choix du visage dominant (le plus grand = le plus proche de la caméra),
    ce qui suit naturellement l'intervenant principal quand il change;
  * lissage entre segments (EMA + delta max) pour éviter les sauts de caméra
    virtuelle brusques;
  * fallback CENTRE contrôlé et journalisé quand aucun visage n'est détecté
    ou quand OpenCV n'est pas disponible.

Modes (``SMART_CROP_MODE`` / paramètre): ``auto`` (suivi, défaut), ``center``,
``left`` (personne cadrée au tiers gauche), ``right``.

LIMITES DOCUMENTÉES du MVP:
  * un seul cadrage par segment d'EDL (pas de panoramique continu à
    l'intérieur d'un même segment);
  * pas de diarisation: si deux personnes parlent en alternance dans le MÊME
    segment, c'est le visage dominant qui gagne;
  * pas de split-screen deux intervenants (prévu après stabilisation);
  * détection Haar frontal + profil: les visages très de dos ou très petits
    retombent sur le cadrage centre.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from typing import List, Optional

from . import config

SMART_CROP_MODE = os.getenv("SMART_CROP_MODE", "auto").lower()
_SAMPLES_PER_SEGMENT = 3      # frames analysées par segment (20/50/80 %)
_EMA_ALPHA = 0.6              # lissage entre segments (1 = pas de lissage)
_MAX_STEP = 0.18              # déplacement max du centre entre deux segments
_MIN_FACE_FRACTION = 0.04     # visage < 4 % de la largeur = bruit, ignoré

FIXED_CENTERS = {"center": 0.5, "left": 0.33, "right": 0.67}


def _cv2():
    try:
        import cv2  # noqa: PLC0415 - optional dependency
        return cv2
    except Exception:  # noqa: BLE001 - absence d'OpenCV = fallback centre
        return None


def opencv_available() -> bool:
    return _cv2() is not None


def _detect_face_center(image_path: str) -> Optional[float]:
    """Centre x normalisé (0..1) du visage dominant, ou None."""
    cv2 = _cv2()
    if cv2 is None:
        return None
    img = cv2.imread(image_path)
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    w = gray.shape[1]
    best: Optional[tuple] = None
    for cascade_name in ("haarcascade_frontalface_default.xml",
                         "haarcascade_profileface.xml"):
        cascade = cv2.CascadeClassifier(
            os.path.join(cv2.data.haarcascades, cascade_name))
        faces = cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5,
            minSize=(int(w * _MIN_FACE_FRACTION), int(w * _MIN_FACE_FRACTION)))
        for (x, y, fw, fh) in faces:
            if best is None or fw * fh > best[2]:
                best = (x + fw / 2.0, y + fh / 2.0, fw * fh)
        if best is not None:
            break                      # frontal prioritaire sur profil
    if best is None:
        return None
    return float(best[0]) / float(w)


def _sample_frames(source: str, start: float, end: float, outdir: str,
                   n: int = _SAMPLES_PER_SEGMENT) -> List[str]:
    """Extrait *n* frames réparties dans [start, end] (petites, pour la détection)."""
    paths: List[str] = []
    dur = max(0.2, end - start)
    for i in range(n):
        t = start + dur * (0.2 + 0.6 * i / max(1, n - 1))
        out = os.path.join(outdir, f"f_{start:.2f}_{i}.jpg")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", source,
                 "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "5", out],
                check=True, timeout=60,
            )
            if os.path.exists(out) and os.path.getsize(out) > 0:
                paths.append(out)
        except Exception:  # noqa: BLE001 - une frame ratée n'est pas bloquante
            continue
    return paths


def smooth_centers(raw: List[Optional[float]],
                   ema_alpha: float = _EMA_ALPHA,
                   max_step: float = _MAX_STEP) -> List[float]:
    """Comble les trous (None -> voisin le plus proche, sinon 0.5) puis lisse.

    Pure et testable: EMA + écrêtage du déplacement pour une caméra virtuelle
    stable, sans à-coups d'un segment à l'autre.
    """
    n = len(raw)
    if n == 0:
        return []
    # 1) fill: plus proche valeur détectée (avant/après), sinon centre.
    filled: List[float] = []
    for i, v in enumerate(raw):
        if v is not None:
            filled.append(min(1.0, max(0.0, v)))
            continue
        prev_v = next((raw[j] for j in range(i - 1, -1, -1) if raw[j] is not None), None)
        next_v = next((raw[j] for j in range(i + 1, n) if raw[j] is not None), None)
        if prev_v is not None and next_v is not None:
            filled.append((prev_v + next_v) / 2.0)
        else:
            filled.append(prev_v if prev_v is not None
                          else (next_v if next_v is not None else 0.5))
    # 2) EMA + delta max entre segments consécutifs.
    smoothed: List[float] = [filled[0]]
    for v in filled[1:]:
        target = ema_alpha * v + (1.0 - ema_alpha) * smoothed[-1]
        delta = max(-max_step, min(max_step, target - smoothed[-1]))
        smoothed.append(round(smoothed[-1] + delta, 4))
    return smoothed


def crop_filter(center_x: float) -> str:
    """Filtre ffmpeg 9:16 « cover » recadré sur *center_x* (0..1).

    Équivalent de VERTICAL_COVER mais avec un x de crop piloté: pour une
    source verticale (iw == 1080 après scale) l'expression vaut 0 — no-op.
    """
    cx = min(1.0, max(0.0, float(center_x)))
    return (
        f"scale={config.WIDTH}:{config.HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={config.WIDTH}:{config.HEIGHT}:"
        f"x='clip(iw*{cx:.4f}-{config.WIDTH // 2},0,iw-{config.WIDTH})':"
        f"y='(ih-{config.HEIGHT})/2'"
    )


def source_is_landscape(source: str) -> bool:
    """True si la source est plus large que le ratio cible (recadrage utile)."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0", source],
            check=True, capture_output=True, text=True, timeout=30,
        ).stdout.strip().split(",")
        w, h = int(out[0]), int(out[1])
        return (w / max(1, h)) > (config.WIDTH / config.HEIGHT) + 0.01
    except Exception:  # noqa: BLE001
        return False


def plan_crop_centers(source: str, ranges: List[dict],
                      mode: Optional[str] = None) -> tuple[List[float], dict]:
    """Centre de cadrage lissé PAR RANGE de l'EDL + rapport d'observabilité.

    Returns (centers, report). En mode fixe ou sans OpenCV/paysage, tous les
    centres valent la valeur fixe (0.5 par défaut) — jamais d'échec.
    """
    mode = (mode or SMART_CROP_MODE or "auto").lower()
    report = {"mode": mode, "engine": "haar", "segments": len(ranges),
              "segments_with_face": 0, "fallback": None}

    if mode in FIXED_CENTERS:
        report["engine"] = "fixed"
        return [FIXED_CENTERS[mode]] * len(ranges), report
    if not source_is_landscape(source):
        report["engine"] = "fixed"
        report["fallback"] = "source_not_landscape"
        return [0.5] * len(ranges), report
    if not opencv_available():
        report["engine"] = "fixed"
        report["fallback"] = "opencv_unavailable"
        print("[smart_crop] WARN OpenCV indisponible — cadrage centre",
              file=sys.stderr)
        return [0.5] * len(ranges), report

    raw: List[Optional[float]] = []
    with tempfile.TemporaryDirectory(prefix="smartcrop_") as tmp:
        for rng in ranges:
            frames = _sample_frames(source, float(rng["start"]), float(rng["end"]), tmp)
            centers = [c for c in (_detect_face_center(f) for f in frames)
                       if c is not None]
            if centers:
                raw.append(sum(centers) / len(centers))
                report["segments_with_face"] += 1
            else:
                raw.append(None)
    if report["segments_with_face"] == 0:
        report["fallback"] = "no_face_detected"
        return [0.5] * len(ranges), report
    return smooth_centers(raw), report
