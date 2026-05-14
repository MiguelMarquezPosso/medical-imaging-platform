"""Filesystem-backed storage. Production deployments can swap in an S3 provider."""

from __future__ import annotations

import os
from pathlib import Path

import aiofiles

from app.core.config import get_settings
from app.core.errors import NotFoundError


class FilesystemStorageProvider:
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or get_settings().STORAGE_ROOT)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Defence-in-depth — never let `..` escape the storage root
        safe = key.replace("\\", "/").lstrip("/")
        if ".." in safe.split("/"):
            raise ValueError("Invalid storage key")
        return self.root / safe

    async def put(self, key: str, data: bytes, *, content_type: str = "application/dicom") -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)
        return f"file://{path}"

    async def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise NotFoundError(f"Storage object not found: {key}")
        async with aiofiles.open(path, "rb") as f:
            return await f.read()

    async def exists(self, key: str) -> bool:
        return self._path(key).exists()

    async def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            os.remove(path)
