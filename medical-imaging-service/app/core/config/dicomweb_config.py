"""Mutable DICOMweb configuration with hot reload support.

The base URL, credentials and TLS verification can be reconfigured at runtime
via the admin endpoint without restarting the service.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Literal

from app.core.config.settings import get_settings


@dataclass(frozen=True)
class DICOMwebConfig:
    base_url: str
    auth_type: Literal["none", "basic", "bearer"]
    username: str
    password: str
    bearer_token: str
    verify_tls: bool
    timeout_seconds: int


class DICOMwebConfigStore:
    """Thread-safe in-memory store. Seeded from env, mutable at runtime."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        s = get_settings()
        self._current = DICOMwebConfig(
            base_url=str(s.DICOMWEB_BASE_URL).rstrip("/"),
            auth_type=s.DICOMWEB_AUTH_TYPE,
            username=s.DICOMWEB_USERNAME,
            password=s.DICOMWEB_PASSWORD,
            bearer_token=s.DICOMWEB_BEARER_TOKEN,
            verify_tls=s.DICOMWEB_VERIFY_TLS,
            timeout_seconds=s.DICOMWEB_TIMEOUT_SECONDS,
        )

    def get(self) -> DICOMwebConfig:
        with self._lock:
            return self._current

    def update(self, **changes) -> DICOMwebConfig:
        with self._lock:
            current = self._current.__dict__ | changes
            if "base_url" in changes and current["base_url"]:
                current["base_url"] = current["base_url"].rstrip("/")
            self._current = DICOMwebConfig(**current)
            return self._current


_store: DICOMwebConfigStore | None = None


def get_dicomweb_config_store() -> DICOMwebConfigStore:
    global _store
    if _store is None:
        _store = DICOMwebConfigStore()
    return _store
