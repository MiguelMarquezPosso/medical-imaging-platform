"""Study repository implementation that delegates to a DICOMwebProvider."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.domains.studies.domain.entities import StudyQuery
from app.providers.dicomweb import DICOMwebProvider


class DICOMwebStudyRepository:
    def __init__(self, provider: DICOMwebProvider) -> None:
        self._provider = provider

    async def find(self, query: StudyQuery) -> list[dict[str, Any]]:
        return await self._provider.search_studies(query.to_dicomweb_params())

    async def get_metadata(self, study_uid: str) -> list[dict[str, Any]]:
        return await self._provider.retrieve_metadata(study_uid)

    async def stream(self, study_uid: str) -> AsyncIterator[bytes]:
        return await self._provider.retrieve_study(study_uid)
