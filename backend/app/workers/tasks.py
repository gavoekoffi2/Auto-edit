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
            progress_callback(1, "Vérification de la vidéo source…")
            url = video_download.validate_source_url(source_url)
            # Limites AVANT téléchargement: durée du plan + refus des directs.
            max_dur = (job.params or {}).get("max_source_duration_s")
            probe = video_download.probe_source(
                url, max_duration_s=float(max_dur) if max_dur else None)

            # Préflight disque: ne pas commencer un téléchargement qui va
            # remplir le volume (téléchargement + intermédiaires de rendu).
            import shutil as _shutil
            free_gb = _shutil.disk_usage(settings.UPLOAD_DIR).free / 1e9
            if free_gb < settings.UPLOAD_MIN_FREE_GB:
                from app.services.errors import tag as _err_tag
                raise RuntimeError(_err_tag("DISK_FULL", f"{free_gb:.1f} GB free"))

            progress_callback(2, "Téléchargement de la vidéo source…")

            def dl_progress(fraction: float):
                _update_job(job_id, progress=2 + int(fraction * 8))  # 2 -> 10 %

            final_path, info = video_download.download_source(
                url, video_path, progress=dl_progress)
            info.setdefault("title", probe.get("title"))
            # yt-dlp peut produire un autre conteneur que .mp4.
            rel = os.path.relpath(final_path, os.path.abspath(settings.UPLOAD_DIR))
            duration = get_video_duration(final_path)
            # Re-vérifie la durée APRÈS téléchargement (certains extracteurs
            # n'annoncent pas de durée au probe).
            if max_dur and duration and float(duration) > float(max_dur) + 5:
                try:
                    os.unlink(final_path)
                except OSError:
                    pass
                from app.services.errors import tag as _err_tag
                raise RuntimeError(_err_tag(
                    "SOURCE_TOO_LONG", f"{duration / 60:.0f} min"))
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
        if result.get("source_vu_path"):
            result["source_vu_path"] = _rel(result["source_vu_path"])
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
        # Erreurs de source URL: préfixe le code produit stable pour le
        # frontend/support ([SOURCE_TOO_LONG] Vidéo trop longue…).
        if isinstance(e, video_download.SourceURLError):
            e = RuntimeError(f"[{getattr(e, 'code', 'URL_UNSUPPORTED')}] {e}")
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


@celery_app.task(name="purge_expired_files")
def purge_expired_files_task():
    """Purge de rétention — idempotente, planifiée par Celery beat.

    Politique (configurable via settings, 0 = ne jamais purger):
      * rendus terminés   -> RETENTION_OUTPUT_DAYS
      * sources URL       -> RETENTION_SOURCE_DAYS
      * jobs échoués      -> RETENTION_FAILED_JOB_DAYS
    Seuls les FICHIERS sont supprimés; les lignes DB restent (historique,
    facturation). Un job purgé est marqué `result.files_purged = true` pour
    que l'API réponde FILE_EXPIRED proprement au lieu d'un 404 générique.
    """
    import shutil
    from datetime import timedelta
    from app.config import settings

    now = datetime.now(timezone.utc)
    upload_root = os.path.abspath(settings.UPLOAD_DIR)
    purged = {"outputs": 0, "sources": 0, "bytes": 0}

    def _dir_size(path: str) -> int:
        total = 0
        for root, _, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        return total

    session = SyncSessionLocal()
    try:
        # --- Répertoires de sortie des jobs (terminés et échoués) ------------
        rules = []
        if settings.RETENTION_OUTPUT_DAYS > 0:
            rules.append(("completed", now - timedelta(days=settings.RETENTION_OUTPUT_DAYS)))
        if settings.RETENTION_FAILED_JOB_DAYS > 0:
            rules.append(("failed", now - timedelta(days=settings.RETENTION_FAILED_JOB_DAYS)))
        for status_name, cutoff in rules:
            jobs = (
                session.query(Job)
                .filter(Job.status == status_name, Job.created_at < cutoff)
                .all()
            )
            for job in jobs:
                if (job.result or {}).get("files_purged"):
                    continue
                out_dir = os.path.join(upload_root, str(job.user_id),
                                       "output", str(job.id))
                if os.path.isdir(out_dir):
                    size = _dir_size(out_dir)
                    shutil.rmtree(out_dir, ignore_errors=True)
                    purged["outputs"] += 1
                    purged["bytes"] += size
                job.result = {**(job.result or {}), "files_purged": True}
                session.commit()

        # --- Sources importées par URL (gros fichiers, re-téléchargeables) ---
        if settings.RETENTION_SOURCE_DAYS > 0:
            cutoff_ts = (now - timedelta(days=settings.RETENTION_SOURCE_DAYS)).timestamp()
            for user_dir in os.listdir(upload_root) if os.path.isdir(upload_root) else []:
                src_dir = os.path.join(upload_root, user_dir, "url_sources")
                if not os.path.isdir(src_dir):
                    continue
                for name in os.listdir(src_dir):
                    path = os.path.join(src_dir, name)
                    try:
                        if os.path.isfile(path) and os.path.getmtime(path) < cutoff_ts:
                            purged["bytes"] += os.path.getsize(path)
                            os.unlink(path)
                            purged["sources"] += 1
                    except OSError:
                        pass
    finally:
        session.close()

    logger.info("purge_expired_files: %s output dirs, %s sources, %.1f MB freed",
                purged["outputs"], purged["sources"], purged["bytes"] / 1e6)
    return purged
