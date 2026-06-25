from __future__ import annotations

from typing import Any, Mapping, Protocol

from sqlalchemy.orm import Session

from backend.repositories.models import ModelRepository

DEFAULT_JOB_PAYLOAD: dict[str, Any] = {
    "recursive": True,
    "batch": 16,
    "imgsz": None,
    "conf": 0.25,
    "iou": 0.45,
    "copy_fallback": False,
    "preprocess_workers": 4,
    "prefetch_batches": 2,
    "allowed_class_ids": None,
    "unmatched_label": "no_detection",
    "force_class_names": None,
    "draw_boxes": False,
    "save_txt": False,
    "execution_device": "auto",
}

PERSON_FILTER_PAYLOAD: dict[str, Any] = {
    "allowed_class_ids": [0],
    "unmatched_label": "no_person",
    "force_class_names": ["person"],
}


def normalize_job_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    normalized = dict(DEFAULT_JOB_PAYLOAD)
    if payload:
        normalized.update(dict(payload))
    if normalized["allowed_class_ids"] is not None:
        normalized["allowed_class_ids"] = list(normalized["allowed_class_ids"])
    if normalized["force_class_names"] is not None:
        normalized["force_class_names"] = list(normalized["force_class_names"])
    return normalized


class JobModeHandler(Protocol):
    """任务模式处理器：payload 构造、创建校验、上传时模型解析。"""

    def build_payload(self, advanced_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        ...

    def validate_create(self, session: Session, model_id: int | None) -> None:
        ...

    def resolve_model_id_for_upload(self, session: Session, model_id: int | None) -> int:
        ...


class PersonFilterModeHandler:
    """人员筛选模式：绑定默认人员模型，合并 person_filter 默认 payload。"""

    def build_payload(self, advanced_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        del advanced_payload
        return normalize_job_payload(PERSON_FILTER_PAYLOAD)

    def validate_create(self, session: Session, model_id: int | None) -> None:
        del session, model_id

    def resolve_model_id_for_upload(self, session: Session, model_id: int | None) -> int:
        del model_id
        model = ModelRepository(session).get_default_person_model()
        if model is None:
            raise ValueError("default person model is not configured")
        return model.id


class AdvancedModeHandler:
    """高级模式：创建时校验模型存在且可见，上传时使用绑定的 model_id。"""

    def build_payload(self, advanced_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return normalize_job_payload(advanced_payload)

    def validate_create(self, session: Session, model_id: int | None) -> None:
        if model_id is None:
            raise ValueError("advanced mode requires model_id")
        model = ModelRepository(session).get(model_id)
        if model is None:
            raise LookupError(f"model not found: {model_id}")
        if not model.visible_in_advanced_mode:
            raise ValueError("model is not visible in advanced mode")

    def resolve_model_id_for_upload(self, session: Session, model_id: int | None) -> int:
        if model_id is None:
            raise ValueError("advanced job has no model bound")
        ModelRepository(session).get(model_id)
        return model_id


_MODE_HANDLERS: dict[str, JobModeHandler] = {
    "person_filter": PersonFilterModeHandler(),
    "advanced": AdvancedModeHandler(),
}


def get_mode_handler(mode: str) -> JobModeHandler:
    handler = _MODE_HANDLERS.get(mode)
    if handler is None:
        raise ValueError(f"unsupported job mode: {mode}")
    return handler
