from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.services import inference_adapter
from backend.services.job_service import build_job_event, normalize_job_payload


class TaskRunner:
    def __init__(self, job_repo, model_repo, config_repo, gpu_gate, runtime_paths) -> None:
        self.job_repo = job_repo
        self.model_repo = model_repo
        self.config_repo = config_repo
        self.gpu_gate = gpu_gate
        self.runtime_paths = runtime_paths

    def run(self, job_id: int) -> None:
        self.runtime_paths.ensure()

        job = self.job_repo.get(job_id)
        model = self.model_repo.get(job.model_id)
        payload = normalize_job_payload(getattr(job, "payload_json", None))
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
            if not getattr(job, "input_path", None):
                raise ValueError("job input path is missing")
            with self.gpu_gate.acquire():
                summary = inference_adapter.run_job_inference(
                    model_path=Path(model.onnx_path),
                    images_dir=Path(job.input_path),
                    out_dir=out_dir,
                    payload=payload,
                )
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
                },
            ),
        )

    def _record_event(self, job_id: int, event: dict[str, Any]) -> None:
        record_event = getattr(self.job_repo, "record_event", None)
        if callable(record_event):
            record_event(job_id, **event)
