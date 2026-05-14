"""Lightweight Auth Service client — login + refresh."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.config import Settings
from src.core.logging import get_logger

log = get_logger("auth")


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str
    expires_at: float  # epoch seconds


class AuthClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._tokens: TokenSet | None = None
        self._lock = asyncio.Lock()

    async def get_access_token(self) -> str:
        async with self._lock:
            now = time.time()
            if self._tokens and now < self._tokens.expires_at - 30:
                return self._tokens.access_token
            if self._tokens:
                try:
                    await self._refresh()
                    return self._tokens.access_token
                except httpx.HTTPError:
                    pass  # fall through to login
            await self._login()
            assert self._tokens
            return self._tokens.access_token

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=4), reraise=True)
    async def _login(self) -> None:
        async with self._client() as client:
            resp = await client.post(
                "/auth/login",
                json={
                    "email": self._settings.SYNC_DEVICE_EMAIL,
                    "password": self._settings.SYNC_DEVICE_PASSWORD,
                },
            )
            resp.raise_for_status()
            self._tokens = self._to_token_set(resp.json())
            log.info("auth_login_ok")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=4), reraise=True)
    async def _refresh(self) -> None:
        assert self._tokens
        async with self._client() as client:
            resp = await client.post(
                "/auth/refresh",
                json={"refresh_token": self._tokens.refresh_token},
            )
            resp.raise_for_status()
            self._tokens = self._to_token_set(resp.json())
            log.info("auth_refresh_ok")

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=str(self._settings.API_BASE_URL).rstrip("/"),
            verify=self._settings.API_VERIFY_TLS,
            timeout=30,
        )

    @staticmethod
    def _to_token_set(payload: dict) -> TokenSet:
        return TokenSet(
            access_token=payload["access_token"],
            refresh_token=payload["refresh_token"],
            expires_at=time.time() + int(payload.get("expires_in", 0)),
        )
