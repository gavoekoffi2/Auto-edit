import os
import mimetypes
import logging
from uuid import UUID
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.models.user import User
from app.models.video import Video
from app.schemas.video import VideoResponse, VideoListResponse
from app.api.deps import get_current_user
from app.services.auth import decode_token
from app.services.storage import save_upload, get_absolute_path, get_video_duration
from app.config import settings
from app.services.subscriptions import effective_plan

logger = logging.getLogger(__name__)

router = APIRouter()
optional_security = HTTPBearer(auto_error=False)

ALLOWED_EXTENSIONS = {
    ".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".flv", ".wmv",
    ".3gp", ".3g2", ".mts", ".m2ts",
}


async def get_stream_user(
    db: AsyncSession,
    credentials: HTTPAuthorizationCredentials | None,
    access_token: str | None,
) -> User:
    """Authenticate video streaming via header or query token.

    Normal API calls use the Authorization header. Native HTML video playback
    cannot attach custom headers, so the frontend may pass the current access
    token as a query parameter specifically for media streaming.
    """
    token = credentials.credentials if credentials else access_token
    payload = decode_token(token) if token else None
    if payload is None or payload.get("type") != "access" or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    result = await db.execute(select(User).where(User.id == UUID(payload["sub"])))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


@router.post("/upload", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate file type
    if file.filename:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    current_plan = effective_plan(current_user)

    # Check monthly video quota for free users
    if current_plan == "free":
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        count_result = await db.execute(
            select(func.count()).select_from(Video).where(
                Video.user_id == current_user.id,
                Video.created_at >= month_start,
            )
        )
        monthly_count = count_result.scalar() or 0
        if monthly_count >= settings.MAX_VIDEOS_PER_MONTH_FREE:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Free plan limited to {settings.MAX_VIDEOS_PER_MONTH_FREE} videos/month. Upgrade to Pro.",
            )

    # Taille attendue (Content-Length) pour le préflight disque. Le body
    # multipart ajoute un petit overhead, donc c'est une borne haute utile.
    expected_size = None
    try:
        cl = request.headers.get("content-length")
        expected_size = int(cl) if cl else None
    except (TypeError, ValueError):
        expected_size = None

    # Save file with size + disk validation
    relative_path, size_bytes = await save_upload(
        file, str(current_user.id), expected_size=expected_size
    )

    # Get video duration
    abs_path = get_absolute_path(relative_path)
    duration = get_video_duration(abs_path)

    # Check duration limits
    if duration is not None and current_plan == "free":
        if duration > settings.MAX_VIDEO_DURATION_FREE:
            # Clean up uploaded file
            try:
                os.unlink(abs_path)
            except OSError:
                pass
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Free plan limited to {settings.MAX_VIDEO_DURATION_FREE // 60} min videos. "
                       f"Your video is {duration / 60:.1f} min. Upgrade to Pro.",
            )
    elif duration is not None and current_plan == "pro":
        if duration > settings.MAX_VIDEO_DURATION_PRO:
            try:
                os.unlink(abs_path)
            except OSError:
                pass
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Pro plan limited to {settings.MAX_VIDEO_DURATION_PRO // 60} min videos. "
                       f"Upgrade to Enterprise for unlimited.",
            )

    compress_enabled = settings.INGEST_COMPRESS_ENABLED
    initial_status = "compressing" if compress_enabled else "uploaded"

    video = Video(
        user_id=current_user.id,
        title=file.filename,
        original_path=relative_path,
        size_bytes=size_bytes,
        duration_s=duration,
        status=initial_status,
    )
    db.add(video)
    await db.flush()

    if compress_enabled:
        from app.workers.tasks import compress_ingest_video_task
        compress_ingest_video_task.delay(str(video.id))
        logger.info(
            f"Video uploaded (compressing): {video.id} by user {current_user.id} ({size_bytes} bytes)"
        )
    else:
        logger.info(f"Video uploaded: {video.id} by user {current_user.id} ({size_bytes} bytes)")

    return video


@router.get("", response_model=VideoListResponse)
async def list_videos(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Video)
        .where(Video.user_id == current_user.id)
        .order_by(Video.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    videos = result.scalars().all()

    count_result = await db.execute(
        select(func.count()).select_from(Video).where(Video.user_id == current_user.id)
    )
    total = count_result.scalar()

    return VideoListResponse(videos=videos, total=total)


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Video).where(Video.id == video_id, Video.user_id == current_user.id)
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return video


@router.get("/{video_id}/stream")
async def stream_video(
    video_id: UUID,
    request: Request,
    access_token: str | None = Query(None),
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_security),
    db: AsyncSession = Depends(get_db),
):
    current_user = await get_stream_user(db, credentials, access_token)
    result = await db.execute(
        select(Video).where(Video.id == video_id, Video.user_id == current_user.id)
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    file_path = get_absolute_path(video.original_path)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found on disk")

    guessed_type, _ = mimetypes.guess_type(file_path)
    media_type = guessed_type or "application/octet-stream"
    if not media_type.startswith("video/"):
        media_type = "video/mp4"
    # Range-aware: the <video> element can seek without re-downloading the file.
    from app.services.media import ranged_file_response

    return ranged_file_response(file_path, request, media_type=media_type)


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Video).where(Video.id == video_id, Video.user_id == current_user.id)
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    # Clean up file on disk
    try:
        file_path = get_absolute_path(video.original_path)
        if os.path.exists(file_path):
            os.unlink(file_path)
    except Exception as e:
        logger.warning(f"Failed to delete file for video {video_id}: {e}")

    await db.delete(video)
    await db.flush()
