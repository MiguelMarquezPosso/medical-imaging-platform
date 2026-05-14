"""DICOMweb-backed instance repository (QIDO + WADO + STOW)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.domains.instances.domain.entities import InstanceQuery
from app.providers.dicomweb import DICOMwebProvider


class DICOMwebInstanceRepository:
    def __init__(self, provider: DICOMwebProvider) -> None:
        self._provider = provider

    async def find(
        self, study_uid: str, series_uid: str, query: InstanceQuery
    ) -> list[dict[str, Any]]:
        return await self._provider.search_instances(
            study_uid, series_uid, query.to_dicomweb_params()
        )

    async def get_metadata(
        self, study_uid: str, series_uid: str, instance_uid: str
    ) -> list[dict[str, Any]]:
        return await self._provider.retrieve_instance_metadata(
            study_uid, series_uid, instance_uid
        )

    async def stream(
        self, study_uid: str, series_uid: str, instance_uid: str
    ) -> AsyncIterator[bytes]:
        return await self._provider.retrieve_instance(study_uid, series_uid, instance_uid)

    async def store(
        self,
        body: bytes,
        *,
        content_type: str,
        study_uid: str | None,
    ) -> dict[str, Any]:
        return await self._provider.store_instances(
            body, content_type=content_type, study_uid=study_uid
        )
