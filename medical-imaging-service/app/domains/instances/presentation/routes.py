"""QIDO/WADO routes for instances."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.dependencies import (
    AuthenticatedUser,
    get_dicomweb_provider,
    require_permissions,
)
from app.domains.instances.application.use_cases import (
    GetInstanceMetadataUseCase,
    RetrieveInstanceUseCase,
    SearchInstancesUseCase,
)
from app.domains.instances.domain.entities import InstanceQuery
from app.domains.instances.infrastructure.repository_impl import (
    DICOMwebInstanceRepository,
)
from app.providers.dicomweb import DICOMwebProvider

router = APIRouter(
    prefix="/studies/{study_uid}/series/{series_uid}/instances",
    tags=["instances"],
)


def _repo(provider: DICOMwebProvider = Depends(get_dicomweb_provider)) -> DICOMwebInstanceRepository:
    return DICOMwebInstanceRepository(provider)


@router.get("", summary="QIDO-RS — search instances within a series")
async def search_instances(
    study_uid: str,
    series_uid: str,
    _user: Annotated[AuthenticatedUser, Depends(require_permissions("studies:read"))],
    repo: Annotated[DICOMwebInstanceRepository, Depends(_repo)],
    sop_class_uid: Annotated[str | None, Query(max_length=128)] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict]:
    use_case = SearchInstancesUseCase(repo)
    return await use_case.execute(
        study_uid,
        series_uid,
        InstanceQuery(sop_class_uid=sop_class_uid, limit=limit, offset=offset),
    )


@router.get("/{instance_uid}/metadata", summary="WADO-RS — retrieve instance metadata")
async def get_instance_metadata(
    study_uid: str,
    series_uid: str,
    instance_uid: str,
    _user: Annotated[AuthenticatedUser, Depends(require_permissions("studies:read"))],
    repo: Annotated[DICOMwebInstanceRepository, Depends(_repo)],
) -> list[dict]:
    use_case = GetInstanceMetadataUseCase(repo)
    return await use_case.execute(study_uid, series_uid, instance_uid)


@router.get("/{instance_uid}", summary="WADO-RS — retrieve instance")
async def retrieve_instance(
    study_uid: str,
    series_uid: str,
    instance_uid: str,
    _user: Annotated[AuthenticatedUser, Depends(require_permissions("studies:read"))],
    repo: Annotated[DICOMwebInstanceRepository, Depends(_repo)],
) -> StreamingResponse:
    use_case = RetrieveInstanceUseCase(repo)
    iterator = await use_case.execute(study_uid, series_uid, instance_uid)
    return StreamingResponse(
        iterator,
        media_type='multipart/related; type="application/dicom"; transfer-syntax=*',
        headers={
            "Content-Disposition": f'attachment; filename="instance-{instance_uid}.dcm"'
        },
    )
