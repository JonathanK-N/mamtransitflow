"""
TransitFlow — environnement Alembic
Auteur : Jonathan K-N

Branche Alembic sur nos propres modeles (backend/models_registry.py) et sur
l adresse de base de donnees definie dans backend/settings.py, plutot que
de dupliquer cette configuration dans alembic.ini.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Permet d importer le package "backend" quand alembic est lance depuis la racine du projet.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.models_registry import Base  # noqa: E402
from backend.settings import settings  # noqa: E402

config = context.config
config.set_main_option('sqlalchemy.url', settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}),
                                      prefix='sqlalchemy.', poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
