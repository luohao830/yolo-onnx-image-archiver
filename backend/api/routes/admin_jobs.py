from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.api.deps import require_admin
from backend.services.job_service import JobService, get_job_service


router = APIRouter(prefix="/admin/jobs", tags=["admin-jobs"])


class AdminJobResponse(BaseModel):
    id: int
    job_code: str
    mode: str
    status: str
    cancel_requested: bool
    error_message: str | None = None


@router.get("", response_model=list[AdminJobResponse])
def list_jobs(
    admin: Annotated[dict[str, Any], Depends(require_admin)],
    service: Annotated[JobService, Depends(get_job_service)],
) -> list[AdminJobResponse]:
    del admin
    return [AdminJobResponse(**item) for item in service.list_admin_jobs()]


@router.post("/{job_id}/cancel", response_model=AdminJobResponse)
def cancel_job(
    job_id: int,
    admin: Annotated[dict[str, Any], Depends(require_admin)],
    service: Annotated[JobService, Depends(get_job_service)],
) -> AdminJobResponse:
    del admin
    try:
        job = service.cancel_job(job_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AdminJobResponse(**job)


@router.post("/{job_id}/retry", response_model=AdminJobResponse)
def retry_job(
    job_id: int,
    admin: Annotated[dict[str, Any], Depends(require_admin)],
    service: Annotated[JobService, Depends(get_job_service)],
) -> AdminJobResponse:
    del admin
    try:
        job = service.retry_job(job_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return AdminJobResponse(**job)
