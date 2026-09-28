"""Moteur « Motion Pro » — vidéo face caméra → montage pro avec animations plein écran.

    transcription mot à mot → coupes intelligentes (silences, faux départs,
    répétitions, bégaiements) → base 9:16 avec zooms alternés qui masquent les
    coupes → plan des animations (IA ou règles) → animations plein écran en
    transparence (entrée/sortie par-dessus le visage) → sous-titres karaoké
    (hors animations) → SFX calés + musique discrète sous la voix → MP4.

Réutilise le moteur web de la « Pub explicative » et les templates communs.
"""
from __future__ import annotations

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
from .composer import FONTS, WEB
from .conf import setting
from .facecam_planner import merge_tokens, plan_cutaways
from .templates import resolve_template

logger = logging.getLogger(__name__)
Progress = Callable[[int, str], None]
W, H, FPS = 1080, 1920, 30

# sous-titres karaoké assortis à chaque template (styles ASS du moteur Auto Edit)
CAPTION_STYLE = {"prestige": "gold_lux", "neon": "neon_hype", "editorial": "pill_editorial",
                 "minimal": "bold_box", "solaire": "tiktok_yellow"}


def _ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def probe(path: str) -> dict[str, Any]:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,avg_frame_rate:format=duration",
                          "-of", "json", path], capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    has_audio = any(s.get("codec_type") == "audio" for s in d.get("streams", []))
    try:
        n, d_ = (v.get("avg_frame_rate") or "30/1").split("/")
        fps = float(n) / float(d_ or 1)
    except (ValueError, ZeroDivisionError):
        fps = 30.0
    return {"w": int(v.get("width", 0)), "h": int(v.get("height", 0)),
            "fps": round(fps) if 23 <= fps <= 31 else FPS,
            "duration": float(d.get("format", {}).get("duration", 0)), "audio": has_audio}


# ----------------------------------------------------------------- transcription
def transcribe(video: str, workdir: str, language: Optional[str] = None) -> dict[str, Any]:
    """Transcription mot à mot au format « vu » du moteur Auto Edit."""
    cached = Path(workdir, "transcript_vu.json")
    if cached.exists() and cached.stat().st_mtime >= os.path.getmtime(video):
        return json.loads(cached.read_text())  # reprise d'un rendu interrompu
    wav = os.path.join(workdir, "audio16k.wav")
    _ff("-i", video, "-ac", "1", "-ar", "16000", wav)
    lang = language or setting("WHISPER_LANGUAGE") or None
    try:
        from faster_whisper import WhisperModel  # type: ignore
        model = WhisperModel(setting("WHISPER_MODEL", "small") or "small", device="cpu", compute_type="int8")
        segs, info = model.transcribe(wav, language=lang, word_timestamps=True, beam_size=5,
                                      condition_on_previous_text=False)
        segments = [{"start": s.start, "end": s.end, "text": s.text,
                     "words": [{"word": w.word.strip(), "start": w.start, "end": w.end} for w in (s.words or [])]}
                    for s in segs]
        language_out = info.language
    except ImportError:
        from app.processing.transcription_service import TranscriptionService
        tr = TranscriptionService(model_name=setting("WHISPER_MODEL", "small") or "small").transcribe(video, workdir)
        segments = [{"start": s.start, "end": s.end, "text": s.text,
                     "words": [{"word": w.text.strip(), "start": w.start, "end": w.end} for w in s.words]}
                    for s in tr.segments]
        language_out = tr.language
    vu = {"duration": probe(video)["duration"], "language": language_out, "segments": segments}
    Path(workdir, "transcript_vu.json").write_text(json.dumps(vu, ensure_ascii=False))
    return vu


