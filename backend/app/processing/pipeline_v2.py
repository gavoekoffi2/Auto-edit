"""Pipeline V2 — orchestre les services modulaires.

Étapes:
  0. Setup (validate input, output dirs)
  1. Transcription mot-par-mot       (TranscriptionService)
  2. Détection des silences          (SilenceDetector)
  3. Edit Decision List              (EditDecisionService)
  4. Plan B-roll                     (BrollPlanner)        — si ENABLE_AI_BROLL
  5. Génération d'images B-roll      (ImageGenerationService) — si activé
  6. Animation des B-roll en clips   (BrollAnimationService)
  7. Overlays animés (intro/CTA…)    (TemplateRenderer)
  8. Rendu final FFmpeg              (FFmpegRenderer)

Tout est best-effort: une étape qui échoue est loggée dans `result.steps_failed`
mais le pipeline continue avec le meilleur état atteint. Si le rendu final
échoue, on retombe sur un export "passthrough" (copie de la source) pour
préserver l'expérience utilisateur.

Ce pipeline ne casse PAS le pipeline V1 — il vit à côté, opt-in via
`job.pipeline_version=v2`.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Optional

from app.config import settings

logger = logging.getLogger(__name__)


# Presets de mode pour v2. Compatibles ascendants avec v1 (tiktok/youtube/podcast)
# + nouveaux modes africains.
V2_MODE_PRESETS: dict[str, dict] = {
    # --- legacy v1 ----------------------------------------------------------
    "tiktok": {
        "remove_silence": True,
        "dynamic_captions": True,
        "ai_broll": True,
        "motion_design": True,
        "music": True,
        "sfx": True,
        "vertical_9_16": True,
        "final_cta": False,
        "broll_style": "tiktok_viral",
        "broll_demographic": "african",
    },
    "youtube": {
        "remove_silence": True,
        "dynamic_captions": True,
        "ai_broll": True,
        "motion_design": True,
        "music": False,
        "sfx": False,
        "vertical_9_16": False,
        "final_cta": False,
        "broll_style": "african_business_premium",
        "broll_demographic": "african",
    },
    "podcast": {
        "remove_silence": True,
        "dynamic_captions": True,
        "ai_broll": False,
        "motion_design": False,
        "music": False,
        "sfx": False,
        "vertical_9_16": False,
        "final_cta": False,
        "broll_style": "podcast_propre",
        "broll_demographic": "african",
    },
    # --- nouveaux v2 (Afrique francophone) ----------------------------------
    "tiktok_viral": {
        "remove_silence": True,
        "dynamic_captions": True,
        "ai_broll": True,
        "motion_design": True,
        "music": True,
        "sfx": True,
        "vertical_9_16": True,
        "final_cta": True,
        "broll_style": "tiktok_viral",
        "broll_demographic": "african",
    },
    "business_premium_african": {
        "remove_silence": True,
        "dynamic_captions": True,
        "ai_broll": True,
        "motion_design": True,
        "music": True,
        "sfx": True,
        "vertical_9_16": True,
        "final_cta": True,
        "broll_style": "african_business_premium",
        "broll_demographic": "african",
    },
    "publicite_locale": {
        "remove_silence": True,
        "dynamic_captions": True,
        "ai_broll": True,
        "motion_design": True,
        "music": True,
        "sfx": True,
        "vertical_9_16": True,
        "final_cta": True,
        "broll_style": "publicite_locale",
        "broll_demographic": "african",
    },
    "podcast_propre": {
        "remove_silence": True,
        "dynamic_captions": False,
        "ai_broll": False,
        "motion_design": False,
        "music": False,
        "sfx": False,
        "vertical_9_16": False,
        "final_cta": False,
        "broll_style": "podcast_propre",
        "broll_demographic": "african",
    },
    "formation_educative": {
        "remove_silence": True,
        "dynamic_captions": True,
        "ai_broll": True,
        "motion_design": True,
        "music": False,
        "sfx": False,
        "vertical_9_16": False,
        "final_cta": False,
        "broll_style": "formation_educative",
        "broll_demographic": "african",
    },
    # --- nouveau défaut MVP : montage créateur économique -------------------
    # Rapide, non bloquant, sans dépendre des images IA : silences coupés,
    # captions, zooms, flashs caméra + shutter SFX, transitions, motion design.
    "credit_saver_creator_edit": {
        "remove_silence": True,
        "dynamic_captions": True,
        "ai_broll": False,          # pas d'image IA payante par défaut
        "motion_design": True,
        "music": True,
        "sfx": True,
        "vertical_9_16": True,
        "final_cta": True,
        "visual_mode": "credit_saver",
        "broll_style": "tiktok_viral",
        "broll_demographic": "african",
    },
}
# Alias historique accepté pour le même mode.
V2_MODE_PRESETS["creator_economy_mode"] = dict(V2_MODE_PRESETS["credit_saver_creator_edit"])

# --- Styles Captions AI (réfs TikTok analysées image par image) --------------
# Chaque style = template de sous-titres + thème de popups + famille motion
# design cohérents. Comme les vidéos de référence, ils génèrent des B-rolls IA
# quand une clé/crédits existent, et retombent proprement en économique sinon.
for _style_mode, _style_tpl, _style_motion in (
    ("pill_editorial", "pill_editorial", "editorial_paper"),
    ("neon_hype", "neon_hype", "neon_social"),
    ("handwritten_note", "handwritten_note", "sketch_notes"),
):
    V2_MODE_PRESETS[_style_mode] = {
        **V2_MODE_PRESETS["credit_saver_creator_edit"],
        "ai_broll": True,
        "visual_mode": "auto_fallback",
        "subtitle_template": _style_tpl,
        "motion_preset": _style_motion,
    }

# --- Style signature (défaut produit) + nouveaux styles viraux ---------------
# Tous générent des images IA (3D) quand une clé/crédits existent et retombent
# proprement en économique sinon. `motion_preset` absent = la famille de
# couleurs/compositions tourne d'une vidéo à l'autre (seed stable) — c'est ce
# qui garantit que deux montages ne partagent jamais le même look.
for _style_mode, _style_tpl in (
    ("signature_3d", "tiktok_yellow"),
    ("beast_impact", "beast_impact"),
    ("mint_wave", "mint_wave"),
    ("bangers_comic", "bangers_fun"),
):
    V2_MODE_PRESETS[_style_mode] = {
        **V2_MODE_PRESETS["credit_saver_creator_edit"],
        "ai_broll": True,
        "visual_mode": "auto_fallback",
        "subtitle_template": _style_tpl,
    }


ProgressFn = Callable[[int, str], None]


def resolve_visual_mode(options: dict, default: str) -> str:
    """Resolve the visual strategy: explicit option > mode preset > env default.

    Pure + testable. Crucially, an OLD job whose stored options carry no
    `visual_mode` is NOT forced to the new credit-saver mode — it falls back to
    the configured *default* (so historical jobs keep their behaviour).
    """
    from app.config import VALID_VISUAL_MODES
    chosen = (options or {}).get("visual_mode") or default
    return chosen if chosen in VALID_VISUAL_MODES else default


def _choose_transcription_provider(provider: Optional[str], has_elevenlabs_key: bool) -> str:
    """Decide which STT backend to use.

    - "whisper"     -> always local Whisper
    - "elevenlabs"  -> Scribe IF a key exists, else Whisper (can't do otherwise)
    - "auto"/other  -> Scribe when a key exists, else Whisper
    The caller still falls back to Whisper if a live Scribe call fails.
    """
    p = (provider or "auto").lower()
    if p == "whisper":
        return "whisper"
    if p == "elevenlabs":
        return "elevenlabs" if has_elevenlabs_key else "whisper"
    return "elevenlabs" if has_elevenlabs_key else "whisper"


# Mode -> ASS subtitle template of the Auto Edit engine.
MODE_TO_TEMPLATE: dict[str, str] = {
    "tiktok": "tiktok_yellow",
    "tiktok_viral": "tiktok_yellow",
    "business_premium_african": "gold_lux",
    "publicite_locale": "bold_box",
    "youtube": "bold_box",
    "formation_educative": "bold_box",
    "podcast": "tiktok_yellow",
    "podcast_propre": "tiktok_yellow",
    "credit_saver_creator_edit": "tiktok_yellow",
    "creator_economy_mode": "tiktok_yellow",
    "pill_editorial": "pill_editorial",
    "neon_hype": "neon_hype",
    "handwritten_note": "handwritten_note",
    "signature_3d": "tiktok_yellow",
    "beast_impact": "beast_impact",
    "mint_wave": "mint_wave",
    "bangers_comic": "bangers_fun",
}


def _transcript_to_vu(transcript, output_dir: str, video_path: str) -> str:
    """Bridge the Whisper Transcript -> the engine's word-level `_vu.json`.

    Reuses the existing (free, local) Whisper transcription so the engine does
    not need a paid ElevenLabs call. Segments without word timestamps get words
    synthesised by splitting the segment text evenly across its time span.
    """
    from app.autoedit_engine import ffmpeg_utils as engine_ffmpeg

    segments: list[dict] = []
    for s in transcript.segments:
        words = [
            {"word": w.text.strip(), "start": float(w.start), "end": float(w.end)}
            for w in s.words
            if (w.text or "").strip()
        ]
        if not words and (s.text or "").strip():
            toks = s.text.split()
            span = max(0.01, float(s.end) - float(s.start))
            step = span / len(toks)
            words = [
                {
                    "word": tok,
                    "start": round(float(s.start) + i * step, 3),
                    "end": round(float(s.start) + (i + 1) * step, 3),
                }
                for i, tok in enumerate(toks)
            ]
        if words:
            segments.append({
                "text": s.text,
                "start": float(s.start),
                "end": float(s.end),
                "words": words,
            })

    duration = segments[-1]["end"] if segments else 0.0
    probed = engine_ffmpeg.probe_duration(video_path)
    if probed:
        duration = max(duration, probed)

    vu = {
        "language": transcript.language or "auto",
        "duration": round(duration, 3),
        "segments": segments,
    }
    vu_path = os.path.join(output_dir, "engine_vu.json")
    with open(vu_path, "w", encoding="utf-8") as fh:
        json.dump(vu, fh, ensure_ascii=False, indent=2)
    return vu_path


def run_pipeline_v2(
    video_path: str,
    output_dir: str,
    mode: Optional[str] = None,
    params: Optional[dict] = None,
    progress_callback: Optional[ProgressFn] = None,
) -> dict:
    """Pipeline V2 = the Auto Edit viral montage engine.

    Reuses the local Whisper transcription, then drives the engine
    (cut+grade -> dynamic zoom -> overlays -> SFX -> animated ASS subs) to
    produce a vertical 1080x1920 reel. Return contract is V1-compatible:
    `result.output_path` is what the Celery worker stores.

    The previous modular V2 is kept as `run_pipeline_v2_legacy` for rollback.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Input video not found: {video_path}")
    if os.path.getsize(video_path) == 0:
        raise ValueError("Input video file is empty")
    os.makedirs(output_dir, exist_ok=True)

    # ---- préflight disque ----------------------------------------------------
    # Un rendu écrit plusieurs Go d'intermédiaires; sans espace, ffmpeg meurt en
    # plein encodage avec un cryptique "[Errno 32] Broken pipe". On échoue TÔT
    # avec un message actionnable à la place.
    free_gb = shutil.disk_usage(output_dir).free / 1e9
    src_gb = os.path.getsize(video_path) / 1e9
    needed_gb = max(3.0, src_gb * 4)
    if free_gb < needed_gb:
        raise RuntimeError(
            f"Espace disque insuffisant sur le serveur ({free_gb:.1f} Go libres, "
            f"~{needed_gb:.0f} Go requis pour ce rendu). Réessaie dans quelques "
            "minutes ou contacte le support."
        )

    # ---- options & flags ---------------------------------------------------
    preset = V2_MODE_PRESETS.get(mode or "", {}) if mode else {}
    options = dict(preset)
    raw_opts = (params or {}).get("options") if params else None
    if isinstance(raw_opts, dict):
        for k, v in raw_opts.items():
            if v is not None:
                options[k] = v

    # The engine reads OPENROUTER_API_KEY from os.environ. Settings may have
    # loaded it from a .env file (which does NOT export to the process env),
    # so propagate it explicitly — otherwise B-roll/illustrations silently skip.
    settings_key = getattr(settings, "OPENROUTER_API_KEY", "") or ""
    if settings_key and not os.environ.get("OPENROUTER_API_KEY"):
        os.environ["OPENROUTER_API_KEY"] = settings_key

    # Visual strategy: explicit option > mode preset > env default.
    # credit_saver  -> never any paid image (MVP, non bloquant)
    # ai_broll      -> ancien comportement (images IA quand possible)
    # auto_fallback -> tente l'IA, retombe en credit_saver si échec/crédits
    visual_mode = resolve_visual_mode(options, settings.AUTOEDIT_DEFAULT_VISUAL_MODE)
    disable_paid_images = bool(getattr(settings, "AUTOEDIT_DISABLE_PAID_IMAGE_GENERATION", False))

    # `do_broll` = the user toggle only; the engine applies the visual_mode /
    # key / disable gating (single source of truth) and NEVER fails on B-roll.
    do_broll = (
        bool(settings.ENABLE_AI_BROLL)
        and options.get("ai_broll", True) is not False
    )
    motion_preset = options.get("motion_preset") or None
    # Motion design works WITHOUT an API key (procedural drawings), so it only
    # follows the product flag and the user toggle.
    do_motion = (
        bool(getattr(settings, "ENABLE_MOTION_DESIGN", True))
        and options.get("motion_design", True) is not False
    )

    template = MODE_TO_TEMPLATE.get(mode or "", "tiktok_yellow")
    from app.autoedit_engine import config as engine_config
    # Priorité: option explicite du job > preset du mode > mapping par mode.
    # `options` fusionne déjà preset + options utilisateur (les options gagnent).
    requested_tpl = options.get("subtitle_template")
    if requested_tpl in engine_config.ASS_TEMPLATES:
        template = requested_tpl

    def progress(p: int, msg: str) -> None:
        if progress_callback:
            progress_callback(p, msg)
        logger.info(f"[pipeline_v2/engine {p}%] {msg}")

    results: dict = {
        "pipeline_version": "v2",
        "engine": "autoedit_v4",
        "mode": mode,
        "options": options,
        "aspect_ratio": "9:16",
        "subtitle_template": template,
        "visual_mode": visual_mode,
        "steps_completed": [],
        "steps_failed": [],
        "broll": {"enabled": do_broll},
        "motion_design": {"enabled": do_motion},
    }

    # ---- 1. Transcription (ElevenLabs Scribe si dispo, sinon Whisper) ------
    progress(5, "Transcription…")
    # La clé ElevenLabs vit peut-être seulement dans settings/.env: le moteur
    # lit os.environ, donc on la propage (comme OPENROUTER_API_KEY).
    el_key = getattr(settings, "ELEVENLABS_API_KEY", "") or ""
    if el_key and not os.environ.get("ELEVENLABS_API_KEY"):
        os.environ["ELEVENLABS_API_KEY"] = el_key

    provider = getattr(settings, "TRANSCRIPTION_PROVIDER", "auto")
    use_elevenlabs = _choose_transcription_provider(
        provider, bool(os.environ.get("ELEVENLABS_API_KEY"))
    ) == "elevenlabs"
    lang = (getattr(settings, "TRANSCRIPTION_LANGUAGE", "") or "").strip() or None

    vu_path = None
    if use_elevenlabs:
        # Scribe: plus rapide (déchargé du VPS), plus précis, timestamps natifs.
        try:
            from app.autoedit_engine import transcribe as el_transcribe
            vu_path = el_transcribe.transcribe(
                video_path,
                out_path=os.path.join(output_dir, "engine_vu.json"),
                language=lang,
            )
            vu = json.load(open(vu_path, encoding="utf-8"))
            n_words = sum(len(s.get("words", [])) for s in vu.get("segments", []))
            results["transcription"] = {
                "provider": "elevenlabs",
                "language": vu.get("language"),
                "text": " ".join(s.get("text", "") for s in vu.get("segments", [])).strip(),
                "segments_count": len(vu.get("segments", [])),
                "words_count": n_words,
            }
            if n_words < 3:
                raise RuntimeError("Scribe: transcription quasi vide")
            results["steps_completed"].append("transcription")
        except Exception as e:
            logger.warning("[pipeline_v2] ElevenLabs Scribe failed (%s) — fallback Whisper", e)
            results.setdefault("transcription_warnings", []).append(f"elevenlabs: {str(e)[:200]}")
            vu_path = None

    if vu_path is None:
        # Repli local Whisper (gratuit, hors-ligne).
        from app.processing.transcription_service import TranscriptionService
        ts = TranscriptionService(model_name=settings.WHISPER_MODEL, word_timestamps=True)
        transcript = ts.transcribe(video_path, output_dir)
        vu_path = _transcript_to_vu(transcript, output_dir, video_path)
        results["transcription"] = {
            "provider": "whisper",
            "language": transcript.language,
            "text": transcript.text,
            "segments_count": len(transcript.segments),
            "words_count": len(transcript.words),
        }
        if "transcription" not in results["steps_completed"]:
            results["steps_completed"].append("transcription")
        if len(transcript.words) < 3:
            raise RuntimeError("Transcription quasi vide — pas de parole exploitable pour le montage.")

    # ---- 2. Auto Edit engine render ---------------------------------------
    progress(10, "Montage Auto Edit…")
    from app.autoedit_engine import ffmpeg_utils as engine_ffmpeg
    from app.autoedit_engine import pipeline as engine_pipeline

    engine_ffmpeg.ensure_ffmpeg()  # clear error if ffmpeg is missing in the image
    montage_report: dict = {}
    final_path = engine_pipeline.run(
        video_path,
        output_dir,
        vu=vu_path,
        template=template,
        do_broll=do_broll,
        do_motion=do_motion,
        broll_demographic=options.get("broll_demographic") or "african",
        visual_mode=visual_mode,
        motion_preset=motion_preset,
        disable_paid_images=disable_paid_images,
        cleanup_level=options.get("cleanup_level"),
        smart_crop_mode=options.get("smart_crop_mode"),
        scrub_source_subtitles=options.get("remove_source_subtitles", True) is not False,
        progress_callback=progress,
        report=montage_report,
    )

    if not os.path.exists(final_path) or os.path.getsize(final_path) == 0:
        raise RuntimeError("Le moteur Auto Edit n'a pas produit de vidéo de sortie.")

    # Documented job contract: what the render actually did with the visuals.
    # The render is NEVER blocked by missing AI images — these fields explain
    # WHY images were skipped (if they were) without surfacing a hard error.
    results["visualModeUsed"] = montage_report.get("visual_mode_used", "credit_saver")
    results["aiImagesSkipped"] = bool(montage_report.get("ai_images_skipped", True))
    results["fallbackReason"] = montage_report.get("fallback_reason")
    results["effectsApplied"] = montage_report.get("effects_applied", {})

    # Preuve de contenu: le résultat du job dit exactement ce que le montage
    # contient (scènes motion design, B-rolls, popups, SFX) — fini les doutes
    # "est-ce l'ancien rendu ?".
    results["montage"] = montage_report
    if do_motion:
        if montage_report.get("motion_scenes_rendered", 0) > 0:
            results["steps_completed"].append("motion_design")
        else:
            results["steps_failed"].append("motion_design")
            logger.warning(
                "[pipeline_v2] motion design demandé mais 0 scène rendue "
                "(dérivées=%s) — vérifier les logs moteur",
                montage_report.get("motion_scenes_derived"),
            )

    results["output_path"] = final_path
    results["output_size_bytes"] = os.path.getsize(final_path)
    results["steps_completed"].append("engine_render")
    progress(100, "Terminé")
    return results


def run_pipeline_v2_legacy(
    video_path: str,
    output_dir: str,
    mode: Optional[str] = None,
    params: Optional[dict] = None,
    progress_callback: Optional[ProgressFn] = None,
) -> dict:
    """[LEGACY] Ancien pipeline V2 modulaire — conservé pour rollback.

    Le pipeline V2 actif est désormais le moteur Auto Edit (voir
    `run_pipeline_v2` plus haut). On garde cette implémentation intacte afin de
    pouvoir y revenir en une ligne si besoin.

    Le contrat de retour est compatible avec celui du pipeline V1: le worker
    Celery écrit `result.output_path` relatif à `UPLOAD_DIR`.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Input video not found: {video_path}")
    if os.path.getsize(video_path) == 0:
        raise ValueError("Input video file is empty")

    os.makedirs(output_dir, exist_ok=True)

    # ---- options/flags -----------------------------------------------------
    preset = V2_MODE_PRESETS.get(mode or "", {}) if mode else {}
    options = dict(preset)  # copie
    raw_opts = (params or {}).get("options") if params else None
    if isinstance(raw_opts, dict):
        for k, v in raw_opts.items():
            if v is not None:
                options[k] = v

    # For premium viral/business renders, shutter SFX and flash cues are part
    # of the visible value proposition. Some older API calls persisted
    # `sfx=false`, which made the video look acceptable but silent/basic. Keep a
    # separate premium flag so the final renderer still gets capture/photo cues
    # unless the user explicitly passes `disable_premium_sfx=true`.
    premium_motion_mode = (mode or "") in {"business_premium_african", "tiktok_viral", "publicite_locale"}
    if premium_motion_mode and not options.get("disable_premium_sfx"):
        options["sfx"] = True
        options["shutter_effects"] = True
        options["speaker_first_broll"] = True

    # Env feature flags = veto global
    if not settings.ENABLE_AI_BROLL:
        options["ai_broll"] = False
    if not settings.ENABLE_DYNAMIC_CAPTIONS:
        options["dynamic_captions"] = False
    if not settings.ENABLE_MUSIC:
        options["music"] = False
    if not settings.ENABLE_SFX:
        options["sfx"] = False

    aspect_ratio = "9:16" if options.get("vertical_9_16", True) else "16:9"
    broll_style = options.get("broll_style") or settings.BROLL_STYLE

    def progress(p: int, msg: str) -> None:
        if progress_callback:
            progress_callback(p, msg)
        logger.info(f"[pipeline_v2 {p}%] {msg}")

    results: dict = {
        "pipeline_version": "v2",
        "mode": mode,
        "options": options,
        "aspect_ratio": aspect_ratio,
        "steps_completed": [],
        "steps_failed": [],
        "broll": {"cues": [], "successes": 0, "failures": 0},
    }

    # 1. Transcription
    transcript = None
    try:
        progress(5, "Transcription…")
        from app.processing.transcription_service import TranscriptionService
        ts = TranscriptionService(model_name=settings.WHISPER_MODEL, word_timestamps=True)
        transcript = ts.transcribe(video_path, output_dir)
        results["transcription"] = {
            "language": transcript.language,
            "text": transcript.text,
            "segments_count": len(transcript.segments),
            "words_count": len(transcript.words),
            "srt_path": os.path.join(output_dir, "subtitles.srt"),
            "premium_ass_path": None,
            "transcript_path": os.path.join(output_dir, "transcript.json"),
        }
        # Captions premium mot-par-mot: écriture dès la transcription pour que
        # le rendu final ne tombe pas sur le SRT basique à fond noir.
        try:
            from app.processing.premium_caption_service import PremiumCaptionService
            premium_ass = PremiumCaptionService().write_ass(
                transcript,
                os.path.join(output_dir, "premium_captions.ass"),
            )
            results["transcription"]["premium_ass_path"] = premium_ass
        except Exception as cap_err:
            logger.warning("[pipeline_v2] premium captions failed: %s", cap_err)
        results["steps_completed"].append("transcription")
        progress(20, "Transcription terminée")
    except Exception as e:
        logger.error("[pipeline_v2] transcription failed: %s", e, exc_info=True)
        results["transcription_error"] = str(e)[:500]
        results["steps_failed"].append("transcription")

    # 2. Silence detection
    silences: list = []
    try:
        if options.get("remove_silence", True):
            progress(28, "Détection des silences…")
            from app.processing.silence_detector import SilenceDetector
            sd = SilenceDetector()
            silences = sd.detect(video_path)
            results["silences"] = [s.to_dict() for s in silences]
            results["steps_completed"].append("silence_detection")
        progress(35, "Silences analysés")
    except Exception as e:
        logger.error("[pipeline_v2] silence detection failed: %s", e, exc_info=True)
        results["silence_detection_error"] = str(e)[:500]
        results["steps_failed"].append("silence_detection")

    # 3. EDL
    total_duration = _get_duration_safe(video_path)
    edl = None
    try:
        progress(42, "Génération de l'EDL…")
        from app.processing.edit_decision_service import EditDecisionService
        from app.processing.types import Transcript
        eds = EditDecisionService()
        edl = eds.build_edl(
            source_path=video_path,
            transcript=transcript or Transcript(language="unknown", text="", segments=[]),
            silences=silences,
            total_duration=total_duration,
        )
        edl_path = os.path.join(output_dir, "edl.json")
        with open(edl_path, "w", encoding="utf-8") as f:
            json.dump(edl.to_dict(), f, ensure_ascii=False, indent=2)
        results["edl_path"] = edl_path
        results["edl_total_kept_duration"] = edl.total_kept_duration
        results["steps_completed"].append("edl")
        progress(50, "EDL générée")
    except Exception as e:
        logger.error("[pipeline_v2] EDL failed: %s", e, exc_info=True)
        results["edl_error"] = str(e)[:500]
        results["steps_failed"].append("edl")

    # 4-6. B-roll planning + images + animation
    cues = []
    if options.get("ai_broll", True) and transcript is not None and edl is not None:
        try:
            progress(55, "Planification du B-roll africain…")
            from app.processing.broll_planner import BrollPlanner, BrollPlannerConfig
            max_cues = (
                settings.BROLL_SHORTS_MAX_CUES_PER_VIDEO
                if total_duration <= settings.BROLL_SHORTS_MAX_DURATION_SECONDS
                else settings.BROLL_MAX_CUES_PER_VIDEO
            )
            planner = BrollPlanner(
                BrollPlannerConfig(
                    style=broll_style,
                    aspect_ratio=aspect_ratio,
                    min_segment_duration=settings.BROLL_MIN_SEGMENT_DURATION,
                    max_segment_duration=settings.BROLL_MAX_SEGMENT_DURATION,
                    max_cues=max_cues,
                )
            )
            cues = planner.plan(transcript, edl)
            results["broll"]["planned"] = len(cues)

            if cues:
                progress(60, f"Génération d'images IA ({len(cues)} cues)…")
                from app.processing.image_generation_service import ImageGenerationService
                igs = ImageGenerationService()
                cues = igs.generate_for_cues(cues, broll_dir=os.path.join(output_dir, "broll"))

                progress(72, "Animation des B-roll…")
                from app.processing.broll_animation_service import (
                    AnimationConfig, BrollAnimationService,
                )
                anim = BrollAnimationService(AnimationConfig(aspect_ratio=aspect_ratio))
                cues = anim.animate_cues(cues, out_dir=os.path.join(output_dir, "broll"))

                results["broll"]["successes"] = sum(1 for c in cues if c.clip_path)
                results["broll"]["failures"] = sum(1 for c in cues if c.failure_reason)
                results["broll"]["cues"] = [c.to_dict() for c in cues]
                results["steps_completed"].append("broll")
        except Exception as e:
            logger.error("[pipeline_v2] broll pipeline failed: %s", e, exc_info=True)
            results["broll_error"] = str(e)[:500]
            results["steps_failed"].append("broll")

    # 7. Overlays premium — intro/CTA + labels de section + titres de B-roll
    # + vraies cartes motion-design explicatives indépendantes des B-rolls.
    overlays = _build_overlays(options=options, params=params or {}, total_duration=total_duration)
    overlays.extend(_build_explainer_motion_overlays(total_duration=total_duration))
    overlays.extend(_build_broll_motion_overlays(cues))
    rendered_overlays = []
    if overlays:
        try:
            progress(80, "Rendu des overlays…")
            from app.processing.template_renderer import TemplateRenderer
            tr = TemplateRenderer()
            rendered_overlays = tr.render_overlays(
                overlays,
                out_dir=os.path.join(output_dir, "overlays"),
                aspect_ratio=aspect_ratio,
            )
            results["overlays"] = [o.to_dict() for o in rendered_overlays]
            results["steps_completed"].append("overlays")
        except Exception as e:
            logger.warning("[pipeline_v2] overlays failed: %s", e)
            results["overlays_error"] = str(e)[:500]
            results["steps_failed"].append("overlays")

    # 8. Rendu final
    final_output = os.path.join(output_dir, "final_output.mp4")
    try:
        if edl is None:
            raise RuntimeError("no EDL — cannot render")
        progress(88, "Rendu final FFmpeg…")
        from app.processing.ffmpeg_renderer import FFmpegRenderer, RenderOptions
        renderer = FFmpegRenderer()
        caption_path = None
        if options.get("dynamic_captions", True):
            caption_path = (results.get("transcription") or {}).get("premium_ass_path")
            if not caption_path:
                caption_path = os.path.join(output_dir, "subtitles.srt")

        sfx_timestamps = []
        if options.get("sfx", False) or options.get("shutter_effects", False):
            sfx_timestamps.extend([float(c.segment_start) for c in cues if c.clip_path])
            sfx_timestamps.extend([float(o.start) for o in rendered_overlays])

        renderer.render(
            edl=edl,
            out_dir=output_dir,
            broll_cues=[c for c in cues if c.clip_path],
            overlays=rendered_overlays,
            options=RenderOptions(
                aspect_ratio=aspect_ratio,
                burn_captions_srt=caption_path,
                sfx_timestamps=sfx_timestamps,
                flash_timestamps=[float(c.segment_start) for c in cues if c.clip_path],
            ),
        )
        results["steps_completed"].append("export")
        progress(98, "Export terminé")
    except Exception as e:
        logger.error("[pipeline_v2] final render failed: %s", e, exc_info=True)
        results["render_error"] = str(e)[:500]
        results["steps_failed"].append("export")
        # Fallback: copie de la source pour ne pas livrer un job vide
        try:
            shutil.copy2(video_path, final_output)
            results["fallback"] = "passthrough_copy"
        except Exception as copy_err:
            raise RuntimeError(
                f"Pipeline v2 failed and fallback copy failed: {copy_err}"
            ) from e

    if not os.path.exists(final_output) or os.path.getsize(final_output) == 0:
        raise RuntimeError("Pipeline v2 produced empty or missing output")

    results["output_path"] = final_output
    results["output_size_bytes"] = os.path.getsize(final_output)
    progress(100, "Pipeline V2 terminé")

    # Cleanup intermédiaires (best-effort)
    try:
        from app.services.storage import cleanup_directory
        cleanup_directory(output_dir)
    except Exception as e:
        logger.warning("[pipeline_v2] cleanup failed: %s", e)

    return results


# ---------------------------------------------------------------------------
def _get_duration_safe(video_path: str) -> float:
    try:
        from app.services.storage import get_video_duration
        d = get_video_duration(video_path)
        return float(d) if d is not None else 0.0
    except Exception:
        return 0.0


def _build_overlays(options: dict, params: dict, total_duration: float) -> list:
    """Construit la liste des overlays à partir des options produit."""
    from app.processing.types import OverlayClip

    overlays: list[OverlayClip] = []
    opts = options or {}
    p = params or {}

    # Intro card — si aucun titre n'est fourni, on met quand même une carte
    # légère pour rendre le montage visible dès le début (style Captions/Reels).
    intro_title = p.get("intro_title") or opts.get("logo_text")
    if not intro_title and opts.get("dynamic_captions", True):
        intro_title = "CutForge"
    if intro_title:
        overlays.append(
            OverlayClip(
                kind="intro_card",
                start=0.0,
                end=min(2.0, max(0.8, total_duration)),
                props={"title": intro_title},
            )
        )

    # Petits labels de section pour éviter un rendu trop plat quand Remotion
    # n'est pas encore branché. Ils sont brûlés par FFmpeg dans le pass final.
    if opts.get("dynamic_captions", True) and total_duration >= 25.0:
        labels = ["POINT CLÉ", "FORMATION", "ACTION"]
        for i, start in enumerate([18.0, 36.0, 54.0]):
            if start + 2.2 < total_duration - 3.0:
                overlays.append(
                    OverlayClip(
                        kind="lower_third",
                        start=start,
                        end=start + 2.2,
                        props={"title": labels[i % len(labels)]},
                    )
                )

    # CTA final
    if opts.get("final_cta") and total_duration > 4.0:
        cta_text = (
            (opts.get("cta_text") if isinstance(opts.get("cta_text"), str) else None)
            or p.get("cta_text")
            or "Abonne-toi 🔔"
        )
        overlays.append(
            OverlayClip(
                kind="cta",
                start=max(0.0, total_duration - 3.0),
                end=total_duration,
                props={"title": cta_text},
            )
        )
    return overlays


def _build_explainer_motion_overlays(total_duration: float) -> list:
    """[LEGACY — disabled] Explainer cards for the old modular pipeline.

    The previous implementation displayed HARDCODED, invented content
    ("ENRÔLER / Dépôts + PDV", "LOCALISER / Google Maps", …) at fixed
    timestamps on EVERY video — fabricated motion design unrelated to what the
    speaker actually says. Real illustrated motion design now lives in the
    active engine (`app.autoedit_engine.motion_design`), which derives its
    scenes from the transcript. This legacy hook intentionally returns nothing.
    """
    _ = total_duration
    return []


def _build_broll_motion_overlays(cues: list) -> list:
    """Ajoute des titres très visibles synchronisés aux B-rolls.

    La référence Captions.ai montre souvent un gros mot-clé en haut ou au
    centre au moment des changements visuels. Ces overlays rendent les B-rolls
    immédiatement perceptibles, même sans Remotion.
    """
    from app.processing.types import OverlayClip

    overlays: list[OverlayClip] = []
    seen = 0
    for cue in cues or []:
        if not getattr(cue, "clip_path", None):
            continue
        title = _keyword_from_broll_prompt(getattr(cue, "prompt", ""))
        start = float(getattr(cue, "segment_start", 0.0))
        overlays.append(
            OverlayClip(
                kind="broll_title",
                start=start + 0.10,
                end=min(float(getattr(cue, "segment_end", start + 2.0)), start + 1.65),
                props={"title": title},
            )
        )
        # Petit mot script/cyan en deuxième niveau comme dans la ref.
        script_word = _script_word_for_title(title)
        if script_word:
            overlays.append(
                OverlayClip(
                    kind="script",
                    start=start + 0.35,
                    end=min(float(getattr(cue, "segment_end", start + 2.0)), start + 2.15),
                    props={"title": script_word},
                )
            )
        seen += 1
        if seen >= 8:
            break
    return overlays


def _keyword_from_broll_prompt(prompt: str) -> str:
    p = (prompt or "").lower()
    rules = [
        (("coach", "class", "formation", "teacher", "trainer"), "FORMATION"),
        (("customer", "service", "client", "support"), "CLIENTS"),
        (("creator", "smartphone", "tiktok", "facebook", "whatsapp"), "CONTENU"),
        (("financial", "money", "budget", "banking"), "ARGENT"),
        (("team", "startup", "coworking", "professionals"), "ÉQUIPE"),
        (("entrepreneur", "business", "office", "laptop"), "DÉCISION"),
        (("door", "opportunity"), "OPPORTUNITÉ"),
    ]
    for keys, title in rules:
        if any(k in p for k in keys):
            return title
    return "ACTION"


def _script_word_for_title(title: str) -> str:
    return {
        "FORMATION": "apprendre",
        "CLIENTS": "grandir",
        "CONTENU": "créer",
        "ARGENT": "évoluer",
        "ÉQUIPE": "ensemble",
        "DÉCISION": "décision",
        "OPPORTUNITÉ": "possibilité",
        "ACTION": "maintenant",
    }.get(title, "")
