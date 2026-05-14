"""Abstract DICOMweb provider — the integration seam.

Concrete implementations (Orthanc, DCM4CHE, vendor cloud PACS, etc.) implement
this protocol. The application layer depends only on the protocol — never on a
specific PACS vendor.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol


class DICOMwebProvider(Protocol):
    """DICOMweb façade — QIDO-RS + WADO-RS + STOW-RS."""

    # ---------- QIDO-RS ----------
    async def search_studies(self, query: dict[str, Any]) -> list[dict[str, Any]]: ...
    async def search_series(self, study_uid: str, query: dict[str, Any]) -> list[dict[str, Any]]: ...
    async def search_instances(
        self, study_uid: str, series_uid: str, query: dict[str, Any]
    ) -> list[dict[str, Any]]: ...

    # ---------- WADO-RS ----------
    async def retrieve_study(self, study_uid: str) -> AsyncIterator[bytes]: ...
    async def retrieve_series(self, study_uid: str, series_uid: str) -> AsyncIterator[bytes]: ...
    async def retrieve_instance(
        self, study_uid: str, series_uid: str, instance_uid: str
    ) -> AsyncIterator[bytes]: ...
    async def retrieve_metadata(self, study_uid: str) -> list[dict[str, Any]]: ...
    async def retrieve_series_metadata(
        self, study_uid: str, series_uid: str
    ) -> list[dict[str, Any]]: ...
    async def retrieve_instance_metadata(
        self, study_uid: str, series_uid: str, instance_uid: str
    ) -> list[dict[str, Any]]: ...

    # ---------- STOW-RS ----------
    async def store_instances(
        self,
        body: bytes,
        *,
        content_type: str,
        study_uid: str | None = None,
    ) -> dict[str, Any]: ...

    # ---------- Health ----------
    async def healthcheck(self) -> bool: ...
