"""FastAPI application factory for the Medical Imaging Service."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app import __version__
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestIDMiddleware
from app.routes import api_router

settings = get_settings()
configure_logging(settings.LOG_LEVEL)
log = get_logger("main")


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info(
        "medical_imaging_service_starting",
        env=settings.APP_ENV,
        version=__version__,
        storage_backend=settings.STORAGE_BACKEND,
    )
    yield
    log.info("medical_imaging_service_stopping")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Medical Imaging Platform — Medical Imaging Service",
        version=__version__,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
        docs_url="/docs" if settings.APP_ENV != "production" else None,
        redoc_url="/redoc" if settings.APP_ENV != "production" else None,
        openapi_url="/openapi.json" if settings.APP_ENV != "production" else None,
    )

    if settings.cors_origins_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID", "Content-Disposition"],
        )

    app.add_middleware(RequestIDMiddleware)
    register_exception_handlers(app)

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/healthz", include_in_schema=False)
    async def _root_health():
        return {"status": "ok"}

    return app


app = create_app()
