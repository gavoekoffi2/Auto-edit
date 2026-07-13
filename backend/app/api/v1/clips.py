"""API « Clips » — transformer une vidéo longue en shorts viraux.

L'utilisateur fournit une URL publique (YouTube, TikTok, etc.) ou une vidéo
déjà uploadée. Le worker télécharge la source si besoin, détecte les moments
viraux (IA + repli heuristique) et monte chaque extrait avec le style choisi.
Les clips terminés sont listés dans `job.result.clips`; chacun se télécharge
via `GET /jobs/{job_id}/clips/{index}/download`.
"""
import logging
import os
import uuid as uuid_lib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_current_user
from app.config import settings
from app.db.session import get_db
from app.models.job import Job
from app.models.user import User
from app.models.video import Video
from app.schemas.job import ClipsCreate, JobResponse
from app.services.subscriptions import effective_plan
from app.services.video_download import SourceURLError, validate_source_url
from app.services.storage import get_absolute_path

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_clips_job(
    data: ClipsCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ---- Résolution de la source (URL publique ou vidéo uploadée) ----------
    source_url = None
    if data.source_url:
        try:
            source_url = validate_source_url(data.source_url)
        except SourceURLError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        # Quota mensuel du plan gratuit: une vidéo importée par URL compte
        # comme un upload (même ressource serveur).
        if effective_plan(current_user) == "free":
            month_start = datetime.now(timezone.utc).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0)
            count_result = await db.execute(
                select(func.count()).select_from(Video).where(
                    Video.user_id == current_user.id,
                    Video.created_at >= month_start,
                )
            )
            if (count_result.scalar() or 0) >= settings.MAX_VIDEOS_PER_MONTH_FREE:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Plan gratuit limité à {settings.MAX_VIDEOS_PER_MONTH_FREE} "
                        "vidéos/mois. Passe en Pro."
                    ),
                )

        # Ligne Video « placeholder »: le worker télécharge le fichier à ce
        # chemin puis met à jour taille/durée/titre.
        rel_path = os.path.join(
            str(current_user.id), "url_sources", f"{uuid_lib.uuid4()}.mp4")
        video = Video(
            user_id=current_user.id,
            title=f"Import URL — {source_url[:400]}",
            original_path=rel_path,
            size_bytes=0,
            status="uploaded",
        )
        db.add(video)
        await db.flush()
    else:
        result = await db.execute(
            select(Video).where(Video.id == data.video_id,
                                Video.user_id == current_user.id)
        )
        video = result.scalar_one_or_none()
        if not video:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Video not found")
        if not os.path.exists(get_absolute_path(video.original_path)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Video file not found on disk. Please re-upload.",
            )

    # ---- Limite de jobs simultanés (même règle que /jobs) -------------------
    if current_user.plan == "free":
        count_result = await db.execute(
            select(func.count()).select_from(Job).where(
                Job.user_id == current_user.id,
                Job.status.in_(["pending", "processing"]),
            )
        )
        if (count_result.scalar() or 0) >= 2:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Free plan limited to 2 concurrent jobs. Upgrade to Pro.",
            )

    params: dict = {}
    if source_url:
        params["source_url"] = source_url
    if data.options is not None:
        opts = data.options.model_dump(exclude_none=True)
        if opts:
            params["options"] = opts

    job = Job(
        video_id=video.id,
        user_id=current_user.id,
        job_type="clips",
        mode=data.mode,
        params=params,
        pipeline_version="v2",
    )
    db.add(job)
    await db.flush()

    from app.workers.tasks import process_clips_task
    process_clips_task.delay(str(job.id))

    logger.info(
        f"Clips job created: {job.id} source={'url' if source_url else 'video'} "
        f"mode={data.mode} by user {current_user.id}"
    )
    return job
