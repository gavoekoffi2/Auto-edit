"""Durable quota usage records (monthly montage quota).

Revision ID: 005
Revises: 004
Create Date: 2026-09-24
"""
from alembic import op


revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS usage_records (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            job_id UUID NULL,
            kind VARCHAR(20) NOT NULL DEFAULT 'montage',
            refunded BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_usage_user_kind_created ON usage_records (user_id, kind, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_usage_records_job_id ON usage_records (job_id)")
    # Reprise de l'existant: chaque montage déjà lancé devient une consommation
    # (même identifiant que le job -> idempotent).
    op.execute("""
        INSERT INTO usage_records (id, user_id, job_id, kind, refunded, created_at)
        SELECT j.id, j.user_id, j.id, 'montage', FALSE, j.created_at
        FROM jobs j
        WHERE j.job_type <> 'clips'
        ON CONFLICT (id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS usage_records")
