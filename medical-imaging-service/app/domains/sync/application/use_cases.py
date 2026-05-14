"""Application use case for Raspberry Pi sync ingestion."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

from app.core.errors import ConflictError, UpstreamError, ValidationError
from app.core.logging import get_logger
from app.domains.sync.domain.entities import SyncRecord, SyncStatus
from app.domains.sync.infrastructure.repository_impl import (
    AuditLogRepository,
    SqlSyncRecordRepository,
)
from app.providers.crypto import SyncCrypto
from app.providers.dicomweb import DICOMwebProvider
from app.providers.storage import StorageProvider

log = get_logger("sync.ingest")


@dataclass
class IngestRequest:
    encrypted_body: bytes
    device_id: str
    user_id: str | None
    request_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    forward_to_pacs: bool = True


@dataclass
class IngestResult:
    record_id: str
    sha256: str
    size_bytes: int
    status: str
    sop_instance_uid: str | None
    study_instance_uid: str | None
    series_instance_uid: str | None
    storage_uri: str | None


class IngestSyncUploadUseCase:
    """Decrypt → hash → store → register → optionally forward to PACS."""

    def __init__(
        self,
        *,
        records: SqlSyncRecordRepository,
        audit: AuditLogRepository,
        crypto: SyncCrypto,
        storage: StorageProvider,
        dicomweb: DICOMwebProvider,
    ) -> None:
        self.records = records
        self.audit = audit
        self.crypto = crypto
        self.storage = storage
        self.dicomweb = dicomweb

    async def execute(self, req: IngestRequest) -> IngestResult:
        if not req.encrypted_body:
            raise ValidationError("Empty body")

        # 1. Decrypt
        plain = self.crypto.decrypt(req.encrypted_body, aad=req.device_id.encode())

        # 2. Hash for dedup and audit
        sha = hashlib.sha256(plain).hexdigest()
        size = len(plain)

        if await self.records.exists_by_sha(sha):
            await self.audit.record(
                actor=req.user_id,
                action="sync.duplicate",
                target=sha,
                request_id=req.request_id,
                ip_address=req.ip_address,
                user_agent=req.user_agent,
                payload={"device_id": req.device_id, "size": size},
            )
            raise ConflictError("This DICOM payload has already been synced", details={"sha256": sha})

        # 3. Parse to extract UIDs (best effort — we still store on parse failure)
        sop_uid = study_uid = series_uid = None
        try:
            import pydicom  # local import to keep the module light

            ds = pydicom.dcmread(io.BytesIO(plain), stop_before_pixels=False, force=True)
            sop_uid = getattr(ds, "SOPInstanceUID", None)
            study_uid = getattr(ds, "StudyInstanceUID", None)
            series_uid = getattr(ds, "SeriesInstanceUID", None)
            sop_uid = str(sop_uid) if sop_uid else None
            study_uid = str(study_uid) if study_uid else None
            series_uid = str(series_uid) if series_uid else None
        except Exception as exc:  # noqa: BLE001
            log.warning("dicom_parse_failed", error=str(exc))

        # 4. Persist DICOM to central storage
        key = self._build_key(sha, study_uid, series_uid, sop_uid)
        storage_uri = await self.storage.put(key, plain, content_type="application/dicom")

        record = SyncRecord(
            device_id=req.device_id,
            user_id=req.user_id,
            sha256=sha,
            size_bytes=size,
            status=SyncStatus.STORED,
            sop_instance_uid=sop_uid,
            study_instance_uid=study_uid,
            series_instance_uid=series_uid,
            storage_uri=storage_uri,
        )
        await self.records.add(record)

        # 5. Forward to PACS so the same QIDO/WADO endpoints can serve it.
        #    Failure here is non-fatal — the file is already stored centrally and
        #    a background worker can retry. We mark the record accordingly.
        if req.forward_to_pacs:
            try:
                multipart = _wrap_multipart(plain)
                await self.dicomweb.store_instances(
                    multipart,
                    content_type=_MULTIPART_CT,
                    study_uid=study_uid,
                )
                record.mark_forwarded()
                await self.records.update(record)
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "stow_forward_failed",
                    sop=sop_uid,
                    error=str(exc),
                )
                # Record stays in `stored` — a separate retry job can promote it.
                if isinstance(exc, UpstreamError):
                    pass  # swallow; record reflects the truth

        # 6. Audit
        await self.audit.record(
            actor=req.user_id,
            action="sync.upload",
            target=str(record.id),
            request_id=req.request_id,
            ip_address=req.ip_address,
            user_agent=req.user_agent,
            payload={
                "device_id": req.device_id,
                "sha256": sha,
                "size": size,
                "sop": sop_uid,
                "study": study_uid,
                "series": series_uid,
                "status": record.status.value,
            },
        )

        return IngestResult(
            record_id=str(record.id),
            sha256=sha,
            size_bytes=size,
            status=record.status.value,
            sop_instance_uid=sop_uid,
            study_instance_uid=study_uid,
            series_instance_uid=series_uid,
            storage_uri=storage_uri,
        )

    @staticmethod
    def _build_key(sha: str, study: str | None, series: str | None, sop: str | None) -> str:
        parts = ["incoming", study or "unknown-study", series or "unknown-series", f"{sop or sha[:16]}.dcm"]
        return "/".join(parts)


_BOUNDARY = "medimgsyncboundary"
_MULTIPART_CT = f'multipart/related; type="application/dicom"; boundary={_BOUNDARY}'


def _wrap_multipart(dicom_bytes: bytes) -> bytes:
    """Wrap a raw DICOM file in a STOW-RS multipart/related body."""
    crlf = b"\r\n"
    boundary = f"--{_BOUNDARY}".encode()
    body = (
        boundary
        + crlf
        + b"Content-Type: application/dicom"
        + crlf
        + crlf
        + dicom_bytes
        + crlf
        + boundary
        + b"--"
        + crlf
    )
    return body
