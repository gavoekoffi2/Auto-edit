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
    max_video_duration_s: int | None       # None = illimité
    max_videos_per_month: int | None      # None = illimité
    max_concurrent_jobs: int | None
    # Fonctionnalité Clips (vidéo longue -> shorts)
    clips_max_source_duration_s: int | None  # None = illimité
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
        "enterprise": PlanRules(
            name="enterprise",
            max_video_duration_s=None,
            max_videos_per_month=None,
            max_concurrent_jobs=None,
            clips_max_source_duration_s=None,
            clips_max_per_job=100,
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


def rules_for_user(user) -> PlanRules:
    """Règles globales, avec priorité absolue au statut fondateur."""
    if bool(getattr(user, "is_super_admin", False)):
        return rules_for("enterprise")
    from app.services.subscriptions import effective_plan
    return rules_for(effective_plan(user))


def effective_video_duration_limit_s(user, *, clips: bool = False) -> int | None:
    """Durée maximale effective d'une source pour un compte.

    Priorité: super-admin > quota personnalisé > plan. La valeur personnalisée
    0 signifie explicitement « illimité »; NULL conserve les règles du plan.
    """
    if bool(getattr(user, "is_super_admin", False)):
        return None

    custom = getattr(user, "video_duration_limit_s", None)
    if custom is not None:
        return None if int(custom) == 0 else int(custom)

    from app.services.subscriptions import effective_plan

    rules = rules_for(effective_plan(user))
    return rules.clips_max_source_duration_s if clips else rules.max_video_duration_s
