"""Règles de plan centralisées — source de vérité unique des quotas.

TOUTES les limites par plan vivent ici (et sont surchargeables par env via
``settings``): durée max de la source, nombre de clips, vidéos par mois,
jobs simultanés. Aucun module ne doit coder ces valeurs en dur ailleurs.

L'application des quotas doit être ATOMIQUE: les endpoints verrouillent la
ligne utilisateur (SELECT ... FOR UPDATE) avant le check-then-create, sinon
deux requêtes simultanées passent toutes les deux sous la limite.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class PlanRules:
    name: str
    # Montage classique (upload court)
    max_video_duration_s: int
    max_videos_per_month: int | None      # None = illimité
    max_concurrent_jobs: int | None
    # Fonctionnalité Clips (vidéo longue -> shorts)
    clips_max_source_duration_s: int
    clips_max_per_job: int
    # B-roll IA autorisé sur ce plan
    ai_broll_allowed: bool


def _rules() -> dict[str, PlanRules]:
    return {
        "free": PlanRules(
            name="free",
            max_video_duration_s=settings.MAX_VIDEO_DURATION_FREE,
            max_videos_per_month=settings.MAX_VIDEOS_PER_MONTH_FREE,
            max_concurrent_jobs=2,
            clips_max_source_duration_s=settings.CLIPS_MAX_SOURCE_DURATION_FREE,
            clips_max_per_job=settings.CLIPS_MAX_PER_JOB_FREE,
            ai_broll_allowed=True,
        ),
        "pro": PlanRules(
            name="pro",
            max_video_duration_s=settings.MAX_VIDEO_DURATION_PRO,
            max_videos_per_month=None,
            max_concurrent_jobs=5,
            clips_max_source_duration_s=settings.CLIPS_MAX_SOURCE_DURATION_PRO,
            clips_max_per_job=settings.CLIPS_MAX_PER_JOB_PRO,
            ai_broll_allowed=True,
        ),
        "business": PlanRules(
            name="business",
            max_video_duration_s=settings.MAX_VIDEO_DURATION_PRO * 3,
            max_videos_per_month=None,
            max_concurrent_jobs=10,
            clips_max_source_duration_s=settings.CLIPS_MAX_SOURCE_DURATION_BUSINESS,
            clips_max_per_job=settings.CLIPS_MAX_PER_JOB_BUSINESS,
            ai_broll_allowed=True,
        ),
    }


def rules_for(plan: str | None) -> PlanRules:
    """Règles du *plan* (les plans inconnus retombent sur `free`)."""
    return _rules().get((plan or "free").lower(), _rules()["free"])
