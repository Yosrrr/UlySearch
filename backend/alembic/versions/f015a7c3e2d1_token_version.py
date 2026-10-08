"""F-015 : token_version sur users

Revision ID: f015a7c3e2d1
Revises: d9e8f7a6b5c4
"""
from alembic import op
import sqlalchemy as sa

revision = "f015a7c3e2d1"
down_revision = "d9e8f7a6b5c4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("users", "token_version")
