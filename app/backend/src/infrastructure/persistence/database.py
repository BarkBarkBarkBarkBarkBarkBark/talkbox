"""Async SQLAlchemy setup + User model for fastapi-users.

The repo's DB_URI ships with a sync driver (``postgresql+psycopg://``) since the
SQL agent and the pgvector seeder use psycopg2. Here we derive an async URL
(``postgresql+asyncpg://``) for fastapi-users' ``AsyncSession`` usage.
"""

from __future__ import annotations

import ssl
from datetime import datetime
from typing import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from fastapi import Depends
from fastapi_users.db import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from sqlalchemy import DateTime, String, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.infrastructure.config import settings


def _async_db_uri(db_uri: str) -> tuple[str, dict]:
    """Return (asyncpg URL, connect_args) for the given DB_URI.

    asyncpg does not accept ``sslmode`` / ``channel_binding`` as query params —
    strip those and negotiate SSL via connect_args instead.
    """
    if not db_uri:
        raise RuntimeError("DB_URI is not set")

    # Normalise driver prefix to asyncpg.
    url = db_uri
    for old, new in (
        ("postgresql+psycopg://", "postgresql+asyncpg://"),
        ("postgresql+psycopg2://", "postgresql+asyncpg://"),
        ("postgresql://", "postgresql+asyncpg://"),
    ):
        if url.startswith(old):
            url = url.replace(old, new, 1)
            break

    # Strip params asyncpg cannot handle; detect SSL requirement.
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    needs_ssl = params.pop("sslmode", ["disable"])[0] in ("require", "verify-ca", "verify-full")
    params.pop("channel_binding", None)
    clean_url = urlunparse(parsed._replace(query=urlencode(params, doseq=True)))

    connect_args: dict = {}
    if needs_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ctx

    return clean_url, connect_args


class Base(DeclarativeBase):
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


_async_url, _connect_args = _async_db_uri(settings.db_uri)
engine = create_async_engine(_async_url, connect_args=_connect_args, pool_pre_ping=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)
