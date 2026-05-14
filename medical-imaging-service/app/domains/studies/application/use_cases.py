"""Application use cases for the Studies bounded context."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.domains.studies.domain.entities import StudyQuery
from app.domains.studies.domain.repository import StudyRepository


class SearchStudiesUseCase:
    def __init__(self, repository: StudyRepository) -> None:
        self._repo = repository

    async def execute(self, query: StudyQuery) -> list[dict[str, Any]]:
        return await self._repo.find(query)


class GetStudyMetadataUseCase:
    def __init__(self, repository: StudyRepository) -> None:
        self._repo = repository

    async def execute(self, study_uid: str) -> list[dict[str, Any]]:
        return await self._repo.get_metadata(study_uid)


class RetrieveStudyUseCase:
    def __init__(self, repository: StudyRepository) -> None:
        self._repo = repository

    async def execute(self, study_uid: str) -> AsyncIterator[bytes]:
        return await self._repo.stream(study_uid)
