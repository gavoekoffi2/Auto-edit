"""Rendu: base 9:16 (recadrage centré visage), habillage animé, son, export.

L'habillage (bandeau, sous-titres, cartes, scènes plein écran) est une page web
transparente rendue par Chromium. Pour tenir sur un petit disque, elle est rendue
par TRANCHES de 20 s: chaque tranche est incrustée sur la base puis effacée
aussitôt (un calque ProRes 4444 de 7 min pèserait ~6 Go).
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Optional

from .. import renderer
from ..composer import WEB
from .rushes import face_y
from .timeline import FPS

W, H = 1080, 1920
SLICE = 600  # images par tranche d'habillage (20 s)

THEMES: dict[str, dict[str, str]] = {
    "or_noir": {"g": "#FFC93C", "g2": "#F5A300", "gl": "#FFE38A", "ink": "#0A0A0D", "card": "rgba(10,10,13,.86)",
                "line": "rgba(255,201,60,.75)", "glow": "rgba(255,201,60,.25)", "bg": "#050506", "bg2": "#1d1a10", "red": "#FF3B4E"},
    "braise": {"g": "#FF7A1A", "g2": "#E2361B", "gl": "#FFB36B", "ink": "#140804", "card": "rgba(20,8,4,.86)",
               "line": "rgba(255,122,26,.75)", "glow": "rgba(255,90,20,.25)", "bg": "#090403", "bg2": "#2a0f06", "red": "#FF2D55"},
    "ocean": {"g": "#33D6FF", "g2": "#1E8BFF", "gl": "#9BEBFF", "ink": "#03111F", "card": "rgba(4,16,32,.86)",
              "line": "rgba(51,214,255,.7)", "glow": "rgba(51,214,255,.22)", "bg": "#020a14", "bg2": "#0b2340", "red": "#FF4D5E"},
    "menthe": {"g": "#4BE3A1", "g2": "#12B886", "gl": "#A8F5D3", "ink": "#04140D", "card": "rgba(5,22,16,.86)",
               "line": "rgba(75,227,161,.7)", "glow": "rgba(75,227,161,.22)", "bg": "#03100b", "bg2": "#0d2a1f", "red": "#FF5A5F"},
    "royal": {"g": "#FFD25A", "g2": "#E0A82E", "gl": "#FFE9A8", "ink": "#1A0B2E", "card": "rgba(30,12,52,.88)",
              "line": "rgba(255,210,90,.75)", "glow": "rgba(160,90,255,.28)", "bg": "#0c0518", "bg2": "#2a1050", "red": "#FF4D6D"},
}
THEME_SOUND = {"or_noir": ("hopeful", 84), "braise": ("energetic", 104), "ocean": ("calm", 92),
               "menthe": ("hopeful", 96), "royal": ("hopeful", 80)}
FONTS = ["Anton", "DMSerif", "Poppins-500", "Poppins-700", "Poppins-800"]


def _ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def _even(x: float) -> int:
    return max(2, int(round(x / 2)) * 2)


# ----------------------------------------------------------------- base
def shot_filter(shot: dict[str, Any], src: dict[str, Any], fy: int, layout: str) -> str:
    sw, sh, z = src["w"], src["h"], shot["zoom"]
    grade = "eq=contrast=1.06:saturation=1.12:brightness=0.01"
    if layout == "cadre":
        ch = sh / z; cw = ch * 4 / 5
        if cw > sw:
            cw = sw / z; ch = cw * 5 / 4
        x = min(max(shot["cx"] - cw / 2, 0), sw - cw); y = min(max(fy - ch * 0.40, 0), sh - ch)
        # fond flouté calculé en basse définition (x16 plus rapide, invisible une fois flou)
        return (f"split[a][b];[a]scale=-2:480,crop=270:480,boxblur=8:2,scale={W}:{H},eq=brightness=-0.22:saturation=0.8[bg];"
                f"[b]crop={_even(cw)}:{_even(ch)}:{int(x)}:{int(y)},scale={W}:1350:flags=lanczos,unsharp=5:5:0.5,{grade}[fg];"
                f"[bg][fg]overlay=0:250,fps={FPS},format=yuv420p")
    ch = sh / z; cw = ch * 9 / 16
    if cw > sw:
        cw = sw / z; ch = cw * 16 / 9
    x = min(max(shot["cx"] - cw / 2, 0), sw - cw); y = min(max(fy - ch * 0.36, 0), sh - ch)
    return f"crop={_even(cw)}:{_even(ch)}:{int(x)}:{int(y)},scale={W}:{H}:flags=lanczos,unsharp=5:5:0.4,{grade},fps={FPS},format=yuv420p"


def render_base(rushes: list[dict[str, Any]], shots: list[dict[str, Any]], layout: str, out_mov: str, workers: int,
                progress: Optional[Callable[[float], None]] = None) -> str:
    tmp = tempfile.mkdtemp(prefix="shorts_base_", dir=os.path.dirname(out_mov))
    fys = {r["index"]: face_y(r["faces"], r["info"]["h"]) for r in rushes}
    done = [0]

    def one(i: int) -> str:
        s = shots[i]; r = rushes[s["rush"]]; d = s["dur"]
        p = os.path.join(tmp, f"c{i:04d}.mov")
        vf = shot_filter(s, r["info"], fys[s["rush"]], layout)
        args = ["-ss", f"{s['t0']:.3f}", "-t", f"{d + 0.2:.3f}", "-i", r["path"]]
        if r["info"].get("audio"):
            af = f"aresample=48000,apad,atrim=0:{d:.4f},afade=t=in:d=0.012,afade=t=out:st={max(0.0, d - 0.015):.4f}:d=0.015"
        else:
            args += ["-f", "lavfi", "-t", f"{d:.4f}", "-i", "anullsrc=r=48000:cl=mono"]
            af = None
        # sortie vidéo du filtre + meilleure piste audio (celle du rush, ou le silence)
        args += ["-filter_complex", vf, "-frames:v", str(s.get("frames") or round(d * FPS)), "-c:v", "libx264", "-preset", "veryfast", "-crf", "17"]
        if af:
            args += ["-af", af]
        args += ["-c:a", "pcm_s16le", "-ar", "48000", "-ac", "1", p]
        _ff(*args)
        done[0] += 1
        if progress:
            progress(done[0] / len(shots))
        return p

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        parts = list(ex.map(one, range(len(shots))))
    lst = os.path.join(tmp, "list.txt")
    Path(lst).write_text("".join(f"file '{p}'\n" for p in parts))
    _ff("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out_mov)
    shutil.rmtree(tmp, ignore_errors=True)
    return out_mov


def clean_voice(base: str, out_wav: str) -> str:
    _ff("-i", base, "-vn", "-af",
        "highpass=f=75,lowpass=f=12000,afftdn=nf=-28,equalizer=f=3000:t=q:w=1.2:g=2,"
        "acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=3,loudnorm=I=-15:TP=-1.5:LRA=9",
        "-ar", "48000", "-ac", "1", out_wav)
    return out_wav


# ----------------------------------------------------------------- habillage
def compose_page(data: dict[str, Any], theme: str, out_html: str) -> str:
    html = (WEB / "shorts.html").read_text(encoding="utf-8")
    for f in FONTS:
        html = html.replace(f"__FONT_{f}__", base64.b64encode((WEB / "fonts" / f"{f}.woff2").read_bytes()).decode())
    data = {**data, "theme": {"id": theme, "vars": THEMES.get(theme, THEMES["or_noir"])}}
    html = html.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    Path(out_html).write_text(html, encoding="utf-8")
    return out_html


def render_picture(page: str, base: str, duration: float, out_mp4: str, workers: int,
                   progress: Optional[Callable[[float], None]] = None) -> str:
    """Habillage rendu tranche par tranche et incrusté aussitôt sur la base (vidéo seule)."""
    total = int(round(duration * FPS))
    tmp = tempfile.mkdtemp(prefix="shorts_pic_", dir=os.path.dirname(out_mp4))
    slices = [(f0, min(total, f0 + SLICE)) for f0 in range(0, total, SLICE)]
    done = [0]

    def one(k: int) -> str:
        f0, f1 = slices[k]
        alpha = os.path.join(tmp, f"ov{k:03d}.mov")
        part = os.path.join(tmp, f"p{k:03d}.mp4")
        renderer._run([page, "--video", alpha, "--from", str(f0), "--to", str(f1), "--fps", str(FPS), "--sub", "1", "--alpha", "1"])
        _ff("-ss", f"{f0 / FPS:.4f}", "-i", base, "-i", alpha, "-filter_complex",
            "[1:v]format=yuva444p10le[o];[0:v][o]overlay=0:0:format=auto:eof_action=pass,format=yuv420p",
            "-frames:v", str(f1 - f0), "-an", "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "21",
            "-maxrate", "3200k", "-bufsize", "6400k", "-g", str(FPS * 2), part)
        os.unlink(alpha)
        done[0] += 1
        if progress:
            progress(done[0] / len(slices))
        return part

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        parts = list(ex.map(one, range(len(slices))))
    lst = os.path.join(tmp, "list.txt")
    Path(lst).write_text("".join(f"file '{p}'\n" for p in parts))
    _ff("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out_mp4)
    shutil.rmtree(tmp, ignore_errors=True)
    return out_mp4
