from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class CreateJobRequest(BaseModel):
    mode: Literal["person_filter", "advanced"]


class JobReceipt(BaseModel):
    job_code: str
    access_token: str
    status: str


class PublicJobStatus(BaseModel):
    job_code: str
    mode: str
    status: str
    error_message: str | None = None


class PublishedModel(BaseModel):
    id: str
    name: str
