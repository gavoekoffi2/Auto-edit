"""API du moteur d'illustration — analyse et aperçu, sans rendre une seule frame.

Le **rendu** reste l'affaire de l'API Jobs existante : une illustration n'a de
sens qu'à l'intérieur d'un montage, et dupliquer le pipeline ici créerait un
second chemin à maintenir. Ces routes servent ce que l'API Jobs ne peut pas
donner : savoir ce que le moteur ferait **avant** de lancer un rendu.

* ``GET  /illustrations/capabilities`` — ce que sait faire ce déploiement
* ``POST /illustrations/analyze``      — comprendre un passage
* ``POST /illustrations/storyboard``   — le plan complet, sans rendu
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.job import Job
from app.models.user import User
from app.services.storage import get_output_dir

logger = logging.getLogger(__name__)
router = APIRouter()

# Transcripts the pipeline persists, most word-accurate first.
_VU_FILENAMES = ("engine_vu.json", "transcript_vu.json", "vu.json")


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000,
                      description="Un passage de discours à comprendre.")


class StoryboardRequest(BaseModel):
    """Fournir SOIT un transcript mot-à-mot, SOIT le job qui l'a produit."""
    transcript: Optional[Dict[str, Any]] = Field(
        default=None, description="Transcript au format vu (segments + words).")
    job_id: Optional[UUID] = Field(
        default=None, description="Job terminé dont on réutilise le transcript.")
    style: Optional[str] = None
    intensity: Optional[str] = None
    ai_mode: Optional[str] = None
    aspect: Optional[str] = None


@router.get("/capabilities")
async def capabilities(_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Ce que ce déploiement sait réellement faire."""
    from app.illustration_engine.bridge import capabilities as engine_capabilities
    return engine_capabilities()


@router.post("/analyze")
async def analyze(payload: AnalyzeRequest,
                  _user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Comment le moteur lit un passage: figure de discours et matière extraite."""
    from app.illustration_engine.bridge import analyze_passage
    return analyze_passage(payload.text)


async def _transcript_for_job(job_id: UUID, user: User,
                              db: AsyncSession) -> Dict[str, Any]:
    """The word-level transcript a finished job produced, ownership checked."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None or str(job.user_id) != str(user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Job introuvable.")
    output_dir = get_output_dir(str(user.id), str(job_id))
    for name in _VU_FILENAMES:
        path = os.path.join(output_dir, name)
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as handle:
                    return json.load(handle)
            except (OSError, ValueError) as exc:
                logger.warning("[illustrations] transcript illisible %s: %s",
                               path, exc)
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Ce job n'a pas encore de transcript mot-à-mot exploitable.")


@router.post("/storyboard")
async def storyboard(payload: StoryboardRequest,
                     user: User = Depends(get_current_user),
                     db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Le plan d'illustration, sans rendre une seule frame.

    Permet de montrer à l'utilisateur ce qui sera illustré — et de laisser
    régler le style et l'intensité — avant de dépenser du CPU.
    """
    if payload.transcript is None and payload.job_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Fournissez « transcript » ou « job_id ».")

    vu = payload.transcript
    if vu is None:
        vu = await _transcript_for_job(payload.job_id, user, db)
    if not isinstance(vu, dict) or not vu.get("segments"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Transcript invalide: « segments » est requis.")

    from app.illustration_engine.bridge import plan_only

    try:
        return plan_only(vu, style=payload.style, intensity=payload.intensity,
                         ai_mode=payload.ai_mode, aspect=payload.aspect)
    except Exception as exc:  # noqa: BLE001 - a preview must never 500 silently
        logger.exception("[illustrations] storyboard failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storyboard impossible: {exc}") from exc
