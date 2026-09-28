"""Moteur « Studio face caméra » — le montage qu'un monteur motion designer ferait à la main.

    vidéo brute 9:16 (ou 16:9)
      → transcription mot à mot (vocabulaire du client en indice)
      → coupes: relecture IA (répétitions éloignées, passages confus) + règles
        (silences, faux départs, bégaiements) + AFFINAGE À L'ÉNERGIE DU SON
        (coupe au ras de la voix: ni souffle, ni début de « euh »)
      → base 9:16 à la cadence source, zooms alternés qui masquent les coupes
      → ADN de style: choisi selon le sujet ET différent des derniers montages
        de l'utilisateur (ou inventé), puis muté (jamais deux fois la même image)
      → plan: accroche flottante, cartes/tampons/étiquettes sur l'image,
        démonstrations plein écran, appel à commenter, carte de fin avec logo
      → calque transparent pleine durée (rendu Chromium parallèle, ProRes 4444)
      → voix nettoyée + SFX calés sur chaque animation + musique dans la
        tonalité du style, sous la voix, -14 LUFS
      → MP4 H.264 prêt pour TikTok / Facebook (< 30 Mo pour ~1 min)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Optional

from . import audio, renderer
from .brand import prepare_logo
from .composer import FONTS, WEB
from .facecam import probe, remap_words, render_base, transcribe
from .styles import choose_style, resolve_colors
from .studio_planner import fix_display, plan_studio
from .templates import SCENE_CATALOG

logger = logging.getLogger(__name__)
Progress = Callable[[int, str], None]


def _ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


# ----------------------------------------------------------------- coupes précises
def _load_pcm(video: str, sr: int = 16000):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32), sr


def _env_db(x, sr: int, t0: float, t1: float, hop: float = 0.01, win: float = 0.05):
    import numpy as np
    ts = np.arange(max(0.0, t0), max(t0 + hop, t1), hop)
    out = np.empty(len(ts))
    for i, t in enumerate(ts):
        a = x[max(0, int((t - win / 2) * sr)):int((t + win / 2) * sr)]
        out[i] = 20 * np.log10(np.sqrt(np.mean(a ** 2)) + 1e-9) if len(a) else -120.0
    return ts, out


def refine_ranges(video: str, ranges: list[dict[str, float]], words: list[dict[str, Any]],
                  lead: float = 0.05, tail: float = 0.09) -> list[dict[str, float]]:
    """Recale chaque borne sur l'énergie réelle de la voix (RMS 50 ms, seuil pic − 28 dB).

    Whisper place souvent les fins de mots trop tard (souffle, début d'hésitation)
    et les débuts trop tôt: on coupe au ras de la parole, avec une petite marge
    (50 ms avant, 90 ms après) pour ne jamais manger une consonne.
    """
    import numpy as np
    try:
        x, sr = _load_pcm(video)
    except Exception as e:  # pas d'audio lisible: on garde les coupes
        logger.warning("affinage des coupes ignoré: %s", e)
        return ranges
    out: list[dict[str, float]] = []
    for r in ranges:
        a, b = float(r["start"]), float(r["end"])
        inside = [w for w in words if a - 0.02 <= float(w["start"]) and float(w["end"]) <= b + 0.02]
        if not inside:
            out.append({"start": a, "end": b}); continue
        ws0, we = float(inside[0]["start"]), float(inside[-1]["end"])
        ts, e = _env_db(x, sr, ws0 - 0.35, ws0 + 0.35)
        loud = np.where(e > e.max() - 28)[0] if len(e) else []
        na = (ts[loud[0]] - lead) if len(loud) else a
        na = min(max(na, ws0 - 0.14, a), ws0 + 0.10)
        ts, e = _env_db(x, sr, we - 0.35, we + 0.35)
        loud = np.where(e > e.max() - 28)[0] if len(e) else []
        nb = (ts[loud[-1]] + tail) if len(loud) else b
        nb = max(min(nb, we + 0.14, b), we - 0.25)
        if nb - na < 0.2:
            na, nb = a, b
        out.append({"start": round(na, 3), "end": round(nb, 3)})
    # passages presque jointifs: une coupe de < 80 ms ne sert à rien (clic garanti)
    merged: list[dict[str, float]] = []
    for r in out:
        if merged and r["start"] - merged[-1]["end"] < 0.08:
            merged[-1]["end"] = max(merged[-1]["end"], r["end"])
        elif merged and r["start"] < merged[-1]["end"]:
            r = {"start": merged[-1]["end"], "end": r["end"]}
            if r["end"] - r["start"] > 0.15:
                merged.append(r)
        else:
            merged.append(r)
    return merged


def editorial_cut(vu: dict[str, Any], level: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Relecture IA du transcript (répétitions éloignées, passages confus, faux
    départs) via la passerelle LLM du projet. Transcript inchangé si pas d'IA."""
    info: dict[str, Any] = {"llm_cleanup": False, "level": level}
    if level == "off":
        return vu, info
    from .writer import chat, llm_available
    if not llm_available():
        return vu, info
    try:
        from app.autoedit_engine import smart_cleanup as sc
        text = chat(sc._PROMPT.replace("{transcript}", sc._transcript_lines(vu)), temperature=0.2, timeout=90)
        i, j = text.find("["), text.rfind("]")
        spans = sc._validate_spans(json.loads(text[i:j + 1]), vu, level=level) if 0 <= i < j else []
        if spans:
            vu, removed = sc.apply_spans(vu, spans)
            info.update(llm_cleanup=True, removed_s=round(removed, 2), spans=spans)
    except Exception as e:  # jamais bloquant
        logger.warning("relecture IA ignorée: %s", e)
    return vu, info


def smart_cut(video: str, vu: dict[str, Any], level: str = "balanced") -> tuple[list[dict[str, float]], dict[str, Any]]:
    from app.autoedit_engine import build_edl
    vu2, info = editorial_cut(vu, level)
    ranges = build_edl.build_ranges(vu2)
    words = [w for s in vu2.get("segments", []) for w in s.get("words", [])]
    ranges = refine_ranges(video, ranges, words)
    info["ranges"] = len(ranges)
    info["kept_s"] = round(sum(r["end"] - r["start"] for r in ranges), 2)
    return ranges, info


# ----------------------------------------------------------------- page d'animation
def _tone_of(words: list[dict[str, Any]]) -> str:
    import re
    txt = " ".join(w["w"].lower() for w in words)
    return "tu" if len(re.findall(r"\b(tu|ton|ta|tes|toi)\b", txt)) > len(re.findall(r"\b(vous|votre|vos)\b", txt)) else "vous"


def compose_studio(plan: list[dict[str, Any]], words: list[dict[str, Any]], duration: float, style: dict[str, Any], *,
                   logo: str = "", brand: str = "", captions: bool = True,
                   frames: Optional[dict[str, Any]] = None) -> str:
    import base64
    dark_style = style.get("tone", "dark") == "dark"
    shots = []
    for c in plan:
        sc = dict(c["scene"])
        st = sc.get("type")
        ws = [w for w in words if c["start"] - 0.05 <= w["s"] <= c["end"]]
        tone = c.get("tone")
        if not tone:
            if st in ("question",):
                tone = "dark"
            elif st in ("comment_cta", "end_card"):
                tone = "dark" if dark_style else "light"
            else:
                tone = sc.get("tone") or SCENE_CATALOG.get(st, {}).get("tone", "dark")
        elif st in ("comment_cta", "end_card"):
            tone = "dark" if dark_style else "light"
        shots.append({"start": c["start"], "end": c["end"], "speechEnd": max([w["e"] for w in ws] or [c["end"]]),
                      "words": ws, "text": c.get("text", ""), "scene": sc, "tone": tone, "layout": c.get("layout", "full")})
    tpl = {"colors": resolve_colors(style), "head_font": style["head_font"], "textCase": "upper" if style.get("caps") else "none",
           "transition": style["transition"], "grain": style.get("grain", 0.06), "pushIn": style["motion"]["push"],
           "shake": style["motion"]["shake"], "radius": style.get("radius", 24)}
    disp = [{"w": fix_display(w["w"]) or w["w"], "s": w["s"], "e": w["e"]} for w in words]
    story = {"duration": round(duration, 3), "template": tpl, "style": style, "shots": shots, "overlay": True,
             "words": disp if captions else [], "logo": logo, "brand": brand, "tone": _tone_of(words),
             "frames": frames}
    html = (WEB / "page.html").read_text(encoding="utf-8")
    for f in FONTS:
        html = html.replace(f"__FONT_{f}__", base64.b64encode((WEB / "fonts" / f"{f}.woff2").read_bytes()).decode())
    head = {"Anton": "'Anton'", "Bebas": "'Bebas'", "DMSerif": "'DMSerif'"}.get(style["head_font"], "'Anton'")
    html = html.replace("<script>__ENGINE__</script>", "<script>__STUDIO__</script><script>__ENGINE__</script>")
    return (html.replace("__HEAD_FONT__", head).replace("__ACCENT__", tpl["colors"]["accent"])
                .replace("__RADIUS__", str(tpl["radius"]))
                .replace("__STORY__", json.dumps(story, ensure_ascii=False).replace("</", "<\\/"))
                .replace("__STUDIO__", (WEB / "studio.js").read_text(encoding="utf-8"))
                .replace("__ENGINE__", (WEB / "engine.js").read_text(encoding="utf-8")))


def extract_frames(base: str, outdir: str, fps: int) -> dict[str, Any]:
    """Images de la vidéo montée: le moteur web les place (plein cadre, fenêtre,
    téléphone, polaroid…) selon le mode de montage."""
    os.makedirs(outdir, exist_ok=True)
    _ff("-i", base, "-vf", f"fps={fps},scale=1080:1920", "-q:v", "3", os.path.join(outdir, "%05d.jpg"))
    n = len([f for f in os.listdir(outdir) if f.endswith(".jpg")])
    return {"url": Path(outdir).resolve().as_uri() + "/", "fps": fps, "count": n, "ext": "jpg"}


def render_overlay(page: str, duration: float, out_mov: str, fps: int, workers: int,
                   progress: Optional[Callable[[float], None]] = None) -> str:
    """Calque transparent pleine durée, rendu en tranches parallèles puis recollé."""
    total = int(round(duration * fps))
    workers = max(1, min(workers, 8, total // 45 or 1))
    step = -(-total // workers)
    tmp = tempfile.mkdtemp(prefix="studio_", dir=os.path.dirname(out_mov))
    jobs, parts, progs = [], [], []
    for i in range(workers):
        f0, f1 = i * step, min(total, (i + 1) * step)
        if f0 >= f1:
            continue
        part, prog = os.path.join(tmp, f"part{i:02d}.mov"), os.path.join(tmp, f"p{i}.txt")
        parts.append(part); progs.append(prog)
        jobs.append([page, "--video", part, "--from", str(f0), "--to", str(f1), "--fps", str(fps), "--sub", "2",
                     "--alpha", "1", "--progress", prog])
    stop = [False]

    def watch():
        last = -1.0
        while not stop[0]:
            vals = []
            for p in progs:
                try:
                    vals.append(float(Path(p).read_text() or 0))
                except Exception:
                    vals.append(0.0)
            f = sum(vals) / max(1, len(vals))
            if progress and f - last >= 0.03:
                last = f; progress(f)
            time.sleep(1.5)

    with ThreadPoolExecutor(max_workers=len(jobs) + 1) as ex:
        w = ex.submit(watch)
        try:
            for f in [ex.submit(renderer._run, j) for j in jobs]:
                f.result()
        finally:
            stop[0] = True
            w.result()
    lst = os.path.join(tmp, "list.txt")
    Path(lst).write_text("".join(f"file '{p}'\n" for p in parts))
    _ff("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out_mov)
    for p in parts:
        try:
            os.unlink(p)
        except OSError:
            pass
    return out_mov


# ----------------------------------------------------------------- orchestration
def run_studio(video_path: str, output_dir: str, *, style: str = "auto", history: Optional[list[dict[str, Any]]] = None,
               density: str = "medium", captions: bool = True, music: bool = True, brand_color: Optional[str] = None,
               logo_path: Optional[str] = None, brand: str = "", vocabulary: str = "", cleanup: str = "balanced",
               language: Optional[str] = None, seed: Optional[str] = None, progress: Optional[Progress] = None,
               workers: Optional[int] = None) -> dict[str, Any]:
    prog = progress or (lambda p, m: logger.info("[%s%%] %s", p, m))
    wd = Path(output_dir); wd.mkdir(parents=True, exist_ok=True)
    work = wd / "studio"; work.mkdir(exist_ok=True)
    n = max(1, min(workers or (os.cpu_count() or 2), 8))
    t0 = time.time(); steps: list[str] = []
    src = probe(video_path)
    fps = src["fps"]

    prog(3, "Transcription mot à mot")
    hint = ", ".join(x for x in [brand, vocabulary] if x) or None
    vu = transcribe(video_path, str(work), language, prompt=hint); steps.append("transcription")

    prog(12, "Coupes précises (répétitions, hésitations, silences)")
    ranges, cut_info = smart_cut(video_path, vu, cleanup)
    if not ranges:
        ranges = [{"start": 0.0, "end": src["duration"]}]
    steps.append("smart_cut")

    prog(18, "Assemblage du montage 9:16")
    base = str(work / "base.mp4")
    dur = render_base(video_path, ranges, base, src, n); steps.append("base")
    words = remap_words(vu, ranges)

    prog(26, "Choix d'un style unique")
    text = " ".join(w["w"] for w in words)
    sd = seed or hashlib.sha1(f"{video_path}:{os.path.getsize(video_path)}:{len(history or [])}".encode()).hexdigest()
    st = choose_style(text, requested=style, history=history, seed=sd, brand_color=brand_color)
    (work / "style.json").write_text(json.dumps(st, ensure_ascii=False, indent=1))

    prog(30, "Plan du motion design")
    plan, planner = plan_studio(words, dur, density)
    (work / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1))
    logo = prepare_logo(logo_path)
    frames_dir = str(work / "frames")
    frames = extract_frames(base, frames_dir, fps)
    page = str(work / "studio.html")
    html = compose_studio(plan, words, dur, st, logo=logo, brand=brand, captions=captions, frames=frames)
    Path(page).write_text(html, encoding="utf-8")
    ev = renderer.events(page, str(work / "events.json"))
    if ev.get("errors"):
        logger.warning("erreurs page Studio: %s", ev["errors"][:3])
    steps.append("plan")

    prog(34, "Montage et motion design")
    picture = str(work / "picture.mp4")
    renderer.video(page, dur, picture, fps=fps, sub=int(os.getenv("STUDIO_SUBFRAMES", "1")), workers=n,
                   progress=lambda f: prog(34 + int(48 * f), "Montage et motion design"))
    steps.append("motion")

    prog(84, "Voix, sound design et musique")
    mix = None
    if src["audio"]:
        voice = str(work / "voice.wav")
        _ff("-i", base, "-af", "highpass=f=90,afftdn=nf=-28,acompressor=threshold=-18dB:ratio=3:attack=5:release=80",
            "-ar", "48000", "-ac", "1", voice)
        turn = next((c["start"] for c in plan if c["scene"].get("kicker") == "La solution"
                     or c["scene"].get("type") in ("hero_reveal", "comment_cta")), dur * 0.35)
        mix = str(work / "mix.wav")
        snd = st["sound"]
        audio.mix(voice, ev.get("events", []), dur, mix, mood=snd["mood"], bpm=snd["bpm"], turn=turn,
                  music_db=-24 if music else -120, sfx_db=-9, transpose=snd.get("transpose", 0))
    steps.append("sound")

    prog(92, "Export final")
    out = str(wd / "final_studio.mp4")
    args = ["-i", picture]
    if mix:
        args += ["-i", mix, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k"]
    args += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-maxrate", "3000k", "-bufsize", "6M",
             "-pix_fmt", "yuv420p", "-r", str(fps), "-movflags", "+faststart", "-t", f"{dur:.3f}", out]
    _ff(*args)
    poster = str(wd / "poster.jpg")
    try:
        _ff("-ss", f"{min(1.2, dur / 3):.2f}", "-i", out, "-frames:v", "1", "-q:v", "3", poster)
    except subprocess.CalledProcessError:
        poster = ""
    import shutil
    shutil.rmtree(frames_dir, ignore_errors=True)
    try:
        os.unlink(picture)
    except OSError:
        pass
    steps.append("export")
    prog(100, "Terminé")
    return {
        "output_path": out, "poster_path": poster, "engine": "studio", "duration": round(probe(out)["duration"], 2),
        "source_duration": round(src["duration"], 2), "cut": {k: v for k, v in cut_info.items() if k != "spans"},
        "style": {"id": st["id"], "name": st["name"], "montage": st.get("montage"), "invented": st.get("invented", False), "reason": st.get("reason"),
                  "palette": st["palette"], "chrome": st["chrome"], "panel": st["panel"], "transition": st["transition"],
                  "captions": st["captions"]["style"], "head_font": st["head_font"], "fingerprint": st["fingerprint"]},
        "plan": [{"start": c["start"], "end": c["end"], "layout": c["layout"], "type": c["scene"].get("type")} for c in plan],
        "planner": planner, "sfx_count": len(ev.get("events", [])), "steps_completed": steps, "steps_failed": [],
        "render_seconds": round(time.time() - t0, 1),
    }
