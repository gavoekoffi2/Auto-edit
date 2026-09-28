"""Vidéo de test synthétique pour le moteur YouTube long.

Chaque « mot » du transcript = un bip audio ET un flash blanc à l'image, sur
exactement le même intervalle. Après montage, bip et flash doivent rester
alignés : c'est la preuve signal que la synchro labiale est conservée.
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import List, Tuple

# (texte, durée du mot) ; None = pause (durée)
SCRIPT: List[Tuple] = [
    ("Bonjour", 0.45), ("à", 0.15), ("tous", 0.35), ("et", 0.15), ("bienvenue.", 0.55), (None, 0.9),
    # prise ratée puis refaite : la dernière doit gagner
    ("Aujourd'hui", 0.5), ("je", 0.15), ("vais", 0.2), ("vous", 0.2), (None, 1.1),
    ("euh", 0.35), (None, 0.8),
    ("Aujourd'hui", 0.5), ("je", 0.15), ("vais", 0.2), ("vous", 0.2), ("montrer", 0.4),
    ("la", 0.12), ("méthode", 0.5), ("complète.", 0.6), (None, 2.5),
    ("Le", 0.15), ("prix", 0.35), ("est", 0.15), ("de", 0.12), ("500", 0.45), ("euros", 0.4),
    ("par", 0.15), ("mois.", 0.45), (None, 0.7),
    ("C'est", 0.25), ("vraiment", 0.4), ("important", 0.55), ("pour", 0.2), ("votre", 0.25),
    ("business.", 0.6), (None, 1.6),
    # bégaiement
    ("Il", 0.15), ("faut", 0.25), ("il", 0.15), ("faut", 0.25), ("tester", 0.45), ("chaque", 0.3),
    ("semaine.", 0.55), (None, 0.5),
    ("Merci", 0.4), ("et", 0.15), ("à", 0.12), ("bientôt.", 0.6), (None, 0.6),
]
GAP_IN_RUN = 0.07  # micro-silence entre deux mots d'un même passage


def make(out_dir: str, *, vertical: bool = False) -> Tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    t = 0.3
    words = []
    for item in SCRIPT:
        if item[0] is None:
            t += item[1]
            continue
        text, d = item
        words.append({"word": text, "start": round(t, 3), "end": round(t + d, 3)})
        t += d + GAP_IN_RUN
    dur = round(t + 0.5, 3)
    en = "+".join(f"between(t,{w['start']:.3f},{w['end']:.3f})" for w in words)
    size = "1080x1920" if vertical else "1920x1080"
    video = os.path.join(out_dir, "source_vertical.mp4" if vertical else "source.mp4")
    subprocess.run([
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=25:duration={dur}",
        "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=48000:duration={dur}",
        "-filter_complex",
        f"[0:v]drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='{en}'[v];"
        f"[1:a]volume='if({en},0.5,0)':eval=frame[a]",
        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", video,
    ], check=True)
    vu = {"language": "fr", "duration": dur,
          "segments": [{"text": " ".join(w["word"] for w in words), "start": words[0]["start"],
                        "end": words[-1]["end"], "words": words}]}
    vu_path = os.path.join(out_dir, "vu.json")
    json.dump(vu, open(vu_path, "w"), ensure_ascii=False)
    return video, vu_path
