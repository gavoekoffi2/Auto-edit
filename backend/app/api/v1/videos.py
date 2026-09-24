import os
import mimetypes
import logging
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.models.user import User
from app.models.video import Video
from app.schemas.video import VideoResponse, VideoListResponse
from app.api.deps import get_current_user, get_media_user
from app.services.storage import save_upload, get_absolute_path, get_video_duration
from app.config import settings
from app.services.subscriptions import effective_plan
from app.services.plans import effective_video_duration_limit_s

logger = logging.getLogger(__name__)

router = APIRouter()
optional_security = HTTPBearer(auto_error=False)

ALLOWED_EXTENSIONS = {
    ".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".flv", ".wmv",
    ".3gp", ".3g2", ".mts", ".m2ts",
}


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
    # Check monthly limit for free users. Le fondateur est toujours Enterprise
    # effectif afin qu'aucun quota mensuel ne puisse le bloquer.
    current_plan = "enterprise" if bool(getattr(current_user, "is_super_admin", False)) else effective_plan(current_user)

    # Check monthly video quota for free users
    if current_plan == "free":
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Les imports échoués (statut `error`) ne consomment pas le quota.
        count_result = await db.execute(
            select(func.count()).select_from(Video).where(
                Video.user_id == current_user.id,
                Video.created_at >= month_start,
                Video.status != "error",
            )
        )
        monthly_count = count_result.scalar() or 0
        if monthly_count >= settings.MAX_VIDEOS_PER_MONTH_FREE:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(f"Le plan gratuit est limité à {settings.MAX_VIDEOS_PER_MONTH_FREE} "
                        "vidéos par mois. Passe en Pro pour continuer."),
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

    # Get video duration — ffprobe est bloquant (jusqu'à 30 s): hors de la
    # boucle async pour ne pas geler les autres requêtes.
    abs_path = get_absolute_path(relative_path)
    duration = await run_in_threadpool(get_video_duration, abs_path)
    if not duration or duration <= 0:
        # Signature vidéo reconnue mais flux illisible (fichier tronqué par une
        # coupure réseau, codec exotique…): le montage échouerait plus tard
        # avec une erreur obscure. On refuse tout de suite, clairement.
        try:
            os.unlink(abs_path)
        except OSError:
            pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=("Impossible de lire cette vidéo (fichier incomplet ou corrompu). "
                    "Réessaie l'envoi ou exporte-la de nouveau en MP4."),
        )

    # Limite centrale: super-admin/Enterprise illimités, ou quota personnalisé.
    duration_limit_s = effective_video_duration_limit_s(current_user, clips=False)
    if duration_limit_s is not None and duration > duration_limit_s:
        try:
            os.unlink(abs_path)
        except OSError:
            pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"Ce compte accepte des vidéos de {duration_limit_s / 60:g} min maximum. "
                    f"Cette vidéo dure {duration / 60:.1f} min."),
        )

    video = Video(
        user_id=current_user.id,
        title=os.path.basename(file.filename)[:500],
        original_path=relative_path,
        size_bytes=size_bytes,
        duration_s=duration,
    )
    db.add(video)
    await db.flush()

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
    current_user = await get_media_user(db, credentials, access_token)
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

    # Un montage en cours sur cette vidéo doit être arrêté AVANT de retirer ses
    # fichiers: sinon le worker continue à tourner pour rien puis plante sur
    # un fichier disparu.
    from app.models.job import Job
    active_jobs = (await db.execute(
        select(Job).where(Job.video_id == video.id,
                          Job.status.in_(["pending", "processing"]))
    )).scalars().all()
    if active_jobs:
        try:
            from app.workers.celery_app import celery_app
            for job in active_jobs:
                celery_app.control.revoke(str(job.id), terminate=True, signal="SIGTERM")
        except Exception as e:
            logger.warning(f"Failed to revoke jobs of video {video_id}: {e}")
        for job in active_jobs:
            job.status = "cancelled"
        await db.flush()

    # Clean up file on disk
    try:
        file_path = get_absolute_path(video.original_path)
        if os.path.exists(file_path):
            os.unlink(file_path)
    except Exception as e:
        logger.warning(f"Failed to delete file for video {video_id}: {e}")

    # Purge aussi les répertoires de sortie des jobs de cette vidéo — la
    # cascade DB supprime les lignes Job mais laissait leurs fichiers rendus
    # sur le disque (confidentialité + espace).
    all_jobs = (await db.execute(select(Job).where(Job.video_id == video.id))).scalars().all()
    from app.services.usage import refund_before_delete
    await refund_before_delete(db, all_jobs)
    try:
        import shutil
        for jid in [j.id for j in all_jobs]:
            out_dir = os.path.join(
                os.path.abspath(settings.UPLOAD_DIR),
                str(current_user.id), "output", str(jid))
            if os.path.isdir(out_dir):
                shutil.rmtree(out_dir, ignore_errors=True)
    except Exception as e:
        logger.warning(f"Failed to purge job outputs for video {video_id}: {e}")

    await db.delete(video)
    await db.flush()
