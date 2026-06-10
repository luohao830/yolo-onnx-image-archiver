from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from functools import lru_cache
from typing import Any, BinaryIO, Mapping

from sqlalchemy.engine import Engine

from backend.core.config import PROJECT_ROOT
from backend.core.db import create_all, session_scope
from backend.repositories.models import ModelRepository
from backend.services.job_service import get_job_service


DEFAULT_MODEL_KIND = "person_detector"


class ModelService:
    def __init__(
        self,
        engine: Engine,
        *,
        models_dir: Path | None = None,
        model_path_prefix: str | None = None,
    ) -> None:
        self.engine = engine
        self.models_dir = models_dir or self._default_models_dir()
        self.model_path_prefix = model_path_prefix or str(self.models_dir)

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
        self.refresh_models_from_directory()
        with session_scope(self.engine) as session:
            repo = ModelRepository(session)
            return [self._serialize(item) for item in repo.list_models()]

    def list_public_models(self) -> list[dict[str, Any]]:
        with session_scope(self.engine) as session:
            repo = ModelRepository(session)
            return [
                {
                    "id": str(item.id),
                    "name": item.name or item.slug or f"model-{item.id}",
                }
                for item in repo.list_models()
                if item.enabled and item.visible_in_advanced_mode
            ]

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

    def refresh_models_from_directory(self) -> list[dict[str, Any]]:
        self.models_dir.mkdir(parents=True, exist_ok=True)
        with session_scope(self.engine) as session:
            repo = ModelRepository(session)
            for model_path in sorted(self.models_dir.glob("*.onnx")):
                onnx_path = self._to_record_path(model_path)
                slug = self._build_unique_slug(repo, model_path.stem)
                if repo.get_by_onnx_path(onnx_path) is not None:
                    continue
                repo.create_model(
                    name=model_path.stem,
                    slug=slug,
                    onnx_path=onnx_path,
                    sidecar_path=None,
                    model_kind=DEFAULT_MODEL_KIND,
                )
            return [self._serialize(item) for item in repo.list_models()]

    def upload_onnx_model(self, *, filename: str, file_obj: BinaryIO) -> dict[str, Any]:
        safe_filename = Path(filename or "").name
        if Path(safe_filename).suffix.lower() != ".onnx":
            raise ValueError("only .onnx files can be uploaded")
        if not safe_filename:
            raise ValueError("model filename is required")

        self.models_dir.mkdir(parents=True, exist_ok=True)
        target = self.models_dir / safe_filename
        if target.exists():
            raise FileExistsError(f"model file already exists: {safe_filename}")

        try:
            with target.open("wb") as dst:
                shutil.copyfileobj(file_obj, dst)
        except Exception:
            target.unlink(missing_ok=True)
            raise

        with session_scope(self.engine) as session:
            repo = ModelRepository(session)
            onnx_path = self._to_record_path(target)
            if repo.get_by_onnx_path(onnx_path) is not None:
                raise FileExistsError(f"model record already exists: {safe_filename}")
            slug = self._build_unique_slug(repo, target.stem)
            created = repo.create_model(
                name=target.stem,
                slug=slug,
                onnx_path=onnx_path,
                sidecar_path=None,
                model_kind=DEFAULT_MODEL_KIND,
            )
            return self._serialize(created)

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

    @staticmethod
    def _default_models_dir() -> Path:
        configured = os.environ.get("MODELS_DIR")
        if configured:
            return Path(configured)
        return PROJECT_ROOT / "models"

    def _to_record_path(self, model_path: Path) -> str:
        return str(Path(self.model_path_prefix) / model_path.name)

    @classmethod
    def _normalize_slug(cls, value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-").lower()
        return slug or "model"

    def _build_unique_slug(self, repo: ModelRepository, value: str) -> str:
        base_slug = self._normalize_slug(value)
        slug = base_slug
        index = 2
        while repo.get_by_slug(slug) is not None:
            slug = f"{base_slug}-{index}"
            index += 1
        return slug


@lru_cache(maxsize=1)
def get_model_service() -> ModelService:
    job_service = get_job_service()
    create_all(job_service.engine)
    return ModelService(job_service.engine)
