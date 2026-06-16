"""Add 'compressing' to video_status enum.

Revision ID: 004
Revises: 003
Create Date: 2026-06-16
"""
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADD VALUE IF NOT EXISTS is idempotent and safe to re-run.
    # PostgreSQL does not allow removing enum values, so downgrade is a no-op.
    op.execute(
        "ALTER TYPE video_status ADD VALUE IF NOT EXISTS 'compressing' AFTER 'uploaded'"
    )


def downgrade() -> None:
    # Cannot drop individual values from a Postgres enum without recreating the
    # type and all columns that reference it. Accept the new value permanently.
    pass
