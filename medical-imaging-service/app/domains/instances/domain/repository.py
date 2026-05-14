"""Instance repository protocols."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from app.domains.instances.domain.entities import InstanceQuery


class InstanceRepository(Protocol):
    async def find(
        self, study_uid: str, series_uid: str, query: InstanceQuery
    ) -> list[dict[str, Any]]: ...

    async def get_metadata(
        self, study_uid: str, series_uid: str, instance_uid: str
    ) -> list[dict[str, Any]]: ...

    async def stream(
        self, study_uid: str, series_uid: str, instance_uid: str
    ) -> AsyncIterator[bytes]: ...

    async def store(
        self,
        body: bytes,
        *,
        content_type: str,
        study_uid: str | None,
    ) -> dict[str, Any]: ...
