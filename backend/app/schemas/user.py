import re
from pydantic import BaseModel, field_validator
from uuid import UUID
from datetime import datetime
from typing import Optional

from app.services.subscriptions import effective_plan
from app.services.plans import effective_video_duration_limit_s


def _is_configured_admin(obj) -> bool:
    """Comptes listés dans ADMIN_EMAILS: mêmes droits que dans app.api.deps."""
    from app.config import settings
    return (getattr(obj, "email", "") or "").lower() in settings.admin_email_set


_PASSWORD_MAX = 128


def _check_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Le mot de passe doit contenir au moins 8 caractères")
    if len(v) > _PASSWORD_MAX:
        raise ValueError("Mot de passe trop long (128 caractères max.)")
    if not re.search(r"[A-Za-z]", v):
        raise ValueError("Le mot de passe doit contenir au moins une lettre")
    if not re.search(r"[0-9]", v):
        raise ValueError("Le mot de passe doit contenir au moins un chiffre")
    return v


class UserCreate(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("Adresse email invalide")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _check_password(v)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 200:
                raise ValueError("Nom trop long")
        return v


class UserLogin(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: Optional[str]
    plan: str
    effective_plan: str
    subscription_expires_at: Optional[datetime] = None
    is_admin: bool = False
    is_super_admin: bool = False
    video_duration_limit_s: Optional[int] = None
    effective_video_duration_limit_s: Optional[int] = None
    created_at: datetime

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        if not isinstance(obj, dict):
            data = {
                "id": obj.id,
                "email": obj.email,
                "full_name": obj.full_name,
                "plan": obj.plan,
                "effective_plan": effective_plan(obj),
                "subscription_expires_at": obj.subscription_expires_at,
                "is_admin": bool(getattr(obj, "is_admin", False)) or _is_configured_admin(obj),
                "is_super_admin": bool(getattr(obj, "is_super_admin", False)) or _is_configured_admin(obj),
                "video_duration_limit_s": getattr(obj, "video_duration_limit_s", None),
                "effective_video_duration_limit_s": effective_video_duration_limit_s(obj),
                "created_at": obj.created_at,
            }
            return super().model_validate(data, *args, **kwargs)
        return super().model_validate(obj, *args, **kwargs)

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _check_password(v)


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _check_password(v)
