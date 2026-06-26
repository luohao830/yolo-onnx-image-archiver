from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    events: list["JobEvent"] = Field(default_factory=list)
    error_message: str | None = None
    download_ready: bool = False
    summary: dict[str, Any] | None = None


class PublishedModel(BaseModel):
    id: str
    name: str


class PublicJobEventsTokenRequest(BaseModel):
    access_token: str


class JobEventsTokenResponse(BaseModel):
    token: str


class DetectionBox(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str
    confidence: float
    bbox: list[float]
    cls_id: int

    @field_validator("bbox")
    @classmethod
    def _check_bbox_length(cls, v: list[float]) -> list[float]:
        if len(v) != 4:
            raise ValueError(f"bbox must contain exactly 4 coordinates, got {len(v)}")
        return v


class DetectionImage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    filename: str
    rel_path: str | None = None
    width: int = 0
    height: int = 0
    detections: list[DetectionBox] = Field(default_factory=list)
    has_drawn: bool = False
    drawn_path: str | None = None


class JobDetectionsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    images: list[DetectionImage] = Field(default_factory=list)


class JobEvent(BaseModel):
    id: int
    event_type: str
    message: str
    payload_json: dict[str, Any] = Field(default_factory=dict)


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
    events: list[JobEvent] = Field(default_factory=list)
    summary: dict[str, Any] | None = None
