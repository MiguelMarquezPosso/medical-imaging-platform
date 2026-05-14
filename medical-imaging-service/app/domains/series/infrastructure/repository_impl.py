"""DICOMweb-backed series repository."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.domains.series.domain.entities import SeriesQuery
from app.providers.dicomweb import DICOMwebProvider


class DICOMwebSeriesRepository:
    def __init__(self, provider: DICOMwebProvider) -> None:
        self._provider = provider

    async def find(self, study_uid: str, query: SeriesQuery) -> list[dict[str, Any]]:
        return await self._provider.search_series(study_uid, query.to_dicomweb_params())

    async def get_metadata(self, study_uid: str, series_uid: str) -> list[dict[str, Any]]:
        return await self._provider.retrieve_series_metadata(study_uid, series_uid)

    async def stream(self, study_uid: str, series_uid: str) -> AsyncIterator[bytes]:
        return await self._provider.retrieve_series(study_uid, series_uid)
