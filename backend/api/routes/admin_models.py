from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from backend.api.deps import require_admin
from backend.services.model_service import ModelService, get_model_service


router = APIRouter(prefix="/admin/models", tags=["admin-models"])


class CreateModelRequest(BaseModel):
    name: str
    slug: str
    model_kind: str
    onnx_path: str
    sidecar_path: str | None = None


class PublishModelRequest(BaseModel):
    enabled: bool
    visible_in_advanced_mode: bool
    is_default_person_model: bool = False


class ModelResponse(BaseModel):
    id: int
    name: str
    slug: str
    onnx_path: str
    sidecar_path: str | None = None
    model_kind: str
    enabled: bool
    visible_in_advanced_mode: bool
    is_default_person_model: bool


@router.get("", response_model=list[ModelResponse])
def list_models(
    admin: Annotated[dict[str, Any], Depends(require_admin)],
    service: Annotated[ModelService, Depends(get_model_service)],
) -> list[ModelResponse]:
    del admin
    return [ModelResponse(**item) for item in service.list_models()]


@router.post("", response_model=ModelResponse, status_code=status.HTTP_201_CREATED)
def create_model(
    payload: CreateModelRequest,
    admin: Annotated[dict[str, Any], Depends(require_admin)],
    service: Annotated[ModelService, Depends(get_model_service)],
) -> ModelResponse:
    del admin
    created = service.create_model(payload.model_dump())
    return ModelResponse(**created)


@router.post("/refresh", response_model=list[ModelResponse])
def refresh_models(
    admin: Annotated[dict[str, Any], Depends(require_admin)],
    service: Annotated[ModelService, Depends(get_model_service)],
) -> list[ModelResponse]:
    del admin
    return [ModelResponse(**item) for item in service.refresh_models_from_directory()]


@router.post("/upload", response_model=ModelResponse, status_code=status.HTTP_201_CREATED)
def upload_onnx_model(
    file: Annotated[UploadFile, File()],
    admin: Annotated[dict[str, Any], Depends(require_admin)],
    service: Annotated[ModelService, Depends(get_model_service)],
) -> ModelResponse:
    del admin
    try:
        created = service.upload_onnx_model(
            filename=file.filename or "",
            file_obj=file.file,
        )
    except FileExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ModelResponse(**created)


@router.patch("/{model_id}/publish", response_model=ModelResponse)
def publish_model(
    model_id: int,
    payload: PublishModelRequest,
    admin: Annotated[dict[str, Any], Depends(require_admin)],
    service: Annotated[ModelService, Depends(get_model_service)],
) -> ModelResponse:
    del admin
    try:
        updated = service.publish_model(model_id, payload.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ModelResponse(**updated)
