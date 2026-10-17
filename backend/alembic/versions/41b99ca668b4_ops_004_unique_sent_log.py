"""OPS-004 unique sent_log

Revision ID: 41b99ca668b4
Revises: 904144568633
Create Date: 2026-10-13 13:39:18.172858

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '41b99ca668b4'
down_revision = '904144568633'
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
        DELETE FROM sent_log a USING sent_log b
        WHERE a.id > b.id
          AND a.company_tender_id IS NOT NULL
          AND a.company_tender_id = b.company_tender_id
          AND a.canal = b.canal
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_sent_log_company_tender_canal
        ON sent_log (company_tender_id, canal)
        WHERE company_tender_id IS NOT NULL
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_sent_log_company_tender_canal")