"""Orchestrateur du moteur « YouTube long ».

    transcription -> coupe voix (dernière prise) -> chapitres -> habillage ASS
    -> voix montée + SFX + musique (−14 LUFS) -> image 1:1 (un encodeur,
    habillage incrusté) -> mux -> vérifications -> rapport

Contrat de retour compatible avec les autres pipelines : ``output_path``,
``steps_completed``, ``steps_failed`` + un bloc ``longform`` (chapitres, coupes,
vérifications) que le frontend peut afficher.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Callable, List, Optional

from app.autoedit_engine import ffmpeg_utils

from . import audio, chapters as chapters_mod, graphics, render, styles, takes

logger = logging.getLogger(__name__)

ProgressFn = Callable[[int, str], None]

FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                         "autoedit_engine", "assets", "fonts")

X264_PRESET = os.getenv("LONGFORM_X264_PRESET", "veryfast")
X264_CRF = int(os.getenv("LONGFORM_X264_CRF", "19"))


def _opt(options: dict, key: str, default=None):
    v = options.get(key)
    return default if v is None else v


# --------------------------------------------------------------------------- #
# Transcription
# --------------------------------------------------------------------------- #
def transcribe(video_path: str, work: str, options: dict, results: dict) -> str:
    given = options.get("transcript_vu")
    if given and os.path.isfile(given):
        results["transcription"] = {"provider": "fourni"}
        return given
    from app.config import settings
    el_key = getattr(settings, "ELEVENLABS_API_KEY", "") or os.environ.get("ELEVENLABS_API_KEY", "")
    lang = options.get("language") or (getattr(settings, "TRANSCRIPTION_LANGUAGE", "") or "").strip() or None
    provider = (getattr(settings, "TRANSCRIPTION_PROVIDER", "auto") or "auto").lower()
    if el_key and provider != "whisper":
        try:
            from app.autoedit_engine import transcribe as el
            vu_path = el.transcribe(video_path, out_path=os.path.join(work, "vu.json"),
                                    api_key=el_key, language=lang)
            results["transcription"] = {"provider": "elevenlabs"}
            return vu_path
        except Exception as exc:  # noqa: BLE001
            logger.warning("[longform] Scribe a échoué (%s) — repli Whisper", exc)
            results.setdefault("warnings", []).append(f"scribe: {str(exc)[:160]}")
    from app.processing.pipeline_v2 import _transcript_to_vu
    from app.processing.transcription_service import TranscriptionService
    ts = TranscriptionService(model_name=settings.WHISPER_MODEL, word_timestamps=True)
    tr = ts.transcribe(video_path, work)
    results["transcription"] = {"provider": "whisper"}
    return _transcript_to_vu(tr, work, video_path)


# --------------------------------------------------------------------------- #
# Plan de cadrage (zoom alterné qui masque les coupes)
# --------------------------------------------------------------------------- #
def plan_zoom(ranges: List[dict], st: styles.LongformStyle, centers: List[float],
              enabled: bool = True) -> List[dict]:
    last_emph = -999.0
    acc = 0.0
    tight = False
    for i, r in enumerate(ranges):
        dur = r["end"] - r["start"]
        r["cx"] = centers[i] if i < len(centers) else 0.5
        r["cy"] = 0.42
        r["emphasis"] = False
        if not enabled:
            r["zoom"] = 1.0
        else:
            if i > 0 and dur >= 0.5:
                tight = not tight
            toks = {takes.norm(x) for x in r["text"].split()}
            emph = bool(toks & graphics.EMPHASIS) and dur >= 1.6 and acc - last_emph >= 40.0
            if emph:
                r["zoom"] = st.emphasis_zoom
                r["emphasis"] = True
                last_emph = acc
            else:
                r["zoom"] = st.punch_zoom if tight else 1.0
        acc += dur
    return ranges


def face_center(video_path: str, duration: float, samples: int = 10) -> tuple:
    """Centre horizontal du visage, mesuré UNE fois sur toute la vidéo.

    Une vidéo YouTube longue est presque toujours filmée caméra fixe : une
    dizaine d'images réparties suffisent (recherche rapide sur image clé),
    au lieu d'une analyse coupe par coupe qui coûtait des minutes.
    """
    import statistics
    import subprocess
    import tempfile
    rep = {"engine": "haar_global", "samples": 0, "faces": 0, "center": 0.5}
    try:
        from app.autoedit_engine import smart_crop
        if not smart_crop.opencv_available():
            rep["fallback"] = "opencv_unavailable"
            return 0.5, rep
        found = []
        with tempfile.TemporaryDirectory(prefix="lf_face_") as tmp:
            for i in range(samples):
                t = duration * (0.05 + 0.9 * i / max(1, samples - 1))
                out = os.path.join(tmp, f"f{i}.jpg")
                subprocess.run([ffmpeg_utils.FFMPEG, "-nostdin", "-v", "error", "-y",
                                "-ss", f"{t:.2f}", "-i", video_path, "-frames:v", "1",
                                "-vf", "scale=480:-2", "-q:v", "5", out],
                               timeout=60, check=False)
                if os.path.exists(out):
                    rep["samples"] += 1
                    c = smart_crop._detect_face_center(out)
                    if c is not None:
                        found.append(c)
        rep["faces"] = len(found)
        if found:
            cx = min(0.8, max(0.2, statistics.median(found)))
            rep["center"] = round(cx, 3)
            return cx, rep
        rep["fallback"] = "no_face_detected"
    except Exception as exc:  # noqa: BLE001 — le cadrage n'est jamais bloquant
        rep["fallback"] = f"error: {type(exc).__name__}"
    return 0.5, rep


def output_words(vu: dict, tl: render.Timeline) -> List[dict]:
    words = takes.flatten_words(vu)
    out: List[dict] = []
    prev_src_end: Optional[float] = None
    j = 0
    items = tl.items
    for w in words:
        while j < len(items) and items[j].end < w["start"] - 1e-6:
            j += 1
        if j >= len(items):
            break
        it = items[j]
        if not (it.start - 1e-6 <= w["start"] <= it.end + 1e-6):
            continue
        o0 = it.out_start + (w["start"] - it.start)
        o1 = it.out_start + (min(w["end"], it.end) - it.start)
        out.append({"word": w["word"], "start": round(o0, 3), "end": round(max(o1, o0 + 0.05), 3),
                    "gap_before": round(w["start"] - prev_src_end, 3) if prev_src_end is not None else 0.0})
        prev_src_end = w["end"]
    return out


# --------------------------------------------------------------------------- #
# Entrée principale
# --------------------------------------------------------------------------- #
def run_longform(video_path: str, output_dir: str, mode: Optional[str] = None,
                 options: Optional[dict] = None,
                 progress_callback: Optional[ProgressFn] = None) -> dict:
    t0 = time.time()
    options = dict(options or {})
    os.makedirs(output_dir, exist_ok=True)
    work = os.path.join(output_dir, "longform")
    os.makedirs(work, exist_ok=True)

    timings: dict = {}
    _mark = {"t": time.time(), "step": "setup"}

    def progress(p: int, msg: str) -> None:
        if progress_callback:
            progress_callback(int(p), msg)
        logger.info("[longform %s%%] %s", p, msg)

    def step(name: str) -> None:
        now = time.time()
        timings[_mark["step"]] = round(now - _mark["t"], 2)
        _mark.update(t=now, step=name)

    ffmpeg_utils.ensure_ffmpeg()
    info = render.probe_video(video_path)
    if not info.has_audio:
        raise RuntimeError("La vidéo n'a pas de piste audio : impossible de couper la voix.")

    seed = styles.seed_for(video_path)
    style_id = options.get("longform_style") or styles.MODE_STYLE.get(mode or "", "auto")
    st = styles.resolve_style(style_id, seed)

    results: dict = {
        "pipeline_version": "v2", "engine": "longform_v1", "mode": mode,
        "options": {k: v for k, v in options.items() if k != "transcript_vu"},
        "aspect_ratio": "16:9", "steps_completed": [], "steps_failed": [],
        "style": {"id": st.id, "name": st.name, "requested": style_id},
    }

    # 1. transcription ------------------------------------------------------
    step("transcription")
    progress(3, "Transcription de la voix…")
    vu_path = transcribe(video_path, work, options, results)
    vu = json.load(open(vu_path, encoding="utf-8"))
    results["steps_completed"].append("transcription")

    # 1b. relecture IA optionnelle (phrases redites / reformulées)
    level = options.get("cleanup_level") or "light"
    if level != "off" and not options.get("transcript_vu"):
        try:
            from app.autoedit_engine import smart_cleanup
            clean_path, rep = smart_cleanup.clean_vu(vu_path, os.path.join(work, "vu_clean.json"),
                                                     level=level)
            if clean_path != vu_path:
                vu = json.load(open(clean_path, encoding="utf-8"))
                results["steps_completed"].append("llm_cleanup")
            results["llm_cleanup"] = {k: v for k, v in rep.items() if k != "llm_cleanup_removed_spans"}
        except Exception as exc:  # noqa: BLE001
            results["steps_failed"].append("llm_cleanup")
            logger.warning("[longform] relecture IA ignorée: %s", exc)

    # 2. coupe de la voix ---------------------------------------------------
    step("voice_cut")
    progress(18, "Coupe de la voix : dernière prise, répétitions, silences…")
    src48 = render.extract_audio(video_path, os.path.join(work, "src48.wav"))
    env = takes.Envelope.from_wav(src48)
    ranges, cut_report = takes.build_ranges(vu, takes.TakeConfig(), env, info.duration)
    if not ranges:
        raise RuntimeError("Aucune parole exploitable trouvée dans la vidéo.")
    results["steps_completed"].append("voice_cut")

    step("framing")
    centers = [0.5] * len(ranges)
    if info.landscape and _opt(options, "zoom_cuts", True):
        cx, crop_rep = face_center(video_path, info.duration)
        centers = [cx] * len(ranges)
        results["framing"] = crop_rep
    ranges = plan_zoom(ranges, st, centers, enabled=bool(_opt(options, "zoom_cuts", True)))
    tl = render.Timeline(ranges)
    json.dump({"source": video_path, "ranges": ranges}, open(os.path.join(work, "edl.json"), "w"),
              ensure_ascii=False, indent=1)

    # 3. chapitres ----------------------------------------------------------
    step("chapters")
    progress(24, "Chapitres…")
    words_out = output_words(vu, tl)
    ch = chapters_mod.build_chapters(words_out, tl.duration,
                                     use_llm=bool(_opt(options, "llm_titles", True)))
    results["steps_completed"].append("chapters")

    # 4. habillage ----------------------------------------------------------
    step("graphics")
    progress(28, f"Habillage « {st.name} »…")
    captions_on = _opt(options, "dynamic_captions", True) is not False
    ass, cues, gstats = graphics.build_ass(
        words_out, ch["chapters"], st, tl.duration, seed=seed,
        captions=captions_on,
        popups=_opt(options, "keyword_popups", True) is not False,
        cards=_opt(options, "chapter_cards", True) is not False)
    # whoosh discret sur les zooms d'emphase
    if st.sfx_zoom:
        for it, r in zip(tl.items, ranges):
            if r.get("emphasis"):
                cues.append({"t": max(0.0, it.out_start - 0.12), "name": st.sfx_zoom[0],
                             "db": st.sfx_db - 3.0, "kind": "zoom"})
    ass_path = os.path.join(work, "habillage.ass")
    with open(ass_path, "w", encoding="utf-8") as fh:
        fh.write(ass)
    results["steps_completed"].append("graphics")

    # 5. son ------------------------------------------------------------------
    step("audio")
    progress(32, "Voix, effets sonores et musique…")
    voice = render.build_voice(src48, tl, os.path.join(work, "voice.wav"))
    sfx_on = _opt(options, "sfx", True) is not False
    sfx_wav = None
    sfx_rep: dict = {"cues": 0}
    if sfx_on and cues:
        sfx_wav = os.path.join(work, "sfx.wav")
        sfx_rep = audio.build_sfx_track(cues, tl.duration, sfx_wav, work, seed=seed)
    music = audio.pick_music(options.get("music_path"), seed) \
        if _opt(options, "music", True) is not False else None
    mix_wav = os.path.join(work, "mix.wav")
    mix_rep = audio.mix(voice, sfx_wav, music, tl.duration, mix_wav, work, music_db=st.music_db)
    results["steps_completed"].append("audio_mix")

    # 6. image ------------------------------------------------------------------
    step("picture")
    progress(38, "Assemblage image + habillage (synchro exacte)…")
    video_only = os.path.join(work, "video.mp4")

    def pic_progress(frac: float) -> None:
        progress(38 + int(55 * frac), f"Rendu de l'image… {int(frac * 100)} %")

    try:
        pic = render.build_picture(video_path, info, tl, video_only, grade=st.grade,
                                   crf=X264_CRF, preset=X264_PRESET,
                                   ass_path=ass_path, fonts_dir=FONTS_DIR,
                                   progress=pic_progress)
    except BrokenPipeError as exc:
        raise RuntimeError("L'encodeur vidéo s'est arrêté pendant le rendu "
                           "(habillage ou espace disque).") from exc
    results["steps_completed"].append("picture")

    # 7. mux ----------------------------------------------------------------------
    step("mux_verify")
    progress(95, "Finalisation…")
    final = os.path.join(output_dir, "youtube_long_final.mp4")
    ffmpeg_utils.run([ffmpeg_utils.FFMPEG, "-nostdin", "-v", "error", "-y",
                      "-i", video_only, "-i", mix_wav, "-map", "0:v:0", "-map", "1:a:0",
                      "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                      "-movflags", "+faststart", final])

    # 8. vérifications (signal uniquement — on n'« écoute » pas) ----------------
    frames = render.count_frames(final)
    audio_s = render.wav_duration(mix_wav)
    video_s = frames / render.FPS
    checks = {
        "frames_expected": tl.n_frames, "frames_written": frames,
        "picture_s": round(video_s, 3), "sound_s": round(audio_s, 3),
        "av_diff_ms": round(abs(video_s - audio_s) * 1000, 1),
        "sync_ok": frames == tl.n_frames and abs(video_s - audio_s) <= 1.0 / render.FPS + 1e-3,
        "loudness_lufs": mix_rep.get("final_lufs"), "true_peak_db": mix_rep.get("final_true_peak"),
        "loudness_ok": (mix_rep.get("final_lufs") is not None
                        and abs(mix_rep["final_lufs"] + 14) <= 1.0),
        "repeated_5grams": takes.repeated_ngrams(ranges)[:20],
        "micro_fragments": len(cut_report.get("micro_fragments", [])),
        "method": "vérifications signal (images, durées, loudness) — pas d'écoute humaine",
    }
    if not checks["sync_ok"]:
        results["steps_failed"].append("verify_sync")

    with open(os.path.join(output_dir, "chapitres.txt"), "w", encoding="utf-8") as fh:
        fh.write(ch["text"] + "\n")

    results["longform"] = {
        "chapters": ch["chapters"], "chapters_text": ch["text"],
        "chapters_youtube_valid": ch["youtube_valid"], "chapter_titles": ch["titles_source"],
        "cut": {k: v for k, v in cut_report.items() if k != "removed"},
        "removed": cut_report.get("removed", [])[:400],
        "graphics": gstats, "sfx": sfx_rep, "audio": mix_rep,
        "checks": checks,
        "picture": {"frames": pic["frames"], "fps": pic["fps"], "av_offset_s": info.video_offset},
        "render_seconds": round(time.time() - t0, 1),
    }
    step("done")
    results["longform"]["timings"] = timings
    results["output_path"] = final
    results["output_size_bytes"] = os.path.getsize(final)
    results["steps_completed"].append("verify")
    # Rapport complet (avec la timeline plage par plage) sur disque ; le
    # résultat stocké en base reste léger.
    full = dict(results)
    full["longform"] = dict(results["longform"], timeline=tl.to_json(),
                            removed=cut_report.get("removed", []))
    with open(os.path.join(output_dir, "rapport_montage.json"), "w", encoding="utf-8") as fh:
        json.dump(full, fh, ensure_ascii=False, indent=1)

    # ménage des intermédiaires lourds
    if not options.get("keep_intermediates"):
        for f in ("src48.wav", "voice.wav", "sfx.wav", "mix.wav", "video.mp4"):
            try:
                os.remove(os.path.join(work, f))
            except OSError:
                pass
    progress(100, "Terminé")
    return results
