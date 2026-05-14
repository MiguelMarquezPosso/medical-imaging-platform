"""Data access for users and refresh tokens."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import RefreshToken, Role, User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self.session.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(self, *, email: str, full_name: str | None, hashed_password: str) -> User:
        user = User(
            email=email.lower(),
            full_name=full_name,
            hashed_password=hashed_password,
            is_active=True,
            is_verified=False,
            roles=[],
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_role_by_name(self, name: str) -> Role | None:
        result = await self.session.execute(select(Role).where(Role.name == name))
        return result.scalar_one_or_none()

    async def assign_role(self, user: User, role: Role) -> None:
        if role not in user.roles:
            user.roles.append(role)
            await self.session.flush()

    async def record_login(self, user_id: UUID, *, when: datetime) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(last_login_at=when)
        )


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(
        self,
        *,
        user_id: UUID,
        jti: str,
        expires_at: datetime,
        user_agent: str | None,
        ip_address: str | None,
    ) -> RefreshToken:
        rt = RefreshToken(
            user_id=user_id,
            jti=jti,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.session.add(rt)
        await self.session.flush()
        return rt

    async def get_by_jti(self, jti: str) -> RefreshToken | None:
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.jti == jti)
        )
        return result.scalar_one_or_none()

    async def revoke(self, jti: str) -> None:
        await self.session.execute(
            update(RefreshToken).where(RefreshToken.jti == jti).values(revoked=True)
        )

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        await self.session.execute(
            update(RefreshToken).where(RefreshToken.user_id == user_id).values(revoked=True)
        )
