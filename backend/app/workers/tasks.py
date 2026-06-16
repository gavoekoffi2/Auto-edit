"""Celery tasks for async video processing."""
import os
import logging
from datetime import datetime, timezone

from app.workers.celery_app import celery_app
from app.db.session import SyncSessionLocal
from app.models.job import Job
from app.models.video import Video
from app.services.storage import get_absolute_path, get_output_dir
from app.config import settings

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
        if output_dir and os.path.exists(output_dir):
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
    name="compress_ingest_video",
    autoretry_for=(ConnectionError,),
    retry_kwargs={"max_retries": 1, "countdown": 10},
)
def compress_ingest_video_task(self, video_id: str):
    """Fast ingest compression task (runs immediately after upload).

    Re-encodes the uploaded file with CRF 26 + veryfast preset to cut working
    file size by 40–70%.  All downstream pipeline steps then run on a smaller
    file, reducing total job time.  On success the original is replaced; on
    failure the original is kept and the status reverts to 'uploaded'.
    """
    from app.services.video_compression import compress_for_ingest, safe_replace_with_compressed

    session = SyncSessionLocal()
    temp_path = None
    try:
        video = session.query(Video).filter(Video.id == video_id).first()
        if not video:
            logger.error("compress_ingest: video not found: %s", video_id)
            return

        abs_path = get_absolute_path(video.original_path)
        if not os.path.exists(abs_path):
            logger.error("compress_ingest: file missing: %s", abs_path)
            video.status = "uploaded"
            session.commit()
            return

        temp_path = abs_path + ".ingest_tmp.mp4"

        beneficial = compress_for_ingest(abs_path, temp_path)

        if beneficial and os.path.exists(temp_path):
            final_abs, new_size = safe_replace_with_compressed(abs_path, temp_path)
            temp_path = None  # ownership transferred to safe_replace_with_compressed

            upload_root = os.path.abspath(settings.UPLOAD_DIR)
            rel_path = os.path.relpath(final_abs, upload_root)
            video.original_path = rel_path
            video.size_bytes = new_size
            logger.info(
                "compress_ingest done: video=%s size=%d MB",
                video_id,
                new_size // 1_000_000,
            )
        else:
            logger.info("compress_ingest skipped for video %s (not beneficial)", video_id)

        video.status = "uploaded"
        session.commit()

    except Exception as exc:
        session.rollback()
        logger.error("compress_ingest failed for video %s: %s", video_id, exc, exc_info=True)
        # Always fall back to "uploaded" so the user can still process their video.
        try:
            v = session.query(Video).filter(Video.id == video_id).first()
            if v:
                v.status = "uploaded"
                session.commit()
        except Exception:
            pass
        raise

    finally:
        # Remove temp file if we still own it (i.e. replace never happened).
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass
        session.close()
