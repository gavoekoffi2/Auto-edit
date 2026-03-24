"""Scene detection module using PySceneDetect."""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def detect_scenes(
    video_path: str,
    output_dir: str,
    threshold: float = 27.0,
    min_scene_len: int = 15,
) -> dict:
    """
    Detect scene changes in video using PySceneDetect.

    Args:
        video_path: Path to input video
        output_dir: Directory for output
        threshold: Content detector threshold (lower = more sensitive)
        min_scene_len: Minimum scene length in frames

    Returns dict with:
        - scenes: list of {start, end, duration} dicts (seconds)
        - scene_count: number of scenes detected
        - scene_list_path: path to CSV with scene list
    """
    from scenedetect import open_video, SceneManager
    from scenedetect.detectors import ContentDetector

    logger.info(f"Detecting scenes in: {video_path}")

    video = open_video(video_path)
    scene_manager = SceneManager()
    scene_manager.add_detector(
        ContentDetector(threshold=threshold, min_scene_len=min_scene_len)
    )

    scene_manager.detect_scenes(video)
    scene_list = scene_manager.get_scene_list()

    scenes = []
    for start, end in scene_list:
        scenes.append({
            "start": start.get_seconds(),
            "end": end.get_seconds(),
            "duration": (end - start).get_seconds(),
        })

    # Save scene list to CSV
    scene_list_path = os.path.join(output_dir, "scenes.csv")
    with open(scene_list_path, "w") as f:
        f.write("scene,start_time,end_time,duration\n")
        for i, scene in enumerate(scenes, 1):
            f.write(f"{i},{scene['start']:.3f},{scene['end']:.3f},{scene['duration']:.3f}\n")

    logger.info(f"Detected {len(scenes)} scenes")

    return {
        "scenes": scenes,
        "scene_count": len(scenes),
        "scene_list_path": scene_list_path,
    }


def split_video_by_scenes(
    video_path: str,
    output_dir: str,
    scenes: list[dict],
) -> list[str]:
    """
    Split video into individual scene clips using MoviePy.
    Returns list of output file paths.
    """
    from moviepy.editor import VideoFileClip

    clip = VideoFileClip(video_path)
    try:
        output_paths = []
        for i, scene in enumerate(scenes):
            scene_clip = clip.subclip(scene["start"], scene["end"])
            try:
                output_path = os.path.join(output_dir, f"scene_{i+1:03d}.mp4")
                scene_clip.write_videofile(
                    output_path,
                    codec="libx264",
                    audio_codec="aac",
                    logger=None,
                )
                output_paths.append(output_path)
            finally:
                scene_clip.close()
    finally:
        clip.close()
    return output_paths
