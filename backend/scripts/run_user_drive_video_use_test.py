from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.processing.pipeline_v2 import run_pipeline_v2

source = ROOT / "uploads" / "user_drive_test" / "source_video.mp4"
out = ROOT / "uploads" / "user_drive_test" / "autoedit_video_use_output"
out.mkdir(parents=True, exist_ok=True)

result = run_pipeline_v2(
    video_path=str(source),
    output_dir=str(out),
    mode="business_premium_african",
    params={
        "options": {
            "remove_silence": True,
            "dynamic_captions": True,
            "ai_broll": False,
            "music": False,
            "sfx": True,
            "vertical_9_16": True,
            "final_cta": True,
            "video_use_analysis": True,
            "motion_design_overlays": False,
            "section_labels": False,
            "cta_text": "Abonne-toi pour la suite",
            "logo_text": "AutoEdit Premium",
        }
    },
    progress_callback=lambda p, msg: print(f"[{p}%] {msg}", flush=True),
)
print(json.dumps(result, ensure_ascii=False, indent=2))
