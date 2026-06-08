from app.config import settings
from app.workers.celery_app import celery_app
from app.autoedit_engine import ffmpeg_utils


def test_long_processing_timeouts_are_not_hardcoded_to_30_minutes():
    assert settings.CELERY_TASK_TIME_LIMIT_SECONDS == 0
    assert settings.CELERY_TASK_SOFT_TIME_LIMIT_SECONDS == 0
    assert celery_app.conf.task_time_limit is None
    assert celery_app.conf.task_soft_time_limit is None
    assert settings.FFMPEG_COMMAND_TIMEOUT_SECONDS >= 6 * 60 * 60
    media_timeout = ffmpeg_utils._default_timeout()
    assert media_timeout is not None
    assert media_timeout >= 6 * 60 * 60
