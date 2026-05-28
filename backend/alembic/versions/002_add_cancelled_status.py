"""Add 'cancelled' value to the job_status enum

Revision ID: 002
Revises: 001
Create Date: 2024-01-15
"""
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADD VALUE cannot run inside a transaction block on older PostgreSQL, so
    # commit the current transaction first, then run it autonomously.
    op.execute("COMMIT")
    op.execute("ALTER TYPE job_status ADD VALUE IF NOT EXISTS 'cancelled'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum type.
    pass
