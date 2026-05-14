"""Series repository protocol."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from app.domains.series.domain.entities import SeriesQuery


class SeriesRepository(Protocol):
    async def find(self, study_uid: str, query: SeriesQuery) -> list[dict[str, Any]]: ...
    async def get_metadata(self, study_uid: str, series_uid: str) -> list[dict[str, Any]]: ...
    async def stream(self, study_uid: str, series_uid: str) -> AsyncIterator[bytes]: ...
