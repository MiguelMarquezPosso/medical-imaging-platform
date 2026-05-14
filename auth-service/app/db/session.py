"""SQLAlchemy async engine and session factory."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_settings = get_settings()

_execution_options: dict = {}
if _settings.DB_SCHEMA:
    _execution_options["schema_translate_map"] = {None: _settings.DB_SCHEMA}

engine = create_async_engine(
    _settings.DATABASE_URL,
    pool_size=_settings.DATABASE_POOL_SIZE,
    max_overflow=_settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    echo=False,
    execution_options=_execution_options,
)

if _settings.DB_SCHEMA:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_search_path(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        try:
            cur.execute(f'SET search_path TO "{_settings.DB_SCHEMA}", public')
        finally:
            cur.close()

SessionFactory = async_sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
