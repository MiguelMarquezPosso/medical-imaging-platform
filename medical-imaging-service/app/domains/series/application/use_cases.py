"""Series application use cases."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.domains.series.domain.entities import SeriesQuery
from app.domains.series.domain.repository import SeriesRepository


class SearchSeriesUseCase:
    def __init__(self, repository: SeriesRepository) -> None:
        self._repo = repository

    async def execute(self, study_uid: str, query: SeriesQuery) -> list[dict[str, Any]]:
        return await self._repo.find(study_uid, query)


class GetSeriesMetadataUseCase:
    def __init__(self, repository: SeriesRepository) -> None:
        self._repo = repository

    async def execute(self, study_uid: str, series_uid: str) -> list[dict[str, Any]]:
        return await self._repo.get_metadata(study_uid, series_uid)


class RetrieveSeriesUseCase:
    def __init__(self, repository: SeriesRepository) -> None:
        self._repo = repository

    async def execute(self, study_uid: str, series_uid: str) -> AsyncIterator[bytes]:
        return await self._repo.stream(study_uid, series_uid)
