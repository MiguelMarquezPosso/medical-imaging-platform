"""HTTP routes for the Series bounded context."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.dependencies import (
    AuthenticatedUser,
    get_dicomweb_provider,
    require_permissions,
)
from app.domains.series.application.use_cases import (
    GetSeriesMetadataUseCase,
    RetrieveSeriesUseCase,
    SearchSeriesUseCase,
)
from app.domains.series.domain.entities import SeriesQuery
from app.domains.series.infrastructure.repository_impl import (
    DICOMwebSeriesRepository,
)
from app.providers.dicomweb import DICOMwebProvider

router = APIRouter(prefix="/studies/{study_uid}/series", tags=["series"])


def _repo(provider: DICOMwebProvider = Depends(get_dicomweb_provider)) -> DICOMwebSeriesRepository:
    return DICOMwebSeriesRepository(provider)


@router.get("", summary="QIDO-RS — search series within a study")
async def search_series(
    study_uid: str,
    _user: Annotated[AuthenticatedUser, Depends(require_permissions("studies:read"))],
    repo: Annotated[DICOMwebSeriesRepository, Depends(_repo)],
    modality: Annotated[str | None, Query(max_length=32)] = None,
    series_description: Annotated[str | None, Query(max_length=255)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict]:
    use_case = SearchSeriesUseCase(repo)
    return await use_case.execute(
        study_uid,
        SeriesQuery(
            modality=modality,
            series_description=series_description,
            limit=limit,
            offset=offset,
        ),
    )


@router.get("/{series_uid}/metadata", summary="WADO-RS — retrieve series metadata")
async def get_series_metadata(
    study_uid: str,
    series_uid: str,
    _user: Annotated[AuthenticatedUser, Depends(require_permissions("studies:read"))],
    repo: Annotated[DICOMwebSeriesRepository, Depends(_repo)],
) -> list[dict]:
    use_case = GetSeriesMetadataUseCase(repo)
    return await use_case.execute(study_uid, series_uid)


@router.get("/{series_uid}", summary="WADO-RS — retrieve series")
async def retrieve_series(
    study_uid: str,
    series_uid: str,
    _user: Annotated[AuthenticatedUser, Depends(require_permissions("studies:read"))],
    repo: Annotated[DICOMwebSeriesRepository, Depends(_repo)],
) -> StreamingResponse:
    use_case = RetrieveSeriesUseCase(repo)
    iterator = await use_case.execute(study_uid, series_uid)
    return StreamingResponse(
        iterator,
        media_type='multipart/related; type="application/dicom"; transfer-syntax=*',
        headers={
            "Content-Disposition": f'attachment; filename="series-{series_uid}.dcm"'
        },
    )
