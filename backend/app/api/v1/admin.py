from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models.job import Job
from app.models.payment import Payment
from app.models.user import User
from app.models.video import Video
from app.services.auth import hash_password
from app.services.subscriptions import effective_plan
from app.services.plans import effective_video_duration_limit_s

router = APIRouter()
Plan = Literal["free", "pro", "enterprise"]


class AdminUserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    plan: str
    effective_plan: str
    subscription_expires_at: datetime | None = None
    is_admin: bool
    is_super_admin: bool
    is_active: bool
    video_duration_limit_s: int | None = None
    effective_video_duration_limit_s: int | None = None
    created_at: datetime
    videos_count: int = 0
    jobs_count: int = 0
    completed_jobs_count: int = 0
    failed_jobs_count: int = 0
    total_spent_xof: int = 0
    last_activity_at: datetime | None = None


class AdminStatsResponse(BaseModel):
    users_total: int
    active_users: int
    blocked_users: int
    admins: int
    free_users: int
    pro_users: int
    enterprise_users: int
    videos_total: int
    jobs_total: int
    completed_jobs: int
    failed_jobs: int
    pending_jobs: int
    processing_jobs: int
    revenue_xof: int


class GrantSubscriptionRequest(BaseModel):
    email: str
    plan: Plan = "enterprise"
    duration_days: int | None = Field(
        default=None,
        ge=1,
        le=3650,
        description="Nombre de jours d'accès. Vide/null = accès permanent.",
    )
    create_if_missing: bool = False
    initial_password: str | None = Field(default=None, min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)
    is_admin: bool | None = None
    is_active: bool | None = None
    video_duration_limit_minutes: int | None = Field(
        default=None,
        ge=0,
        le=10080,
        description="NULL = règle du plan, 0 = illimité, sinon durée max par vidéo en minutes.",
    )

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("Invalid email format")
        return value


class UserUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    is_admin: bool | None = None
    is_active: bool | None = None


class GrantSubscriptionResponse(BaseModel):
    user: AdminUserResponse
    message: str
    account_created: bool = False
    temporary_password: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _expires_from_duration(duration_days: int | None) -> datetime | None:
    if duration_days is None:
        return None
    return _now() + timedelta(days=duration_days)


async def _user_counts(db: AsyncSession, user_id: UUID) -> dict:
    videos_result = await db.execute(
        select(func.count()).select_from(Video).where(Video.user_id == user_id)
    )
    jobs_result = await db.execute(
        select(
            func.count(Job.id),
            func.coalesce(func.sum(case((Job.status == "completed", 1), else_=0)), 0),
            func.coalesce(func.sum(case((Job.status == "failed", 1), else_=0)), 0),
            func.max(Job.created_at),
        ).where(Job.user_id == user_id)
    )
    payments_result = await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.user_id == user_id,
            Payment.status == "completed",
        )
    )
    jobs_count, completed_jobs, failed_jobs, last_job_at = jobs_result.one()
    return {
        "videos_count": videos_result.scalar() or 0,
        "jobs_count": int(jobs_count or 0),
        "completed_jobs_count": int(completed_jobs or 0),
        "failed_jobs_count": int(failed_jobs or 0),
        "total_spent_xof": int(payments_result.scalar() or 0),
        "last_activity_at": last_job_at,
    }


async def _to_admin_response(db: AsyncSession, user: User) -> AdminUserResponse:
    counts = await _user_counts(db, user.id)
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        plan=user.plan,
        effective_plan=effective_plan(user),
        subscription_expires_at=user.subscription_expires_at,
        is_admin=bool(user.is_admin),
        is_super_admin=bool(getattr(user, "is_super_admin", False)),
        is_active=bool(user.is_active),
        video_duration_limit_s=getattr(user, "video_duration_limit_s", None),
        effective_video_duration_limit_s=effective_video_duration_limit_s(user, clips=True),
        created_at=user.created_at,
        **counts,
    )


