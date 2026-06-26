from __future__ import annotations

import logging
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
from backend.workers.progress_writer import ProgressEventWriter

logger = logging.getLogger(__name__)


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
            job_repo = JobRepository(session)
            job = job_repo.get(job_id)
            model_id = job.model_id
            input_path = job.input_path
            payload_json = job.payload_json
            job_code = job.job_code
            if job.cancel_requested:
                self._mark_canceled(job_id)
                return
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
            result_out_dir = summary.get("out_dir")
            if result_out_dir is None:
                self._fast_fail(job_id, "inference summary missing out_dir")
                return
            if detections:
                inference_adapter.write_detections_json(Path(result_out_dir), detections)
            zip_path = inference_adapter.package_job_output(Path(result_out_dir))
        except Exception as exc:  # noqa: BLE001
            error_message = str(exc) or exc.__class__.__name__
            self._fast_fail(job_id, error_message)
            return

        # ── 阶段 3：写终态（先检查取消标记）──────────────────────
        terminal_event: dict[str, Any] | None = None
        terminal_record_id: int | None = None
        with session_scope(self.engine) as session:
            job_repo = JobRepository(session)
            job = job_repo.get(job_id)
            # 推理期间用户可能已请求取消
            if job.cancel_requested:
                job_repo.mark_canceled(job_id)
                terminal_event = build_job_event(
                    event_type="canceled",
                    message="任务已被取消",
                    payload_json={"result_dir": str(result_out_dir)},
                )
                record = job_repo.record_event(job_id, **terminal_event)
                terminal_record_id = getattr(record, "id", None)
            else:
                summary_json = inference_adapter.build_job_summary_json(summary)
                job_repo.update_summary(job_id, summary_json=summary_json)
                job_repo.mark_completed(
                    job_id,
                    result_dir=str(result_out_dir),
                    result_zip_path=str(zip_path),
                )
                terminal_event = build_job_event(
                    event_type="completed",
                    message="任务执行完成",
                    payload_json={
                        "result_dir": str(result_out_dir),
                        "result_zip_path": str(zip_path),
                        "total": summary.get("total"),
                        "written": summary.get("written"),
                        "detections_ready": bool(detections),
                    },
                )
                record = job_repo.record_event(job_id, **terminal_event)
                terminal_record_id = getattr(record, "id", None)

        if terminal_event is not None:
            self._publish_event(job_id, terminal_event, record_id=terminal_record_id)

    def _fast_fail(self, job_id: int, error_message: str) -> None:
        failed_record_id: int | None = None
        try:
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
        except Exception as db_exc:  # noqa: BLE001
            logger.error("_fast_fail DB write failed for job %s: %s", job_id, db_exc)
            # DB 写入失败时尽力尝试一次不带 record_id 的 SSE 发布
            failed_event = build_job_event(
                event_type="failed",
                message="任务执行失败",
                payload_json={"error": error_message},
            )

        self._publish_event(job_id, failed_event, record_id=failed_record_id)

    def _mark_canceled(self, job_id: int) -> None:
        """阶段 2 期间取消标记已被设置，终止任务。"""
        terminal_record_id: int | None = None
        try:
            with session_scope(self.engine) as session:
                job_repo = JobRepository(session)
                job_repo.mark_canceled(job_id)
                canceled_event = build_job_event(
                    event_type="canceled",
                    message="任务已被取消",
                    payload_json={},
                )
                record = job_repo.record_event(job_id, **canceled_event)
                terminal_record_id = getattr(record, "id", None)
        except Exception as db_exc:  # noqa: BLE001
            logger.error("_mark_canceled DB write failed for job %s: %s", job_id, db_exc)
            canceled_event = build_job_event(
                event_type="canceled",
                message="任务已被取消",
                payload_json={},
            )

        self._publish_event(job_id, canceled_event, record_id=terminal_record_id)

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
        except RuntimeError:
            logger.warning("SSE publish skipped for job %s: event loop closed", job_id)
        except Exception:  # noqa: BLE001
            logger.warning("SSE publish failed for job %s", job_id, exc_info=True)
