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
        "subtitles": True,
        "max_duration": 60,  # seconds
    },
    "youtube": {
        "transcribe": True,
        "silence_removal": True,
        "scene_detection": True,
        "effects": {
            "fade_in": 0.5,
            "fade_out": 0.5,
        },
        "subtitles": True,
        "max_duration": None,
    },
    "podcast": {
        "transcribe": True,
        "silence_removal": True,
        "scene_detection": False,
        "effects": {},
        "subtitles": True,
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

    # Merge mode preset with custom params
    config = {}
    if mode and mode in MODE_PRESETS:
        config = MODE_PRESETS[mode].copy()
    if params:
        config.update(params)

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
    }
    current_video = video_path

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
            logger.error(f"Transcription failed: {e}")
            results["transcription_error"] = str(e)

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
            current_video = silence_result["output_path"]
            results["silence_removal"] = silence_result
            results["steps_completed"].append("silence_removal")
            update_progress(50, "Silence removal complete")
        except Exception as e:
            logger.error(f"Silence removal failed: {e}")
            results["silence_removal_error"] = str(e)

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
            logger.error(f"Scene detection failed: {e}")
            results["scene_detection_error"] = str(e)

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
            current_video = effects_result["output_path"]
            results["effects"] = effects_result
            results["steps_completed"].append("effects")
            update_progress(85, "Effects applied")
        except Exception as e:
            logger.error(f"Effects failed: {e}")
            results["effects_error"] = str(e)

    # Step 5: Add Subtitles (85-95%)
    if config.get("subtitles") and results.get("transcription", {}).get("srt_path"):
        update_progress(88, "Adding subtitles...")
        try:
            srt_path = results["transcription"]["srt_path"]
            sub_result = add_subtitles(
                current_video,
                srt_path,
                output_dir,
                style=config.get("subtitle_style"),
            )
            current_video = sub_result["output_path"]
            results["subtitles"] = sub_result
            results["steps_completed"].append("subtitles")
            update_progress(95, "Subtitles added")
        except Exception as e:
            logger.error(f"Subtitles failed: {e}")
            results["subtitles_error"] = str(e)

    # Final: Copy result to standard output name
    final_output = os.path.join(output_dir, "final_output.mp4")
    if current_video != video_path and os.path.exists(current_video):
        if current_video != final_output:
            shutil.copy2(current_video, final_output)
    else:
        shutil.copy2(video_path, final_output)

    results["output_path"] = final_output
    results["steps_completed"].append("export")
    update_progress(100, "Pipeline complete!")

    return results
