"""Tests des règles de plan centralisées et de la taxonomie d'erreurs."""
import pytest

from app.services.errors import ERRORS, http_error, tag
from app.services.plans import rules_for


def test_plan_rules_centralized_and_ordered():
    free, pro, biz = rules_for("free"), rules_for("pro"), rules_for("business")
    # Les limites croissent avec le plan.
    assert (free.clips_max_source_duration_s < pro.clips_max_source_duration_s
            < biz.clips_max_source_duration_s)
    assert free.clips_max_per_job < pro.clips_max_per_job <= biz.clips_max_per_job
    assert free.max_concurrent_jobs < pro.max_concurrent_jobs <= biz.max_concurrent_jobs
    # Free = quota mensuel; payants = illimité.
    assert free.max_videos_per_month is not None
    assert pro.max_videos_per_month is None


def test_unknown_plan_falls_back_to_free():
    assert rules_for(None).name == "free"
    assert rules_for("banana").name == "free"
    assert rules_for("PRO").name == "pro"     # insensible à la casse


def test_error_codes_have_stable_shape():
    for code, err in ERRORS.items():
        assert err.code == code
        assert 400 <= err.http_status < 600
        assert err.user_message                      # message FR non vide
        # Aucun détail interne dans les messages utilisateur.
        for banned in ("Traceback", "sqlalchemy", "asyncpg", "redis://", "postgres"):
            assert banned.lower() not in err.user_message.lower()


def test_http_error_carries_code_message_and_request_id():
    exc = http_error("QUOTA_MONTHLY_REACHED", request_id="req-123")
    assert exc.status_code == 429
    assert exc.detail["code"] == "QUOTA_MONTHLY_REACHED"
    assert exc.detail["request_id"] == "req-123"
    # Code inconnu -> 500 générique, jamais de crash.
    assert http_error("DOES_NOT_EXIST").status_code == 500


def test_worker_tag_prefixes_stable_code():
    msg = tag("SOURCE_TOO_LONG", "42 min")
    assert msg.startswith("[SOURCE_TOO_LONG]")
    assert "42 min" in msg


def test_validate_render_moments_guards():
    from app.processing.clips_pipeline import validate_render_moments

    ok = validate_render_moments(
        [{"start": 10, "end": 40, "title": "A"},
         {"start": 50, "end": 80, "title": "B", "score": 91}],
        source_duration=120.0, max_clips=3)
    assert [m["title"] for m in ok] == ["A", "B"]
    assert ok[1]["score"] == 91

    with pytest.raises(ValueError):   # vide
        validate_render_moments([], 120.0, 3)
    with pytest.raises(ValueError):   # trop de clips pour le plan
        validate_render_moments(
            [{"start": i * 20, "end": i * 20 + 10} for i in range(4)], 120.0, 3)
    with pytest.raises(ValueError):   # hors source
        validate_render_moments([{"start": 100, "end": 200}], 120.0, 3)
    with pytest.raises(ValueError):   # trop court
        validate_render_moments([{"start": 10, "end": 12}], 120.0, 3)
    with pytest.raises(ValueError):   # chevauchement
        validate_render_moments(
            [{"start": 10, "end": 40}, {"start": 30, "end": 60}], 120.0, 3)
    with pytest.raises(ValueError):   # payload non-dict
        validate_render_moments(["junk"], 120.0, 3)


def test_clips_render_request_schema():
    from app.schemas.job import ClipsRenderRequest

    req = ClipsRenderRequest(clips=[{"start": 0, "end": 30, "title": "x"}],
                             mode="neon_hype")
    assert req.clips[0].end == 30
    with pytest.raises(ValueError):
        ClipsRenderRequest(clips=[])
    with pytest.raises(ValueError):
        ClipsRenderRequest(clips=[{"start": 0, "end": 30}], mode="not_a_mode")


def test_url_with_credentials_rejected():
    from app.services.video_download import SourceURLError, validate_source_url
    with pytest.raises(SourceURLError):
        validate_source_url("https://user:pass@youtube.com/watch?v=1")
