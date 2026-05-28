"""
AutoEdit Processing Pipeline
Orchestrates the full video editing workflow:
  Upload -> Transcribe -> Remove Silence -> Detect Scenes -> Apply Effects -> Export
"""
import os
import shutil
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Mode presets define which steps run and with what parameters
MODE_PRESETS = {
    "tiktok": {
        "transcribe": True,
        "silence_removal": True,
        "scene_detection": True,
        "effects": {
            "crop_vertical": True,
            "fade_in": 0.3,
            "fade_out": 0.3,
            "speed": 1.05,
        },
        # Motion design: animated captions are the signature TikTok look, plus a
        # short branded intro/outro. Animated captions replace burned-in subs.
        "subtitles": False,
        "motion": {
            "animated_captions": True,
            "caption_position": "center",
            "font_scale": 1.15,
            "intro": {"title": "AutoEdit", "subtitle": ""},
            "outro": {"title": "Follow for more", "call_to_action": "Follow"},
            "intro_seconds": 2.0,
            "outro_seconds": 2.5,
        },
        "max_duration": 60,
    },
    "youtube": {
        "transcribe": True,
        "silence_removal": True,
        "scene_detection": True,
        "effects": {
            "fade_in": 0.5,
            "fade_out": 0.5,
        },
        "subtitles": False,
        "motion": {
            "animated_captions": True,
            "caption_position": "bottom",
            "font_scale": 1.0,
            "intro": {"title": "AutoEdit", "subtitle": ""},
            "outro": {"title": "Thanks for watching", "call_to_action": "Subscribe"},
        },
        "max_duration": None,
    },
    "podcast": {
        "transcribe": True,
        "silence_removal": True,
        "scene_detection": False,
        "effects": {},
        "subtitles": True,
        "motion": {},
        "max_duration": None,
    },
}


