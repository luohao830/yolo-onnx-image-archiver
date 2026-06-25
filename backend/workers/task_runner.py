from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine

from backend.core.db import session_scope
from backend.repositories.jobs import JobRepository
from backend.repositories.models import ModelRepository
from backend.services import inference_adapter
from backend.services.event_bus import EventBus
from backend.services.job_service import build_job_event, normalize_job_payload
from backend.services.runtime_paths import RuntimePaths
from backend.workers.gpu_gate import GpuGate
from backend.workers.progress_writer import ProgressEventWriter  # noqa: F401 — 向后兼容再导出


@dataclass
class TaskRunResult:
    """TaskRunner 执行结果，明确成功/失败/输出位置。"""

    success: bool
    summary: dict[str, Any] | None = None
    zip_path: str | None = None
    detections: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    error_message: str | None = None


class TaskRunner:
    """编排推理生命周期：三阶段事务。

    阶段 1（短事务）：mark_running + running event → commit → SSE 发布。
    阶段 2（无 DB session）：执行推理；进度事件通过 progress_recorder 以短事务写入。
    阶段 3（短事务）：终态写入 + 终态 event → commit → SSE 发布。
    """

    def __init__(
        self,
        *,
        engine: Engine,
        event_bus: EventBus | None,
        progress_recorder,
        gpu_gate: GpuGate,
        runtime_paths: RuntimePaths,
    ) -> None:
        self.engine = engine
        self.event_bus = event_bus
        self.progress_recorder = progress_recorder
        self.gpu_gate = gpu_gate
        self.runtime_paths = runtime_paths

    def run(self, job_id: int) -> None:
        self.runtime_paths.ensure()

        # ── 阶段 1：打标 running，写入 running 事件并提交 ────────
        running_event_record_id: int | None = None
        with session_scope(self.engine) as session:
            job_repo = JobRepository(session)
            job = job_repo.get(job_id)
            out_dir = self.runtime_paths.results / job.job_code

            job_repo.mark_running(job_id)
            running_event = build_job_event(
                event_type="running",
                message="任务开始执行",
                payload_json={"job_code": job.job_code, "out_dir": str(out_dir)},
            )
            record = job_repo.record_event(job_id, **running_event)
            running_event_record_id = getattr(record, "id", None)
            # session_scope 退出时自动 commit

        # SSE 发布（在事务提交之后）
        self._publish_event(job_id, running_event, record_id=running_event_record_id)

        # ── 阶段 2：执行推理（无 DB session）────────────────────

        # 重新获取可重读字段（新 session）
        with session_scope(self.engine) as session:
            job = JobRepository(session).get(job_id)
            model_id = getattr(job, "model_id", None)
            input_path = getattr(job, "input_path", None)
            payload_json = getattr(job, "payload_json", None)
            job_code = job.job_code
            if model_id is not None:
                try:
                    model_onnx = ModelRepository(session).get(model_id).onnx_path
                except LookupError:
                    model_onnx = None
            else:
                model_onnx = None

        if model_id is None:
            self._fast_fail(job_id, "job model is missing")
            return
        if model_onnx is None:
            self._fast_fail(job_id, "bound model not found")
            return
        if not input_path:
            self._fast_fail(job_id, "job input path is missing")
            return

        out_dir = self.runtime_paths.results / job_code
        payload = normalize_job_payload(payload_json)

        progress_writer = ProgressEventWriter(
            job_id=job_id,
            record_event=lambda job_id, event: self.progress_recorder(job_id, event),
        )
        detections: list[dict[str, Any]] = []

        def _detection_callback(batch_detections: list[dict[str, Any]]) -> None:
            detections.extend(batch_detections)

        try:
            with self.gpu_gate.acquire():
                summary = inference_adapter.run_job_inference(
                    model_path=Path(model_onnx),
                    images_dir=Path(input_path),
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
            self._fast_fail(job_id, error_message)
            return

        # ── 阶段 3：写终态 ──────────────────────────────────────
        completed_record_id: int | None = None
        with session_scope(self.engine) as session:
            job_repo = JobRepository(session)
            summary_json = inference_adapter.build_job_summary_json(summary)
            job_repo.update_summary(job_id, summary_json=summary_json)
            job_repo.mark_completed(
                job_id,
                result_dir=str(summary["out_dir"]),
                result_zip_path=str(zip_path),
            )
            completed_event = build_job_event(
                event_type="completed",
                message="任务执行完成",
                payload_json={
                    "result_dir": str(summary["out_dir"]),
                    "result_zip_path": str(zip_path),
                    "total": summary.get("total"),
                    "written": summary.get("written"),
                    "detections_ready": bool(detections),
                },
            )
            record = job_repo.record_event(job_id, **completed_event)
            completed_record_id = getattr(record, "id", None)

        self._publish_event(job_id, completed_event, record_id=completed_record_id)

    def _fast_fail(self, job_id: int, error_message: str) -> None:
        failed_record_id: int | None = None
        with session_scope(self.engine) as session:
            job_repo = JobRepository(session)
            job_repo.mark_failed(job_id, error_message=error_message)
            failed_event = build_job_event(
                event_type="failed",
                message="任务执行失败",
                payload_json={"error": error_message},
            )
            record = job_repo.record_event(job_id, **failed_event)
            failed_record_id = getattr(record, "id", None)

        self._publish_event(job_id, failed_event, record_id=failed_record_id)

    def _publish_event(self, job_id: int, event: dict[str, Any], record_id: int | None = None) -> None:
        if self.event_bus is None:
            return
        payload = {
            "id": record_id,
            "job_id": job_id,
            "event_type": event["event_type"],
            "message": event["message"],
            "payload_json": event.get("payload_json") or {},
        }
        try:
            self.event_bus.publish(f"job:{job_id}", payload)
        except Exception:  # noqa: BLE001
            pass
