import re
from pydantic import BaseModel, field_validator
from uuid import UUID
from datetime import datetime
from typing import Optional

from app.services.subscriptions import effective_plan
from app.services.plans import effective_video_duration_limit_s


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
            raise ValueError("Invalid email format")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one number")
        return v

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 200:
                raise ValueError("Name too long")
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
                "is_admin": bool(getattr(obj, "is_admin", False)),
                "is_super_admin": bool(getattr(obj, "is_super_admin", False)),
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
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one number")
        return v


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one number")
        return v
