"""Projet « Pub explicative » (moteur motion design sans vidéo source)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utc_now():
    return datetime.now(timezone.utc)


class AdProject(Base):
    __tablename__ = "ad_projects"
    __table_args__ = (
        Index("ix_ad_projects_user_created", "user_id", "created_at"),
        Index("ix_ad_projects_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    template: Mapped[str] = mapped_column(String(40), nullable=False, default="prestige")
    angle: Mapped[str] = mapped_column(String(40), nullable=False, default="douleur")
    brief: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    storyboard: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # pending | processing | completed | failed | cancelled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    stage: Mapped[str | None] = mapped_column(String(120), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
