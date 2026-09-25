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
from app.services.auth import decode_token, token_matches_password
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
    if user is None or not user.is_active or not token_matches_password(payload, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user


async def _monthly_usage(db: AsyncSession, user: User) -> int:
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # Les vidéos supprimées COMPTENT (soft delete) — seuls les imports en
    # erreur ne consomment pas le quota.
    result = await db.execute(
        select(func.count()).select_from(Video).where(
            Video.user_id == user.id,
            Video.created_at >= month_start,
            Video.status != "error",
        )
    )
    return result.scalar() or 0


@router.get("/upload-check")
async def upload_check(
    purpose: str = Query("edit", pattern="^(edit|clips)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Préflight AVANT l'envoi d'une vidéo: quota, durée et taille maximales.

    FastAPI lit tout le corps multipart avant d'exécuter l'endpoint d'upload:
    sans ce contrôle préalable, un utilisateur au quota atteint envoyait des
    centaines de Mo sur mobile pour recevoir un refus à la fin.
    """
    from app.services.plans import rules_for_user

    rules = rules_for_user(current_user)
    used = await _monthly_usage(db, current_user)
    limit = rules.max_videos_per_month
    can_upload = limit is None or used < limit
    return {
        "can_upload": can_upload,
        "reason": None if can_upload else (
            f"Tu as utilisé tes {limit} vidéos gratuites de ce mois. Passe Pro pour continuer."),
        "monthly_used": used,
        "monthly_limit": limit,
        "max_duration_s": effective_video_duration_limit_s(current_user, clips=purpose == "clips"),
        "max_upload_mb": settings.MAX_UPLOAD_SIZE_MB,
    }


@router.post("/upload", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    # « clips »: source d'une découpe en shorts -> limite de durée Clips du
    # plan (plus longue que celle du montage classique).
    purpose: str = Query("edit", pattern="^(edit|clips)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate file type
    if file.filename:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Format non supporté. Formats acceptés : {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nom de fichier manquant.",
        )
    # Check monthly limit for free users. Le fondateur est toujours Enterprise
    # effectif afin qu'aucun quota mensuel ne puisse le bloquer.
    current_plan = "enterprise" if bool(getattr(current_user, "is_super_admin", False)) else effective_plan(current_user)
    # Check monthly video quota for free users
    if current_plan == "free":
        # Verrou de la ligne utilisateur: deux uploads simultanés ne peuvent
        # plus passer tous les deux sous la limite.
        await db.execute(select(User.id).where(User.id == current_user.id).with_for_update())
        monthly_count = await _monthly_usage(db, current_user)
        if monthly_count >= settings.MAX_VIDEOS_PER_MONTH_FREE:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(f"Le plan Free est limité à {settings.MAX_VIDEOS_PER_MONTH_FREE} vidéos par mois. "
                        "Passe Pro pour continuer."),
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

    # Fichier illisible (upload tronqué, conteneur corrompu): refus immédiat
    # et clair, plutôt qu'un montage qui échoue plus tard sans explication.
    if duration is None or duration <= 0.3:
        try:
            os.unlink(abs_path)
        except OSError:
            pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=("Impossible de lire cette vidéo (fichier incomplet ou corrompu). "
                    "Réessaie l'envoi ou exporte-la de nouveau depuis ton téléphone."),
        )

    # Limite centrale: super-admin/Enterprise illimités, ou quota personnalisé.
    duration_limit_s = effective_video_duration_limit_s(current_user, clips=purpose == "clips")
    if duration is not None and duration_limit_s is not None and duration > duration_limit_s:
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
        title=file.filename,
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
        .where(Video.user_id == current_user.id, Video.deleted_at.is_(None))
        .order_by(Video.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    videos = result.scalars().all()

    count_result = await db.execute(
        select(func.count()).select_from(Video).where(
            Video.user_id == current_user.id, Video.deleted_at.is_(None))
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
        select(Video).where(Video.id == video_id, Video.user_id == current_user.id,
                            Video.deleted_at.is_(None))
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vidéo introuvable")
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
        select(Video).where(Video.id == video_id, Video.user_id == current_user.id,
                            Video.deleted_at.is_(None))
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vidéo introuvable")

    file_path = get_absolute_path(video.original_path)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Le fichier de cette vidéo a expiré. Réimporte-la.")

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
        select(Video).where(Video.id == video_id, Video.user_id == current_user.id,
                            Video.deleted_at.is_(None))
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vidéo introuvable")

    import shutil
    from app.models.job import Job

    # 1) Stoppe les traitements encore actifs sur cette vidéo: sinon le worker
    #    continuait des heures à rendre une vidéo dont le fichier n'existe plus.
    jobs = (await db.execute(select(Job).where(Job.video_id == video.id))).scalars().all()
    for job in jobs:
        if job.status in ("pending", "processing"):
            try:
                from app.workers.celery_app import celery_app
                celery_app.control.revoke(str(job.id), terminate=True, signal="SIGTERM")
            except Exception as e:
                logger.warning(f"Failed to revoke Celery task {job.id}: {e}")

    # 2) Fichiers: source + rendus de tous les jobs (confidentialité + disque).
    try:
        file_path = get_absolute_path(video.original_path)
        if os.path.exists(file_path):
            os.unlink(file_path)
    except Exception as e:
        logger.warning(f"Failed to delete file for video {video_id}: {e}")
    for job in jobs:
        out_dir = os.path.join(
            os.path.abspath(settings.UPLOAD_DIR), str(current_user.id), "output", str(job.id))
        if os.path.isdir(out_dir):
            shutil.rmtree(out_dir, ignore_errors=True)
        await db.delete(job)

    # 3) Soft delete: la ligne reste (sans fichier) pour que le quota mensuel
    #    ne puisse pas être remis à zéro en supprimant puis réimportant.
    video.deleted_at = datetime.now(timezone.utc)
    video.title = "Vidéo supprimée"
    await db.flush()
    logger.info(f"Video {video_id} deleted by user {current_user.id}")
