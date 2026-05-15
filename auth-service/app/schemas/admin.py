"""Pydantic schemas for the admin user-management endpoints."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.schemas.auth import UserOut


class AdminCreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)
    roles: list[str] = Field(default_factory=list)
    is_active: bool = True


class AdminUpdateUserRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_verified: bool | None = None
    roles: list[str] | None = None


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=12, max_length=128)


class UserListResponse(BaseModel):
    items: list[UserOut]
    total: int
    limit: int
    offset: int


class RoleInfo(BaseModel):
    name: str
    description: str | None = None
    permissions: list[str]


class RoleListResponse(BaseModel):
    items: list[RoleInfo]
