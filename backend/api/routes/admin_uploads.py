from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.api.deps import require_admin
from backend.schemas.jobs import AdminUploadedArchive, DeleteUploadedArchivesResponse
from backend.services.job_service import JobService, get_job_service


router = APIRouter(prefix="/admin/uploads", tags=["admin-uploads"])


class DeleteUploadedArchivesRequest(BaseModel):
    ids: list[int]


@router.get("", response_model=list[AdminUploadedArchive])
def list_uploaded_archives(
    admin: Annotated[dict[str, Any], Depends(require_admin)],
    service: Annotated[JobService, Depends(get_job_service)],
) -> list[AdminUploadedArchive]:
    del admin
    return [AdminUploadedArchive(**item) for item in service.list_uploaded_archives()]


@router.delete("", response_model=DeleteUploadedArchivesResponse)
def delete_uploaded_archives(
    payload: DeleteUploadedArchivesRequest,
    admin: Annotated[dict[str, Any], Depends(require_admin)],
    service: Annotated[JobService, Depends(get_job_service)],
) -> DeleteUploadedArchivesResponse:
    del admin
    return DeleteUploadedArchivesResponse(deleted=service.delete_uploaded_archives(payload.ids))
