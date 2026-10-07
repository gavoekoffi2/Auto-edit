import os
import logging
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.media import ranged_file_response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.models.user import User
from app.models.video import Video
from app.models.job import Job
from app.schemas.job import JobCreate, JobResponse
from app.api.v1.modes import FAMILIES, MODE_DEFINITIONS, DEFAULT_MODE
from app.api.deps import get_current_user
from app.services.auth import decode_token, token_matches_password
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
    if user is None or not user.is_active or not token_matches_password(payload, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user




@router.get("/styles")
async def list_styles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Catalogue des styles du Studio + les derniers styles utilisés par l'utilisateur
    (le moteur ne les réutilisera pas tout de suite) + son dernier logo."""
    from app.explainer.styles import public_styles
    from app.services.brand_assets import latest_logo

    recent = await _style_history(db, current_user.id, limit=8)
    return {"styles": public_styles(), "recent": recent, "logo_asset": latest_logo(str(current_user.id))}


@router.post("/assets/logo", status_code=status.HTTP_201_CREATED)
async def upload_logo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Logo du client (PNG/JPG/WEBP, 5 Mo max): détouré et posé sur chaque montage Studio."""
    from app.services.brand_assets import MAX_LOGO_BYTES, save_logo

    data = await file.read(MAX_LOGO_BYTES + 1)
    try:
        aid = save_logo(str(current_user.id), data, file.content_type or "")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"asset_id": aid}


@router.get("/assets/logo/{asset_id}")
async def get_logo(
    asset_id: str,
    request: Request,
    access_token: Optional[str] = Query(default=None),
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_security),
    db: AsyncSession = Depends(get_db),
):
    from fastapi.responses import FileResponse
    from app.services.brand_assets import logo_path_for

    user = await get_media_user(db, credentials, access_token)
    path = logo_path_for(str(user.id), asset_id)
    if not path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Logo introuvable")
    return FileResponse(path)


async def _style_history(db: AsyncSession, user_id, limit: int = 30) -> list[dict]:
    """Empreintes des styles des derniers montages Studio (plus récent d'abord)."""
    rows = await db.execute(
        select(Job.result).where(Job.user_id == user_id, Job.mode == "studio_facecam",
                                 Job.status == "completed").order_by(Job.created_at.desc()).limit(limit)
    )
    out = []
    for (res,) in rows.all():
        st = (res or {}).get("style") if isinstance(res, dict) else None
        if isinstance(st, dict) and isinstance(st.get("fingerprint"), dict):
            out.append({**st["fingerprint"], "name": st.get("name")})
    return out


