"""Sync repository protocol."""

from __future__ import annotations

from typing import Protocol

from app.domains.sync.domain.entities import SyncRecord


class SyncRecordRepository(Protocol):
    async def add(self, record: SyncRecord) -> None: ...
    async def update(self, record: SyncRecord) -> None: ...
    async def exists_by_sha(self, sha256: str) -> bool: ...
    async def list_recent(self, *, limit: int = 100, offset: int = 0) -> list[SyncRecord]: ...
