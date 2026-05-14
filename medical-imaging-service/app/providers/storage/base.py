"""Storage abstraction used by the sync flow."""

from __future__ import annotations

from typing import Protocol


class StorageProvider(Protocol):
    async def put(self, key: str, data: bytes, *, content_type: str = "application/dicom") -> str:
        """Store an object and return its canonical URI."""

    async def get(self, key: str) -> bytes:
        """Read an object."""

    async def exists(self, key: str) -> bool: ...

    async def delete(self, key: str) -> None: ...
