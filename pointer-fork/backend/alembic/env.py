from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from src.infrastructure.config import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _sync_db_url() -> str:
    """Alembic runs synchronously; strip any async driver suffix from DB_URI."""
    url = settings.db_uri
    if not url:
        raise RuntimeError("DB_URI is not set")
    return (
        url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
           .replace("postgresql+psycopg_async://", "postgresql+psycopg://")
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_db_url(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section) or {}
    cfg["sqlalchemy.url"] = _sync_db_url()

    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