# ----------------------------------------------------------------- coupe + base
def cut_ranges(vu: dict[str, Any]) -> tuple[list[dict[str, float]], dict[str, Any]]:
    from app.autoedit_engine import build_edl
    info: dict[str, Any] = {"llm_cleanup": False}
    key = setting("OPENROUTER_API_KEY")
    if key:
        try:
            from app.autoedit_engine import smart_cleanup
            spans = smart_cleanup.llm_cleanup_spans(vu, api_key=key)
            if spans:
                vu, removed = smart_cleanup.apply_spans(vu, spans)
                info.update(llm_cleanup=True, llm_removed_s=round(removed, 2))
        except Exception as e:  # jamais bloquant
            logger.warning("nettoyage IA ignoré: %s", e)
    ranges = build_edl.build_ranges(vu)
    return ranges, info


def render_base(video: str, ranges: list[dict[str, float]], out: str, src: dict[str, Any], workers: int) -> float:
    FPS = src.get("fps") or globals()["FPS"]  # cadence de la source (25 reste 25: pas de saccade)
    """Assemble les passages gardés en 9:16, zoom alterné pour masquer les coupes."""
    tmp = tempfile.mkdtemp(prefix="fc_", dir=os.path.dirname(out))
    # recadrage « cover » vers 1080x1920 (vidéos horizontales: centre)
    cover = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"

    def seg(i: int) -> str:
        r = ranges[i]; a, b = r["start"], r["end"]; d = b - a
        z = 1.0 if i % 2 == 0 else 1.1
        vf = f"{cover},setpts=PTS-STARTPTS"
        if z != 1.0:
            vf += f",scale={int(W * z) // 2 * 2}:{int(H * z) // 2 * 2},crop={W}:{H}:(iw-{W})/2:(ih-{H})*0.42"
        af = f"afade=t=in:d=0.012,afade=t=out:st={max(0.0, d - 0.012):.3f}:d=0.012"
        p = os.path.join(tmp, f"s{i:04d}.mp4")
        args = ["-ss", f"{a:.3f}", "-i", video, "-t", f"{d:.3f}", "-frames:v", str(max(1, round(d * FPS))), "-vf", vf, "-r", str(FPS),
                "-c:v", "libx264", "-crf", "17", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
        args += (["-af", af, "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"] if src["audio"] else ["-an"])
        _ff(*args, p)
        return p

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        parts = list(ex.map(seg, range(len(ranges))))
    lst = os.path.join(tmp, "list.txt")
    Path(lst).write_text("".join(f"file '{p}'\n" for p in parts))
    _ff("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", out)
    for p in parts:
        os.unlink(p)
    return probe(out)["duration"]


def remap_words(vu: dict[str, Any], ranges: list[dict[str, float]]) -> list[dict[str, Any]]:
    from app.autoedit_engine.timeline import s2o
    out = []
    for seg in vu.get("segments", []):
        for w in seg.get("words", []):
            txt = (w.get("word") or "").strip()
            s = s2o(float(w["start"]), ranges); e = s2o(float(w["end"]), ranges)
            if not txt or s is None:
                continue
            if e is None or e <= s:
                e = s + max(0.08, float(w["end"]) - float(w["start"]))
            out.append({"w": txt, "s": round(s, 3), "e": round(e, 3)})
    out.sort(key=lambda w: w["s"])
    # les coupes « snappent » au début du passage suivant: on retire les doublons proches
    dedup = []
    for w in out:
        if dedup and w["w"] == dedup[-1]["w"] and abs(w["s"] - dedup[-1]["s"]) < 0.05:
            continue
        dedup.append(w)
    return merge_tokens(dedup)


# ----------------------------------------------------------------- overlay
def compose_overlay(cutaways: list[dict[str, Any]], words: list[dict[str, Any]], duration: float,
                    template_id: str, brand_color: Optional[str]) -> str:
    import base64
    from .templates import SCENE_CATALOG
    tpl = resolve_template(template_id, brand_color)
    shots = []
    for c in cutaways:
        ws = [w for w in words if c["start"] - 0.05 <= w["s"] <= c["end"]]
        stype = c["scene"].get("type")
        shots.append({"start": c["start"], "end": c["end"], "speechEnd": max([w["e"] for w in ws] or [c["end"]]),
                      "words": ws, "text": c.get("text", ""), "scene": c["scene"],
                      "tone": c["scene"].get("tone") or SCENE_CATALOG.get(stype, {}).get("tone", "dark")})
    story = {"duration": round(duration, 3), "template": tpl, "shots": shots, "overlay": True}
    html = (WEB / "page.html").read_text(encoding="utf-8")
    for f in FONTS:
        html = html.replace(f"__FONT_{f}__", base64.b64encode((WEB / "fonts" / f"{f}.woff2").read_bytes()).decode())
    head = {"Anton": "'Anton'", "Bebas": "'Bebas'", "DMSerif": "'DMSerif'"}.get(tpl.get("head_font", "Anton"), "'Anton'")
    return (html.replace("__HEAD_FONT__", head).replace("__ACCENT__", tpl["colors"]["accent"])
                .replace("__RADIUS__", str(tpl.get("radius", 36)))
                .replace("__STORY__", json.dumps(story, ensure_ascii=False).replace("</", "<\\/"))
                .replace("__ENGINE__", (WEB / "engine.js").read_text(encoding="utf-8")))


def render_cutaways(page: str, cutaways: list[dict[str, Any]], outdir: str, workers: int,
                    progress: Optional[Callable[[float], None]] = None, fps: int = FPS) -> list[dict[str, Any]]:
    FPS = fps
    """Chaque animation → .mov ProRes 4444 avec alpha (entrée/sortie incluses)."""
    jobs = []
    for k, c in enumerate(cutaways):
        f0 = max(0, int((c["start"] - 0.2) * FPS)); f1 = int((c["end"] + 0.2) * FPS) + 1
        out = os.path.join(outdir, f"cut_{k:02d}.mov")
        jobs.append((k, f0, f1, out))
    done = [0]

    def run(j):
        k, f0, f1, out = j
        renderer._run([page, "--video", out, "--from", str(f0), "--to", str(f1), "--fps", str(FPS), "--sub", "2", "--alpha", "1"])
        done[0] += 1
        if progress:
            progress(done[0] / len(jobs))
        return {"file": out, "t0": f0 / FPS, "t1": f1 / FPS}

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        return list(ex.map(run, jobs))


# ----------------------------------------------------------------- sous-titres
def captions_ass(vu: dict[str, Any], ranges: list[dict[str, float]], template_id: str,
                 cutaways: list[dict[str, Any]], out: str) -> Optional[str]:
    try:
        from app.autoedit_engine import subs_ass
        style = CAPTION_STYLE.get(template_id, "tiktok_yellow")
        txt = subs_ass.build_ass(vu, ranges, style)
    except Exception as e:
        logger.warning("sous-titres ignorés: %s", e)
        return None

    def secs(ts: str) -> float:
        h, m, s = ts.split(":"); return int(h) * 3600 + int(m) * 60 + float(s)

    keep = []
    for line in txt.splitlines():
        if line.startswith("Dialogue:"):
            st = secs(line.split(",")[1]); en = secs(line.split(",")[2])
            if any(st < c["end"] + 0.1 and en > c["start"] - 0.1 for c in cutaways):
                continue  # pas de sous-titres par-dessus une animation plein écran
        keep.append(line)
    Path(out).write_text("\n".join(keep) + "\n", encoding="utf-8")
    return out


# ----------------------------------------------------------------- orchestration
def run_facecam(video_path: str, output_dir: str, *, template: str = "prestige", density: str = "medium",
                captions: bool = True, music: bool = True, brand_color: Optional[str] = None,
                language: Optional[str] = None, progress: Optional[Progress] = None,
                workers: Optional[int] = None) -> dict[str, Any]:
    prog = progress or (lambda p, m: logger.info("[%s%%] %s", p, m))
    wd = Path(output_dir); wd.mkdir(parents=True, exist_ok=True)
    work = wd / "motion_pro"; work.mkdir(exist_ok=True)
    n = max(1, min(workers or (os.cpu_count() or 2), 8))
    t0 = time.time(); steps: list[str] = []; failed: list[str] = []
    src = probe(video_path)

    prog(4, "Transcription mot à mot")
    vu = transcribe(video_path, str(work), language); steps.append("transcription")

    prog(14, "Coupes intelligentes (silences, répétitions, hésitations)")
    ranges, cut_info = cut_ranges(vu)
    if not ranges:
        ranges = [{"start": 0.0, "end": src["duration"]}]
    steps.append("smart_cut")

    prog(20, "Assemblage du montage")
    base = str(work / "base.mp4")
    dur = render_base(video_path, ranges, base, src, n); steps.append("base")
    words = remap_words(vu, ranges)

    prog(30, "Plan des animations")
    cutaways, planner = plan_cutaways(words, dur, density, None, (vu.get("language") or "fr"))
    (work / "cutaways.json").write_text(json.dumps(cutaways, ensure_ascii=False, indent=1))
    page = str(work / "overlay.html")
    Path(page).write_text(compose_overlay(cutaways, words, dur, template, brand_color), encoding="utf-8")
    ev = renderer.events(page, str(work / "events.json"))
    steps.append("plan")

    prog(35, "Animation des scènes plein écran")
    clips = render_cutaways(page, cutaways, str(work), n, progress=lambda f: prog(35 + int(45 * f), "Animation des scènes plein écran"), fps=src["fps"]) if cutaways else []
    steps.append("motion")

    prog(82, "Sound design et mixage")
    mix = str(work / "mix.wav")
    if src["audio"]:
        tpl = resolve_template(template)
        audio.mix(base, ev.get("events", []), dur, mix, mood=tpl.get("music", "hopeful"), bpm=tpl.get("bpm", 96),
                  turn=0.0, music_db=-22 if music else -120, sfx_db=-8)
    steps.append("sound")

    prog(88, "Sous-titres et export final")
    ass = captions_ass(vu, ranges, template, cutaways, str(work / "captions.ass")) if captions else None
    out = str(wd / "final_motion_pro.mp4")
    inputs = ["-i", base]
    fc = []; last = "0:v"
    for k, c in enumerate(clips):
        inputs += ["-i", c["file"]]
        fc.append(f"[{k + 1}:v]setpts=PTS-STARTPTS+{c['t0']:.3f}/TB[o{k}]")
        fc.append(f"[{last}][o{k}]overlay=eof_action=pass:enable='between(t,{c['t0']:.3f},{c['t1']:.3f})'[v{k}]"); last = f"v{k}"
    if ass:
        esc = ass.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        fc.append(f"[{last}]ass='{esc}'[vs]"); last = "vs"
    fc.append(f"[{last}]format=yuv420p[vout]")
    args = [*inputs]
    if src["audio"]:
        args += ["-i", mix]
    args += ["-filter_complex", ";".join(fc), "-map", "[vout]"]
    if src["audio"]:
        args += ["-map", f"{len(clips) + 1}:a", "-c:a", "aac", "-b:a", "192k"]
    args += ["-c:v", "libx264", "-crf", "20", "-preset", "medium", "-r", str(src["fps"]), "-movflags", "+faststart", "-shortest", out]
    try:
        _ff(*args)
    except subprocess.CalledProcessError:
        if not ass:
            raise
        failed.append("captions")  # repli sans sous-titres (police/libass indisponible)
        fc = [f for f in fc if "ass=" not in f]
        fc[-1] = f"[{'v' + str(len(clips) - 1) if clips else '0:v'}]format=yuv420p[vout]"
        i = args.index("-filter_complex"); args[i + 1] = ";".join(fc)
        _ff(*args)
    steps.append("export")
    for c in clips:
        try:
            os.unlink(c["file"])
        except OSError:
            pass
    prog(100, "Terminé")
    return {"output_path": out, "engine": "motion_pro", "template": template, "density": density,
            "duration": round(probe(out)["duration"], 2), "source_duration": round(src["duration"], 2),
            "cutaways": [{"start": c["start"], "end": c["end"], "type": c["scene"].get("type"), "text": c.get("text")} for c in cutaways],
            "planner": planner, "cut": cut_info, "steps_completed": steps, "steps_failed": failed,
            "render_seconds": round(time.time() - t0, 1)}
