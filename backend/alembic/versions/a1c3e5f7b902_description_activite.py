"""add description_activite to configuration

Revision ID: a1c3e5f7b902
Revises: d9e9f38b3a43
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

revision = "a1c3e5f7b902"
down_revision = "d9e9f38b3a43"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "configuration",
        sa.Column("description_activite", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column("configuration", "description_activite")
