from fastapi import FastAPI

from src.presentation.middleware import configure_cors
from src.presentation.sms_routes import router as sms_router


def create_sms_app() -> FastAPI:
    app = FastAPI(title="Talk Box SMS", version="1.0.0")
    configure_cors(app)
    app.include_router(sms_router, prefix="/api")
    return app


app = create_sms_app()
