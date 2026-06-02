from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.processing.ffmpeg_renderer import FFmpegRenderer, RenderOptions
from app.processing.template_renderer import TemplateRenderer
from app.processing.premium_caption_service import PremiumCaptionService
from app.processing.types import BrollCue, Cut, EditDecisionList, OverlayClip, Transcript, TranscriptSegment, Word


BACKEND_ROOT = Path(__file__).resolve().parents[1]
SOURCE = BACKEND_ROOT / "uploads" / "test_input" / "autoedit_speech_test.mp4"
BROLL = BACKEND_ROOT / "uploads" / "59d54ae1-29e2-4a74-a667-4d491fe0b040" / "output" / "c2e46b4c-cc99-4f3f-998e-90a6cc501784" / "broll" / "0001.mp4"
OUT = BACKEND_ROOT / "uploads" / "hyperframes_live_test"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    assert SOURCE.exists(), f"missing source {SOURCE}"
    overlays = [
        OverlayClip("intro_card", 0.0, 1.8, {"title": "AUTOEDIT PREMIUM", "subtitle": "HyperFrames activé", "step": "✓"}),
        OverlayClip("explain_card", 2.4, 5.2, {"title": "CAPTIONS PRO", "subtitle": "Sous-titres dynamiques", "step": "1"}),
        OverlayClip("flow_step", 6.0, 8.8, {"title": "B-ROLL MIX", "subtitle": "Bas + plein écran", "step": "2"}),
        OverlayClip("metric_pill", 9.0, 11.0, {"title": "SHUTTER SFX", "subtitle": "Flash + son", "step": "3"}),
        OverlayClip("cta", 14.5, 17.8, {"title": "Abonne-toi 🔔", "subtitle": "Montage niveau Captions.ai", "step": "→"}),
    ]
    tr = TemplateRenderer(backend="hyperframes")
    rendered_overlays = tr.render_overlays(overlays, str(OUT / "overlays"), aspect_ratio="9:16")

    broll = []
    if BROLL.exists():
        broll.append(BrollCue(5.0, 8.6, "African business premium office", clip_path=str(BROLL)))

    edl = EditDecisionList(
        source_path=str(SOURCE),
        cuts=[Cut(0.0, 18.0, True, "keep", "hyperframes live test")],
        total_kept_duration=18.0,
    )
    caption_ass = PremiumCaptionService().write_ass(
        Transcript(
            language="fr",
            text="AutoEdit transforme une vidéo simple en montage premium avec captions dynamiques b-roll et effets professionnels",
            segments=[
                TranscriptSegment(
                    start=0.35,
                    end=17.2,
                    text="AutoEdit transforme une vidéo simple en montage premium avec captions dynamiques b-roll et effets professionnels",
                    words=[
                        Word("AutoEdit", 0.35, 0.78), Word("transforme", 0.78, 1.22), Word("une", 1.22, 1.48),
                        Word("vidéo", 1.48, 1.90), Word("simple", 1.90, 2.30), Word("en", 2.30, 2.55),
                        Word("montage", 2.55, 3.05), Word("premium", 3.05, 3.55), Word("avec", 4.05, 4.34),
                        Word("captions", 4.34, 4.88), Word("dynamiques", 4.88, 5.55), Word("b-roll", 6.08, 6.62),
                        Word("speaker", 6.62, 7.02), Word("first", 7.02, 7.40), Word("flash", 9.10, 9.48),
                        Word("shutter", 9.48, 10.05), Word("et", 10.05, 10.28), Word("effets", 10.28, 10.80),
                        Word("professionnels", 14.65, 15.48), Word("niveau", 15.48, 15.88), Word("Captions", 15.88, 16.42),
                        Word("AI", 16.42, 16.82),
                    ],
                )
            ],
        ),
        str(OUT / "premium_captions.ass"),
    )
    final = FFmpegRenderer().render(
        edl,
        str(OUT),
        broll_cues=broll,
        overlays=rendered_overlays,
        options=RenderOptions(
            aspect_ratio="9:16",
            fps=30,
            crf=22,
            burn_captions_srt=caption_ass,
            sfx_timestamps=[0.0, 2.4, 5.0, 6.0, 9.0, 14.5],
            flash_timestamps=[0.0, 2.4, 5.0, 6.0, 9.0, 14.5],
        ),
    )
    print(json.dumps({
        "final": final,
        "bytes": os.path.getsize(final),
        "overlays": [o.to_dict() for o in rendered_overlays],
        "broll_used": bool(broll),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
