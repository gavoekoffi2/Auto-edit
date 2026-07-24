import os
import logging
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.media import ranged_file_response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.models.user import User
from app.models.video import Video
from app.models.job import Job
from app.schemas.job import JobCreate, JobResponse
from app.api.v1.modes import MODE_DEFINITIONS, DEFAULT_MODE
from app.api.deps import get_current_user
from app.services.auth import decode_token
from app.services.storage import get_absolute_path

logger = logging.getLogger(__name__)

router = APIRouter()
optional_security = HTTPBearer(auto_error=False)


async def get_media_user(
    db: AsyncSession,
    credentials: HTTPAuthorizationCredentials | None,
    access_token: str | None,
) -> User:
    token = credentials.credentials if credentials else access_token
    payload = decode_token(token) if token else None
    if payload is None or payload.get("type") != "access" or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    try:
        user_uuid = UUID(payload["sub"])
    except (ValueError, TypeError, AttributeError):
        # Un `sub` malformé doit répondre 401, pas une 500 interne.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user




@router.get("/modes")
async def list_modes():
    """Liste les modes de montage disponibles + leurs defaults d'options.

    Endpoint public — le frontend l'utilise pour rendre dynamiquement le
    selecteur de modes sans dupliquer la liste cote TS. `default_mode` indique
    le choix par defaut (style Signature 3D — images IA + motion design).
    """
    return {"modes": MODE_DEFINITIONS, "default_mode": DEFAULT_MODE}


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    data: JobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify video belongs to user
    result = await db.execute(
        select(Video).where(Video.id == data.video_id, Video.user_id == current_user.id)
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    # Verify video file exists on disk
    video_file = get_absolute_path(video.original_path)
    if not os.path.exists(video_file):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Video file not found on disk. Please re-upload.",
        )

    # Check plan limits for free users
    if current_user.plan == "free":
        count_result = await db.execute(
            select(func.count()).select_from(Job).where(
                Job.user_id == current_user.id,
                Job.status.in_(["pending", "processing"]),
            )
        )
        active_count = count_result.scalar() or 0
        if active_count >= 2:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Free plan limited to 2 concurrent jobs. Upgrade to Pro for unlimited.",
            )

    # Merge params + options dans le payload du job (options prennent le pas)
    merged_params: dict = dict(data.params or {})
    if data.options is not None:
        # exclude_none=True pour ne pas écraser des défauts par des None
        opts = data.options.model_dump(exclude_none=True)
        if opts:
            merged_params["options"] = opts

    from app.config import settings
    pipeline_version = data.pipeline_version or settings.PIPELINE_VERSION

    job = Job(
        video_id=data.video_id,
        user_id=current_user.id,
        job_type=data.job_type,
        mode=data.mode,
        params=merged_params,
        pipeline_version=pipeline_version,
    )
    db.add(job)
    await db.flush()

    # Trigger async processing
    from app.workers.tasks import process_video_task

    process_video_task.delay(str(job.id))

    logger.info(
        f"Job created: {job.id} type={data.job_type} mode={data.mode} "
        f"pipeline={pipeline_version} by user {current_user.id}"
    )
    return job


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    video_id: Optional[UUID] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Job).where(Job.user_id == current_user.id)
    if video_id:
        query = query.where(Job.video_id == video_id)
    query = query.order_by(Job.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a pending or processing job."""
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if job.status not in ("pending", "processing"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status '{job.status}'",
        )

    # Revoke the Celery task if it's still queued
    if job.status == "pending":
        try:
            from app.workers.celery_app import celery_app
            celery_app.control.revoke(str(job.id), terminate=True)
        except Exception as e:
            logger.warning(f"Failed to revoke Celery task {job.id}: {e}")

    job.status = "cancelled"
    await db.flush()

    logger.info(f"Job {job.id} cancelled by user {current_user.id}")
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Supprime un job ET tous ses fichiers (rendus, transcriptions, clips).

    Confidentialité: l'utilisateur peut retirer ses contenus du serveur.
    La ligne Job est effacée; la vidéo source (ligne Video) reste gérée par
    DELETE /videos/{id}.
    """
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status in ("pending", "processing"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Annule d'abord le traitement avant de le supprimer.",
        )

    import shutil
    from app.config import settings
    out_dir = os.path.join(
        os.path.abspath(settings.UPLOAD_DIR), str(job.user_id), "output", str(job.id))
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir, ignore_errors=True)

    await db.delete(job)
    await db.flush()
    logger.info(f"Job {job_id} and its files deleted by user {current_user.id}")


@router.get("/{job_id}/download")
async def download_result(
    job_id: UUID,
    request: Request,
    access_token: str | None = Query(None),
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_security),
    db: AsyncSession = Depends(get_db),
):
    current_user = await get_media_user(db, credentials, access_token)
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if job.status != "completed" or not job.result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job not completed yet",
        )

    output_path = job.result.get("output_path")
    if not output_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Output file not found",
        )

    absolute_path = get_absolute_path(output_path)
    if not os.path.exists(absolute_path):
        # Fichier purgé par la rétention (ou supprimé): code stable FILE_EXPIRED
        # (410) pour que le frontend/support comprennent, pas un 404 générique.
        from app.services.errors import http_error
        raise http_error("FILE_EXPIRED",
                         getattr(request.state, "request_id", None))

    # Range-aware response: resumable downloads + seekable preview playback
    # (the pinned Starlette FileResponse ignores Range headers).
    return ranged_file_response(
        absolute_path,
        request,
        media_type="video/mp4",
        filename=f"cutforge_{job_id}.mp4",
    )


@router.get("/{job_id}/clips/{clip_index}/download")
async def download_clip(
    job_id: UUID,
    clip_index: int,
    request: Request,
    access_token: str | None = Query(None),
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_security),
    db: AsyncSession = Depends(get_db),
):
    """Télécharge UN clip d'un job « Clips » (vidéo longue -> shorts viraux)."""
    current_user = await get_media_user(db, credentials, access_token)
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status != "completed" or not job.result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job not completed yet",
        )

    clips = job.result.get("clips") or []
    clip = next(
        (c for c in clips if c.get("index") == clip_index and c.get("output_path")),
        None,
    )
    if clip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")

    absolute_path = get_absolute_path(clip["output_path"])
    if not os.path.exists(absolute_path):
        from app.services.errors import http_error
        raise http_error("FILE_EXPIRED",
                         getattr(request.state, "request_id", None))
    return ranged_file_response(
        absolute_path,
        request,
        media_type="video/mp4",
        filename=f"cutforge_{job_id}_clip{clip_index + 1}.mp4",
    )