def run_pipeline(
    video_path: str,
    output_dir: str,
    mode: Optional[str] = None,
    params: Optional[dict] = None,
    progress_callback=None,
) -> dict:
    """
    Run the full AutoEdit pipeline on a video.

    Args:
        video_path: Path to input video
        output_dir: Directory for all outputs
        mode: Preset mode (tiktok, youtube, podcast) or None for custom
        params: Custom parameters (overrides mode preset)
        progress_callback: Callable(progress_int, status_msg) for progress updates

    Returns dict with all pipeline results.
    """
    from app.processing.transcribe import transcribe_video
    from app.processing.silence import remove_silence
    from app.processing.scenes import detect_scenes
    from app.processing.effects import apply_effects, add_subtitles
    from app.config import settings

    # Validate input video exists
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Input video not found: {video_path}")

    # Validate input video is not empty
    if os.path.getsize(video_path) == 0:
        raise ValueError("Input video file is empty")

    # Merge mode preset with custom params. The "motion" and "effects" dicts are
    # merged shallowly so the frontend can override a single knob (e.g. brand
    # color) without discarding the rest of the preset.
    config = {}
    if mode and mode in MODE_PRESETS:
        config = MODE_PRESETS[mode].copy()
    if params:
        for key, value in params.items():
            if (
                key in ("motion", "effects")
                and isinstance(value, dict)
                and isinstance(config.get(key), dict)
            ):
                merged = config[key].copy()
                merged.update(value)
                config[key] = merged
            else:
                config[key] = value

    # Default: enable all steps
    if not config:
        config = {
            "transcribe": True,
            "silence_removal": True,
            "scene_detection": True,
            "effects": {},
            "subtitles": True,
        }

    results = {
        "mode": mode,
        "steps_completed": [],
        "steps_failed": [],
    }
    current_video = video_path
    intermediate_files = []

    def update_progress(progress: int, message: str):
        if progress_callback:
            progress_callback(progress, message)
        logger.info(f"[{progress}%] {message}")

    # Step 1: Transcription (0-25%)
    if config.get("transcribe"):
        update_progress(5, "Starting transcription...")
        try:
            transcript = transcribe_video(
                current_video,
                output_dir,
                model_name=settings.WHISPER_MODEL,
            )
            results["transcription"] = transcript
            results["steps_completed"].append("transcribe")
            update_progress(25, "Transcription complete")
        except Exception as e:
            logger.error(f"Transcription failed: {e}", exc_info=True)
            results["transcription_error"] = str(e)
            results["steps_failed"].append("transcribe")

    # Step 2: Silence Removal (25-50%)
    if config.get("silence_removal"):
        update_progress(30, "Removing silence...")
        try:
            silence_result = remove_silence(
                current_video,
                output_dir,
                margin=config.get("silence_margin", "0.2s"),
                threshold=config.get("silence_threshold", "4%"),
            )
            new_video = silence_result["output_path"]
            if os.path.exists(new_video) and os.path.getsize(new_video) > 0:
                intermediate_files.append(current_video if current_video != video_path else None)
                current_video = new_video
                results["silence_removal"] = {
                    "output_path": new_video,
                }
                results["steps_completed"].append("silence_removal")
            else:
                logger.warning("Silence removal produced empty output, keeping original")
                results["steps_failed"].append("silence_removal")
            update_progress(50, "Silence removal complete")
        except Exception as e:
            logger.error(f"Silence removal failed: {e}", exc_info=True)
            results["silence_removal_error"] = str(e)
            results["steps_failed"].append("silence_removal")

    # Step 3: Scene Detection (50-65%)
    if config.get("scene_detection"):
        update_progress(55, "Detecting scenes...")
        try:
            scenes_result = detect_scenes(
                current_video,
                output_dir,
                threshold=config.get("scene_threshold", 27.0),
            )
            results["scenes"] = scenes_result
            results["steps_completed"].append("scene_detection")
            update_progress(65, f"Detected {scenes_result['scene_count']} scenes")
        except Exception as e:
            logger.error(f"Scene detection failed: {e}", exc_info=True)
            results["scene_detection_error"] = str(e)
            results["steps_failed"].append("scene_detection")

    # Step 4: Apply Effects (65-85%)
    effects_config = config.get("effects", {})
    if effects_config:
        update_progress(70, "Applying effects...")
        try:
            effects_result = apply_effects(
                current_video,
                output_dir,
                effects_config=effects_config,
            )
            new_video = effects_result["output_path"]
            if os.path.exists(new_video) and os.path.getsize(new_video) > 0:
                intermediate_files.append(current_video if current_video != video_path else None)
                current_video = new_video
                results["effects"] = effects_result
                results["steps_completed"].append("effects")
            else:
                results["steps_failed"].append("effects")
            update_progress(85, "Effects applied")
        except Exception as e:
            logger.error(f"Effects failed: {e}", exc_info=True)
            results["effects_error"] = str(e)
            results["steps_failed"].append("effects")

    # Step 5: Add Subtitles (85-90%)
    srt_path = results.get("transcription", {}).get("srt_path")
    if config.get("subtitles") and srt_path and os.path.exists(srt_path):
        update_progress(87, "Adding subtitles...")
        try:
            sub_result = add_subtitles(
                current_video,
                srt_path,
                output_dir,
                style=config.get("subtitle_style"),
            )
            new_video = sub_result["output_path"]
            if os.path.exists(new_video) and os.path.getsize(new_video) > 0:
                intermediate_files.append(current_video if current_video != video_path else None)
                current_video = new_video
                results["subtitles"] = sub_result
                results["steps_completed"].append("subtitles")
            else:
                results["steps_failed"].append("subtitles")
            update_progress(90, "Subtitles added")
        except Exception as e:
            logger.error(f"Subtitles failed: {e}", exc_info=True)
            results["subtitles_error"] = str(e)
            results["steps_failed"].append("subtitles")

    # Step 6: Motion Design via Remotion (90-99%)
    motion_config = config.get("motion") or {}
    if motion_config and any(
        motion_config.get(k) for k in ("intro", "outro", "animated_captions")
    ):
        update_progress(92, "Adding motion design...")
        try:
            from app.processing.motion import add_motion_graphics

            motion_result = add_motion_graphics(
                current_video,
                output_dir,
                motion_config=motion_config,
                transcription=results.get("transcription"),
            )
            new_video = motion_result.get("output_path")
            if (
                new_video
                and new_video != current_video
                and os.path.exists(new_video)
                and os.path.getsize(new_video) > 0
            ):
                intermediate_files.append(current_video if current_video != video_path else None)
                current_video = new_video
                results["motion"] = motion_result
                results["steps_completed"].append("motion_design")
            elif motion_result.get("skipped"):
                logger.warning("Motion design skipped: %s", motion_result["skipped"])
                results["motion"] = motion_result
            else:
                results["steps_failed"].append("motion_design")
            update_progress(99, "Motion design complete")
        except Exception as e:
            logger.error(f"Motion design failed: {e}", exc_info=True)
            results["motion_error"] = str(e)
            results["steps_failed"].append("motion_design")

    # Final: Copy result to standard output name
    final_output = os.path.join(output_dir, "final_output.mp4")
    if current_video != video_path and os.path.exists(current_video):
        if current_video != final_output:
            shutil.copy2(current_video, final_output)
    else:
        # No processing changed the video, copy original
        shutil.copy2(video_path, final_output)

    # Validate final output
    if not os.path.exists(final_output) or os.path.getsize(final_output) == 0:
        raise RuntimeError("Pipeline produced empty or missing output file")

    results["output_path"] = final_output
    results["output_size_bytes"] = os.path.getsize(final_output)
    results["steps_completed"].append("export")
    update_progress(100, "Pipeline complete!")

    # Cleanup intermediate files
    from app.services.storage import cleanup_directory
    cleanup_directory(output_dir)

    return results
