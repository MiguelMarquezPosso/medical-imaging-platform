"""DTOs exposed by the studies presentation layer."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class StudySearchQuery(BaseModel):
    patient_id: str | None = Field(default=None, max_length=64)
    patient_name: str | None = Field(default=None, max_length=255)
    study_date_from: date | None = None
    study_date_to: date | None = None
    accession_number: str | None = Field(default=None, max_length=64)
    modalities_in_study: str | None = Field(default=None, max_length=32)
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
