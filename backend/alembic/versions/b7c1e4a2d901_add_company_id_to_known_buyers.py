"""Add tenant ownership to known buyers."""

from alembic import op
import sqlalchemy as sa


revision = "b7c1e4a2d901"
down_revision = "9fcd11011821"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("known_buyers", sa.Column("company_id", sa.Integer(), nullable=True))
    op.create_index("ix_known_buyers_company_id", "known_buyers", ["company_id"])
    op.create_foreign_key(
        "fk_known_buyers_company_id",
        "known_buyers",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_known_buyers_company_id", "known_buyers", type_="foreignkey")
    op.drop_index("ix_known_buyers_company_id", table_name="known_buyers")
    op.drop_column("known_buyers", "company_id")
