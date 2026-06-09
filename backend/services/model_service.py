from __future__ import annotations

from functools import lru_cache
from typing import Any, Mapping

from sqlalchemy.engine import Engine

from backend.core.db import create_all, session_scope
from backend.repositories.models import ModelRepository
from backend.services.job_service import get_job_service


class ModelService:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def create_model(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        with session_scope(self.engine) as session:
            repo = ModelRepository(session)
            created = repo.create_model(
                name=str(payload["name"]),
                slug=str(payload["slug"]),
                onnx_path=str(payload["onnx_path"]),
                sidecar_path=self._to_optional_str(payload.get("sidecar_path")),
                model_kind=str(payload["model_kind"]),
            )
            return self._serialize(created)

    def list_models(self) -> list[dict[str, Any]]:
        with session_scope(self.engine) as session:
            repo = ModelRepository(session)
            return [self._serialize(item) for item in repo.list_models()]

    def publish_model(self, model_id: int, payload: Mapping[str, Any]) -> dict[str, Any]:
        with session_scope(self.engine) as session:
            repo = ModelRepository(session)
            model = repo.get(model_id)
            is_default_person_model = bool(payload["is_default_person_model"])

            if is_default_person_model and model.model_kind != "person_detector":
                raise ValueError("default person model must use person_detector kind")
            if is_default_person_model:
                repo.clear_default_person_model()

            updated = repo.update_publish_state(
                model_id,
                enabled=bool(payload["enabled"]),
                visible_in_advanced_mode=bool(payload["visible_in_advanced_mode"]),
                is_default_person_model=is_default_person_model,
            )
            return self._serialize(updated)

    @staticmethod
    def _to_optional_str(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _serialize(record: Any) -> dict[str, Any]:
        return {
            "id": record.id,
            "name": record.name,
            "slug": record.slug,
            "onnx_path": record.onnx_path,
            "sidecar_path": record.sidecar_path,
            "model_kind": record.model_kind,
            "enabled": record.enabled,
            "visible_in_advanced_mode": record.visible_in_advanced_mode,
            "is_default_person_model": record.is_default_person_model,
        }


@lru_cache(maxsize=1)
def get_model_service() -> ModelService:
    job_service = get_job_service()
    create_all(job_service.engine)
    return ModelService(job_service.engine)
