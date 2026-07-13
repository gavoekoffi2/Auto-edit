"""Celery tasks for async video processing."""
import os
import logging
from datetime import datetime, timezone

from app.workers.celery_app import celery_app
from app.db.session import SyncSessionLocal
from app.models.job import Job
from app.models.video import Video
from app.services.storage import get_absolute_path, get_output_dir

logger = logging.getLogger(__name__)


def _update_job(job_id: str, **kwargs):
    """Update job status in database (sync for Celery)."""
    session = SyncSessionLocal()
    try:
        job = session.query(Job).filter(Job.id == job_id).first()
        if job:
            for key, value in kwargs.items():
                setattr(job, key, value)
            session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update job {job_id}: {e}")
    finally:
        session.close()


def _update_video_status(video_id: str, new_status: str):
    """Update video status in database (sync for Celery)."""
    session = SyncSessionLocal()
    try:
        video = session.query(Video).filter(Video.id == video_id).first()
        if video:
            video.status = new_status
            session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update video {video_id}: {e}")
    finally:
        session.close()


@celery_app.task(
    bind=True,
    name="process_video",
    autoretry_for=(ConnectionError, OSError),
    retry_kwargs={"max_retries": 2, "countdown": 30},
    retry_backoff=True,
)
def process_video_task(self, job_id: str):
    """Main video processing task with retry support.

    Dispatch v1 (pipeline.py) ou v2 (pipeline_v2.py) selon `job.pipeline_version`.
    """
    from app.processing.pipeline import run_pipeline

    session = SyncSessionLocal()
    output_dir = None
    try:
        job = session.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"Job not found: {job_id}")
            return

        video = session.query(Video).filter(Video.id == job.video_id).first()
        if not video:
            logger.error(f"Video not found for job: {job_id}")
            _update_job(job_id, status="failed", error_message="Video not found")
            return

        video_path = get_absolute_path(video.original_path)

        # Validate video file exists
        if not os.path.exists(video_path):
            logger.error(f"Video file missing: {video_path}")
            _update_job(
                job_id,
                status="failed",
                error_message="Video file not found on disk. Please re-upload.",
            )
            _update_video_status(str(video.id), "error")
            return

        # Mark as processing
        _update_job(job_id, status="processing", progress=0)
        _update_video_status(str(video.id), "processing")

        output_dir = get_output_dir(str(job.user_id), str(job.id))

        def progress_callback(progress: int, message: str):
            _update_job(job_id, progress=progress)
            self.update_state(state="PROGRESS", meta={"progress": progress, "message": message})

        # Choisit le pipeline selon job.pipeline_version (défaut v1)
        pipeline_version = getattr(job, "pipeline_version", "v1") or "v1"
        if pipeline_version == "v2":
            from app.processing.pipeline_v2 import run_pipeline_v2
            result = run_pipeline_v2(
                video_path=video_path,
                output_dir=output_dir,
                mode=job.mode,
                params=job.params,
                progress_callback=progress_callback,
            )
        else:
            result = run_pipeline(
                video_path=video_path,
                output_dir=output_dir,
                mode=job.mode,
                params=job.params,
                progress_callback=progress_callback,
            )

        # Convert absolute output path to relative for storage
        output_path = result.get("output_path", "")
        if output_path:
            from app.config import settings
            upload_dir = os.path.abspath(settings.UPLOAD_DIR)
            abs_output = os.path.abspath(output_path)
            if abs_output.startswith(upload_dir):
                result["output_path"] = abs_output[len(upload_dir) + 1:]

        # Mark as completed
        _update_job(
            job_id,
            status="completed",
            progress=100,
            result=result,
            completed_at=datetime.now(timezone.utc),
        )
        _update_video_status(str(video.id), "ready")

        logger.info(
            f"Job {job_id} completed: {len(result.get('steps_completed', []))} steps, "
            f"{len(result.get('steps_failed', []))} failures"
        )
        return result

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        error_msg = str(e)[:1900]  # Truncate to fit DB column
        # Un job échoué ne doit pas laisser ses Go d'intermédiaires sur le
        # disque (c'est ce qui finissait par tuer les rendus suivants).
        if output_dir:
            try:
                from app.autoedit_engine.pipeline import cleanup_intermediates
                cleanup_intermediates(output_dir)
            except Exception as cleanup_err:  # noqa: BLE001 - best effort
                logger.warning(f"Cleanup after failure skipped: {cleanup_err}")
        _update_job(
            job_id,
            status="failed",
            error_message=error_msg,
            completed_at=datetime.now(timezone.utc),
        )
        # Update linked video status — la session principale est peut-être cassée,
        # on ré-ouvre une session courte dédiée.
        try:
            lookup_session = SyncSessionLocal()
            try:
                failed_job = lookup_session.query(Job).filter(Job.id == job_id).first()
                if failed_job is not None and failed_job.video_id is not None:
                    _update_video_status(str(failed_job.video_id), "error")
            finally:
                lookup_session.close()
        except Exception as inner:
            logger.warning(f"Could not update video status for failed job {job_id}: {inner}")
        raise

    finally:
        session.close()


