"""Add encrypted accounts for private scraping sources."""

from alembic import op
import sqlalchemy as sa


revision = "d9e8f7a6b5c4"
down_revision = "c4f8d1a2e703"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_source_id", sa.Integer(), nullable=False),
        sa.Column("login", sa.String(length=255), nullable=False),
        sa.Column("password_encrypted", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_source_id"], ["company_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_source_id", name="uq_source_account_company_source"),
    )
    op.create_index("ix_source_accounts_company_source_id", "source_accounts", ["company_source_id"])


def downgrade() -> None:
    op.drop_index("ix_source_accounts_company_source_id", table_name="source_accounts")
    op.drop_table("source_accounts")