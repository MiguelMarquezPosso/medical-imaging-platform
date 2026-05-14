"""Pydantic schemas for auth endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # access token lifetime in seconds


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    name: str
    description: str | None = None
    permissions: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("permission_list", "permissions"),
    )


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str | None
    is_active: bool
    is_verified: bool
    created_at: datetime
    roles: list[RoleOut] = Field(default_factory=list)


class IntrospectResponse(BaseModel):
    active: bool
    sub: str | None = None
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    exp: int | None = None
    iat: int | None = None
    jti: str | None = None