@celery_app.task(
    bind=True,
    name="process_clips",
    autoretry_for=(ConnectionError,),
    retry_kwargs={"max_retries": 1, "countdown": 60},
)
def process_clips_task(self, job_id: str):
    """Fonctionnalité « Clips » : vidéo longue (URL ou upload) -> shorts viraux.

    Contrairement à `process_video_task`, la source peut ne pas encore exister
    sur le disque: quand le job porte `params.source_url`, on télécharge
    d'abord la vidéo (yt-dlp), on met à jour la ligne Video, puis on lance le
    pipeline clips (transcription -> détection IA des moments viraux ->
    montage moteur de chaque clip).
    """
    from app.config import settings
    from app.processing.clips_pipeline import run_clips_pipeline
    from app.services import video_download
    from app.services.storage import get_video_duration

    session = SyncSessionLocal()
    output_dir = None
    try:
        job = session.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"Clips job not found: {job_id}")
            return
        video = session.query(Video).filter(Video.id == job.video_id).first()
        if not video:
            _update_job(job_id, status="failed", error_message="Video not found")
            return

        _update_job(job_id, status="processing", progress=0)
        _update_video_status(str(video.id), "processing")
        output_dir = get_output_dir(str(job.user_id), str(job.id))

        def progress_callback(progress: int, message: str):
            _update_job(job_id, progress=progress)
            self.update_state(state="PROGRESS",
                              meta={"progress": progress, "message": message})

        video_path = get_absolute_path(video.original_path)
        source_url = (job.params or {}).get("source_url")

        # --- Téléchargement de la source si elle vient d'une URL -------------
        if source_url and not os.path.exists(video_path):
            progress_callback(2, "Téléchargement de la vidéo source…")
            url = video_download.validate_source_url(source_url)

            def dl_progress(fraction: float):
                _update_job(job_id, progress=2 + int(fraction * 8))  # 2 -> 10 %

            final_path, info = video_download.download_source(
                url, video_path, progress=dl_progress)
            # yt-dlp peut produire un autre conteneur que .mp4.
            rel = os.path.relpath(final_path, os.path.abspath(settings.UPLOAD_DIR))
            duration = get_video_duration(final_path)
            v = session.query(Video).filter(Video.id == video.id).first()
            if v:
                v.original_path = rel
                v.size_bytes = os.path.getsize(final_path)
                v.duration_s = duration
                if info.get("title"):
                    v.title = info["title"]
                session.commit()
            video_path = final_path

        if not os.path.exists(video_path):
            _update_job(job_id, status="failed",
                        error_message="Source video not found on disk.")
            _update_video_status(str(video.id), "error")
            return

        result = run_clips_pipeline(
            video_path=video_path,
            output_dir=output_dir,
            mode=job.mode,
            params=job.params,
            progress_callback=progress_callback,
        )

        # Chemins relatifs pour le stockage (comme process_video_task).
        upload_dir = os.path.abspath(settings.UPLOAD_DIR)

        def _rel(p: str) -> str:
            ap = os.path.abspath(p)
            return ap[len(upload_dir) + 1:] if ap.startswith(upload_dir + os.sep) else p

        if result.get("output_path"):
            result["output_path"] = _rel(result["output_path"])
        for clip in result.get("clips", []):
            if clip.get("output_path"):
                clip["output_path"] = _rel(clip["output_path"])

        _update_job(
            job_id,
            status="completed",
            progress=100,
            result=result,
            completed_at=datetime.now(timezone.utc),
        )
        _update_video_status(str(video.id), "ready")
        logger.info(f"Clips job {job_id} completed: "
                    f"{result.get('clips_rendered', 0)} clips rendered")
        return result

    except Exception as e:
        logger.error(f"Clips job {job_id} failed: {e}", exc_info=True)
        if output_dir:
            try:
                from app.autoedit_engine.pipeline import cleanup_intermediates
                cleanup_intermediates(output_dir)
            except Exception as cleanup_err:  # noqa: BLE001 - best effort
                logger.warning(f"Cleanup after failure skipped: {cleanup_err}")
        _update_job(
            job_id,
            status="failed",
            error_message=str(e)[:1900],
            completed_at=datetime.now(timezone.utc),
        )
        try:
            lookup_session = SyncSessionLocal()
            try:
                failed_job = lookup_session.query(Job).filter(Job.id == job_id).first()
                if failed_job is not None and failed_job.video_id is not None:
                    _update_video_status(str(failed_job.video_id), "error")
            finally:
                lookup_session.close()
        except Exception as inner:
            logger.warning(f"Could not update video status for failed clips job "
                           f"{job_id}: {inner}")
        raise
    finally:
        session.close()
