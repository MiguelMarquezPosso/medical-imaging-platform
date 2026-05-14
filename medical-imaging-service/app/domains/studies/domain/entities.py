"""Domain entities for the Studies bounded context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class StudyQuery:
    """Value object representing a QIDO-RS query."""

    patient_id: str | None = None
    patient_name: str | None = None
    study_date_from: date | None = None
    study_date_to: date | None = None
    accession_number: str | None = None
    modalities_in_study: str | None = None
    limit: int = 50
    offset: int = 0
    extras: dict[str, str] = field(default_factory=dict)

    def to_dicomweb_params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self.patient_id:
            params["PatientID"] = self.patient_id
        if self.patient_name:
            params["PatientName"] = self.patient_name
        if self.study_date_from or self.study_date_to:
            f = self.study_date_from.strftime("%Y%m%d") if self.study_date_from else ""
            t = self.study_date_to.strftime("%Y%m%d") if self.study_date_to else ""
            params["StudyDate"] = f"{f}-{t}" if (f or t) else ""
        if self.accession_number:
            params["AccessionNumber"] = self.accession_number
        if self.modalities_in_study:
            params["ModalitiesInStudy"] = self.modalities_in_study
        params["limit"] = str(self.limit)
        params["offset"] = str(self.offset)
        params.update(self.extras)
        return params


@dataclass
class Study:
    """Lightweight projection — most of the time we forward DICOM+JSON directly."""

    study_instance_uid: str
    patient_id: str | None = None
    patient_name: str | None = None
    study_date: str | None = None
    accession_number: str | None = None
    modalities: list[str] = field(default_factory=list)
    number_of_series: int | None = None
    number_of_instances: int | None = None
    source: str = "dicomweb"  # or "sync"
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dicomweb_json(cls, item: dict[str, Any]) -> Study:
        def _val(tag: str) -> Any:
            node = item.get(tag)
            if not node:
                return None
            return node.get("Value", [None])[0]

        modalities = item.get("00080061", {}).get("Value", []) or []
        if isinstance(modalities, str):
            modalities = [m.strip() for m in modalities.split(",") if m.strip()]

        return cls(
            study_instance_uid=str(_val("0020000D") or ""),
            patient_id=_val("00100020"),
            patient_name=(_val("00100010") or {}).get("Alphabetic")
            if isinstance(_val("00100010"), dict)
            else _val("00100010"),
            study_date=_val("00080020"),
            accession_number=_val("00080050"),
            modalities=list(modalities),
            number_of_series=_val("00201206"),
            number_of_instances=_val("00201208"),
            raw=item,
        )
