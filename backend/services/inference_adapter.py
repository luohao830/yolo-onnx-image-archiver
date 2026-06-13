from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from webui.processing import InferenceProgress, package_output_dir, run_inference


def run_job_inference(
    *,
    model_path: Path,
    images_dir: Path,
    out_dir: Path,
    payload: Mapping[str, Any],
    progress_callback: Callable[[InferenceProgress], None] | None = None,
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
    )
    return summary.__dict__


def package_job_output(out_dir: Path) -> str:
    return package_output_dir(out_dir).zip_saved_path
