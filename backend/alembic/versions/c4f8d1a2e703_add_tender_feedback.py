"""Add client feedback to company tenders."""

from alembic import op
import sqlalchemy as sa


revision = "c4f8d1a2e703"
down_revision = "b7c1e4a2d901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("company_tenders", sa.Column("feedback", sa.String(length=20), nullable=True))
    op.add_column("company_tenders", sa.Column("feedback_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("company_tenders", "feedback_at")
    op.drop_column("company_tenders", "feedback")
