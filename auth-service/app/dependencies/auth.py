"""FastAPI dependencies for auth and authorization."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_auth_service(session: Annotated[AsyncSession, Depends(get_db)]) -> AuthService:
    return AuthService(session)


async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if not token:
        raise UnauthorizedError("Missing bearer token")
    try:
        payload = decode_token(token, expected_type="access")
    except ValueError as exc:
        raise UnauthorizedError(str(exc)) from exc

    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise UnauthorizedError("Malformed access token") from exc

    user = await UserRepository(session).get_by_id(user_id)
    if not user or not user.is_active:
        raise UnauthorizedError("User no longer exists or is inactive")

    # Stash on request.state so middleware/logging can pick it up
    request.state.user_id = str(user.id)
    request.state.user_roles = [r.name for r in user.roles]
    return user


def require_roles(*roles: str):
    required = set(roles)

    async def _checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        owned = {r.name for r in current_user.roles}
        if not required.issubset(owned) and not owned.intersection(required):
            raise ForbiddenError(
                f"Requires one of roles: {', '.join(sorted(required))}"
            )
        return current_user

    return _checker


def require_permissions(*permissions: Sequence[str]):
    required = set(permissions)

    async def _checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        owned = {p for role in current_user.roles for p in role.permission_list}
        if not required.issubset(owned):
            missing = required - owned
            raise ForbiddenError(
                f"Missing permissions: {', '.join(sorted(missing))}"
            )
        return current_user

    return _checker
