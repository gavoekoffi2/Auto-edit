"""
STEP 0 — Burned-in subtitle cleanup on the IMPORTED source video.

Si la vidéo importée porte déjà des sous-titres incrustés (hardcoded), le
montage final aurait un DOUBLE sous-titrage: l'ancien texte + les nouveaux
sous-titres animés brûlés par le moteur. Ce module:

  1. échantillonne des frames sur toute la durée (OpenCV),
  2. détecte les blocs de texte "type sous-titre" dans le bas du cadre
     (traits à fort contraste, larges, centrés, dans une bande horizontale),
  3. ne conclut à des sous-titres incrustés QUE si la bande est PERSISTANTE
     (présente sur une fraction significative des frames — un titre ponctuel
     ou un objet contrasté isolé ne déclenche rien),
  4. efface la bande détectée avec ffmpeg `delogo` (interpolation depuis les
     pixels voisins) sur toute la vidéo, audio copié tel quel.

Best-effort par design: en cas de doute (pas de bande stable, OpenCV absent,
vidéo illisible), la source repart INCHANGÉE — jamais de faux positif
destructif, jamais un render bloqué.

Usage:
    python -m app.autoedit_engine.subtitle_removal input.mp4 --workdir out
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional, Tuple

from . import config
from . import ffmpeg_utils

Box = Tuple[int, int, int, int]   # x, y, w, h (pixels, source scale)


# --------------------------------------------------------------------------- #
# per-frame detection (pure: numpy image in -> candidate boxes out)
# --------------------------------------------------------------------------- #
def subtitle_boxes(frame_bgr, scan_from: float = config.SOURCE_SUBS_SCAN_FROM) -> List[Box]:
    """Candidate subtitle text boxes in the bottom band of ONE frame.

    Subtitle text is extreme-contrast BY DESIGN (near-white/yellow fill with a
    dark outline, or dark text on a bright pill), wide, horizontally centered
    and low in the frame. The mask keeps only pixels of one polarity that sit
    right next to the opposite polarity — that isolates outlined text even on
    a busy background, without OCR.
    """
    import cv2
    import numpy as np

    h, w = frame_bgr.shape[:2]
    y_off = int(h * scan_from)
    roi = frame_bgr[y_off:, :]
    if roi.size == 0:
        return []
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    bright = ((gray >= 195).astype(np.uint8)) * 255
    dark = ((gray <= 70).astype(np.uint8)) * 255
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    strokes = cv2.bitwise_or(
        cv2.bitwise_and(bright, cv2.dilate(dark, k)),    # texte clair, liseré sombre
        cv2.bitwise_and(dark, cv2.dilate(bright, k)),    # texte sombre sur pilule claire
    )
    # kill isolated specks, then fuse letters into horizontal text lines
    strokes = cv2.morphologyEx(strokes, cv2.MORPH_OPEN,
                               cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)))
    fused = cv2.morphologyEx(
        strokes, cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, w // 40), 5)))

    contours, _ = cv2.findContours(fused, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: List[Box] = []
    min_h = max(12, int(h * 0.012))
    max_h = int(h * 0.10)
    for c in contours:
        x, y, bw_, bh = cv2.boundingRect(c)
        if bw_ < w * 0.22 or not (min_h <= bh <= max_h) or bw_ < bh * 3:
            continue
        # Subtitle lines are roughly centered horizontally.
        cx = x + bw_ / 2
        if not (w * 0.22 <= cx <= w * 0.78):
            continue
        # Enough actual stroke pixels inside — but not a solid slab either
        # (a plain bright bar / UI banner is not text).
        fill = float(np.count_nonzero(strokes[y:y + bh, x:x + bw_])) / float(bw_ * bh)
        if not (0.08 <= fill <= 0.85):
            continue
        boxes.append((x, y + y_off, bw_, bh))
    return boxes


# --------------------------------------------------------------------------- #
# aggregation across sampled frames (pure)
# --------------------------------------------------------------------------- #
def aggregate_band(per_frame_boxes: List[List[Box]], width: int, height: int,
                   min_hit_ratio: float = config.SOURCE_SUBS_MIN_HIT_RATIO,
                   margin: int = config.SOURCE_SUBS_MARGIN) -> Optional[dict]:
    """Decide whether a PERSISTENT subtitle band exists across sampled frames.

    Returns the band as {"x","y","w","h","hits","frames"} (source pixels) or
    None. Persistence is the anti-false-positive guard: a burned subtitle
    track shows text in a stable vertical band on many frames, while a random
    contrasted object appears once.
    """
    n_frames = len(per_frame_boxes)
    if n_frames == 0:
        return None
    hits = [bs for bs in per_frame_boxes if bs]
    if len(hits) < max(2, int(round(n_frames * min_hit_ratio))):
        return None

    # Cluster on the y-center of each frame's main (widest) box.
    mains = [max(bs, key=lambda b: b[2]) for bs in hits]
    centers = sorted(b[1] + b[3] / 2 for b in mains)
    median_c = centers[len(centers) // 2]
    tol = max(40.0, height * 0.06)
    cluster = [b for b in mains if abs((b[1] + b[3] / 2) - median_c) <= tol]
    if len(cluster) < max(2, int(round(n_frames * min_hit_ratio))):
        return None

    # Vertical band from the persistent cluster; HORIZONTALLY the erase band
    # spans the whole frame: subtitle lines are centered but their width
    # changes with every phrase — a band as wide as the widest SAMPLED line
    # would leave the tails of longer, unsampled lines on screen.
    y0 = min(b[1] for b in cluster) - margin
    y1 = max(b[1] + b[3] for b in cluster) + margin
    # delogo needs the box strictly inside the frame (>= 1 px border).
    x0 = 1
    x1 = width - 1
    y0 = max(1, int(y0))
    y1 = min(height - 1, int(y1))
    if x1 - x0 < 20 or y1 - y0 < 12:
        return None
    return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0,
            "hits": len(cluster), "frames": n_frames}


def build_delogo_filter(band: dict) -> str:
    """The ffmpeg `delogo` filter erasing *band* (interpolated fill)."""
    return (f"delogo=x={band['x']}:y={band['y']}"
            f":w={band['w']}:h={band['h']}")


# --------------------------------------------------------------------------- #
# video-level detection + removal
# --------------------------------------------------------------------------- #
def detect_burned_subtitles(source: str,
                            samples: int = config.SOURCE_SUBS_SAMPLES) -> Optional[dict]:
    """Scan *source* for a persistent burned-in subtitle band; None if clean."""
    try:
        import cv2
    except Exception as exc:  # noqa: BLE001 - opencv optional at runtime
        print(f"[subtitle_removal] OpenCV unavailable ({exc}) — scan skipped",
              file=sys.stderr)
        return None

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"[subtitle_removal] cannot open {source} — scan skipped",
              file=sys.stderr)
        return None
    try:
        n_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if n_total <= 0 or width <= 0 or height <= 0:
            return None
        # Skip the very first/last instants (intro cards, end fades).
        idxs = [int(n_total * (i + 0.5) / samples) for i in range(samples)]
        per_frame: List[List[Box]] = []
        for idx in idxs:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            per_frame.append(subtitle_boxes(frame))
        return aggregate_band(per_frame, width, height)
    finally:
        cap.release()


def remove_burned_subtitles(source: str, out_path: str, band: dict) -> str:
    """Erase *band* on the whole video with `delogo`; audio copied verbatim."""
    ffmpeg_utils.ensure_ffmpeg()
    ffmpeg_utils.run([
        ffmpeg_utils.FFMPEG, "-y", "-i", source,
        "-vf", build_delogo_filter(band),
        "-c:v", "libx264", "-preset", config.ENGINE_INTERMEDIATE_PRESET,
        "-crf", str(config.ENGINE_INTERMEDIATE_CRF), "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        out_path,
    ])
    return out_path


def clean_source(source: str, workdir: str) -> Tuple[str, dict]:
    """Detect + erase burned-in subtitles on *source* (best-effort).

    Returns ``(path_to_use, report)``: the cleaned copy when a persistent
    subtitle band was found, otherwise the original source untouched.
    """
    rep = {"source_subtitles_detected": False,
           "source_subtitles_removed": False}
    band = detect_burned_subtitles(source)
    if band is None:
        print("[subtitle_removal] no burned-in subtitles detected — source kept")
        return source, rep
    rep["source_subtitles_detected"] = True
    rep["source_subtitles_band"] = band
    out_path = os.path.join(workdir, "_source_nosubs.mp4")
    try:
        remove_burned_subtitles(source, out_path, band)
    except Exception as exc:  # noqa: BLE001 - never block the render
        print(f"[subtitle_removal] WARN removal failed ({exc}) — source kept",
              file=sys.stderr)
        return source, rep
    rep["source_subtitles_removed"] = True
    print(f"[subtitle_removal] burned-in subtitles erased "
          f"(band {band['w']}x{band['h']} at y={band['y']}, "
          f"seen on {band['hits']}/{band['frames']} sampled frames) -> {out_path}")
    return out_path, rep


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Detect + erase burned-in subtitles on a source video")
    ap.add_argument("source", help="input video")
    ap.add_argument("--workdir", default=".")
    ap.add_argument("--detect-only", action="store_true",
                    help="print the detected band (if any) and exit")
    args = ap.parse_args(argv)
    if args.detect_only:
        print(detect_burned_subtitles(args.source))
        return 0
    path, rep = clean_source(args.source, args.workdir)
    print(path, rep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
