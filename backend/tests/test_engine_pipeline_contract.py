"""Contrats publics du moteur Auto Edit utilisés par les pipelines applicatifs."""
import inspect

from app.autoedit_engine import pipeline


def test_pipeline_run_accepts_source_subtitle_scrubbing_option():
    """Le pipeline V2/Clips doit pouvoir piloter le nettoyage des sous-titres source."""
    signature = inspect.signature(pipeline.run)
    assert "scrub_source_subtitles" in signature.parameters
