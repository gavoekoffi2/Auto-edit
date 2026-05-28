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

    job = Job(
        video_id=data.video_id,
        user_id=current_user.id,
        job_type=data.job_type,
        mode=data.mode,
        params=data.params or {},
    )
    db.add(job)
    await db.flush()

    # Trigger async processing
    from app.workers.tasks import process_video_task

    process_video_task.apply_async(args=[str(job.id)], task_id=str(job.id))

    logger.info(f"Job created: {job.id} type={data.job_type} mode={data.mode} by user {current_user.id}")
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
