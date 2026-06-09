from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models.user import User
from app.models.video import Video
from app.services.auth import hash_password
from app.services.subscriptions import effective_plan

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
    is_active: bool
    created_at: datetime
    videos_count: int = 0


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

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("Invalid email format")
        return value


class GrantSubscriptionResponse(BaseModel):
    user: AdminUserResponse
    message: str
    account_created: bool = False
    temporary_password: str | None = None


def _expires_from_duration(duration_days: int | None) -> datetime | None:
    if duration_days is None:
        return None
    return datetime.now(timezone.utc) + timedelta(days=duration_days)


async def _to_admin_response(db: AsyncSession, user: User) -> AdminUserResponse:
    count_result = await db.execute(
        select(func.count()).select_from(Video).where(Video.user_id == user.id)
    )
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        plan=user.plan,
        effective_plan=effective_plan(user),
        subscription_expires_at=user.subscription_expires_at,
        is_admin=bool(user.is_admin),
        is_active=bool(user.is_active),
        created_at=user.created_at,
        videos_count=count_result.scalar() or 0,
    )


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users(
    q: str | None = Query(None, description="Recherche par email ou nom"),
    limit: int = Query(50, ge=1, le=200),
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
    admin: User = Depends(get_current_admin),
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
    if data.is_admin is not None:
        user.is_admin = data.is_admin
    if data.is_active is not None:
        user.is_active = data.is_active
    user.updated_at = datetime.now(timezone.utc)
    await db.flush()

    duration_label = "illimité" if data.duration_days is None else f"{data.duration_days} jour(s)"
    action = "créé et configuré" if account_created else "mis à jour"
    return GrantSubscriptionResponse(
        user=await _to_admin_response(db, user),
        message=f"{user.email} a été {action} en plan {data.plan} pour {duration_label}.",
        account_created=account_created,
        temporary_password=temporary_password,
    )


@router.post("/users/{user_id}/deactivate", response_model=AdminUserResponse)
async def deactivate_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if user_id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate yourself")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_active = False
    user.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return await _to_admin_response(db, user)
