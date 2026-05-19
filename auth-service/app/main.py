"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

import orjson
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app import __version__
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.middleware.request_id import RequestIDMiddleware

settings = get_settings()
configure_logging(settings.LOG_LEVEL)
log = get_logger("main")


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info("auth_service_starting", env=settings.APP_ENV, version=__version__)
    yield
    log.info("auth_service_stopping")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Medical Imaging Platform — Auth Service",
        version=__version__,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
        # Mount docs under /api/v1/auth/* so the existing nginx /auth/ route
        # exposes them publicly without extra gateway config.
        docs_url="/api/v1/auth/docs" if settings.ENABLE_DOCS else None,
        redoc_url="/api/v1/auth/redoc" if settings.ENABLE_DOCS else None,
        openapi_url="/api/v1/auth/openapi.json" if settings.ENABLE_DOCS else None,
    )

    if settings.cors_origins_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
        )

    app.add_middleware(RequestIDMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/healthz", include_in_schema=False)
    async def _root_health():
        return {"status": "ok"}

    return app


app = create_app()
