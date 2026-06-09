from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.api.deps import require_admin
from backend.services.config_service import ConfigService, get_config_service


router = APIRouter(prefix="/admin/configs", tags=["admin-configs"])


class ConcurrencyConfigResponse(BaseModel):
    task_slots: int
    gpu_slots: int


class UpdateConcurrencyRequest(BaseModel):
    task_slots: int = Field(ge=1, le=3)
    gpu_slots: int = Field(ge=1, le=3)


@router.get("", response_model=ConcurrencyConfigResponse)
def list_configs(
    admin: Annotated[dict[str, Any], Depends(require_admin)],
    service: Annotated[ConfigService, Depends(get_config_service)],
) -> ConcurrencyConfigResponse:
    del admin
    configs = service.list_configs()
    return ConcurrencyConfigResponse(**configs)


@router.put("/concurrency", response_model=ConcurrencyConfigResponse)
def update_concurrency(
    payload: UpdateConcurrencyRequest,
    admin: Annotated[dict[str, Any], Depends(require_admin)],
    service: Annotated[ConfigService, Depends(get_config_service)],
) -> ConcurrencyConfigResponse:
    del admin
    configs = service.update_concurrency(
        task_slots=payload.task_slots,
        gpu_slots=payload.gpu_slots,
    )
    return ConcurrencyConfigResponse(**configs)
