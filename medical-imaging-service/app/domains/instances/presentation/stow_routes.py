"""STOW-RS — store DICOM instances via the DICOMweb provider."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from app.core.config import get_settings
from app.core.dependencies import (
    AuthenticatedUser,
    get_dicomweb_provider,
    require_permissions,
)
from app.core.errors import ValidationError
from app.domains.instances.application.use_cases import StoreInstancesUseCase
from app.domains.instances.infrastructure.repository_impl import (
    DICOMwebInstanceRepository,
)
from app.providers.dicomweb import DICOMwebProvider

router = APIRouter(prefix="/studies", tags=["instances"])


def _repo(provider: DICOMwebProvider = Depends(get_dicomweb_provider)) -> DICOMwebInstanceRepository:
    return DICOMwebInstanceRepository(provider)


def _validate_stow_content_type(content_type: str) -> None:
    if not content_type:
        raise ValidationError("Content-Type header is required for STOW-RS")
    lower = content_type.lower()
    if "multipart/related" not in lower:
        raise ValidationError("STOW-RS requires multipart/related body")
    if "application/dicom" not in lower:
        raise ValidationError("STOW-RS body type must be application/dicom")


@router.post("", summary="STOW-RS — store one or more DICOM instances")
async def stow_instances_no_study(
    request: Request,
    _user: Annotated[AuthenticatedUser, Depends(require_permissions("studies:write"))],
    repo: Annotated[DICOMwebInstanceRepository, Depends(_repo)],
    content_type: Annotated[str, Header(alias="Content-Type")] = "",
):
    _validate_stow_content_type(content_type)
    body = await _read_capped_body(request)
    use_case = StoreInstancesUseCase(repo)
    return await use_case.execute(body, content_type=content_type, study_uid=None)


@router.post("/{study_uid}", summary="STOW-RS — store instances into a specific study")
async def stow_instances_with_study(
    study_uid: str,
    request: Request,
    _user: Annotated[AuthenticatedUser, Depends(require_permissions("studies:write"))],
    repo: Annotated[DICOMwebInstanceRepository, Depends(_repo)],
    content_type: Annotated[str, Header(alias="Content-Type")] = "",
):
    _validate_stow_content_type(content_type)
    body = await _read_capped_body(request)
    use_case = StoreInstancesUseCase(repo)
    return await use_case.execute(body, content_type=content_type, study_uid=study_uid)


async def _read_capped_body(request: Request) -> bytes:
    cap = get_settings().SYNC_MAX_UPLOAD_BYTES
    buf = bytearray()
    async for chunk in request.stream():
        buf.extend(chunk)
        if len(buf) > cap:
            raise ValidationError(f"STOW body exceeds maximum allowed size ({cap} bytes)")
    return bytes(buf)
