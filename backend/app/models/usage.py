import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


def _utc_now():
    return datetime.now(timezone.utc)


class UsageRecord(Base):
    """Trace DURABLE d'une consommation de quota (ex. un montage lancé).

    Le quota mensuel ne peut pas se compter sur la table ``jobs``: supprimer
    une vidéo ou un job efface ces lignes en cascade, ce qui « rendait » des
    montages gratuits. ``job_id`` n'a donc volontairement PAS de clé
    étrangère: l'enregistrement survit à la suppression du job.

    ``refunded`` = la consommation est annulée (job échoué/annulé puis
    supprimé). Tant que le job existe, son statut fait foi.
    """

    __tablename__ = "usage_records"
    __table_args__ = (Index("ix_usage_user_kind_created", "user_id", "kind", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="montage")
    refunded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)
