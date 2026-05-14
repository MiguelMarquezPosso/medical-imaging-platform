"""FastAPI exception handlers."""

from __future__ import annotations

import traceback
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors.exceptions import AppError
from app.core.logging import get_logger

log = get_logger("errors")


def _rid(request: Request) -> str:
    return request.headers.get("X-Request-ID") or uuid.uuid4().hex


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        rid = _rid(request)
        log.warning(
            "app_error",
            code=exc.code,
            message=exc.message,
            status=exc.status_code,
            request_id=rid,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "request_id": rid,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        rid = _rid(request)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Invalid request payload",
                    "details": exc.errors(),
                    "request_id": rid,
                }
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        rid = _rid(request)
        log.error(
            "unhandled_exception",
            error=str(exc),
            type=type(exc).__name__,
            traceback=traceback.format_exc(),
            request_id=rid,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Internal server error",
                    "request_id": rid,
                }
            },
        )
