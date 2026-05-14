"""Application service — orchestrates the authentication use cases."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repository import RefreshTokenRepository, UserRepository
from app.schemas.auth import TokenPair
from app.services.password_policy import enforce_password_policy

log = get_logger("auth_service")


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)

    # ----- Registration --------------------------------------------------
    async def register(
        self,
        *,
        email: str,
        password: str,
        full_name: str | None,
        is_public_registration: bool = True,
    ) -> User:
        settings = get_settings()
        if is_public_registration and not settings.ALLOW_PUBLIC_REGISTRATION:
            raise ForbiddenError("Public registration is disabled")

        enforce_password_policy(password)

        if await self.users.get_by_email(email):
            raise ConflictError("A user with this email already exists")

        user = await self.users.create(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
        )

        # Auto-assign the default role
        default_role = await self.users.get_role_by_name(settings.DEFAULT_USER_ROLE)
        if default_role:
            await self.users.assign_role(user, default_role)

        await self.session.commit()
        user = await self.users.get_by_id(user.id)
        log.info("user_registered", user_id=str(user.id), email=user.email)
        return user

    # ----- Authentication ------------------------------------------------
    async def authenticate(self, *, email: str, password: str) -> User:
        user = await self.users.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Invalid credentials")
        if not user.is_active:
            raise ForbiddenError("Account is disabled")
        return user

    async def login(
        self,
        *,
        email: str,
        password: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> TokenPair:
        user = await self.authenticate(email=email, password=password)
        token_pair = await self._issue_tokens(user, user_agent=user_agent, ip_address=ip_address)
        await self.users.record_login(user.id, when=datetime.now(UTC))
        await self.session.commit()
        return token_pair

    # ----- Refresh -------------------------------------------------------
    async def refresh(
        self,
        *,
        refresh_token: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> TokenPair:
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except ValueError as exc:
            raise UnauthorizedError(str(exc)) from exc

        jti = payload.get("jti")
        sub = payload.get("sub")
        if not jti or not sub:
            raise UnauthorizedError("Malformed refresh token")

        rt = await self.refresh_tokens.get_by_jti(jti)
        if not rt or rt.revoked:
            raise UnauthorizedError("Refresh token revoked or unknown")
        if rt.expires_at <= datetime.now(UTC):
            raise UnauthorizedError("Refresh token expired")

        user = await self.users.get_by_id(rt.user_id)
        if not user or not user.is_active:
            raise ForbiddenError("Account is disabled")

        # Rotation: revoke the old token, issue a fresh pair
        await self.refresh_tokens.revoke(jti)
        token_pair = await self._issue_tokens(user, user_agent=user_agent, ip_address=ip_address)
        await self.session.commit()
        return token_pair

    # ----- Logout --------------------------------------------------------
    async def logout(self, *, refresh_token: str) -> None:
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except ValueError:
            return  # idempotent — ignore invalid tokens
        jti = payload.get("jti")
        if jti:
            await self.refresh_tokens.revoke(jti)
            await self.session.commit()

    # ----- Introspect ----------------------------------------------------
    async def introspect(self, token: str) -> dict:
        try:
            payload = decode_token(token, expected_type="access")
        except ValueError:
            return {"active": False}
        return {
            "active": True,
            "sub": payload.get("sub"),
            "roles": payload.get("roles", []),
            "permissions": payload.get("permissions", []),
            "exp": payload.get("exp"),
            "iat": payload.get("iat"),
            "jti": payload.get("jti"),
        }

    # ----- Helpers -------------------------------------------------------
    async def _issue_tokens(
        self,
        user: User,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> TokenPair:
        settings = get_settings()
        roles = [r.name for r in user.roles]
        permissions = sorted(
            {p for role in user.roles for p in role.permission_list}
        )

        access_token, _ = create_access_token(
            subject=str(user.id),
            roles=roles,
            permissions=permissions,
            extra_claims={"email": user.email},
        )
        refresh_token, expires_at, jti = create_refresh_token(subject=str(user.id))
        await self.refresh_tokens.add(
            user_id=user.id,
            jti=jti,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def get_user_or_404(self, user_id) -> User:
        user = await self.users.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")
        return user
