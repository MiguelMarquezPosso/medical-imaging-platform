"""Domain-level exceptions and FastAPI exception handlers."""

from __future__ import annotations

import traceback
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

log = get_logger("errors")


class AppError(Exception):
    status_code: int = 400
    code: str = "app_error"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
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
            content={"error": {"code": exc.code, "message": exc.message, "request_id": rid}},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
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
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
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
