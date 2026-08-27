import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.presentation.auth import auth_backend, fastapi_users
from src.presentation.admin_routes import router as admin_router
from src.presentation.kiosk_call_routes import router as kiosk_call_router
from src.presentation.kiosk_core_routes import router as kiosk_router
from src.presentation.kiosk_device_routes import router as kiosk_device_router
from src.presentation.middleware import configure_cors
from src.presentation.query_routes import router as query_router
from src.presentation.resource_routes import router as resource_router
from src.presentation.sms_routes import router as sms_router
from src.presentation.schemas_user import UserRead, UserUpdate

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.application.services.resource_sync_service import resource_sync_service
    from src.infrastructure.config import settings

    if settings.talkbox_seed_admin:
        try:
            from src.infrastructure.seed_admin import seed_admin

            await seed_admin()
        except Exception:
            logger.exception("admin seed failed at startup")
    else:
        logger.info("admin seed disabled")
    if settings.fsc_resource_sync_enabled:
        try:
            await resource_sync_service.start()
        except Exception:
            logger.exception("resource synchronization failed at startup")
    else:
        logger.info("FSC resource synchronization disabled")
    from src.application.services.catalog_pull_service import catalog_pull_service

    try:
        await catalog_pull_service.start()
    except Exception:
        logger.exception("catalog pull failed at startup")
    try:
        yield
    finally:
        await catalog_pull_service.stop()
        await resource_sync_service.stop()


def create_core_app() -> FastAPI:
    app = FastAPI(
        title="Talk Box",
        description="Shelter-oriented query assistant (SQL + Healthscout + vector routing)",
        version="1.0.0",
        lifespan=lifespan,
    )
    configure_cors(app)
    app.include_router(resource_router)
    app.include_router(query_router, prefix="/api")
    app.include_router(kiosk_router, prefix="/api")
    app.include_router(kiosk_device_router, prefix="/api")
    app.include_router(kiosk_call_router, prefix="/api")
    app.include_router(sms_router, prefix="/api")
    app.include_router(admin_router, prefix="/api/admin")
    app.include_router(
        fastapi_users.get_auth_router(auth_backend),
        prefix="/api/auth/jwt",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_users_router(UserRead, UserUpdate),
        prefix="/api/users",
        tags=["users"],
    )
    return app


app = create_core_app()
