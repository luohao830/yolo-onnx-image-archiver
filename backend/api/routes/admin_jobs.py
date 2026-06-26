from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.api.deps import require_admin
from backend.core.admin_auth import AdminTokenService, get_admin_token_service
from backend.schemas.jobs import AdminJobDetail
from backend.services.job_service import JobService, get_job_service


router = APIRouter(prefix="/admin/jobs", tags=["admin-jobs"])


class AdminJobResponse(BaseModel):
    id: int
    job_code: str
    mode: str
    status: str
    progress: int
    cancel_requested: bool
    error_message: str | None = None
    result_zip_available: bool = False
    download_ready: bool = False


class AdminJobEventsTokenResponse(BaseModel):
    token: str


@router.get("", response_model=list[AdminJobResponse])
def list_jobs(
    admin: Annotated[dict[str, Any], Depends(require_admin)],
    service: Annotated[JobService, Depends(get_job_service)],
) -> list[AdminJobResponse]:
    del admin
    return [AdminJobResponse(**item) for item in service.list_admin_jobs()]


@router.get("/{job_id}", response_model=AdminJobDetail)
def get_job_detail(
    job_id: int,
    admin: Annotated[dict[str, Any], Depends(require_admin)],
    service: Annotated[JobService, Depends(get_job_service)],
) -> AdminJobDetail:
    del admin
    try:
        job = service.get_admin_job(job_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AdminJobDetail(**job)


@router.post("/{job_id}/events-token", response_model=AdminJobEventsTokenResponse)
def issue_job_events_token(
    job_id: int,
    admin: Annotated[dict[str, Any], Depends(require_admin)],
    service: Annotated[JobService, Depends(get_job_service)],
    token_service: Annotated[AdminTokenService, Depends(get_admin_token_service)],
) -> AdminJobEventsTokenResponse:
    del admin
    try:
        service.get_admin_job(job_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AdminJobEventsTokenResponse(token=token_service.issue_sse(job_id))


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


@router.get("/{job_id}/download")
def download_job_result(
    job_id: int,
    admin: Annotated[dict[str, Any], Depends(require_admin)],
    service: Annotated[JobService, Depends(get_job_service)],
) -> FileResponse:
    del admin
    try:
        result_zip = service.resolve_admin_result_zip(job_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return FileResponse(
        path=result_zip,
        media_type="application/zip",
        filename=f"job-{job_id}.zip",
    )


@router.get("/{job_id}/detections")
def get_job_detections(
    job_id: int,
    admin: Annotated[dict[str, Any], Depends(require_admin)],
    service: Annotated[JobService, Depends(get_job_service)],
) -> dict:
    del admin
    try:
        detections = service.get_admin_detections(job_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if detections is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="detections not found")
    return detections


@router.get("/{job_id}/images/{file_path:path}")
def get_job_image(
    job_id: int,
    file_path: str,
    admin: Annotated[dict[str, Any], Depends(require_admin)],
    service: Annotated[JobService, Depends(get_job_service)],
) -> FileResponse:
    del admin
    try:
        resolved = service.resolve_admin_result_image(job_id, file_path)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if resolved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="image not found")
    return FileResponse(path=resolved)
