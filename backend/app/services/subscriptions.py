from __future__ import annotations

from datetime import datetime, timezone

from app.models.user import User


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def subscription_is_active(user: User) -> bool:
    """Return True when a paid/admin-granted subscription is still valid.

    A NULL expiration means permanent/unlimited access for the selected plan.
    When an expiration is set and is in the past, the user falls back to the
    free plan without mutating the database during read operations.
    """
    expires_at = getattr(user, "subscription_expires_at", None)
    if expires_at is None:
        return True
    return _ensure_aware(expires_at) > utc_now()


def effective_plan(user: User) -> str:
    if getattr(user, "plan", "free") == "free":
        return "free"
    return user.plan if subscription_is_active(user) else "free"


def has_unlimited_access(user: User) -> bool:
    return bool(getattr(user, "is_super_admin", False)) or effective_plan(user) == "enterprise"
