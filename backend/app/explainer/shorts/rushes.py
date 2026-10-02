"""Rushes: probe, transcription mot à mot, suivi du visage et découpage en « unités ».

Une unité = une phrase (ou un morceau de phrase entre deux longues pauses) d'un
rush, avec ses mots horodatés. C'est la brique que le moteur garde, jette ou
déplace: les LLM et Jev ne voient que des identifiants courts (« B12 ») et du
texte, jamais de timecodes — moins de jetons, moins d'erreurs.
"""
from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Optional

from ..facecam import probe, transcribe

logger = logging.getLogger(__name__)

SENT_END = re.compile(r"[.?!…]$")
GAP_SPLIT = 0.75        # pause qui ferme une unité même sans ponctuation
MAX_WORDS = 34          # au-delà, on coupe à la prochaine virgule
FILLERS = {"euh", "heu", "hum", "hmm", "bah", "ben", "bon", "donc", "alors", "voila", "ok", "okay", "hein", "quoi", "eh"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]", " ", s.replace("-", " "))).replace("'", " ").strip()


def letter(i: int) -> str:
    return "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[i] if i < 26 else f"R{i + 1}_"


# ----------------------------------------------------------------- mots
def words_of(vu: dict[str, Any]) -> list[dict[str, Any]]:
    """Mots du transcript, avec « c » + « 'est » et « Jésus » + « -Christ » recollés."""
    out: list[dict[str, Any]] = []
    for seg in vu.get("segments", []):
        for w in seg.get("words", []):
            t = (w.get("word") or "").strip()
            if not t:
                continue
            s, e = float(w["start"]), float(w["end"])
            if out and (t.startswith("'") or (t.startswith("-") and len(t) > 1)) and s - out[-1]["e"] < 0.3:
                out[-1]["w"] += t; out[-1]["e"] = e
                continue
            out.append({"w": t, "s": round(s, 3), "e": round(max(e, s + 0.04), 3)})
    # horodatages monotones (Whisper chevauche parfois deux mots)
    for a, b in zip(out, out[1:]):
        if b["s"] < a["s"]:
            b["s"] = a["s"]
        if a["e"] > b["s"]:
            a["e"] = max(a["s"] + 0.04, b["s"])
    return out


def split_units(words: list[dict[str, Any]], rush: int) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    cur: list[dict[str, Any]] = []

    def close():
        if cur:
            units.append({"id": f"{letter(rush)}{len(units) + 1}", "rush": rush, "s": cur[0]["s"], "e": cur[-1]["e"],
                          "words": list(cur), "text": " ".join(w["w"] for w in cur)})
            cur.clear()

    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        gap = (nxt["s"] - w["e"]) if nxt else 99
        if not nxt or SENT_END.search(w["w"]) or gap > GAP_SPLIT or (len(cur) >= MAX_WORDS and w["w"].endswith(",")) \
                or len(cur) >= MAX_WORDS * 2:
            close()
    return units


def is_filler(unit: dict[str, Any]) -> bool:
    toks = norm(unit["text"]).split()
    return bool(toks) and all(t in FILLERS for t in toks)


# ----------------------------------------------------------------- visage
def face_track(video: str, step_s: float = 1.0, max_samples: int = 900) -> list[list[float]]:
    """[(t, cx, cy, largeur)] du plus grand visage, ~1 image/s (Haar, CPU)."""
    try:
        import cv2  # type: ignore
    except ImportError:
        return []
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if n <= 0:
        return []
    stride = max(int(fps * step_s), n // max_samples, 1)
    casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    out: list[list[float]] = []
    for k in range(0, n, stride):
        cap.set(cv2.CAP_PROP_POS_FRAMES, k)
        ok, im = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        m = max(60, min(g.shape[:2]) // 8)
        fs = casc.detectMultiScale(g, 1.15, 6, minSize=(m, m))
        if len(fs):
            x, y, w, h = max(fs, key=lambda r: r[2] * r[3])
            out.append([round(k / fps, 2), int(x + w / 2), int(y + h / 2), int(w)])
    cap.release()
    return out


def face_x(track: list[list[float]], t: float, width: int) -> int:
    near = [f[1] for f in track if abs(f[0] - t) < 6] or [f[1] for f in track]
    if not near:
        return width // 2
    near.sort()
    return int(near[len(near) // 2])


def face_y(track: list[list[float]], height: int) -> int:
    ys = sorted(f[2] for f in track)
    return int(ys[len(ys) // 2]) if ys else int(height * 0.4)


# ----------------------------------------------------------------- orchestration
def load_rushes(paths: list[str], workdir: str, *, language: Optional[str] = None, hint: Optional[str] = None,
                model: Optional[str] = None, progress=None) -> list[dict[str, Any]]:
    rushes = []
    for i, p in enumerate(paths):
        if progress:
            progress(i / max(1, len(paths)), f"Transcription du rush {i + 1}/{len(paths)}")
        wd = Path(workdir, f"rush{i + 1}"); wd.mkdir(parents=True, exist_ok=True)
        info = probe(p)
        vu = transcribe(p, str(wd), language, prompt=hint, model=model)
        words = words_of(vu)
        cache = wd / "faces.json"
        if cache.exists() and cache.stat().st_mtime >= os.path.getmtime(p):
            faces = json.loads(cache.read_text())
        else:
            faces = face_track(p)
            cache.write_text(json.dumps(faces))
        rushes.append({"index": i, "id": letter(i), "path": p, "info": info, "language": vu.get("language"),
                       "words": words, "units": split_units(words, i), "faces": faces})
    return rushes
