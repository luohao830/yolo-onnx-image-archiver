from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping

from webui.processing import InferenceProgress, package_output_dir, run_inference


# 落盘到 JobRecord.summary_json 时保留的字段（排除 out_dir 等非统计项）。
SUMMARY_JSON_KEYS = (
    "total",
    "written",
    "by_label",
    "elapsed_sec",
    "inference_sec",
    "preprocess_sec",
    "postprocess_sec",
    "hardlink_sec",
    "draw_sec",
    "drawn",
    "txt_written",
    "hardlinked",
    "copied",
    "failed",
    "used_batch",
    "used_imgsz",
    "cuda_enabled",
    "providers",
)

DETECTIONS_FILENAME = "_detections.json"


def build_job_summary_json(summary: Mapping[str, Any]) -> dict[str, Any]:
    """从 run_inference 返回的 summary 提取可落盘的统计字段。"""
    result: dict[str, Any] = {}
    for key in SUMMARY_JSON_KEYS:
        if key in summary and summary[key] is not None:
            value = summary[key]
            # tuple/imgsz 转为 list，便于 JSON 序列化与前端消费。
            if key == "used_imgsz" and isinstance(value, tuple):
                value = list(value)
            result[key] = value
    return result


def run_job_inference(
    *,
    model_path: Path,
    images_dir: Path,
    out_dir: Path,
    payload: Mapping[str, Any],
    progress_callback: Callable[[InferenceProgress], None] | None = None,
    detection_callback: Callable[[list[dict[str, Any]]], None] | None = None,
) -> dict[str, Any]:
    summary = run_inference(
        model_path=model_path,
        images_dir=images_dir,
        out_dir=out_dir,
        recursive=bool(payload["recursive"]),
        batch=int(payload["batch"]),
        imgsz=int(payload["imgsz"]) if payload["imgsz"] is not None else None,
        conf=float(payload["conf"]),
        iou=float(payload["iou"]),
        copy_fallback=bool(payload["copy_fallback"]),
        preprocess_workers=int(payload["preprocess_workers"]),
        prefetch_batches=int(payload["prefetch_batches"]),
        allowed_class_ids=set(payload["allowed_class_ids"]) if payload["allowed_class_ids"] is not None else None,
        unmatched_label=str(payload["unmatched_label"]),
        force_class_names=list(payload["force_class_names"]) if payload["force_class_names"] else None,
        draw_boxes=bool(payload["draw_boxes"]),
        save_txt=bool(payload["save_txt"]),
        execution_device=str(payload["execution_device"]),
        progress_callback=progress_callback,
        detection_callback=detection_callback,
    )
    return summary.__dict__


def write_detections_json(out_dir: Path, detections: list[dict[str, Any]]) -> Path:
    """将逐图检测结果写入 result_dir/_detections.json。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / DETECTIONS_FILENAME
    with target.open("w", encoding="utf-8") as fh:
        json.dump({"images": detections}, fh, ensure_ascii=False)
    return target


def read_detections_json(out_dir: Path) -> dict[str, Any] | None:
    """读取 result_dir/_detections.json，不存在时返回 None。"""
    target = out_dir / DETECTIONS_FILENAME
    if not target.is_file():
        return None
    with target.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def package_job_output(out_dir: Path) -> str:
    return package_output_dir(out_dir).zip_saved_path
