"""API « Clips » — transformer une vidéo longue en shorts viraux.

Flux en DEUX étapes (économe en ressources et en crédits IA):

  1. ``POST /clips`` — importe la source (URL publique ou vidéo uploadée),
     la transcrit et propose les moments forts. Le job se termine avec
     ``result.stage = "moments_ready"`` et la liste des extraits proposés
     (titre, hook, raison, potentiel, transcript, timecodes).
  2. ``POST /clips/{job_id}/render`` — rend UNIQUEMENT les extraits choisis
     (bornes ajustables, titres modifiables), avec le style sélectionné.

Chaque clip terminé se télécharge via
``GET /jobs/{job_id}/clips/{index}/download`` (ownership vérifié).

Quotas: TOUTES les règles viennent de ``app.services.plans``. Les checks
sont ATOMIQUES — la ligne utilisateur est verrouillée (FOR UPDATE) pendant
le check-then-create pour empêcher le dépassement par requêtes simultanées.
"""
import logging
import os
import uuid as uuid_lib
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_current_user
from app.config import settings
from app.db.session import get_db
from app.models.job import Job
from app.models.user import User
from app.models.video import Video
from app.schemas.job import ClipsCreate, ClipsRenderRequest, JobResponse
from app.services.errors import http_error
from app.services.plans import rules_for_user, effective_video_duration_limit_s
from app.services.video_download import SourceURLError, validate_source_url
from app.services.storage import get_absolute_path

logger = logging.getLogger(__name__)

router = APIRouter()


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


async def _lock_user_and_check_quotas(
    db: AsyncSession, request: Request, user: User, *, count_monthly: bool
) -> None:
    """Verrouille la ligne utilisateur puis applique les quotas du plan.

    Le verrou sérialise les créations concurrentes du même utilisateur: deux
    requêtes simultanées ne peuvent plus passer toutes les deux sous la
    limite (check-then-create atomique).
    """
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    rules = rules_for_user(user)

    if rules.max_concurrent_jobs is not None:
        active = (await db.execute(
            select(func.count()).select_from(Job).where(
                Job.user_id == user.id,
                Job.status.in_(["pending", "processing"]),
            )
        )).scalar() or 0
        if active >= rules.max_concurrent_jobs:
            raise http_error("QUOTA_CONCURRENT_JOBS", _request_id(request))

    if count_monthly and rules.max_videos_per_month is not None:
        month_start = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0)
        # Les imports ÉCHOUÉS (URL invalide, vidéo trop longue…) ne consomment
        # pas le quota: leur ligne Video passe en statut `error` par le worker.
        monthly = (await db.execute(
            select(func.count()).select_from(Video).where(
                Video.user_id == user.id,
                Video.created_at >= month_start,
                Video.status != "error",
            )
        )).scalar() or 0
        if monthly >= rules.max_videos_per_month:
            raise http_error("QUOTA_MONTHLY_REACHED", _request_id(request))


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_clips_job(
    data: ClipsCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Étape 1 — analyse: import + transcription + proposition des extraits."""
    rules = rules_for_user(current_user)
    source_duration_limit_s = effective_video_duration_limit_s(current_user, clips=True)

    # ---- Résolution de la source (URL publique ou vidéo uploadée) ----------
    source_url = None
    if data.source_url:
        try:
            source_url = validate_source_url(data.source_url)
        except SourceURLError as e:
            code = "URL_FORBIDDEN_HOST" if "réseau interdit" in str(e) else "URL_INVALID"
            err = http_error(code, _request_id(request))
            err.detail["message"] = str(e)  # message précis déjà utilisateur-safe
            raise err

        await _lock_user_and_check_quotas(db, request, current_user, count_monthly=True)

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
            raise http_error("VIDEO_NOT_FOUND", _request_id(request))
        if not os.path.exists(get_absolute_path(video.original_path)):
            raise http_error("FILE_EXPIRED", _request_id(request))
        if (source_duration_limit_s is not None
                and (video.duration_s or 0) > source_duration_limit_s):
            raise http_error("SOURCE_TOO_LONG", _request_id(request))
        # Vidéo existante: pas de nouveau comptage mensuel (déjà comptée à
        # l'upload), mais la limite de jobs simultanés s'applique.
        await _lock_user_and_check_quotas(db, request, current_user, count_monthly=False)

    params: dict = {"stage": "analyze"}
    if source_url:
        params["source_url"] = source_url
        # Le worker vérifie la durée AVANT téléchargement (probe yt-dlp) puis
        # après téléchargement — la limite effective voyage avec le job.
        if source_duration_limit_s is not None:
            params["max_source_duration_s"] = source_duration_limit_s
    if data.options is not None:
        opts = data.options.model_dump(exclude_none=True)
        if opts:
            if opts.get("max_clips"):
                opts["max_clips"] = min(int(opts["max_clips"]), rules.clips_max_per_job)
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
        "Clips analyze job created: %s source=%s mode=%s user=%s",
        job.id, "url" if source_url else "video", data.mode, current_user.id,
    )
    return job


@router.post("/{job_id}/render", response_model=JobResponse,
             status_code=status.HTTP_201_CREATED)
async def render_selected_clips(
    job_id: UUID,
    data: ClipsRenderRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Étape 2 — rendu des extraits SÉLECTIONNÉS d'un job d'analyse terminé."""
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    analyze_job = result.scalar_one_or_none()
    if not analyze_job:
        raise http_error("JOB_NOT_FOUND", _request_id(request))
    if analyze_job.status != "completed" or not analyze_job.result:
        raise http_error("JOB_NOT_READY", _request_id(request))
    if analyze_job.result.get("stage") != "moments_ready":
        raise http_error("JOB_NOT_READY", _request_id(request))

    video_result = await db.execute(
        select(Video).where(Video.id == analyze_job.video_id,
                            Video.user_id == current_user.id)
    )
    video = video_result.scalar_one_or_none()
    if not video:
        raise http_error("VIDEO_NOT_FOUND", _request_id(request))
    if not os.path.exists(get_absolute_path(video.original_path)):
        raise http_error("FILE_EXPIRED", _request_id(request))

    rules = rules_for_user(current_user)
    # Validation stricte des extraits côté serveur (bornes, durées, plan).
    from app.processing.clips_pipeline import validate_render_moments
    try:
        moments = validate_render_moments(
            [c.model_dump() for c in data.clips],
            float(video.duration_s or 0.0),
            max_clips=rules.clips_max_per_job,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "QUOTA_CLIPS_PER_JOB", "message": str(e),
                    "request_id": _request_id(request)},
        )

    await _lock_user_and_check_quotas(db, request, current_user, count_monthly=False)

    mode = data.mode or analyze_job.mode
    params: dict = {
        "stage": "render",
        "moments": moments,
        "analyze_job_id": str(analyze_job.id),
        "source_vu_path": analyze_job.result.get("source_vu_path"),
    }
    opts = dict((analyze_job.params or {}).get("options") or {})
    if data.options is not None:
        opts.update(data.options.model_dump(exclude_none=True))
    opts["max_clips"] = rules.clips_max_per_job
    if opts:
        params["options"] = opts

    job = Job(
        video_id=video.id,
        user_id=current_user.id,
        job_type="clips",
        mode=mode,
        params=params,
        pipeline_version="v2",
    )
    db.add(job)
    await db.flush()

    from app.workers.tasks import process_clips_task
    process_clips_task.delay(str(job.id))

    logger.info(
        "Clips render job created: %s (%d clips, from analyze %s) user=%s",
        job.id, len(moments), analyze_job.id, current_user.id,
    )
    return job
