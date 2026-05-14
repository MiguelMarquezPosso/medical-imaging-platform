"""HTTP routes for the Studies bounded context.

These are the QIDO/WADO-RS endpoints for studies. The frontend never knows
whether a study originally arrived via DICOMweb / PACS or via the Raspberry Pi
sync flow — both feed the same provider abstraction.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.dependencies import (
    AuthenticatedUser,
    get_dicomweb_provider,
    require_permissions,
)
from app.domains.studies.application.use_cases import (
    GetStudyMetadataUseCase,
    RetrieveStudyUseCase,
    SearchStudiesUseCase,
)
from app.domains.studies.domain.entities import StudyQuery
from app.domains.studies.infrastructure.repository_impl import (
    DICOMwebStudyRepository,
)
from app.domains.studies.presentation.schemas import StudySearchQuery
from app.providers.dicomweb import DICOMwebProvider

router = APIRouter(prefix="/studies", tags=["studies"])


def _repo(provider: DICOMwebProvider = Depends(get_dicomweb_provider)) -> DICOMwebStudyRepository:
    return DICOMwebStudyRepository(provider)


@router.get("", summary="QIDO-RS — search studies")
async def search_studies(
    _user: Annotated[AuthenticatedUser, Depends(require_permissions("studies:read"))],
    repo: Annotated[DICOMwebStudyRepository, Depends(_repo)],
    q: Annotated[StudySearchQuery, Query()],
) -> list[dict]:
    use_case = SearchStudiesUseCase(repo)
    query = StudyQuery(
        patient_id=q.patient_id,
        patient_name=q.patient_name,
        study_date_from=q.study_date_from,
        study_date_to=q.study_date_to,
        accession_number=q.accession_number,
        modalities_in_study=q.modalities_in_study,
        limit=q.limit,
        offset=q.offset,
    )
    return await use_case.execute(query)


@router.get("/{study_uid}/metadata", summary="WADO-RS — retrieve study metadata")
async def get_study_metadata(
    study_uid: str,
    _user: Annotated[AuthenticatedUser, Depends(require_permissions("studies:read"))],
    repo: Annotated[DICOMwebStudyRepository, Depends(_repo)],
) -> list[dict]:
    use_case = GetStudyMetadataUseCase(repo)
    return await use_case.execute(study_uid)


@router.get("/{study_uid}", summary="WADO-RS — retrieve study")
async def retrieve_study(
    study_uid: str,
    _user: Annotated[AuthenticatedUser, Depends(require_permissions("studies:read"))],
    repo: Annotated[DICOMwebStudyRepository, Depends(_repo)],
) -> StreamingResponse:
    use_case = RetrieveStudyUseCase(repo)
    iterator = await use_case.execute(study_uid)
    return StreamingResponse(
        iterator,
        media_type='multipart/related; type="application/dicom"; transfer-syntax=*',
        headers={"Content-Disposition": f'attachment; filename="study-{study_uid}.dcm"'},
    )
