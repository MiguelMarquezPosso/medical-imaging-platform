"""Alembic environment for the Medical Imaging Service."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.domains.sync.infrastructure.models import Base as SyncBase  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = SyncBase.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema=settings.DB_SCHEMA or None,
        include_schemas=bool(settings.DB_SCHEMA),
    )
    with context.begin_transaction():
        if settings.DB_SCHEMA:
            connection.execute(
                text(f'SET search_path TO "{settings.DB_SCHEMA}", public')
            )
        context.run_migrations()


async def run_migrations_online() -> None:
    connect_args: dict = {}
    if settings.DB_SCHEMA:
        connect_args["server_settings"] = {
            "search_path": f"{settings.DB_SCHEMA},public"
        }
    connectable = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )
    async with connectable.connect() as connection:
        if settings.DB_SCHEMA:
            await connection.execute(
                text(f'CREATE SCHEMA IF NOT EXISTS "{settings.DB_SCHEMA}"')
            )
            await connection.commit()
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
