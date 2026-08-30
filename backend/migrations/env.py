"""Alembic environment.

Takes the database URL and metadata from the application rather than from
alembic.ini, so there is exactly one definition of each and they cannot drift.

``render_as_batch`` is essential on SQLite: it lacks a full ALTER TABLE, so
Alembic emulates column changes by rebuilding the table. Without it, any
migration touching an existing column fails.
"""

from logging.config import fileConfig

from alembic import context

from app.db import Base, engine
from app import models  # noqa: F401  (registers every table on Base.metadata)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting."""
    context.configure(
        url=str(engine.url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
