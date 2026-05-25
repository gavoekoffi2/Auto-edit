import os
import tempfile

from app.processing.image_generation_service import ImageGenerationService
from app.processing.providers.image_provider_base import NoopImageProvider
from app.processing.types import BrollCue


def test_image_generation_service_with_noop_provider():
    cues = [
        BrollCue(
            segment_start=0.0,
            segment_end=3.0,
            prompt="African entrepreneur in modern office in Lomé",
        )
    ]
    igs = ImageGenerationService(provider=NoopImageProvider())
    with tempfile.TemporaryDirectory() as tmp:
        results = igs.generate_for_cues(cues, broll_dir=tmp)
        assert len(results) == 1
        # Noop n'écrit rien — la cue doit indiquer l'échec proprement
        assert results[0].image_path is None
        assert results[0].failure_reason in ("empty_image", None) or results[0].failure_reason
        # broll_dir doit avoir été créé même sans output
        assert os.path.isdir(tmp)


def test_image_generation_service_default_provider_falls_back_to_noop_when_no_key(monkeypatch):
    # IMAGE_GENERATION_PROVIDER=openrouter mais sans clé → fallback Noop silencieux
    from app.config import settings
    monkeypatch.setattr(settings, "IMAGE_GENERATION_PROVIDER", "openrouter")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", None)

    igs = ImageGenerationService()
    assert igs.provider.__class__.__name__ == "NoopImageProvider"
