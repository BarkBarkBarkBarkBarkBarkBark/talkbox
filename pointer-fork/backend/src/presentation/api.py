import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.presentation.auth import auth_backend, fastapi_users
from src.presentation.kiosk_routes import router as kiosk_router
from src.presentation.middleware import configure_cors
from src.presentation.routes import router
from src.presentation.schemas_user import UserCreate, UserRead, UserUpdate

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Bootstrap the admin user once the DB is reachable. Safe to retry on
    # every startup — seed_admin() is idempotent.
    try:
        from src.infrastructure.seed_admin import seed_admin

        await seed_admin()
    except Exception:
        logger.exception("admin seed failed at startup")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Pointer AI",
        description="Shelter-oriented query assistant (SQL + Healthscout + vector routing)",
        version="1.0.0",
        lifespan=lifespan,
    )
    configure_cors(app)

    # Domain routes (query, sms, health)
    app.include_router(router, prefix="/api")

    # Kiosk routes (keypad-first 6-inch UX) — additive, under /api/kiosk
    app.include_router(kiosk_router, prefix="/api")

    # Auth endpoints
    app.include_router(
        fastapi_users.get_auth_router(auth_backend),
        prefix="/api/auth/jwt",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="/api/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_users_router(UserRead, UserUpdate),
        prefix="/api/users",
        tags=["users"],
    )
    return app


app = create_app()
