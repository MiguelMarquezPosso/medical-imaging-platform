"""Sync endpoints — exposed under /api/v1/sync.

The Raspberry Pi devices authenticate with a JWT minted by the Auth Service and
sign their requests with an HMAC of the body. Bodies are AES-256-GCM encrypted.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.config.dicomweb_config import (
    DICOMwebConfigStore,
    get_dicomweb_config_store,
)
from app.core.dependencies import (
    AuthenticatedUser,
    get_current_user,
    get_db,
    get_dicomweb_provider,
    get_storage_provider,
    get_sync_crypto,
    require_roles,
    require_sync_device,
)
from app.core.errors import UnauthorizedError, ValidationError
from app.core.security import verify_hmac_signature
from app.domains.sync.application.use_cases import (
    IngestRequest,
    IngestSyncUploadUseCase,
)
from app.domains.sync.infrastructure.repository_impl import (
    AuditLogRepository,
    SqlSyncRecordRepository,
)
from app.domains.sync.presentation.schemas import (
    DICOMwebConfigOut,
    DICOMwebConfigPatch,
    SyncListItem,
    SyncUploadResponse,
)
from app.providers.crypto import SyncCrypto
from app.providers.dicomweb import DICOMwebProvider
from app.providers.storage import StorageProvider

router = APIRouter(prefix="/sync", tags=["sync"])


# --------- Pi upload endpoint ---------------------------------------------
@router.post(
    "/upload",
    response_model=SyncUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest an encrypted .dicom file from a Raspberry Pi device",
)
async def upload(
    request: Request,
    user: Annotated[AuthenticatedUser, Depends(require_sync_device)],
    session: Annotated[AsyncSession, Depends(get_db)],
    crypto: Annotated[SyncCrypto, Depends(get_sync_crypto)],
    storage: Annotated[StorageProvider, Depends(get_storage_provider)],
    dicomweb: Annotated[DICOMwebProvider, Depends(get_dicomweb_provider)],
    x_sync_device_id: Annotated[str, Header(alias="X-Sync-Device-Id", max_length=64)],
    x_sync_signature: Annotated[
        str | None, Header(alias="X-Sync-Signature", max_length=512)
    ] = None,
) -> SyncUploadResponse:
    settings = get_settings()

    # Cap the body BEFORE buffering it so a malicious peer cannot fill memory
    body = await _read_capped(request, settings.SYNC_MAX_UPLOAD_BYTES)

    # Verify HMAC signature when a key is configured
    if settings.SYNC_HMAC_KEY_BASE64:
        if not x_sync_signature:
            raise UnauthorizedError("Missing X-Sync-Signature header")
        if not verify_hmac_signature(body, x_sync_signature):
            raise UnauthorizedError("Invalid request signature")

    records = SqlSyncRecordRepository(session)
    audit = AuditLogRepository(session)
    use_case = IngestSyncUploadUseCase(
        records=records,
        audit=audit,
        crypto=crypto,
        storage=storage,
        dicomweb=dicomweb,
    )

    ip = request.headers.get("X-Forwarded-For") or (
        request.client.host if request.client else None
    )

    result = await use_case.execute(
        IngestRequest(
            encrypted_body=body,
            device_id=x_sync_device_id,
            user_id=user.id,
            request_id=request.headers.get("X-Request-ID"),
            ip_address=ip,
            user_agent=request.headers.get("User-Agent"),
            forward_to_pacs=True,
        )
    )
    await session.commit()

    return SyncUploadResponse(
        record_id=result.record_id,
        sha256=result.sha256,
        size_bytes=result.size_bytes,
        status=result.status,
        sop_instance_uid=result.sop_instance_uid,
        study_instance_uid=result.study_instance_uid,
        series_instance_uid=result.series_instance_uid,
    )


# --------- Recent sync events (admin / radiologist view) -----------------
@router.get(
    "/records",
    response_model=list[SyncListItem],
    summary="List recent sync events",
)
async def list_records(
    _user: Annotated[AuthenticatedUser, Depends(require_roles("admin", "radiologist"))],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 100,
    offset: int = 0,
) -> list[SyncListItem]:
    repo = SqlSyncRecordRepository(session)
    items = await repo.list_recent(limit=limit, offset=offset)
    return [
        SyncListItem(
            id=r.id,
            device_id=r.device_id,
            user_id=r.user_id,
            sha256=r.sha256,
            size_bytes=r.size_bytes,
            status=r.status.value,
            sop_instance_uid=r.sop_instance_uid,
            study_instance_uid=r.study_instance_uid,
            series_instance_uid=r.series_instance_uid,
            storage_uri=r.storage_uri,
            error=r.error,
            created_at=r.created_at,
        )
        for r in items
    ]


# --------- Dynamic DICOMweb configuration --------------------------------
@router.get(
    "/dicomweb-config",
    response_model=DICOMwebConfigOut,
    summary="Inspect the active DICOMweb provider configuration",
)
async def get_dicomweb_config(
    _user: Annotated[AuthenticatedUser, Depends(require_roles("admin"))],
    store: Annotated[DICOMwebConfigStore, Depends(get_dicomweb_config_store)],
) -> DICOMwebConfigOut:
    cfg = store.get()
    return DICOMwebConfigOut(
        base_url=cfg.base_url,
        auth_type=cfg.auth_type,
        verify_tls=cfg.verify_tls,
        timeout_seconds=cfg.timeout_seconds,
        has_credentials=bool(cfg.username or cfg.bearer_token),
    )


@router.patch(
    "/dicomweb-config",
    response_model=DICOMwebConfigOut,
    summary="Reconfigure the DICOMweb provider at runtime (admin only)",
)
async def patch_dicomweb_config(
    payload: DICOMwebConfigPatch,
    user: Annotated[AuthenticatedUser, Depends(require_roles("admin"))],
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    store: Annotated[DICOMwebConfigStore, Depends(get_dicomweb_config_store)],
) -> DICOMwebConfigOut:
    diff = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not diff:
        raise ValidationError("No fields to update")
    new_cfg = store.update(**diff)

    audit = AuditLogRepository(session)
    await audit.record(
        actor=user.id,
        action="dicomweb_config.update",
        target=new_cfg.base_url,
        request_id=request.headers.get("X-Request-ID"),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        payload={"changed_fields": sorted(diff.keys())},
    )
    await session.commit()

    return DICOMwebConfigOut(
        base_url=new_cfg.base_url,
        auth_type=new_cfg.auth_type,
        verify_tls=new_cfg.verify_tls,
        timeout_seconds=new_cfg.timeout_seconds,
        has_credentials=bool(new_cfg.username or new_cfg.bearer_token),
    )


# --------- Helpers --------------------------------------------------------
async def _read_capped(request: Request, cap: int) -> bytes:
    buf = bytearray()
    async for chunk in request.stream():
        buf.extend(chunk)
        if len(buf) > cap:
            raise ValidationError(f"Upload exceeds maximum size ({cap} bytes)")
    return bytes(buf)
