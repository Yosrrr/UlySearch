"""F-028 drop legacy rappels sotradies

Revision ID: 04e587742500
Revises: 0657be41f855
Create Date: 2026-10-09 10:46:31.191155

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '04e587742500'
down_revision = '0657be41f855'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("sotradies", "rappel_j3_envoye")
    op.drop_column("sotradies", "rappel_j1_envoye")

def downgrade():
    op.add_column("sotradies", sa.Column("rappel_j3_envoye", sa.DateTime(), nullable=True))
    op.add_column("sotradies", sa.Column("rappel_j1_envoye", sa.DateTime(), nullable=True))