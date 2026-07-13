"""Pipeline « Clips » — vidéo longue -> shorts viraux prêts à publier.

Étapes:
  1. Transcription complète de la source (ElevenLabs Scribe si clé, sinon
     Whisper local — même logique que le pipeline v2).
  2. Détection des moments viraux (LLM Gemini via OpenRouter, repli
     heuristique local) — voir ``viral_moments``.
  3. Pour CHAQUE moment: découpe propre de la source (ffmpeg, ré-encodage
     rapide aligné sur les phrases), transcript local recalé à 0, puis
     montage complet par le moteur Auto Edit (captions animées du style
     choisi, zooms, flashs, SFX, motion design, popups mots-clés).
  4. Résultat: ``result.clips`` = liste des shorts (titre, hook, score,
     chemin, durée) — l'utilisateur choisit ceux qu'il télécharge.

Contrat de retour compatible worker: ``output_path`` pointe vers le meilleur
clip pour que l'endpoint de téléchargement historique fonctionne aussi.
Un clip qui échoue n'annule pas les autres (best-effort par clip).
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from typing import Callable, Optional

from app.config import settings

logger = logging.getLogger(__name__)

ProgressFn = Callable[[int, str], None]

DEFAULT_MAX_CLIPS = 5


def _cut_source(src: str, start: float, end: float, out_path: str) -> str:
    """Découpe [start, end] de *src* en mp4 ré-encodé (coupe précise à l'image)."""
    pad_out = 0.25          # petite respiration après la dernière phrase
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-ss", f"{max(0.0, start):.3f}", "-to", f"{end + pad_out:.3f}",
        "-i", src,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        out_path,
    ]
    subprocess.run(cmd, check=True,
                   timeout=settings.FFMPEG_COMMAND_TIMEOUT_SECONDS or None)
    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        raise RuntimeError(f"clip cut produced no output: {out_path}")
    return out_path


def _slice_vu(vu: dict, start: float, end: float) -> dict:
    """Transcript du clip: mots dans [start, end], temps recalés à 0."""
    segments = []
    for seg in vu.get("segments", []):
        words = [
            {"word": w["word"],
             "start": round(float(w["start"]) - start, 3),
             "end": round(float(w["end"]) - start, 3)}
            for w in seg.get("words", [])
            if start <= (float(w["start"]) + float(w["end"])) / 2.0 <= end
        ]
        if words:
            segments.append({
                "text": " ".join(w["word"].strip() for w in words).strip(),
                "start": words[0]["start"],
                "end": words[-1]["end"],
                "words": words,
            })
    return {"language": vu.get("language", "auto"),
            "duration": round(end - start, 3),
            "segments": segments}


def _transcribe_source(video_path: str, output_dir: str, results: dict) -> str:
    """Transcription complète — même stratégie que le pipeline v2."""
    from app.processing.pipeline_v2 import (
        _choose_transcription_provider, _transcript_to_vu,
    )

    el_key = getattr(settings, "ELEVENLABS_API_KEY", "") or ""
    if el_key and not os.environ.get("ELEVENLABS_API_KEY"):
        os.environ["ELEVENLABS_API_KEY"] = el_key
    provider = getattr(settings, "TRANSCRIPTION_PROVIDER", "auto")
    lang = (getattr(settings, "TRANSCRIPTION_LANGUAGE", "") or "").strip() or None

    if _choose_transcription_provider(
            provider, bool(os.environ.get("ELEVENLABS_API_KEY"))) == "elevenlabs":
        try:
            from app.autoedit_engine import transcribe as el_transcribe
            vu_path = el_transcribe.transcribe(
                video_path,
                out_path=os.path.join(output_dir, "source_vu.json"),
                language=lang,
            )
            vu = json.load(open(vu_path, encoding="utf-8"))
            if sum(len(s.get("words", [])) for s in vu.get("segments", [])) >= 3:
                results["transcription"] = {"provider": "elevenlabs",
                                            "language": vu.get("language")}
                return vu_path
        except Exception as exc:  # noqa: BLE001 - fallback Whisper
            logger.warning("[clips] Scribe failed (%s) — fallback Whisper", exc)

    from app.processing.transcription_service import TranscriptionService
    ts = TranscriptionService(model_name=settings.WHISPER_MODEL, word_timestamps=True)
    transcript = ts.transcribe(video_path, output_dir)
    if len(transcript.words) < 3:
        raise RuntimeError(
            "Transcription quasi vide — pas de parole exploitable pour créer des clips.")
    results["transcription"] = {"provider": "whisper", "language": transcript.language}
    vu_path = _transcript_to_vu(transcript, output_dir, video_path)
    # _transcript_to_vu écrit engine_vu.json — renomme pour rester explicite.
    src_vu = os.path.join(output_dir, "source_vu.json")
    shutil.move(vu_path, src_vu)
    return src_vu