@router.get("/modes")
async def list_modes():
    """Liste les modes de montage disponibles + leurs defaults d'options.

    Endpoint public — le frontend l'utilise pour rendre dynamiquement le
    selecteur de modes sans dupliquer la liste cote TS. `default_mode` indique
    le choix par defaut (Collage Premium), `families` l'ordre d'affichage des
    onglets du sélecteur.
    """
    return {"modes": MODE_DEFINITIONS, "default_mode": DEFAULT_MODE,
            "families": FAMILIES}


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    data: JobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify video belongs to user
    result = await db.execute(
        select(Video).where(Video.id == data.video_id, Video.user_id == current_user.id,
                            Video.deleted_at.is_(None))
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vidéo introuvable")

    # Durée autorisée par le plan (une vidéo importée pour Clips, dont la
    # limite est plus longue, ne doit pas servir à contourner celle du montage).
    # Shorts face caméra: rushes supplémentaires, tous à l'utilisateur et encore sur disque.
    rushes: list[Video] = [video]
    if (data.mode or "") == "shorts_facecam" and data.extra_video_ids:
        seen = {video.id}
        for vid in data.extra_video_ids:
            if vid in seen:
                continue
            seen.add(vid)
            r = (await db.execute(select(Video).where(Video.id == vid, Video.user_id == current_user.id,
                                                      Video.deleted_at.is_(None)))).scalar_one_or_none()
            if not r:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Un des rushes est introuvable")
            if not os.path.exists(get_absolute_path(r.original_path)):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"Le fichier du rush « {r.title} » a expiré. Réimporte-le.")
            rushes.append(r)
    total_s = sum((r.duration_s or 0) for r in rushes)

    from app.services.plans import effective_video_duration_limit_s
    limit_s = effective_video_duration_limit_s(current_user, clips=False)
    if limit_s is not None and len(rushes) > 1 and total_s > limit_s + 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"Ton plan permet de monter {limit_s / 60:g} min de rushes au total "
                    f"(ces {len(rushes)} rushes durent {total_s / 60:.1f} min)."),
        )
    if limit_s is not None and (video.duration_s or 0) > limit_s + 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"Ton plan permet de monter des vidéos de {limit_s / 60:g} min maximum "
                    f"(celle-ci dure {(video.duration_s or 0) / 60:.1f} min). "
                    "Utilise la fonction Clips ou passe à un plan supérieur."),
        )

    # Verify video file exists on disk
    video_file = get_absolute_path(video.original_path)
    if not os.path.exists(video_file):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le fichier de cette vidéo a expiré. Réimporte-la.",
        )

    # Limite de jobs simultanés — via les règles CENTRALES (`app.services.plans`).
    # L'ancien contrôle lisait `current_user.plan` en dur et plafonnait à 2: un
    # fondateur (super-admin) ou un abonné Pro dont la colonne `plan` n'avait pas
    # encore basculé restait bloqué à 2 montages, et deux requêtes simultanées
    # passaient toutes les deux sous la limite (pas de verrou).
    from app.services.plans import rules_for_user

    rules = rules_for_user(current_user)
    if rules.max_concurrent_jobs is not None:
        # Verrou de la ligne utilisateur: rend le check-then-create atomique,
        # comme sur la route Clips.
        await db.execute(
            select(User.id).where(User.id == current_user.id).with_for_update()
        )
        count_result = await db.execute(
            select(func.count()).select_from(Job).where(
                Job.user_id == current_user.id,
                Job.status.in_(["pending", "processing"]),
            )
        )
        active_count = count_result.scalar() or 0
        if active_count >= rules.max_concurrent_jobs:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(f"Ton plan autorise {rules.max_concurrent_jobs} montage(s) "
                        "en parallèle. Attends la fin d'un traitement ou passe à "
                        "l'offre supérieure."),
            )

    # Merge params + options dans le payload du job (options prennent le pas)
    merged_params: dict = dict(data.params or {})
    if data.options is not None:
        # exclude_none=True pour ne pas écraser des défauts par des None
        opts = data.options.model_dump(exclude_none=True)
        if opts:
            merged_params["options"] = opts

    # Studio: le moteur doit connaître les styles déjà utilisés pour ne pas se répéter,
    # et l'utilisateur pour retrouver son logo.
    if (data.mode or "") == "studio_facecam":
        merged_params["style_history"] = await _style_history(db, current_user.id)
        merged_params["user_id"] = str(current_user.id)

    if (data.mode or "") == "shorts_facecam":
        # chemins relatifs (résolus par le worker), dans l'ordre d'import
        merged_params["rush_paths"] = [r.original_path for r in rushes]
        merged_params["user_id"] = str(current_user.id)

    from app.config import settings
    pipeline_version = data.pipeline_version or settings.PIPELINE_VERSION
    if (data.mode or "") in ("studio_facecam", "shorts_facecam"):
        pipeline_version = "v2"  # moteurs Studio / Shorts = pipeline v2 uniquement
    from app.processing.longform import LONGFORM_MODES
    if (data.mode or "") in LONGFORM_MODES:
        pipeline_version = "v2"  # moteur YouTube long = pipeline v2 uniquement

    # Même pour les clients API qui omettent `mode`, le moteur produit par
    # défaut doit être explicite et persistant dans le job.
    resolved_mode = data.mode or DEFAULT_MODE
    job = Job(
        video_id=data.video_id,
        user_id=current_user.id,
        job_type=data.job_type,
        mode=resolved_mode,
        params=merged_params,
        pipeline_version=pipeline_version,
    )
    db.add(job)
    await db.flush()

    # Trigger async processing. Le task_id Celery est FORCÉ à l'id du job: sans
    # ça, `celery.control.revoke(job.id)` (route d'annulation) ciblait un
    # identifiant qui n'existait pas et l'annulation ne faisait rien — la tâche
    # continuait et écrasait le statut « cancelled » par « completed ».
    from app.workers.tasks import process_video_task

    process_video_task.apply_async(args=[str(job.id)], task_id=str(job.id))

    logger.info(
        f"Job created: {job.id} type={data.job_type} mode={resolved_mode} "
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Traitement introuvable")
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Traitement introuvable")

    if job.status not in ("pending", "processing"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce traitement est déjà terminé.",
        )

    # Révoque la tâche Celery — en file d'attente ET en cours d'exécution.
    # `terminate=True` ne fait rien sur une tâche encore en file, mais tue le
    # worker qui la traite déjà: avant, un job « processing » n'était jamais
    # révoqué, donc l'annulation ne libérait ni le worker ni le quota.
    try:
        from app.workers.celery_app import celery_app
        celery_app.control.revoke(str(job.id), terminate=True, signal="SIGTERM")
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Traitement introuvable")
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Traitement introuvable")

    if job.status != "completed" or not job.result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le montage n'est pas encore terminé.",
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Traitement introuvable")
    if job.status != "completed" or not job.result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le montage n'est pas encore terminé.",
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
