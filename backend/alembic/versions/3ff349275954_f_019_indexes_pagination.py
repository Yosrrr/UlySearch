"""F-019 indexes pagination

Revision ID: 3ff349275954
Revises: 04e587742500
Create Date: 2026-10-09 13:58:52.608821

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3ff349275954'
down_revision = '04e587742500'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_sotradies_date_detection", "sotradies", ["date_detection"]
    )
    op.create_index(
        "ix_company_tenders_company_decision_score",
        "company_tenders",
        ["company_id", "decision", "score"],
    )


def downgrade():
    op.drop_index(
        "ix_company_tenders_company_decision_score", table_name="company_tenders"
    )
    op.drop_index("ix_sotradies_date_detection", table_name="sotradies")