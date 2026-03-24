"""Initial migration - create all tables

Revision ID: 001
Revises:
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    user_plan = postgresql.ENUM("free", "pro", "enterprise", name="user_plan", create_type=True)
    video_status = postgresql.ENUM("uploaded", "processing", "ready", "error", name="video_status", create_type=True)
    job_status = postgresql.ENUM("pending", "processing", "completed", "failed", name="job_status", create_type=True)
    payment_status = postgresql.ENUM("pending", "completed", "failed", name="payment_status", create_type=True)
    payment_plan = postgresql.ENUM("pro", "enterprise", name="payment_plan", create_type=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("plan", user_plan, server_default="free"),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "videos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("original_path", sa.String(1000), nullable=False),
        sa.Column("duration_s", sa.Float, nullable=True),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("status", video_status, server_default="uploaded"),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("videos.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("mode", sa.String(50), nullable=True),
        sa.Column("params", sa.JSON, nullable=True),
        sa.Column("status", job_status, server_default="pending"),
        sa.Column("progress", sa.Integer, server_default="0"),
        sa.Column("result", sa.JSON, nullable=True),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("completed_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("fedapay_tx_id", sa.String(255), nullable=True),
        sa.Column("amount", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(10)),
        sa.Column("status", payment_status, server_default="pending"),
        sa.Column("plan", payment_plan, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("jobs")
    op.drop_table("videos")
    op.drop_table("users")
    sa.Enum(name="user_plan").drop(op.get_bind())
    sa.Enum(name="video_status").drop(op.get_bind())
    sa.Enum(name="job_status").drop(op.get_bind())
    sa.Enum(name="payment_status").drop(op.get_bind())
    sa.Enum(name="payment_plan").drop(op.get_bind())
