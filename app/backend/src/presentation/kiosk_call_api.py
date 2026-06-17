from fastapi import FastAPI

from src.presentation.kiosk_call_routes import router as kiosk_call_router
from src.presentation.middleware import configure_cors


def create_kiosk_call_app() -> FastAPI:
    app = FastAPI(title="Talk Box Kiosk Calling", version="1.0.0")
    configure_cors(app)
    app.include_router(kiosk_call_router, prefix="/api")
    return app


app = create_kiosk_call_app()
