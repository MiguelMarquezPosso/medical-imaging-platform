"""Schemas for the sync presentation layer."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SyncUploadResponse(BaseModel):
    record_id: str
    sha256: str
    size_bytes: int
    status: str
    sop_instance_uid: str | None
    study_instance_uid: str | None
    series_instance_uid: str | None


class SyncListItem(BaseModel):
    id: UUID
    device_id: str
    user_id: str | None
    sha256: str
    size_bytes: int
    status: str
    sop_instance_uid: str | None
    study_instance_uid: str | None
    series_instance_uid: str | None
    storage_uri: str | None
    error: str | None
    created_at: datetime


class DICOMwebConfigPatch(BaseModel):
    base_url: str | None = Field(default=None, max_length=1024)
    auth_type: str | None = Field(default=None, pattern="^(none|basic|bearer)$")
    username: str | None = None
    password: str | None = None
    bearer_token: str | None = None
    verify_tls: bool | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=600)


class DICOMwebConfigOut(BaseModel):
    base_url: str
    auth_type: str
    verify_tls: bool
    timeout_seconds: int
    has_credentials: bool
