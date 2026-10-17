"""cleanup drop sotradies raw_data

Revision ID: d9e9f38b3a43
Revises: 41b99ca668b4
Create Date: 2026-10-14 10:41:19.895992

"""
from sqlalchemy.dialects import postgresql
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd9e9f38b3a43'
down_revision = '41b99ca668b4'
branch_labels = None
depends_on = None

def upgrade():
    op.drop_column("sotradies", "raw_data")

def downgrade():
    op.add_column(
        "sotradies",
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )