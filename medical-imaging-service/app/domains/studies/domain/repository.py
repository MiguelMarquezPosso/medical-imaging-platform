"""Repository protocol for the Studies bounded context."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from app.domains.studies.domain.entities import StudyQuery


class StudyRepository(Protocol):
    async def find(self, query: StudyQuery) -> list[dict[str, Any]]: ...
    async def get_metadata(self, study_uid: str) -> list[dict[str, Any]]: ...
    async def stream(self, study_uid: str) -> AsyncIterator[bytes]: ...
