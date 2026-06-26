from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

SAFE_EVENT_PAYLOAD_KEYS = frozenset({
    "filename",
    "image_count",
    "progress",
    "size_bytes",
    "stage",
    "total",
    "written",
    "processed",
    "matched",
    "skipped",
    "detections_ready",
})

STATUS_PROGRESS: dict[str, int] = {
    "created": 0,
    "uploaded": 100,
    "running": 0,
    "completed": 100,
    # 失败时如果没有进度事件则回退到 0（而非 100），避免误导"失败但 100% 完成"。
    "failed": 0,
    "canceled": 0,
}


class JobPresenter:
    """任务 DTO 序列化、进度计算与事件 payload 白名单过滤。"""

    @classmethod
    def serialize_public_job(cls, job: Any, events: list[Any]) -> dict[str, Any]:
        return {
            "id": job.id,
            "job_code": job.job_code,
            "mode": job.mode,
            "status": job.status,
            "progress": cls.calculate_progress(job, events),
            "events": [cls.serialize_event(event) for event in events],
            "error_message": job.error_message,
            "download_ready": cls.is_download_ready(job),
            "summary": getattr(job, "summary_json", None),
        }

    @classmethod
    def serialize_admin_job(cls, job: Any, events: list[Any]) -> dict[str, Any]:
        return {
            "id": job.id,
            "job_code": job.job_code,
            "mode": job.mode,
            "status": job.status,
            "progress": cls.calculate_progress(job, events),
            "cancel_requested": bool(job.cancel_requested),
            "error_message": job.error_message,
            "result_zip_available": cls.has_result_zip(job),
            "download_ready": cls.is_download_ready(job),
        }

    @classmethod
    def serialize_admin_job_detail(cls, job: Any, events: list[Any]) -> dict[str, Any]:
        # 直接从 raw field 构建，避免 serialize_admin_job 已包含的 events 被二次序列化。
        payload = {
            "id": job.id,
            "job_code": job.job_code,
            "mode": job.mode,
            "status": job.status,
            "progress": cls.calculate_progress(job, events),
            "cancel_requested": bool(job.cancel_requested),
            "error_message": job.error_message,
            "result_zip_available": cls.has_result_zip(job),
            "download_ready": cls.is_download_ready(job),
            "input_path": job.input_path,
            "result_dir": job.result_dir,
            "events": [cls.serialize_event(event) for event in events],
            "summary": getattr(job, "summary_json", None),
        }
        return payload

    @classmethod
    def calculate_progress(cls, job: Any, events: list[Any]) -> int:
        if job.status == "completed":
            return 100

        event_progress = cls._calculate_event_progress(events)
        if event_progress is not None and job.status in {"running", "failed"}:
            return event_progress

        return cls._clamp(STATUS_PROGRESS.get(job.status, 0))

    @classmethod
    def _calculate_event_progress(cls, events: list[Any]) -> int | None:
        for event in reversed(events):
            payload = event.payload_json or {}
            total = payload.get("total")
            written = payload.get("written")
            if not isinstance(total, (int, float)) or not isinstance(written, (int, float)):
                continue
            if total <= 0:
                continue
            return cls._clamp(round((written / total) * 100))
        return None

    @staticmethod
    def _clamp(progress: int | float) -> int:
        return max(0, min(100, int(progress)))

    @classmethod
    def serialize_event(cls, event: Any) -> dict[str, Any]:
        return {
            "id": event.id,
            "event_type": event.event_type,
            "message": event.message,
            "payload_json": cls.sanitize_event_payload(event.payload_json or {}),
        }

    @staticmethod
    def sanitize_event_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in payload.items() if key in SAFE_EVENT_PAYLOAD_KEYS}

    @classmethod
    def is_download_ready(cls, job: Any) -> bool:
        return job.status == "completed" and cls.has_result_zip(job)

    @staticmethod
    def has_result_zip(job: Any) -> bool:
        return bool(job.result_zip_path and Path(job.result_zip_path).is_file())

    @classmethod
    def resolve_result_zip(cls, job: Any) -> Path:
        if job.status != "completed":
            raise ValueError("job result is not ready")
        if not cls.has_result_zip(job):
            raise FileNotFoundError("job result archive not found")
        return Path(job.result_zip_path)

    @classmethod
    def resolve_result_dir(cls, job: Any) -> Path | None:
        if not getattr(job, "result_dir", None):
            return None
        result_dir = Path(job.result_dir)
        if not result_dir.is_dir():
            return None
        return result_dir

    @classmethod
    def safe_resolve_within(cls, base: Path, rel_path: str) -> Path | None:
        """解析 base 下的相对路径，拒绝路径遍历（..）与跳出 base 的结果。"""
        if not rel_path:
            return None
        if ".." in Path(rel_path).parts:
            return None
        candidate = (base / rel_path).resolve()
        try:
            candidate.relative_to(base.resolve())
        except ValueError:
            return None
        if not candidate.is_file():
            return None
        return candidate
