"""Table ad_projects — moteur « Pub explicative » (motion design sans vidéo source).

Revision ID: 006
Revises: 005
Create Date: 2026-09-27
"""
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS ad_projects (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title VARCHAR(255) NOT NULL DEFAULT '',
            template VARCHAR(40) NOT NULL DEFAULT 'prestige',
            angle VARCHAR(40) NOT NULL DEFAULT 'douleur',
            brief JSON NOT NULL,
            storyboard JSON NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            progress INTEGER NOT NULL DEFAULT 0,
            stage VARCHAR(120) NULL,
            result JSON NULL,
            error_message VARCHAR(2000) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NULL,
            completed_at TIMESTAMPTZ NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ad_projects_user_created ON ad_projects (user_id, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ad_projects_status ON ad_projects (status)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ad_projects")
