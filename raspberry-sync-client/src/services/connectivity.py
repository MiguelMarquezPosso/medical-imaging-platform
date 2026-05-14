"""Tiny connectivity check — TCP-connect to the API host."""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse


async def is_online(api_base_url: str, *, timeout: float = 5.0) -> bool:
    parsed = urlparse(api_base_url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if not host:
        return False
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass
        return True
    except (OSError, asyncio.TimeoutError):
        return False
