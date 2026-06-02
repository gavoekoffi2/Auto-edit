from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.processing.pipeline import run_pipeline

source = ROOT / "uploads" / "user_drive_test" / "source_video.mp4"
out = ROOT / "uploads" / "user_drive_test" / "autoedit_video_use_remotion_output"
out.mkdir(parents=True, exist_ok=True)

result = run_pipeline(
    video_path=str(source),
    output_dir=str(out),
    mode="tiktok",
    params={
        "video_use_analysis": True,
        "smart_cuts": True,
        "silence_removal": True,
        "scene_detection": False,
        "subtitles": False,
        "effects": {"crop_vertical": True, "speed": 1.02},
        "motion": {
            "animated_captions": True,
            "caption_position": "center",
            "font_scale": 1.1,
            "caption_style": "karaoke",
            "font_family": "Bangers",
            "intro": {"title": "AutoEdit Premium", "subtitle": "Smart cuts + video-use"},
            "outro": {"title": "Abonne-toi pour la suite", "call_to_action": "Contacte-nous"},
            "intro_seconds": 1.5,
            "outro_seconds": 2.5,
        },
    },
    progress_callback=lambda p, msg: print(f"[{p}%] {msg}", flush=True),
)
print(json.dumps(result, ensure_ascii=False, indent=2))
