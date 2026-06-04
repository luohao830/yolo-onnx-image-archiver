from __future__ import annotations

import json
import multiprocessing as mp
import queue
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

from webui.processing import InferenceSummary, run_inference
from webui.utils import get_logger


logger = get_logger(__name__)


def _serialize_summary(summary: InferenceSummary) -> Dict[str, Any]:
    return {
        "total": summary.total,
        "written": summary.written,
        "hardlinked": summary.hardlinked,
        "copied": summary.copied,
        "failed": summary.failed,
        "txt_written": summary.txt_written,
        "elapsed_sec": summary.elapsed_sec,
        "preprocess_sec": summary.preprocess_sec,
        "inference_sec": summary.inference_sec,
        "postprocess_sec": summary.postprocess_sec,
        "hardlink_sec": summary.hardlink_sec,
        "drawn": summary.drawn,
        "draw_sec": summary.draw_sec,
        "providers": list(summary.providers),
        "cuda_enabled": summary.cuda_enabled,
        "requested_device": summary.requested_device,
        "used_batch": summary.used_batch,
        "used_imgsz": list(summary.used_imgsz),
        "input_shape": list(summary.input_shape),
        "output_shape": list(summary.output_shape) if summary.output_shape is not None else None,
        "by_label": dict(summary.by_label),
        "out_dir": summary.out_dir,
    }


def _worker_loop(request_queue: "mp.Queue[Dict[str, Any]]", event_queue: "mp.Queue[Dict[str, Any]]") -> None:
    logger.info("推理 worker 已启动")
    while True:
        job = request_queue.get()
        if not isinstance(job, dict):
            continue

        command = job.get("command")
        if command == "shutdown":
            logger.info("收到 worker 关闭请求")
            return
        if command != "infer":
            continue

        job_id = str(job.get("job_id", ""))
        payload = job.get("payload") or {}
        if not job_id:
            continue

        def _emit(event_type: str, **data: Any) -> None:
            event_queue.put({"job_id": job_id, "type": event_type, "data": data})

        def _on_progress(progress_info) -> None:
            _emit(
                "progress",
                stage=getattr(progress_info, "stage", "running"),
                processed=int(getattr(progress_info, "processed", 0)),
                total=int(getattr(progress_info, "total", 0)),
                remaining=int(getattr(progress_info, "remaining", 0)),
                batch_size=int(getattr(progress_info, "batch_size", 0)),
                elapsed_sec=float(getattr(progress_info, "elapsed_sec", 0.0)),
                avg_pre_batch_sec=getattr(progress_info, "avg_pre_batch_sec", None),
                avg_infer_batch_sec=getattr(progress_info, "avg_infer_batch_sec", None),
                avg_post_batch_sec=getattr(progress_info, "avg_post_batch_sec", None),
                avg_write_batch_sec=getattr(progress_info, "avg_write_batch_sec", None),
                eta_sec=getattr(progress_info, "eta_sec", None),
            )

        try:
            _emit("accepted")
            summary = run_inference(
                model_path=Path(payload["model_path"]),
                images_dir=Path(payload["images_dir"]),
                out_dir=Path(payload["out_dir"]),
                recursive=bool(payload["recursive"]),
                batch=int(payload["batch"]),
                imgsz=int(payload["imgsz"]) if payload.get("imgsz") else None,
                conf=float(payload["conf"]),
                iou=float(payload["iou"]),
                copy_fallback=bool(payload["copy_fallback"]),
                preprocess_workers=int(payload["preprocess_workers"]),
                prefetch_batches=int(payload["prefetch_batches"]),
                allowed_class_ids=set(payload["allowed_class_ids"]) if payload.get("allowed_class_ids") is not None else None,
                unmatched_label=str(payload["unmatched_label"]),
                force_class_names=list(payload["force_class_names"]) if payload.get("force_class_names") else None,
                draw_boxes=bool(payload["draw_boxes"]),
                save_txt=bool(payload["save_txt"]),
                execution_device=str(payload["execution_device"]),
                progress_callback=_on_progress,
            )
            _emit("result", summary=_serialize_summary(summary))
        except Exception as exc:  # noqa: BLE001
            logger.exception("worker 推理失败")
            _emit(
                "error",
                message=str(exc),
                traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            )


def create_worker_process(
    request_queue: "mp.Queue[Dict[str, Any]]",
    event_queue: "mp.Queue[Dict[str, Any]]",
) -> mp.Process:
    ctx = mp.get_context("spawn")
    process = ctx.Process(
        target=_worker_loop,
        args=(request_queue, event_queue),
        daemon=True,
        name="yolo-infer-worker",
    )
    return process
