"""Add 'cancelled' to job_status enum and pipeline_version column.

Revision ID: 002
Revises: 001
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa


revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL: ALTER TYPE ... ADD VALUE doit s'exécuter hors transaction
    # quand on est sur une connexion en autocommit. Alembic gère le commit ici.
    op.execute("ALTER TYPE job_status ADD VALUE IF NOT EXISTS 'cancelled'")

    # Colonne pipeline_version pour différencier v1/v2 sans casser les jobs existants.
    op.add_column(
        "jobs",
        sa.Column(
            "pipeline_version",
            sa.String(length=10),
            nullable=False,
            server_default="v1",
        ),
    )


def downgrade() -> None:
    # PostgreSQL ne supporte pas la suppression de valeurs d'enum simplement.
    # On laisse la valeur 'cancelled' en place pour préserver l'historique.
    op.drop_column("jobs", "pipeline_version")
