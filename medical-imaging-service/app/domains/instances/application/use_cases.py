"""Instance use cases — QIDO/WADO/STOW."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.domains.instances.domain.entities import InstanceQuery
from app.domains.instances.domain.repository import InstanceRepository


class SearchInstancesUseCase:
    def __init__(self, repository: InstanceRepository) -> None:
        self._repo = repository

    async def execute(
        self, study_uid: str, series_uid: str, query: InstanceQuery
    ) -> list[dict[str, Any]]:
        return await self._repo.find(study_uid, series_uid, query)


class GetInstanceMetadataUseCase:
    def __init__(self, repository: InstanceRepository) -> None:
        self._repo = repository

    async def execute(
        self, study_uid: str, series_uid: str, instance_uid: str
    ) -> list[dict[str, Any]]:
        return await self._repo.get_metadata(study_uid, series_uid, instance_uid)


class RetrieveInstanceUseCase:
    def __init__(self, repository: InstanceRepository) -> None:
        self._repo = repository

    async def execute(
        self, study_uid: str, series_uid: str, instance_uid: str
    ) -> AsyncIterator[bytes]:
        return await self._repo.stream(study_uid, series_uid, instance_uid)


class StoreInstancesUseCase:
    """STOW-RS — forward to the DICOMweb provider."""

    def __init__(self, repository: InstanceRepository) -> None:
        self._repo = repository

    async def execute(
        self,
        body: bytes,
        *,
        content_type: str,
        study_uid: str | None = None,
    ) -> dict[str, Any]:
        return await self._repo.store(body, content_type=content_type, study_uid=study_uid)
