import os
import logging
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.models.user import User
from app.models.video import Video
from app.models.job import Job
from app.schemas.job import JobCreate, JobResponse
from app.api.deps import get_current_user
from app.services.storage import get_absolute_path

logger = logging.getLogger(__name__)

router = APIRouter()


_MODE_DEFINITIONS: list[dict] = [
    {
        "id": "tiktok_viral",
        "name": "TikTok viral",
        "icon": "🔥",
        "description": "Vertical 9:16, captions animées, B-roll IA africain, CTA final",
        "pipeline": "v2",
        "defaults": {
            "remove_silence": True, "dynamic_captions": True, "ai_broll": True,
            "music": True, "sfx": True, "vertical_9_16": True, "final_cta": True,
            "broll_style": "tiktok_viral",
        },
    },
    {
        "id": "business_premium_african",
        "name": "Business premium 🇸🇳🇨🇮🇹🇬",
        "icon": "💼",
        "description": "Style africain moderne, B-roll premium, musique sobre",
        "pipeline": "v2",
        "defaults": {
            "remove_silence": True, "dynamic_captions": True, "ai_broll": True,
            "music": True, "sfx": False, "vertical_9_16": True, "final_cta": True,
            "broll_style": "african_business_premium",
        },
    },
    {
        "id": "publicite_locale",
        "name": "Publicité locale",
        "icon": "📣",
        "description": "Restaurant, boutique, service local — CTA clair",
        "pipeline": "v2",
        "defaults": {
            "remove_silence": True, "dynamic_captions": True, "ai_broll": True,
            "music": True, "sfx": True, "vertical_9_16": True, "final_cta": True,
            "broll_style": "publicite_locale",
        },
    },
    {
        "id": "podcast_propre",
        "name": "Podcast propre",
        "icon": "🎙️",
        "description": "Suppression silences uniquement, audio préservé",
        "pipeline": "v2",
        "defaults": {
            "remove_silence": True, "dynamic_captions": False, "ai_broll": False,
            "music": False, "sfx": False, "vertical_9_16": False, "final_cta": False,
            "broll_style": "podcast_propre",
        },
    },
    {
        "id": "formation_educative",
        "name": "Formation / éducatif",
        "icon": "🎓",
        "description": "Captions lisibles, B-roll discret, horizontal",
        "pipeline": "v2",
        "defaults": {
            "remove_silence": True, "dynamic_captions": True, "ai_broll": True,
            "music": False, "sfx": False, "vertical_9_16": False, "final_cta": False,
            "broll_style": "formation_educative",
        },
    },
    {
        "id": "tiktok",
        "name": "TikTok (legacy)",
        "icon": "📱",
        "description": "Pipeline v1 — vertical 9:16, sous-titres, cuts rapides",
        "pipeline": "v1",
        "defaults": {},
    },
    {
        "id": "youtube",
        "name": "YouTube (legacy)",
        "icon": "📹",
        "description": "Pipeline v1 — suppression silences + sous-titres",
        "pipeline": "v1",
        "defaults": {},
    },
    {
        "id": "podcast",
        "name": "Podcast (legacy)",
        "icon": "🎧",
        "description": "Pipeline v1 — audio uniquement",
        "pipeline": "v1",
        "defaults": {},
    },
]


@router.get("/modes")
async def list_modes():
    """Liste les modes de montage disponibles + leurs defaults d'options.

    Endpoint public — le frontend l'utilise pour rendre dynamiquement le
    selecteur de modes sans dupliquer la liste cote TS.
    """
    return {"modes": _MODE_DEFINITIONS}


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


@router.get("/{job_id}/download")
async def download_result(
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Output file no longer exists on disk",
        )

    return FileResponse(
        absolute_path,
        media_type="video/mp4",
        filename=f"autoedit_{job_id}.mp4",
    )
