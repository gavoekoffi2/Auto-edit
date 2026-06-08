from celery import Celery

from app.config import settings

celery_app = Celery(
    "autoedit",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

_hard_limit = settings.CELERY_TASK_TIME_LIMIT_SECONDS or None
_soft_limit = settings.CELERY_TASK_SOFT_TIME_LIMIT_SECONDS or None

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # No fixed render cutoff by default. Long mobile videos can legitimately
    # spend a long time in Whisper/FFmpeg/image steps; Docker/proxy/storage
    # limits remain the safety controls. Ops can re-enable limits via env.
    task_time_limit=_hard_limit,
    task_soft_time_limit=_soft_limit,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=10,
)