async def _get_user_or_404(db: AsyncSession, user_id: UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("/stats", response_model=AdminStatsResponse)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    users_total = await db.scalar(select(func.count()).select_from(User)) or 0
    active_users = await db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0
    admins = await db.scalar(select(func.count()).select_from(User).where(User.is_admin.is_(True))) or 0
    free_users = await db.scalar(select(func.count()).select_from(User).where(User.plan == "free")) or 0
    pro_users = await db.scalar(select(func.count()).select_from(User).where(User.plan == "pro")) or 0
    enterprise_users = await db.scalar(select(func.count()).select_from(User).where(User.plan == "enterprise")) or 0
    videos_total = await db.scalar(select(func.count()).select_from(Video)) or 0
    jobs_total = await db.scalar(select(func.count()).select_from(Job)) or 0
    completed_jobs = await db.scalar(select(func.count()).select_from(Job).where(Job.status == "completed")) or 0
    failed_jobs = await db.scalar(select(func.count()).select_from(Job).where(Job.status == "failed")) or 0
    pending_jobs = await db.scalar(select(func.count()).select_from(Job).where(Job.status == "pending")) or 0
    processing_jobs = await db.scalar(select(func.count()).select_from(Job).where(Job.status == "processing")) or 0
    revenue_xof = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "completed")
    ) or 0
    return AdminStatsResponse(
        users_total=int(users_total),
        active_users=int(active_users),
        blocked_users=int(users_total - active_users),
        admins=int(admins),
        free_users=int(free_users),
        pro_users=int(pro_users),
        enterprise_users=int(enterprise_users),
        videos_total=int(videos_total),
        jobs_total=int(jobs_total),
        completed_jobs=int(completed_jobs),
        failed_jobs=int(failed_jobs),
        pending_jobs=int(pending_jobs),
        processing_jobs=int(processing_jobs),
        revenue_xof=int(revenue_xof),
    )


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users(
    q: str | None = Query(None, description="Recherche par email ou nom"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    stmt = select(User).order_by(User.created_at.desc()).limit(limit)
    if q:
        needle = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(func.lower(User.email).like(needle), func.lower(User.full_name).like(needle))
        )
    result = await db.execute(stmt)
    users = result.scalars().all()
    return [await _to_admin_response(db, user) for user in users]


@router.post("/subscriptions/grant", response_model=GrantSubscriptionResponse)
async def grant_subscription(
    data: GrantSubscriptionRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    account_created = False
    temporary_password = None
    if not user:
        if not data.create_if_missing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        temporary_password = data.initial_password or secrets.token_urlsafe(14)
        user = User(
            email=data.email,
            password_hash=hash_password(temporary_password),
            full_name=data.full_name,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        account_created = True

    user.plan = data.plan
    user.subscription_expires_at = _expires_from_duration(data.duration_days)
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.is_admin is not None:
        user.is_admin = data.is_admin
    if data.is_active is not None:
        user.is_active = data.is_active
    if "video_duration_limit_minutes" in data.model_fields_set:
        user.video_duration_limit_s = (
            None if data.video_duration_limit_minutes is None
            else data.video_duration_limit_minutes * 60
        )
    user.updated_at = _now()
    await db.flush()

    duration_label = "illimité" if data.duration_days is None else f"{data.duration_days} jour(s)"
    action = "créé et configuré" if account_created else "mis à jour"
    return GrantSubscriptionResponse(
        user=await _to_admin_response(db, user),
        message=f"{user.email} a été {action} en plan {data.plan} pour {duration_label}.",
        account_created=account_created,
        temporary_password=temporary_password,
    )


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: UUID,
    data: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    user = await _get_user_or_404(db, user_id)
    if user.id == admin.id and data.is_active is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate yourself")
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.is_admin is not None:
        user.is_admin = data.is_admin
    if data.is_active is not None:
        user.is_active = data.is_active
    user.updated_at = _now()
    await db.flush()
    return await _to_admin_response(db, user)


@router.post("/users/{user_id}/deactivate", response_model=AdminUserResponse)
async def deactivate_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    user = await _get_user_or_404(db, user_id)
    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate yourself")
    user.is_active = False
    user.updated_at = _now()
    await db.flush()
    return await _to_admin_response(db, user)


@router.post("/users/{user_id}/activate", response_model=AdminUserResponse)
async def activate_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    user = await _get_user_or_404(db, user_id)
    user.is_active = True
    user.updated_at = _now()
    await db.flush()
    return await _to_admin_response(db, user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    user = await _get_user_or_404(db, user_id)
    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself")
    await db.delete(user)
    await db.flush()
    return None
