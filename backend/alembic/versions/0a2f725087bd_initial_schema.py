"""initial schema

Revision ID: 0a2f725087bd
Revises:
Create Date: 2026-08-21 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0a2f725087bd"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "configuration",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("score_decision_threshold", sa.Integer(), nullable=False),
        sa.Column("score_instant_alert_threshold", sa.Integer(), nullable=False),
        sa.Column("categories", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("exclusion_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("active_sources", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("assignment_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("derniere_modification", sa.DateTime(), nullable=False),
        sa.Column("modifie_par", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "known_buyers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nom_acheteur", sa.String(length=500), nullable=False),
        sa.Column("variantes", sa.Text(), nullable=True),
        sa.Column("client_sotradies", sa.String(length=10), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "sotradies",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("objet", sa.Text(), nullable=False),
        sa.Column("acheteur", sa.String(length=500), nullable=False),
        sa.Column("categorie", sa.String(length=255), nullable=True),
        sa.Column("date_publication", sa.DateTime(), nullable=True),
        sa.Column("date_limite", sa.DateTime(), nullable=True),
        sa.Column("budget_estime", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("lien", sa.Text(), nullable=False),
        sa.Column("date_detection", sa.DateTime(), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("statut", sa.String(length=30), nullable=False),
        sa.Column("commercial_assigne", sa.String(length=255), nullable=True),
        sa.Column("score_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("acheteur_connu", sa.String(length=10), nullable=True),
        sa.Column("date_derniere_action", sa.DateTime(), nullable=True),
        sa.Column("rappel_j3_envoye", sa.DateTime(), nullable=True),
        sa.Column("rappel_j1_envoye", sa.DateTime(), nullable=True),
        sa.Column("description_detaillee", sa.Text(), nullable=True),
        sa.Column("budget_detecte", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("duree_execution", sa.String(length=50), nullable=True),
        sa.Column("montant_cautionnement", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("type_marche", sa.String(length=50), nullable=True),
        sa.Column("procedure_passation", sa.String(length=150), nullable=True),
        sa.Column("region_execution", sa.String(length=150), nullable=True),
        sa.Column("date_debut_execution", sa.Date(), nullable=True),
        sa.Column("date_ouverture_offres", sa.Date(), nullable=True),
        sa.Column("lieu_ouverture_offres", sa.String(length=255), nullable=True),
        sa.Column("caractere_prix", sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "system_action_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("utilisateur_email", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("date_action", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("nom", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("profil", sa.String(length=20), nullable=False),
        sa.Column("actif", sa.Boolean(), nullable=False),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sotradies_id", sa.String(length=64), nullable=True),
        sa.Column("utilisateur_email", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("date_action", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["sotradies_id"], ["sotradies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "sent_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sotradies_id", sa.String(length=64), nullable=False),
        sa.Column("commercial", sa.String(length=255), nullable=False),
        sa.Column("canal", sa.String(length=20), nullable=False),
        sa.Column("date_envoi", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["sotradies_id"], ["sotradies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("sent_log")
    op.drop_table("audit_log")
    op.drop_table("users")
    op.drop_table("system_action_log")
    op.drop_table("sotradies")
    op.drop_table("known_buyers")
    op.drop_table("configuration")