def run_clips_pipeline(
    video_path: str,
    output_dir: str,
    mode: Optional[str] = None,
    params: Optional[dict] = None,
    progress_callback: Optional[ProgressFn] = None,
) -> dict:
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Input video not found: {video_path}")
    if os.path.getsize(video_path) == 0:
        raise ValueError("Input video file is empty")
    os.makedirs(output_dir, exist_ok=True)

    # Préflight disque (chaque clip écrit ses intermédiaires).
    free_gb = shutil.disk_usage(output_dir).free / 1e9
    if free_gb < max(3.0, os.path.getsize(video_path) / 1e9 * 2):
        raise RuntimeError(
            f"Espace disque insuffisant sur le serveur ({free_gb:.1f} Go libres). "
            "Réessaie dans quelques minutes."
        )

    def progress(p: int, msg: str) -> None:
        if progress_callback:
            progress_callback(p, msg)
        logger.info(f"[clips {p}%] {msg}")

    from app.processing.pipeline_v2 import MODE_TO_TEMPLATE, V2_MODE_PRESETS
    from app.processing import viral_moments
    from app.autoedit_engine import config as engine_config
    from app.autoedit_engine import ffmpeg_utils as engine_ffmpeg
    from app.autoedit_engine import pipeline as engine_pipeline
    from app.processing.pipeline_v2 import resolve_visual_mode

    engine_ffmpeg.ensure_ffmpeg()

    preset = V2_MODE_PRESETS.get(mode or "", {}) if mode else {}
    options = dict(preset)
    raw_opts = (params or {}).get("options") if params else None
    if isinstance(raw_opts, dict):
        for k, v in raw_opts.items():
            if v is not None:
                options[k] = v

    settings_key = getattr(settings, "OPENROUTER_API_KEY", "") or ""
    if settings_key and not os.environ.get("OPENROUTER_API_KEY"):
        os.environ["OPENROUTER_API_KEY"] = settings_key

    template = MODE_TO_TEMPLATE.get(mode or "", "tiktok_yellow")
    requested_tpl = options.get("subtitle_template")
    if requested_tpl in engine_config.ASS_TEMPLATES:
        template = requested_tpl
    visual_mode = resolve_visual_mode(options, settings.AUTOEDIT_DEFAULT_VISUAL_MODE)
    do_broll = bool(settings.ENABLE_AI_BROLL) and options.get("ai_broll", True) is not False
    do_motion = (bool(getattr(settings, "ENABLE_MOTION_DESIGN", True))
                 and options.get("motion_design", True) is not False)

    try:
        max_clips = int(options.get("max_clips") or DEFAULT_MAX_CLIPS)
    except (TypeError, ValueError):
        max_clips = DEFAULT_MAX_CLIPS
    max_clips = max(1, min(viral_moments.MAX_CLIPS, max_clips))

    results: dict = {
        "pipeline_version": "clips",
        "engine": "autoedit_v4",
        "mode": mode,
        "options": options,
        "subtitle_template": template,
        "steps_completed": [],
        "steps_failed": [],
        "clips": [],
    }

    # ---- 1. Transcription ---------------------------------------------------
    progress(12, "Transcription de la vidéo source…")
    vu_path = _transcribe_source(video_path, output_dir, results)
    vu = json.load(open(vu_path, encoding="utf-8"))
    results["steps_completed"].append("transcription")

    # ---- 2. Détection des moments viraux ------------------------------------
    progress(28, "Analyse IA : détection des moments viraux…")
    moments, provider = viral_moments.detect_viral_moments(vu, max_clips=max_clips)
    if not moments:
        raise RuntimeError(
            "Aucun extrait exploitable détecté dans cette vidéo "
            "(parole insuffisante ou vidéo trop courte)."
        )
    results["moments_provider"] = provider
    results["moments_detected"] = len(moments)
    results["steps_completed"].append("viral_moments")
    progress(32, f"{len(moments)} moments viraux détectés ({provider})")

    # ---- 3. Découpe + montage de chaque clip --------------------------------
    src_dir = os.path.join(output_dir, "clip_sources")
    os.makedirs(src_dir, exist_ok=True)
    span = 95 - 34
    for i, m in enumerate(moments):
        base_pct = 34 + int(span * i / len(moments))
        progress(base_pct, f"Montage du clip {i + 1}/{len(moments)} : {m['title'][:40]}")
        clip_workdir = os.path.join(output_dir, f"clip_{i:02d}")
        try:
            clip_src = _cut_source(
                video_path, m["start"], m["end"],
                os.path.join(src_dir, f"clip_{i:02d}.mp4"))
            clip_vu = _slice_vu(vu, m["start"], m["end"])
            os.makedirs(clip_workdir, exist_ok=True)
            clip_vu_path = os.path.join(clip_workdir, "clip_vu.json")
            with open(clip_vu_path, "w", encoding="utf-8") as fh:
                json.dump(clip_vu, fh, ensure_ascii=False, indent=2)

            def clip_progress(p: int, label: str, _b=base_pct, _i=i) -> None:
                progress(min(95, _b + int(span / len(moments) * p / 100)),
                         f"Clip {_i + 1}: {label}")

            report: dict = {}
            final = engine_pipeline.run(
                clip_src, clip_workdir,
                vu=clip_vu_path,
                template=template,
                do_broll=do_broll,
                do_motion=do_motion,
                broll_demographic=options.get("broll_demographic") or "african",
                visual_mode=visual_mode,
                motion_preset=options.get("motion_preset") or None,
                style_seed_text=f"{m['title']}|{m['start']}",
                progress_callback=clip_progress,
                report=report,
            )
            results["clips"].append({
                "index": i,
                "title": m["title"],
                "hook": m["hook"],
                "reason": m["reason"],
                "score": m["score"],
                "source_start": m["start"],
                "source_end": m["end"],
                "duration_s": round(m["end"] - m["start"], 2),
                "output_path": final,
                "size_bytes": os.path.getsize(final),
                "effects_applied": report.get("effects_applied", {}),
            })
        except Exception as exc:  # noqa: BLE001 - un clip raté ne bloque pas les autres
            logger.error("[clips] clip %d failed: %s", i, exc, exc_info=True)
            results["steps_failed"].append(f"clip_{i}")
            results["clips"].append({
                "index": i,
                "title": m["title"],
                "hook": m["hook"],
                "score": m["score"],
                "source_start": m["start"],
                "source_end": m["end"],
                "duration_s": round(m["end"] - m["start"], 2),
                "error": str(exc)[:300],
            })
        finally:
            # Chaque clip nettoie ses intermédiaires; garde le master final.
            try:
                engine_pipeline.cleanup_intermediates(clip_workdir)
            except Exception:  # noqa: BLE001
                pass

    ok_clips = [c for c in results["clips"] if c.get("output_path")]
    if not ok_clips:
        raise RuntimeError("Aucun clip n'a pu être monté — voir les logs du moteur.")

    # Contrat historique: output_path = meilleur clip (score max).
    best = max(ok_clips, key=lambda c: c.get("score", 0))
    results["output_path"] = best["output_path"]
    results["output_size_bytes"] = best["size_bytes"]
    results["clips_rendered"] = len(ok_clips)
    results["steps_completed"].append("clips_render")
    progress(100, f"{len(ok_clips)} clips prêts")
    return results
