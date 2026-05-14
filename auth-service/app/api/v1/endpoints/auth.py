"""/auth endpoints — register, login, refresh, logout, introspect, me."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.dependencies.auth import get_auth_service, get_current_user
from app.models.user import User
from app.schemas.auth import (
    IntrospectResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_info(request: Request) -> tuple[str | None, str | None]:
    ua = request.headers.get("User-Agent")
    ip = request.headers.get("X-Forwarded-For") or (
        request.client.host if request.client else None
    )
    return ua, ip


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserOut:
    user = await service.register(
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        is_public_registration=True,
    )
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenPair)
async def login(
    payload: LoginRequest,
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenPair:
    ua, ip = _client_info(request)
    return await service.login(
        email=payload.email,
        password=payload.password,
        user_agent=ua,
        ip_address=ip,
    )


@router.post("/token", response_model=TokenPair)
async def login_oauth2(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenPair:
    """OAuth2 password flow — useful for Swagger UI / OAuth2 clients."""
    ua, ip = _client_info(request)
    return await service.login(
        email=form.username,
        password=form.password,
        user_agent=ua,
        ip_address=ip,
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenPair:
    ua, ip = _client_info(request)
    return await service.refresh(
        refresh_token=payload.refresh_token,
        user_agent=ua,
        ip_address=ip,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    await service.logout(refresh_token=payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/introspect", response_model=IntrospectResponse)
async def introspect(
    payload: RefreshRequest,  # reuse field — keeps OpenAPI simple
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> IntrospectResponse:
    """Token introspection — used by the imaging service to validate access tokens.

    Other services validate JWTs locally for the hot path; this endpoint is for
    the rare case of revocation lookups or server-to-server checks.
    """
    data = await service.introspect(payload.refresh_token)
    return IntrospectResponse(**data)


@router.get("/me", response_model=UserOut)
async def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserOut:
    return UserOut.model_validate(current_user)
