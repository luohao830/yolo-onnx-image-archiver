from __future__ import annotations

import logging
from typing import Any, Mapping, Protocol

from sqlalchemy.orm import Session

from backend.repositories.models import ModelRepository

logger = logging.getLogger(__name__)

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
    normalized["allowed_class_ids"] = _normalize_allowed_class_ids(normalized["allowed_class_ids"])
    normalized["force_class_names"] = _normalize_force_class_names(normalized["force_class_names"])
    return normalized


def _normalize_allowed_class_ids(value: Any) -> list[int] | None:
    if value is None:
        return None
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple, set)):
        raise ValueError("allowed_class_ids must be a list of non-negative integers")

    class_ids: list[int] = []
    for item in value:
        if not isinstance(item, int) or isinstance(item, bool) or item < 0:
            raise ValueError("allowed_class_ids must be a list of non-negative integers")
        class_ids.append(item)
    return class_ids


def _normalize_force_class_names(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError("force_class_names must be a list of strings")

    class_names: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("force_class_names must be a list of strings")
        class_names.append(item)
    return class_names


def validate_job_payload(payload: dict[str, Any]) -> None:
    """校验高级模式推理参数的取值范围，拒绝无效输入。"""
    _require_positive_int(payload, "batch")
    _require_positive_int(payload, "preprocess_workers")
    _require_non_negative_int(payload, "prefetch_batches")
    if payload.get("imgsz") is not None:
        _require_positive_int(payload, "imgsz")
    _require_float_in_range(payload, "conf", 0.0, 1.0)
    _require_float_in_range(payload, "iou", 0.0, 1.0)


def _require_positive_int(payload: dict[str, Any], key: str) -> None:
    val = payload.get(key)
    if val is None:
        return
    if not isinstance(val, int) or isinstance(val, bool):
        raise ValueError(f"{key} must be an integer, got {type(val).__name__} {val!r}")
    if val <= 0:
        raise ValueError(f"{key} must be a positive integer, got {val!r}")


def _require_non_negative_int(payload: dict[str, Any], key: str) -> None:
    val = payload.get(key)
    if val is None:
        return
    if not isinstance(val, int) or isinstance(val, bool):
        raise ValueError(f"{key} must be an integer, got {type(val).__name__} {val!r}")
    if val < 0:
        raise ValueError(f"{key} must be a non-negative integer, got {val!r}")


def _require_float_in_range(payload: dict[str, Any], key: str, lo: float, hi: float) -> None:
    val = payload.get(key)
    if val is None:
        return
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise ValueError(f"{key} must be a number, got {val!r}")
    if not (lo <= float(val) <= hi):
        raise ValueError(f"{key} must be in [{lo}, {hi}], got {float(val)}")


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
        if advanced_payload:
            logger.info(
                "person_filter mode ignoring user-supplied advanced_payload keys: %r",
                list(advanced_payload.keys())[:8],
            )
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
        normalized = normalize_job_payload(advanced_payload)
        validate_job_payload(normalized)
        return normalized

    def validate_create(self, session: Session, model_id: int | None) -> None:
        if model_id is None:
            raise ValueError("advanced mode requires model_id")
        model = ModelRepository(session).get(model_id)
        if model is None:
            raise LookupError(f"model not found: {model_id}")
        if not model.enabled:
            raise ValueError("model is not enabled")
        if not model.visible_in_advanced_mode:
            raise ValueError("model is not visible in advanced mode")

    def resolve_model_id_for_upload(self, session: Session, model_id: int | None) -> int:
        if model_id is None:
            raise ValueError("advanced job has no model bound")
        model = ModelRepository(session).get(model_id)
        if model is None:
            raise LookupError(f"model not found: {model_id}")
        if not model.enabled:
            raise ValueError("model is not enabled")
        if not model.visible_in_advanced_mode:
            raise ValueError("model is not visible in advanced mode")
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
