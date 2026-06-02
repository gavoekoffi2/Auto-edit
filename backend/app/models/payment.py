import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Integer, ForeignKey, Enum as SAEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


def _utc_now():
    return datetime.now(timezone.utc)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_user_id", "user_id"),
        Index("ix_payments_fedapay_tx", "fedapay_tx_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    fedapay_tx_id: Mapped[str] = mapped_column(String(255), nullable=True, unique=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="XOF")
    status: Mapped[str] = mapped_column(
        SAEnum("pending", "completed", "failed", name="payment_status"),
        default="pending",
        server_default="pending",
    )
    plan: Mapped[str] = mapped_column(
        SAEnum("pro", "enterprise", name="payment_plan"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False
    )

    user = relationship("User", back_populates="payments")
