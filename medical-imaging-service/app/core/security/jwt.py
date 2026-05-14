"""JWT verification — validates tokens minted by the Auth Service."""

from __future__ import annotations

from typing import Any

from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.errors import UnauthorizedError


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
        )
    except JWTError as exc:
        raise UnauthorizedError(f"Invalid token: {exc}") from exc
    if payload.get("type") != "access":
        raise UnauthorizedError("Access token required")
    return payload
