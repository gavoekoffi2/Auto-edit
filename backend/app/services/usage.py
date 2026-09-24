"""Décompte durable du quota mensuel de montages (voir ``UsageRecord``)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.usage import UsageRecord

MONTAGE = "montage"
NOT_CHARGED_STATUSES = ("failed", "cancelled")


def month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def record_montage(db: AsyncSession, user_id, job_id) -> None:
    """Enregistre la consommation d'un montage (à appeler avec la création du job)."""
    db.add(UsageRecord(user_id=user_id, job_id=job_id, kind=MONTAGE))


async def count_monthly_montages(db: AsyncSession, user_id) -> int:
    """Montages consommés ce mois-ci.

    Un montage compte tant qu'il n'est pas remboursé ET que son job (s'il
    existe encore) n'a pas échoué / été annulé. Un job supprimé continue de
    compter: supprimer ses vidéos ne rend plus de quota.
    """
    stmt = (
        select(func.count(UsageRecord.id))
        .select_from(UsageRecord)
        .outerjoin(Job, Job.id == UsageRecord.job_id)
        .where(
            UsageRecord.user_id == user_id,
            UsageRecord.kind == MONTAGE,
            UsageRecord.created_at >= month_start(),
            UsageRecord.refunded.is_(False),
            or_(Job.id.is_(None), Job.status.notin_(NOT_CHARGED_STATUSES)),
        )
    )
    return int((await db.execute(stmt)).scalar() or 0)


async def refund_before_delete(db: AsyncSession, jobs: Iterable[Job]) -> None:
    """À appeler AVANT de supprimer des jobs: les montages échoués/annulés
    restent non décomptés une fois leur ligne Job disparue."""
    ids = [j.id for j in jobs if j.status in NOT_CHARGED_STATUSES]
    if not ids:
        return
    await db.execute(
        update(UsageRecord)
        .where(and_(UsageRecord.job_id.in_(ids), UsageRecord.kind == MONTAGE))
        .values(refunded=True)
        .execution_options(synchronize_session=False)
    )
