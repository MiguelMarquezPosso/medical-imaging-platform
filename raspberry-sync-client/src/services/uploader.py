"""Uploader — POSTs encrypted bodies to /sync/upload."""

from __future__ import annotations

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.core.config import Settings
from src.core.logging import get_logger
from src.services.auth_client import AuthClient
from src.services.crypto import SyncCrypto

log = get_logger("uploader")


class Uploader:
    def __init__(
        self,
        settings: Settings,
        auth: AuthClient,
        crypto: SyncCrypto,
    ) -> None:
        self._settings = settings
        self._auth = auth
        self._crypto = crypto

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, max=30),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def upload(self, plaintext: bytes) -> dict:
        ct = self._crypto.encrypt(plaintext, aad=self._settings.SYNC_DEVICE_ID.encode())
        signature = self._crypto.sign(ct)
        access = await self._auth.get_access_token()

        headers = {
            "Authorization": f"Bearer {access}",
            "Content-Type": "application/octet-stream",
            "X-Sync-Device-Id": self._settings.SYNC_DEVICE_ID,
        }
        if signature:
            headers["X-Sync-Signature"] = signature

        async with httpx.AsyncClient(
            base_url=str(self._settings.API_BASE_URL).rstrip("/"),
            verify=self._settings.API_VERIFY_TLS,
            timeout=120,
        ) as client:
            resp = await client.post("/sync/upload", content=ct, headers=headers)
            if resp.status_code == 409:
                # Already ingested upstream — treat as success (idempotent)
                log.info("upload_duplicate", body=resp.json())
                return {"status": "duplicate"}
            resp.raise_for_status()
            return resp.json()
