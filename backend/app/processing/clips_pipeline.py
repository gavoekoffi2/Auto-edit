"""Pipeline « Clips » — vidéo longue -> shorts viraux, en DEUX étapes.

Étape ANALYSE (rapide, peu coûteuse):
  1. Transcription complète de la source (ElevenLabs Scribe si clé, sinon
     Whisper local — même logique que le pipeline v2).
  2. Détection des moments viraux (LLM Gemini via OpenRouter, repli
     heuristique local) — voir ``viral_moments``. Chaque moment embarque son
     transcript (excerpt) pour l'affichage et la correction côté interface.
  -> Le job se termine avec ``result.stage = "moments_ready"``: l'utilisateur
     CHOISIT ses extraits avant de consommer du rendu et des crédits IA.

Étape RENDU (sur les extraits sélectionnés uniquement):
  3. Pour CHAQUE moment retenu: découpe propre de la source (ffmpeg,
     ré-encodage aligné sur les phrases), transcript local recalé à 0, puis
     montage complet par le moteur Auto Edit (captions animées du style
     choisi, zooms, flashs, SFX, motion design, popups mots-clés).
  4. ``result.clips`` = liste des shorts (titre, hook, score, chemin, durée).

``run_clips_pipeline`` reste le point d'entrée unique: ``params.stage`` vaut
``analyze`` (défaut produit), ``render`` (moments fournis) ou ``full``
(comportement historique: analyse + rendu de tout, sans sélection).

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
from app.services.errors import tag as err_tag

logger = logging.getLogger(__name__)

ProgressFn = Callable[[int, str], None]

DEFAULT_MAX_CLIPS = 5
RENDER_MIN_CLIP_S = 8.0
RENDER_MAX_CLIP_S = 180.0


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


def _excerpt_text(vu: dict, start: float, end: float, limit: int = 600) -> str:
    """Texte parlé de l'extrait (pour l'affichage/sélection côté interface)."""
    parts: list[str] = []
    for seg in vu.get("segments", []):
        for w in seg.get("words", []):
            mid = (float(w["start"]) + float(w["end"])) / 2.0
            if start <= mid <= end:
                parts.append(w["word"].strip())
    text = " ".join(p for p in parts if p)
    return text[:limit]


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
        raise RuntimeError(err_tag("NO_SPEECH"))
    results["transcription"] = {"provider": "whisper", "language": transcript.language}
    vu_path = _transcript_to_vu(transcript, output_dir, video_path)
    # _transcript_to_vu écrit engine_vu.json — renomme pour rester explicite.
    src_vu = os.path.join(output_dir, "source_vu.json")
    shutil.move(vu_path, src_vu)
    return src_vu


def _resolve_options(mode: Optional[str], params: Optional[dict]) -> dict:
    from app.processing.pipeline_v2 import V2_MODE_PRESETS

    preset = V2_MODE_PRESETS.get(mode or "", {}) if mode else {}
    options = dict(preset)
    raw_opts = (params or {}).get("options") if params else None
    if isinstance(raw_opts, dict):
        for k, v in raw_opts.items():
            if v is not None:
                options[k] = v
    return options


def validate_render_moments(moments: object, source_duration: float,
                            max_clips: int) -> list[dict]:
    """Valide/normalise des moments fournis par le client pour le rendu.

    Ne fait JAMAIS confiance au payload: bornes dans la source, durées
    [RENDER_MIN_CLIP_S, RENDER_MAX_CLIP_S], nombre <= max_clips, textes
    tronqués. Lève ValueError avec un message montrable.
    """
    if not isinstance(moments, list) or not moments:
        raise ValueError("Aucun extrait sélectionné.")
    if len(moments) > max_clips:
        raise ValueError(f"Maximum {max_clips} clips pour ton plan.")
    cleaned: list[dict] = []
    for m in moments:
        if not isinstance(m, dict):
            raise ValueError("Extrait invalide.")
        try:
            start = float(m["start"])
            end = float(m["end"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Extrait invalide (temps manquants).")
        if not (0.0 <= start < end):
            raise ValueError("Extrait invalide (bornes incohérentes).")
        if source_duration and end > source_duration + 1.0:
            raise ValueError("Extrait hors de la vidéo source.")
        if end - start < RENDER_MIN_CLIP_S:
            raise ValueError(f"Un clip doit durer au moins {RENDER_MIN_CLIP_S:.0f} s.")
        if end - start > RENDER_MAX_CLIP_S:
            raise ValueError(f"Un clip ne peut pas dépasser {RENDER_MAX_CLIP_S:.0f} s.")
        cleaned.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "title": str(m.get("title") or "Extrait")[:120],
            "hook": str(m.get("hook") or "")[:200],
            "reason": str(m.get("reason") or "")[:300],
            "score": max(0, min(100, int(m.get("score") or 50))),
        })
    cleaned.sort(key=lambda m: m["start"])
    for a, b in zip(cleaned, cleaned[1:]):
        if b["start"] < a["end"]:
            raise ValueError("Deux extraits sélectionnés se chevauchent.")
    return cleaned


def _analyze(video_path: str, output_dir: str, options: dict,
             results: dict, progress: ProgressFn) -> tuple[str, list[dict]]:
    """Transcription + détection des moments. Returns (vu_path, moments)."""
    from app.processing import viral_moments

    progress(15, "Transcription de la vidéo source…")
    vu_path = _transcribe_source(video_path, output_dir, results)
    vu = json.load(open(vu_path, encoding="utf-8"))
    results["steps_completed"].append("transcription")

    progress(30, "Analyse IA : détection des moments forts…")
    try:
        max_clips = int(options.get("max_clips") or DEFAULT_MAX_CLIPS)
    except (TypeError, ValueError):
        max_clips = DEFAULT_MAX_CLIPS
    max_clips = max(1, min(viral_moments.MAX_CLIPS, max_clips))
    moments, provider = viral_moments.detect_viral_moments(vu, max_clips=max_clips)
    if not moments:
        raise RuntimeError(err_tag("NO_SPEECH", "no viable moment detected"))
    for m in moments:
        m["excerpt"] = _excerpt_text(vu, m["start"], m["end"])
    results["moments_provider"] = provider
    results["moments_detected"] = len(moments)
    results["steps_completed"].append("viral_moments")
    return vu_path, moments


def _render(video_path: str, output_dir: str, vu: dict, moments: list[dict],
            mode: Optional[str], options: dict, results: dict,
            progress: ProgressFn, pct_from: int = 34) -> None:
    """Monte chaque moment en short via le moteur Auto Edit."""
    from app.autoedit_engine import config as engine_config
    from app.autoedit_engine import ffmpeg_utils as engine_ffmpeg
    from app.autoedit_engine import pipeline as engine_pipeline
    from app.processing.pipeline_v2 import MODE_TO_TEMPLATE, resolve_visual_mode

    engine_ffmpeg.ensure_ffmpeg()
    template = MODE_TO_TEMPLATE.get(mode or "", "tiktok_yellow")
    requested_tpl = options.get("subtitle_template")
    if requested_tpl in engine_config.ASS_TEMPLATES:
        template = requested_tpl
    results["subtitle_template"] = template
    visual_mode = resolve_visual_mode(options, settings.AUTOEDIT_DEFAULT_VISUAL_MODE)
    do_broll = (bool(settings.ENABLE_AI_BROLL)
                and options.get("ai_broll", True) is not False)
    do_motion = (bool(getattr(settings, "ENABLE_MOTION_DESIGN", True))
                 and options.get("motion_design", True) is not False)

    src_dir = os.path.join(output_dir, "clip_sources")
    os.makedirs(src_dir, exist_ok=True)
    span = 95 - pct_from
    for i, m in enumerate(moments):
        base_pct = pct_from + int(span * i / len(moments))
        progress(base_pct,
                 f"Rendu du clip {i + 1}/{len(moments)} : {m['title'][:40]}")
        clip_workdir = os.path.join(output_dir, f"clip_{i:02d}")
        try:
            clip_src = _cut_source(
                video_path, m["start"], m["end"],
                os.path.join(src_dir, f"clip_{i:02d}.mp4"))
            clip_vu = _slice_vu(vu, m["start"], m["end"])
            if not clip_vu["segments"]:
                raise RuntimeError(err_tag("NO_SPEECH", "empty clip transcript"))
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
                cleanup_level=options.get("cleanup_level"),
                smart_crop_mode=options.get("smart_crop_mode"),
                progress_callback=clip_progress,
                report=report,
            )
            results["clips"].append({
                "index": i,
                "title": m["title"],
                "hook": m.get("hook", ""),
                "reason": m.get("reason", ""),
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
                "hook": m.get("hook", ""),
                "score": m["score"],
                "source_start": m["start"],
                "source_end": m["end"],
                "duration_s": round(m["end"] - m["start"], 2),
                "error": err_tag("RENDER_FAILED"),
            })
        finally:
            try:
                engine_pipeline.cleanup_intermediates(clip_workdir)
            except Exception:  # noqa: BLE001
                pass


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
        raise RuntimeError(err_tag("DISK_FULL", f"{free_gb:.1f} GB free"))

    def progress(p: int, msg: str) -> None:
        if progress_callback:
            progress_callback(p, msg)
        logger.info(f"[clips {p}%] {msg}")

    settings_key = getattr(settings, "OPENROUTER_API_KEY", "") or ""
    if settings_key and not os.environ.get("OPENROUTER_API_KEY"):
        os.environ["OPENROUTER_API_KEY"] = settings_key

    options = _resolve_options(mode, params)
    stage = str((params or {}).get("stage") or "full").lower()

    results: dict = {
        "pipeline_version": "clips",
        "engine": "autoedit_v4",
        "mode": mode,
        "stage": stage,
        "options": options,
        "steps_completed": [],
        "steps_failed": [],
        "clips": [],
    }

    if stage == "render":
        # Moments choisis par l'utilisateur; le vu source vient de l'analyse.
        vu_rel = (params or {}).get("source_vu_path")
        vu_abs = vu_rel
        if vu_rel and not os.path.isabs(vu_rel):
            vu_abs = os.path.join(os.path.abspath(settings.UPLOAD_DIR), vu_rel)
        if not vu_abs or not os.path.exists(vu_abs):
            # L'analyse a expiré/été purgée: on retranscrit (plus lent, même
            # résultat) plutôt que d'échouer.
            vu_abs = _transcribe_source(video_path, output_dir, results)
        vu = json.load(open(vu_abs, encoding="utf-8"))
        from app.autoedit_engine.ffmpeg_utils import probe_duration
        source_duration = probe_duration(video_path) or float(vu.get("duration") or 0.0)
        moments = validate_render_moments(
            (params or {}).get("moments"), source_duration,
            max_clips=int(options.get("max_clips") or DEFAULT_MAX_CLIPS))
        progress(10, f"Rendu de {len(moments)} clip(s) sélectionné(s)…")
        _render(video_path, output_dir, vu, moments, mode, options,
                results, progress, pct_from=12)
    else:
        vu_path, moments = _analyze(video_path, output_dir, options, results, progress)
        results["moments"] = moments
        results["source_vu_path"] = vu_path       # relativisé par le worker
        if stage == "analyze":
            results["stage"] = "moments_ready"
            progress(100, f"{len(moments)} extraits proposés — à toi de choisir")
            return results
        # stage == "full": comportement historique (rendu de tous les moments)
        vu = json.load(open(vu_path, encoding="utf-8"))
        _render(video_path, output_dir, vu, moments, mode, options,
                results, progress, pct_from=34)

    ok_clips = [c for c in results["clips"] if c.get("output_path")]
    if not ok_clips:
        raise RuntimeError(err_tag("RENDER_FAILED", "no clip rendered"))

    # Contrat historique: output_path = meilleur clip (score max).
    best = max(ok_clips, key=lambda c: c.get("score", 0))
    results["output_path"] = best["output_path"]
    results["output_size_bytes"] = best["size_bytes"]
    results["clips_rendered"] = len(ok_clips)
    results["steps_completed"].append("clips_render")
    progress(100, f"{len(ok_clips)} clips prêts")
    return results
