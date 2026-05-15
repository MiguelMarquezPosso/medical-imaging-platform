"""Data access for users and refresh tokens."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update
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

    # ----- Admin operations ----------------------------------------------
    async def list_users(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        email_contains: str | None = None,
    ) -> tuple[list[User], int]:
        base = select(User).options(selectinload(User.roles))
        count_q = select(func.count()).select_from(User)
        if email_contains:
            base = base.where(User.email.ilike(f"%{email_contains.lower()}%"))
            count_q = count_q.where(User.email.ilike(f"%{email_contains.lower()}%"))
        base = base.order_by(User.created_at.desc()).limit(limit).offset(offset)
        users = (await self.session.execute(base)).scalars().all()
        total = (await self.session.execute(count_q)).scalar_one()
        return list(users), total

    async def list_roles(self) -> list[Role]:
        result = await self.session.execute(select(Role).order_by(Role.name))
        return list(result.scalars().all())

    async def set_roles(self, user: User, role_names: list[str]) -> None:
        """Replace the user's roles with the given set."""
        result = await self.session.execute(
            select(Role).where(Role.name.in_(role_names))
        )
        roles = list(result.scalars().all())
        found = {r.name for r in roles}
        missing = set(role_names) - found
        if missing:
            raise ValueError(f"Unknown role(s): {', '.join(sorted(missing))}")
        user.roles = roles
        await self.session.flush()

    async def update_fields(
        self,
        user: User,
        *,
        full_name: str | None = None,
        is_active: bool | None = None,
        is_verified: bool | None = None,
        hashed_password: str | None = None,
    ) -> None:
        if full_name is not None:
            user.full_name = full_name
        if is_active is not None:
            user.is_active = is_active
        if is_verified is not None:
            user.is_verified = is_verified
        if hashed_password is not None:
            user.hashed_password = hashed_password
        await self.session.flush()

    async def delete(self, user: User) -> None:
        await self.session.execute(
            delete(RefreshToken).where(RefreshToken.user_id == user.id)
        )
        await self.session.delete(user)
        await self.session.flush()


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
