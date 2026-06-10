"""fastapi-users wiring: UserManager, JWT+Cookie backend, router factories.

Exposes:
 - ``fastapi_users``   → FastAPIUsers instance (router factories + deps)
 - ``auth_backend``    → cookie-JWT authentication backend
 - ``current_active_user``  → dependency for protected routes
 - ``optional_current_user`` → dependency that returns ``None`` if anonymous
"""

from __future__ import annotations

import logging
import uuid

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import AuthenticationBackend, CookieTransport, JWTStrategy

from src.infrastructure.config import settings
from src.infrastructure.persistence.database import User, get_user_db

logger = logging.getLogger(__name__)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.jwt_secret
    verification_token_secret = settings.jwt_secret

    async def on_after_register(self, user: User, request: Request | None = None):
        logger.info("user registered: %s", user.email)

    async def on_after_login(
        self,
        user: User,
        request: Request | None = None,
        response=None,
    ):
        logger.debug("user logged in: %s", user.email)


async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)


def _jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.jwt_secret, lifetime_seconds=3600 * 24)


cookie_transport = CookieTransport(
    cookie_name="pointer_auth",
    cookie_max_age=3600 * 24,
    cookie_secure=settings.cookie_secure,
    cookie_httponly=True,
    cookie_samesite="lax",
)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=_jwt_strategy,
)


fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)
optional_current_user = fastapi_users.current_user(active=True, optional=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)
