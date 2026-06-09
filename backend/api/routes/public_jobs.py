from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.schemas.jobs import CreateJobRequest, JobReceipt, PublicJobStatus
from backend.services.job_service import JobService, get_job_service


router = APIRouter(prefix="/jobs", tags=["public-jobs"])


@router.post("", response_model=JobReceipt, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: CreateJobRequest,
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobReceipt:
    receipt = service.create_public_job(payload.mode)
    return JobReceipt(**receipt)


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
