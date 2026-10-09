"""fix created_at not null

Revision ID: 904144568633
Revises: 3ff349275954
Create Date: 2026-10-09 14:33:49.861926

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '904144568633'
down_revision = '3ff349275954'
branch_labels = None
depends_on = None


def upgrade():
    # Sécurité : remplir les NULL avant d'imposer la contrainte
    op.execute(
        "UPDATE commercials SET created_at = NOW() AT TIME ZONE 'UTC' "
        "WHERE created_at IS NULL"
    )
    op.execute(
        "UPDATE company_sources SET created_at = NOW() AT TIME ZONE 'UTC' "
        "WHERE created_at IS NULL"
    )
    op.execute(
        "UPDATE company_tenders SET created_at = NOW() AT TIME ZONE 'UTC' "
        "WHERE created_at IS NULL"
    )

    op.alter_column(
        "commercials", "created_at",
        existing_type=sa.DateTime(), nullable=False,
    )
    op.alter_column(
        "company_sources", "created_at",
        existing_type=sa.DateTime(), nullable=False,
    )
    op.alter_column(
        "company_tenders", "created_at",
        existing_type=sa.DateTime(), nullable=False,
    )


def downgrade():
    op.alter_column(
        "company_tenders", "created_at",
        existing_type=sa.DateTime(), nullable=True,
    )
    op.alter_column(
        "company_sources", "created_at",
        existing_type=sa.DateTime(), nullable=True,
    )
    op.alter_column(
        "commercials", "created_at",
        existing_type=sa.DateTime(), nullable=True,
    )