"""/auth/admin/* — user management endpoints, gated by the `admin` role.

These let an admin operator manage users without SSH'ing into the DB:
list, create, update, set roles, reset password, delete.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.security import hash_password
from app.db.session import get_db
from app.dependencies.auth import require_roles
from app.models.user import User
from app.repositories.user_repository import RefreshTokenRepository, UserRepository
from app.schemas.admin import (
    AdminCreateUserRequest,
    AdminResetPasswordRequest,
    AdminUpdateUserRequest,
    RoleInfo,
    RoleListResponse,
    UserListResponse,
)
from app.schemas.auth import UserOut
from app.services.password_policy import enforce_password_policy

router = APIRouter(prefix="/auth/admin", tags=["admin"])


async def _get_user_or_404(repo: UserRepository, user_id: UUID) -> User:
    user = await repo.get_by_id(user_id)
    if not user:
        raise NotFoundError("User not found")
    return user


@router.get("/users", response_model=UserListResponse)
async def list_users(
    _admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    email: str | None = Query(None, description="Substring filter on email"),
) -> UserListResponse:
    repo = UserRepository(session)
    users, total = await repo.list_users(limit=limit, offset=offset, email_contains=email)
    return UserListResponse(
        items=[UserOut.model_validate(u) for u in users],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: AdminCreateUserRequest,
    _admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    enforce_password_policy(payload.password)
    repo = UserRepository(session)
    if await repo.get_by_email(payload.email):
        raise ConflictError("A user with this email already exists")

    user = await repo.create(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    if payload.roles:
        try:
            await repo.set_roles(user, payload.roles)
        except ValueError as exc:
            raise NotFoundError(str(exc)) from exc
    if payload.is_active is False:
        await repo.update_fields(user, is_active=False)
    await session.commit()
    user = await repo.get_by_id(user.id)
    return UserOut.model_validate(user)


@router.get("/users/{user_id}", response_model=UserOut)
async def get_user(
    user_id: UUID,
    _admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    repo = UserRepository(session)
    user = await _get_user_or_404(repo, user_id)
    return UserOut.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: UUID,
    payload: AdminUpdateUserRequest,
    _admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    repo = UserRepository(session)
    user = await _get_user_or_404(repo, user_id)
    await repo.update_fields(
        user,
        full_name=payload.full_name,
        is_active=payload.is_active,
        is_verified=payload.is_verified,
    )
    if payload.roles is not None:
        try:
            await repo.set_roles(user, payload.roles)
        except ValueError as exc:
            raise NotFoundError(str(exc)) from exc
    # If admin deactivated the user, also revoke their refresh tokens.
    if payload.is_active is False:
        await RefreshTokenRepository(session).revoke_all_for_user(user.id)
    await session.commit()
    user = await repo.get_by_id(user.id)
    return UserOut.model_validate(user)


@router.post(
    "/users/{user_id}/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def reset_password(
    user_id: UUID,
    payload: AdminResetPasswordRequest,
    _admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    enforce_password_policy(payload.new_password)
    repo = UserRepository(session)
    user = await _get_user_or_404(repo, user_id)
    await repo.update_fields(user, hashed_password=hash_password(payload.new_password))
    # Force-logout: revoke all active refresh tokens for this user.
    await RefreshTokenRepository(session).revoke_all_for_user(user.id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    if admin.id == user_id:
        raise ConflictError("You cannot delete your own admin account")
    repo = UserRepository(session)
    user = await _get_user_or_404(repo, user_id)
    await repo.delete(user)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/roles", response_model=RoleListResponse)
async def list_roles(
    _admin: Annotated[User, Depends(require_roles("admin"))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RoleListResponse:
    repo = UserRepository(session)
    roles = await repo.list_roles()
    return RoleListResponse(
        items=[
            RoleInfo(
                name=r.name,
                description=r.description,
                permissions=r.permission_list,
            )
            for r in roles
        ]
    )
