"""Sanity tests for password hashing and JWT round-trips."""

from __future__ import annotations

import os

os.environ.setdefault("PUBLIC_BASE_URL", "https://api.example.com")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("JWT_SECRET_KEY", "x" * 64)
os.environ.setdefault("JWT_ISSUER", "https://api.example.com")
os.environ.setdefault("JWT_AUDIENCE", "medical-imaging-platform")

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_round_trip() -> None:
    hashed = hash_password("Sup3rS3cret!Passw0rd")
    assert verify_password("Sup3rS3cret!Passw0rd", hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_round_trip() -> None:
    token, _ = create_access_token(
        subject="00000000-0000-0000-0000-000000000001",
        roles=["radiologist"],
        permissions=["studies:read"],
    )
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == "00000000-0000-0000-0000-000000000001"
    assert payload["roles"] == ["radiologist"]


def test_refresh_token_round_trip() -> None:
    token, _, jti = create_refresh_token(subject="user")
    payload = decode_token(token, expected_type="refresh")
    assert payload["jti"] == jti
