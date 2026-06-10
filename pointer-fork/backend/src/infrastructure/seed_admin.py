"""Idempotent admin-user bootstrap.

Run once per process boot (via FastAPI lifespan). If the configured ADMIN_EMAIL
already exists, do nothing. Otherwise create a verified superuser using
``ADMIN_PASSWORD``.
"""

from __future__ import annotations

import logging

from fastapi_users.password import PasswordHelper
from sqlalchemy import select

from src.infrastructure.config import settings
from src.infrastructure.persistence.database import User, async_session_maker

logger = logging.getLogger(__name__)


async def seed_admin() -> None:
    if not settings.admin_email or not settings.admin_password:
        logger.info("admin seed skipped: ADMIN_EMAIL/ADMIN_PASSWORD not set")
        return

    helper = PasswordHelper()
    async with async_session_maker() as session:
        existing = await session.execute(
            select(User).where(User.email == settings.admin_email)
        )
        if existing.scalar_one_or_none() is not None:
            logger.info("admin seed skipped: %s already exists", settings.admin_email)
            return

        user = User(
            email=settings.admin_email,
            hashed_password=helper.hash(settings.admin_password),
            is_active=True,
            is_superuser=True,
            is_verified=True,
            name=settings.admin_name or "Admin",
            company=settings.admin_company or None,
        )
        session.add(user)
        await session.commit()
        logger.info("admin seeded: %s", settings.admin_email)
