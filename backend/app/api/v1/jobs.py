from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.models.video import Video
from app.models.job import Job
from app.schemas.job import JobCreate, JobResponse
from app.api.deps import get_current_user
from app.services.storage import get_absolute_path

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

    # Check plan limits for free users
    if current_user.plan == "free":
        count_result = await db.execute(
            select(Job).where(
                Job.user_id == current_user.id,
                Job.status.in_(["pending", "processing"]),
            )
        )
        active_jobs = count_result.scalars().all()
        if len(active_jobs) >= 2:
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

    # Update video status
    video.status = "processing"

    # Trigger async processing
    from app.workers.tasks import process_video_task

    process_video_task.delay(str(job.id))

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
    video_id: UUID = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Job).where(Job.user_id == current_user.id)
    if video_id:
        query = query.where(Job.video_id == video_id)
    query = query.order_by(Job.created_at.desc()).limit(50)

    result = await db.execute(query)
    return result.scalars().all()


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
    return FileResponse(
        absolute_path,
        media_type="video/mp4",
        filename=f"autoedit_{job_id}.mp4",
    )
