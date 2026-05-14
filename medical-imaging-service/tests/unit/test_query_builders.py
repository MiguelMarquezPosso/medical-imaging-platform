"""Smoke tests for query value objects."""

from __future__ import annotations

import base64
import os
from datetime import date

os.environ.setdefault("PUBLIC_BASE_URL", "https://api.example.com")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("JWT_SECRET_KEY", "x" * 64)
os.environ.setdefault("JWT_ISSUER", "https://api.example.com")
os.environ.setdefault("JWT_AUDIENCE", "medical-imaging-platform")
os.environ.setdefault("DICOMWEB_BASE_URL", "https://orthanc.internal/dicom-web")
os.environ.setdefault("SYNC_AES_KEY_BASE64", base64.b64encode(b"\x42" * 32).decode())

from app.domains.studies.domain.entities import StudyQuery


def test_study_query_serializes_dates() -> None:
    q = StudyQuery(
        patient_id="P1",
        study_date_from=date(2024, 1, 1),
        study_date_to=date(2024, 6, 1),
        limit=10,
    )
    params = q.to_dicomweb_params()
    assert params["PatientID"] == "P1"
    assert params["StudyDate"] == "20240101-20240601"
    assert params["limit"] == "10"
