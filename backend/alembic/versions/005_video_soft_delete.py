"""Soft delete des vidéos (quota mensuel non contournable).

Supprimer une vidéo efface ses FICHIERS et ses traitements, mais garde une
ligne « tombstone » (deleted_at) pour que le quota mensuel du plan Free ne
puisse pas être remis à zéro en supprimant puis réimportant.

Revision ID: 005
Revises: 004
Create Date: 2026-09-25
"""
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE videos ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ NULL")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_status_created ON jobs (status, created_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_jobs_status_created")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE videos DROP COLUMN IF EXISTS deleted_at")
