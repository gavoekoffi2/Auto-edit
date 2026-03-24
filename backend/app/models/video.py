import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Float, BigInteger, ForeignKey, Enum as SAEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


def _utc_now():
    return datetime.now(timezone.utc)


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = (
        Index("ix_videos_user_id", "user_id"),
        Index("ix_videos_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    original_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    duration_s: Mapped[float] = mapped_column(Float, nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        SAEnum("uploaded", "processing", "ready", "error", name="video_status"),
        default="uploaded",
        server_default="uploaded",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )

    user = relationship("User", back_populates="videos")
    jobs = relationship("Job", back_populates="video", cascade="all, delete-orphan")
