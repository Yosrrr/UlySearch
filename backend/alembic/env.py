"""
Alembic environment configuration.
Utilise la même DATABASE_URL que l'application, importe tous les modèles
SQLAlchemy pour l'autogenerate, et supporte les migrations online et offline.
"""
from logging.config import fileConfig
import sys
from pathlib import Path
from app.models import (
    user,
    sotradies,
    sent_log,
    audit_log,
    known_buyer,
    system_action_log,
    configuration,
    commercial,
    pipeline_log,  # ← ajouter
)

from sqlalchemy import engine_from_config, pool
from alembic import context

# Ajouter le dossier parent (backend/) au path pour importer app.*
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.core.database import Base

# Import de TOUS les modèles — obligatoire pour que Base.metadata les connaisse
from app.models import (
    user,
    sotradies,
    sent_log,
    audit_log,
    known_buyer,
    system_action_log,
    configuration,
)

# Configuration Alembic
config = context.config

# Surcharge de l'URL DB depuis settings (au lieu de alembic.ini)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata cible pour autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Mode offline : génère le SQL sans connexion réelle à la DB."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Mode online : exécute les migrations directement sur la DB."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()