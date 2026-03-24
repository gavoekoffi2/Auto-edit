"""Celery tasks for async video processing."""
import logging
from datetime import datetime

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


@celery_app.task(bind=True, name="process_video")
def process_video_task(self, job_id: str):
    """Main video processing task."""
    from app.processing.pipeline import run_pipeline

    session = SyncSessionLocal()
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

        # Mark as processing
        _update_job(job_id, status="processing", progress=0)

        video_path = get_absolute_path(video.original_path)
        output_dir = get_output_dir(str(job.user_id), str(job.id))

        def progress_callback(progress: int, message: str):
            _update_job(job_id, progress=progress)
            self.update_state(state="PROGRESS", meta={"progress": progress, "message": message})

        # Run the pipeline
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
            relative_output = output_path.replace(settings.UPLOAD_DIR + "/", "")
            result["output_path"] = relative_output

        # Mark as completed
        _update_job(
            job_id,
            status="completed",
            progress=100,
            result=result,
            completed_at=datetime.utcnow(),
        )

        # Update video status
        video_obj = session.query(Video).filter(Video.id == job.video_id).first()
        if video_obj:
            video_obj.status = "ready"
            session.commit()

        logger.info(f"Job {job_id} completed successfully")
        return result

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        _update_job(
            job_id,
            status="failed",
            error_message=str(e),
            completed_at=datetime.utcnow(),
        )
        # Update video status
        try:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                video = session.query(Video).filter(Video.id == job.video_id).first()
                if video:
                    video.status = "error"
                    session.commit()
        except Exception:
            session.rollback()
        raise

    finally:
        session.close()
