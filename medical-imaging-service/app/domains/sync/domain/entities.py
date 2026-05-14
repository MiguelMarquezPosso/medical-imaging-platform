"""Sync domain entities."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4


class SyncStatus(str, Enum):
    RECEIVED = "received"
    DECRYPTED = "decrypted"
    STORED = "stored"
    FORWARDED = "forwarded"  # forwarded to DICOMweb provider
    FAILED = "failed"


class SyncRecord:
    """Aggregate root for a single sync upload event."""

    def __init__(
        self,
        *,
        id: UUID | None = None,
        device_id: str,
        user_id: str | None,
        sha256: str,
        size_bytes: int,
        status: SyncStatus = SyncStatus.RECEIVED,
        sop_instance_uid: str | None = None,
        study_instance_uid: str | None = None,
        series_instance_uid: str | None = None,
        storage_uri: str | None = None,
        error: str | None = None,
        created_at: datetime | None = None,
    ) -> None:
        self.id = id or uuid4()
        self.device_id = device_id
        self.user_id = user_id
        self.sha256 = sha256
        self.size_bytes = size_bytes
        self.status = status
        self.sop_instance_uid = sop_instance_uid
        self.study_instance_uid = study_instance_uid
        self.series_instance_uid = series_instance_uid
        self.storage_uri = storage_uri
        self.error = error
        self.created_at = created_at or datetime.now(UTC)

    def mark_stored(self, storage_uri: str) -> None:
        self.storage_uri = storage_uri
        self.status = SyncStatus.STORED

    def mark_forwarded(self) -> None:
        self.status = SyncStatus.FORWARDED

    def mark_failed(self, error: str) -> None:
        self.status = SyncStatus.FAILED
        self.error = error[:1024]
