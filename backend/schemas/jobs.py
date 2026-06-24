from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class CreateJobRequest(BaseModel):
    mode: Literal["person_filter", "advanced"]
    model_id: int | None = None
    payload: dict[str, Any] | None = None


class JobReceipt(BaseModel):
    job_code: str
    access_token: str
    status: str


class PublicJobStatus(BaseModel):
    job_code: str
    mode: str
    status: str
    progress: int
    events: list["JobEvent"] = []
    error_message: str | None = None
    download_ready: bool = False
    summary: dict[str, Any] | None = None


class PublishedModel(BaseModel):
    id: str
    name: str


class JobEvent(BaseModel):
    id: int
    event_type: str
    message: str
    payload_json: dict[str, Any] = {}


class AdminJobDetail(BaseModel):
    id: int
    job_code: str
    mode: str
    status: str
    progress: int
    cancel_requested: bool
    error_message: str | None = None
    input_path: str | None = None
    result_dir: str | None = None
    result_zip_available: bool = False
    download_ready: bool = False
    events: list[JobEvent] = []
    summary: dict[str, Any] | None = None
