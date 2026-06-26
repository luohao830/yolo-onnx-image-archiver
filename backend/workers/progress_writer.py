from __future__ import annotations

from time import monotonic

from backend.services.job_service import build_job_event


class ProgressEventWriter:
    """推理进度回调，节流写入运行中事件。"""

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

        payload_json: dict[str, object] = {
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

    @staticmethod
    def _build_message(*, stage: str, processed: int, total: int, percent: int) -> str:
        if stage == "counting":
            return f"正在统计图片，总计 {total} 张" if total else f"正在统计图片，已扫描 {processed} 张"
        if stage == "done":
            return f"推理完成，已处理 {processed} / {total} 张图片"
        if total > 0:
            return f"正在推理，已处理 {processed} / {total} 张图片（{percent}%）"
        return f"正在推理，已处理 {processed} 张图片"
