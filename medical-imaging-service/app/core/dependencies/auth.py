"""Authentication and authorization dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security.jwt import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


@dataclass
class AuthenticatedUser:
    id: str
    email: str | None
    roles: list[str]
    permissions: list[str]
    jti: str | None

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_permission(self, perm: str) -> bool:
        return perm in self.permissions


async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> AuthenticatedUser:
    if not token:
        raise UnauthorizedError("Missing bearer token")
    payload = decode_access_token(token)
    user = AuthenticatedUser(
        id=str(payload.get("sub", "")),
        email=payload.get("email"),
        roles=list(payload.get("roles", [])),
        permissions=list(payload.get("permissions", [])),
        jti=payload.get("jti"),
    )
    request.state.user_id = user.id
    request.state.user_roles = user.roles
    return user


def require_roles(*roles: str):
    required = set(roles)

    async def _checker(
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        owned = set(current_user.roles)
        if not owned.intersection(required):
            raise ForbiddenError(
                f"Requires one of roles: {', '.join(sorted(required))}"
            )
        return current_user

    return _checker


def require_permissions(*permissions: str):
    required = set(permissions)

    async def _checker(
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        owned = set(current_user.permissions)
        if not required.issubset(owned):
            missing = required - owned
            raise ForbiddenError(
                f"Missing permissions: {', '.join(sorted(missing))}"
            )
        return current_user

    return _checker


# The Raspberry Pi devices authenticate as users with role `sync-device`
require_sync_device = require_roles("sync-device", "admin")
