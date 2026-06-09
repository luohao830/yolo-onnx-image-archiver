from __future__ import annotations

from typing import Any, Mapping


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


def normalize_job_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    normalized = dict(DEFAULT_JOB_PAYLOAD)
    if payload:
        normalized.update(dict(payload))
    if normalized["allowed_class_ids"] is not None:
        normalized["allowed_class_ids"] = list(normalized["allowed_class_ids"])
    if normalized["force_class_names"] is not None:
        normalized["force_class_names"] = list(normalized["force_class_names"])
    return normalized


def build_job_event(
    *,
    event_type: str,
    message: str,
    payload_json: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "message": message,
        "payload_json": dict(payload_json or {}),
    }
