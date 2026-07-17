"""Add founder role and per-account video duration quotas.

Revision ID: 004
Revises: 003
Create Date: 2026-07-17
"""
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_super_admin BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS video_duration_limit_s INTEGER NULL")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_video_duration_limit_nonnegative")
    op.execute("ALTER TABLE users ADD CONSTRAINT users_video_duration_limit_nonnegative CHECK (video_duration_limit_s IS NULL OR video_duration_limit_s >= 0) NOT VALID")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_video_duration_limit_nonnegative")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS video_duration_limit_s")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_super_admin")
