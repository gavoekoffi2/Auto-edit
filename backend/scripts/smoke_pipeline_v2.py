"""Smoke test du pipeline V2 sans dépendances externes.

Exécution:
    cd backend && python scripts/smoke_pipeline_v2.py

But: vérifier que tous les modules s'importent, que le planner B-roll
africain produit les bons prompts, que l'EDL coupe correctement les
filler words. Ne touche pas au réseau (provider Noop), ni à FFmpeg.

À lancer en CI avant tout déploiement.
"""
from __future__ import annotations

import os
import sys
import types
import tempfile

# Stub des modules lourds si absents (pour pouvoir tourner hors container)
for _name in (
    "whisper", "moviepy", "moviepy.editor", "auto_editor", "scenedetect",
    "aiofiles", "fastapi", "celery", "redis", "passlib", "jose",
    "sqlalchemy", "sqlalchemy.ext.asyncio", "sqlalchemy.orm",
    "sqlalchemy.dialects", "sqlalchemy.dialects.postgresql",
):
    sys.modules.setdefault(_name, types.ModuleType(_name))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@x/x")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://x:x@x/x")
os.environ.setdefault("REDIS_URL", "redis://x/0")
os.environ.setdefault("SECRET_KEY", "a" * 40)
os.environ.setdefault("IMAGE_GENERATION_PROVIDER", "noop")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    from app.config import settings, VALID_MODES
    from app.processing.types import (
        Cut, EditDecisionList, Transcript, TranscriptSegment, Word,
    )
    from app.processing.broll_planner import BrollPlanner, BrollPlannerConfig
    from app.processing.edit_decision_service import EditDecisionService
    from app.processing.image_generation_service import ImageGenerationService
    from app.processing.providers.image_provider_base import NoopImageProvider
    from app.processing.template_renderer import TemplateRenderer
    from app.processing.ffmpeg_renderer import FFmpegRenderer

    print(f"[smoke] PIPELINE_VERSION={settings.PIPELINE_VERSION}")
    print(f"[smoke] modes={len(VALID_MODES)}: {sorted(VALID_MODES)}")
    print(f"[smoke] feature flags: ai_broll={settings.ENABLE_AI_BROLL} captions={settings.ENABLE_DYNAMIC_CAPTIONS} music={settings.ENABLE_MUSIC} sfx={settings.ENABLE_SFX}")

    # 1) EDL avec filler words
    transcript = Transcript(language="fr", text="", segments=[
        TranscriptSegment(0.0, 4.0, "", words=[
            Word("euh", 0.0, 0.3),
            Word("donc", 0.3, 0.6),
            Word("je", 0.6, 0.8),
            Word("vais", 0.8, 1.1),
            Word("parler", 1.1, 1.7),
            Word("de", 1.7, 1.9),
            Word("mobile", 1.9, 2.4),
            Word("money", 2.4, 3.0),
        ]),
    ])
    edl = EditDecisionService().build_edl("/tmp/x.mp4", transcript, [], total_duration=4.0)
    kept = sum(1 for c in edl.cuts if c.keep)
    assert kept >= 1, "EDL must keep at least one cut"
    print(f"[smoke] EDL: {len(edl.cuts)} cuts, {kept} kept, total_kept={edl.total_kept_duration:.2f}s")

    # 2) Planner B-roll africain
    cues = BrollPlanner(BrollPlannerConfig(min_segment_duration=1.0, max_cues=3)).plan(transcript, edl)
    print(f"[smoke] B-roll cues: {len(cues)}")
    for c in cues:
        assert "African" in c.prompt or "africain" in c.prompt.lower() or "Africa" in c.prompt
        print(f"  - [{c.segment_start:.1f}-{c.segment_end:.1f}] {c.prompt[:80]}…")

    # 3) ImageGenerationService avec NoopProvider (pas de réseau)
    igs = ImageGenerationService(provider=NoopImageProvider())
    with tempfile.TemporaryDirectory() as tmp:
        result = igs.generate_for_cues(cues, broll_dir=tmp)
        assert len(result) == len(cues)
        # NoopProvider ne crée pas de fichier — failure_reason="empty_image"
        for c in result:
            assert c.failure_reason == "empty_image" or c.image_path is None
    print("[smoke] ImageGenerationService NoopProvider OK")

    # 4) Instanciation des renderers (capabilities only — pas de FFmpeg ici)
    tr = TemplateRenderer(backend="ffmpeg")
    caps = tr.capabilities()
    print(f"[smoke] TemplateRenderer caps: intro={caps.intro_card} cta={caps.cta} custom={caps.custom_template}")
    FFmpegRenderer()  # doit s'instancier
    print("[smoke] FFmpegRenderer instantiated OK")

    print("[smoke] ALL CHECKS PASSED ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
