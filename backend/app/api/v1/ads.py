"""API « Pub explicative » — le moteur motion design sans vidéo source.

Flux:
  1. ``POST /ads/interview``  — entretien guidé (sans état serveur) jusqu'au brief complet.
  2. ``POST /ads/script``     — aperçu instantané du script + storyboard (optionnel).
  3. ``POST /ads``            — lance le rendu (Celery), quotas du plan appliqués.
  4. ``GET  /ads/{id}``       — progression; ``/video`` et ``/thumbnail`` une fois terminé.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.jobs import get_media_user, optional_security
from app.config import settings
from app.db.session import get_db
from app.explainer.interview import brief_from_interview, interview_turn
from app.explainer.templates import public_angles, public_templates
from app.models.ad_project import AdProject
from app.models.user import User
from app.services.errors import http_error
from app.services.media import ranged_file_response
from app.services.plans import rules_for_user
from app.services.storage import get_absolute_path

logger = logging.getLogger(__name__)
router = APIRouter()


class InterviewIn(BaseModel):
    brief: dict[str, Any] = Field(default_factory=dict)
    answer: Optional[str] = Field(default=None, max_length=2000)
    history: list[dict[str, str]] = Field(default_factory=list)


class AdCreate(BaseModel):
    brief: dict[str, Any]
    storyboard: Optional[dict[str, Any]] = None


class AdOut(BaseModel):
    id: UUID
    title: str
    template: str
    angle: str
    status: str
    progress: int
    stage: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    brief: dict[str, Any]
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


def _rid(request: Request) -> Optional[str]:
    return getattr(request.state, "request_id", None)


def _public_error(p: AdProject) -> Optional[str]:
    if not p.error_message:
        return None
    return "La création de la pub a échoué. Réessaie ou change légèrement ton brief." if p.error_message.startswith("[") else p.error_message


def _out(p: AdProject) -> AdOut:
    o = AdOut.model_validate(p)
    o.error_message = _public_error(p)
    return o


@router.get("/catalog")
async def catalog():
    return {"templates": public_templates(), "angles": public_angles()}


@router.post("/interview")
async def interview(body: InterviewIn, user: User = Depends(get_current_user)):
    # L'appel IA éventuel est bloquant (httpx sync): on le sort de la boucle async.
    import anyio
    return await anyio.to_thread.run_sync(lambda: interview_turn(body.brief, body.answer, body.history))


@router.post("/script")
async def preview_script(body: AdCreate, user: User = Depends(get_current_user)):
    import anyio
    from app.explainer.writer import write_storyboard
    brief = brief_from_interview(body.brief)
    board = await anyio.to_thread.run_sync(lambda: write_storyboard(brief))
    return {"brief": brief.to_dict(), "storyboard": board.to_dict()}


@router.post("", response_model=AdOut, status_code=status.HTTP_201_CREATED)
async def create_ad(body: AdCreate, request: Request, user: User = Depends(get_current_user),
                    db: AsyncSession = Depends(get_db)):
    brief = brief_from_interview(body.brief)
    if not (brief.business and brief.offer):
        raise HTTPException(status_code=400, detail="Le brief doit contenir au moins l'entreprise et l'offre.")
    # quotas atomiques (verrou sur la ligne utilisateur)
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    rules = rules_for_user(user)
    if rules.max_concurrent_jobs is not None:
        active = (await db.execute(select(func.count()).select_from(AdProject).where(
            AdProject.user_id == user.id, AdProject.status.in_(["pending", "processing"])))).scalar() or 0
        if active >= rules.max_concurrent_jobs:
            raise http_error("QUOTA_CONCURRENT_JOBS", _rid(request))
    if rules.name == "free":
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly = (await db.execute(select(func.count()).select_from(AdProject).where(
            AdProject.user_id == user.id, AdProject.created_at >= month_start,
            AdProject.status != "failed"))).scalar() or 0
        if monthly >= settings.ADS_MAX_PER_MONTH_FREE:
            raise http_error("QUOTA_MONTHLY_REACHED", _rid(request))
    proj = AdProject(user_id=user.id, title=(brief.business or "Ma pub")[:255], template=brief.template,
                     angle=brief.angle, brief=brief.to_dict(), storyboard=body.storyboard, status="pending")
    db.add(proj)
    await db.commit()
    await db.refresh(proj)
    from app.workers.tasks import process_ad_project_task
    process_ad_project_task.delay(str(proj.id))
    return _out(proj)


@router.get("", response_model=list[AdOut])
async def list_ads(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(AdProject).where(AdProject.user_id == user.id)
                             .order_by(AdProject.created_at.desc()).limit(50))).scalars().all()
    return [_out(p) for p in rows]


async def _get(db: AsyncSession, user_id, ad_id: UUID) -> AdProject:
    p = (await db.execute(select(AdProject).where(AdProject.id == ad_id, AdProject.user_id == user_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Pub introuvable")
    return p


@router.get("/{ad_id}", response_model=AdOut)
async def get_ad(ad_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return _out(await _get(db, user.id, ad_id))


@router.post("/{ad_id}/cancel", response_model=AdOut)
async def cancel_ad(ad_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    p = await _get(db, user.id, ad_id)
    if p.status in ("pending", "processing"):
        p.status = "cancelled"
        await db.commit(); await db.refresh(p)
    return _out(p)


@router.delete("/{ad_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ad(ad_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    p = await _get(db, user.id, ad_id)
    for key in ("video_path", "thumbnail_path"):
        rel = (p.result or {}).get(key)
        if rel:
            try:
                os.unlink(get_absolute_path(rel))
            except (OSError, ValueError):
                pass
    await db.delete(p)
    await db.commit()


async def _media(ad_id: UUID, key: str, media_type: str, request: Request, access_token: Optional[str],
                 credentials: Optional[HTTPAuthorizationCredentials], db: AsyncSession):
    user = await get_media_user(db, credentials, access_token)
    p = await _get(db, user.id, ad_id)
    rel = (p.result or {}).get(key) if p.status == "completed" else None
    if not rel:
        raise HTTPException(status_code=400, detail="La pub n'est pas encore prête.")
    path = get_absolute_path(rel)
    if not os.path.exists(path):
        raise http_error("FILE_EXPIRED", _rid(request))
    ext = "mp4" if media_type == "video/mp4" else "png"
    return ranged_file_response(path, request, media_type=media_type, filename=f"cutforge_pub_{ad_id}.{ext}")


@router.get("/{ad_id}/video")
async def ad_video(ad_id: UUID, request: Request, access_token: Optional[str] = Query(None),
                   credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
                   db: AsyncSession = Depends(get_db)):
    return await _media(ad_id, "video_path", "video/mp4", request, access_token, credentials, db)


@router.get("/{ad_id}/thumbnail")
async def ad_thumbnail(ad_id: UUID, request: Request, access_token: Optional[str] = Query(None),
                       credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
                       db: AsyncSession = Depends(get_db)):
    return await _media(ad_id, "thumbnail_path", "image/png", request, access_token, credentials, db)
