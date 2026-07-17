import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Enum as SAEnum, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


def _utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)
    plan: Mapped[str] = mapped_column(
        SAEnum("free", "pro", "enterprise", name="user_plan"),
        default="free",
        server_default="free",
    )
    subscription_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # NULL = règle du plan, 0 = illimité, valeur positive = secondes max.
    video_duration_limit_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False
    )

    videos = relationship("Video", back_populates="user", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")

    @property
    def effective_plan(self) -> str:
        if self.plan == "free":
            return "free"
        expires_at = self.subscription_expires_at
        if expires_at is None:
            return self.plan
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return self.plan if expires_at > _utc_now() else "free"
