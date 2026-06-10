from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from backend.schemas.jobs import CreateJobRequest, JobReceipt, PublicJobStatus, PublishedModel
from backend.services.job_service import JobService, UploadTooLargeError, get_job_service
from backend.services.model_service import ModelService, get_model_service
from backend.services.scheduler_service import get_job_scheduler
from backend.workers.scheduler import Scheduler


router = APIRouter(prefix="/jobs", tags=["public-jobs"])


@router.post("", response_model=JobReceipt, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: CreateJobRequest,
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobReceipt:
    receipt = service.create_public_job(payload.mode)
    return JobReceipt(**receipt)


@router.get("/models", response_model=list[PublishedModel])
def list_published_models(
    service: Annotated[ModelService, Depends(get_model_service)],
) -> list[PublishedModel]:
    return [PublishedModel(**item) for item in service.list_public_models()]


@router.get("/{job_code}", response_model=PublicJobStatus)
def get_job(
    job_code: str,
    access_token: str,
    service: Annotated[JobService, Depends(get_job_service)],
) -> PublicJobStatus:
    job = service.get_public_job(job_code, access_token)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return PublicJobStatus(**job)


@router.post("/{job_code}/upload", response_model=PublicJobStatus)
def upload_job_file(
    job_code: str,
    access_token: str,
    file: Annotated[UploadFile, File()],
    service: Annotated[JobService, Depends(get_job_service)],
    scheduler: Annotated[Scheduler, Depends(get_job_scheduler)],
) -> PublicJobStatus:
    try:
        job_id, job = service.accept_public_job_upload(
            job_code,
            access_token,
            filename=file.filename or "upload",
            file_obj=file.file,
        )
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=413,
            detail=str(exc),
        ) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    scheduler.submit(job_id)
    return PublicJobStatus(**job)


@router.get("/{job_code}/download")
def download_job_result(
    job_code: str,
    access_token: str,
    service: Annotated[JobService, Depends(get_job_service)],
) -> FileResponse:
    try:
        result_zip = service.resolve_public_result_zip(job_code, access_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if result_zip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")

    return FileResponse(
        path=result_zip,
        media_type="application/zip",
        filename=f"{job_code}.zip",
    )
