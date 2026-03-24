import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Integer, ForeignKey, Enum as SAEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    job_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # transcribe, silence_removal, scene_detect, effects, export, pipeline
    mode: Mapped[str] = mapped_column(
        String(50), nullable=True
    )  # tiktok, youtube, podcast
    params: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)
    status: Mapped[str] = mapped_column(
        SAEnum("pending", "processing", "completed", "failed", name="job_status"),
        default="pending",
        server_default="pending",
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    result: Mapped[dict] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    video = relationship("Video", back_populates="jobs")
    user = relationship("User", back_populates="jobs")
