from __future__ import annotations

from pathlib import Path
from time import monotonic
from typing import Any

from backend.services import inference_adapter
from backend.services.job_service import build_job_event, normalize_job_payload


class ProgressEventWriter:
    def __init__(self, job_id: int, record_event, throttle_seconds: float = 2.0) -> None:
        self.job_id = job_id
        self.record_event = record_event
        self.throttle_seconds = throttle_seconds
        self.last_emit_at = 0.0
        self.last_processed = -1

    def __call__(self, progress) -> None:
        processed = int(getattr(progress, "processed", 0) or 0)
        total = int(getattr(progress, "total", 0) or 0)
        stage = str(getattr(progress, "stage", "running") or "running")

        if not self._should_emit(stage=stage, processed=processed):
            return

        percent = 0
        if total > 0:
            percent = max(0, min(100, round((processed / total) * 100)))

        payload_json = {
            "stage": stage,
            "processed": processed,
            "total": total,
            "progress": percent,
        }
        if stage != "counting":
            payload_json["written"] = processed

        self.last_emit_at = monotonic()
        self.last_processed = processed
        self.record_event(
            self.job_id,
            build_job_event(
                event_type="running",
                message=self._build_message(stage=stage, processed=processed, total=total, percent=percent),
                payload_json=payload_json,
            ),
        )

    def _should_emit(self, *, stage: str, processed: int) -> bool:
        if stage == "done":
            return True
        if processed != self.last_processed and monotonic() - self.last_emit_at >= self.throttle_seconds:
            return True
        return self.last_processed < 0

    def _build_message(self, *, stage: str, processed: int, total: int, percent: int) -> str:
        if stage == "counting":
            return f"正在统计图片，总计 {total} 张" if total else f"正在统计图片，已扫描 {processed} 张"
        if stage == "done":
            return f"推理完成，已处理 {processed} / {total} 张图片"
        if total > 0:
            return f"正在推理，已处理 {processed} / {total} 张图片（{percent}%）"
        return f"正在推理，已处理 {processed} 张图片"


class TaskRunner:
    def __init__(
        self,
        job_repo,
        model_repo,
        config_repo,
        gpu_gate,
        runtime_paths,
        commit_progress=None,
        event_bus=None,
    ) -> None:
        self.job_repo = job_repo
        self.model_repo = model_repo
        self.config_repo = config_repo
        self.gpu_gate = gpu_gate
        self.runtime_paths = runtime_paths
        self.commit_progress = commit_progress
        self.event_bus = event_bus

    def run(self, job_id: int) -> None:
        self.runtime_paths.ensure()

        job = self.job_repo.get(job_id)
        out_dir = self.runtime_paths.results / job.job_code

        self.job_repo.mark_running(job_id)
        self._record_event(
            job_id,
            build_job_event(
                event_type="running",
                message="任务开始执行",
                payload_json={"job_code": job.job_code, "out_dir": str(out_dir)},
            ),
        )

        try:
            model_id = getattr(job, "model_id", None)
            if model_id is None:
                raise LookupError("job model is missing")

            model = self.model_repo.get(model_id)
            payload = normalize_job_payload(getattr(job, "payload_json", None))

            if not getattr(job, "input_path", None):
                raise ValueError("job input path is missing")
            progress_writer = ProgressEventWriter(job_id=job_id, record_event=self._record_event)
            detections: list[dict[str, Any]] = []

            def _detection_callback(batch_detections: list[dict[str, Any]]) -> None:
                detections.extend(batch_detections)

            with self.gpu_gate.acquire():
                summary = inference_adapter.run_job_inference(
                    model_path=Path(model.onnx_path),
                    images_dir=Path(job.input_path),
                    out_dir=out_dir,
                    payload=payload,
                    progress_callback=progress_writer,
                    detection_callback=_detection_callback,
                )
            if detections:
                inference_adapter.write_detections_json(Path(summary["out_dir"]), detections)
            zip_path = inference_adapter.package_job_output(Path(summary["out_dir"]))
        except Exception as exc:  # noqa: BLE001
            error_message = str(exc) or exc.__class__.__name__
            self.job_repo.mark_failed(job_id, error_message=error_message)
            self._record_event(
                job_id,
                build_job_event(
                    event_type="failed",
                    message="任务执行失败",
                    payload_json={"error": error_message},
                ),
            )
            return

        summary_json = inference_adapter.build_job_summary_json(summary)
        self.job_repo.update_summary(job_id, summary_json=summary_json)
        self.job_repo.mark_completed(
            job_id,
            result_dir=str(summary["out_dir"]),
            result_zip_path=str(zip_path),
        )
        self._record_event(
            job_id,
            build_job_event(
                event_type="completed",
                message="任务执行完成",
                payload_json={
                    "result_dir": str(summary["out_dir"]),
                    "result_zip_path": str(zip_path),
                    "total": summary.get("total"),
                    "written": summary.get("written"),
                    "detections_ready": bool(detections),
                },
            ),
        )

    def _record_event(self, job_id: int, event: dict[str, Any]) -> None:
        record = self.job_repo.record_event(job_id, **event)
        if self.commit_progress is not None:
            self.commit_progress()
        if self.event_bus is not None:
            payload = {
                "id": getattr(record, "id", None),
                "job_id": job_id,
                "event_type": event["event_type"],
                "message": event["message"],
                "payload_json": event.get("payload_json") or {},
            }
            try:
                self.event_bus.publish(f"job:{job_id}", payload)
            except Exception:  # noqa: BLE001
                # SSE 推送失败不应影响任务执行。
                pass
