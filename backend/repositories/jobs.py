from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.db.models import JobEventRecord, JobRecord


class JobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_job(
        self,
        *,
        job_code: str,
        access_token_hash: str,
        mode: str,
        model_id: int | None = None,
        payload_json: dict[str, Any] | None = None,
    ) -> JobRecord:
        job = JobRecord(
            job_code=job_code,
            access_token_hash=access_token_hash,
            mode=mode,
            model_id=model_id,
            payload_json=payload_json,
            status="created",
        )
        self.session.add(job)
        self.session.flush()
        return job

    def get(self, job_id: int) -> JobRecord:
        return self._get_required(job_id)

    def get_by_code(self, job_code: str) -> JobRecord | None:
        return self.session.query(JobRecord).filter_by(job_code=job_code).one_or_none()

    def list_jobs(self) -> list[JobRecord]:
        return self.session.query(JobRecord).order_by(JobRecord.id.asc()).all()

    def list_events(self, job_id: int) -> list[JobEventRecord]:
        self._get_required(job_id)
        return (
            self.session.query(JobEventRecord)
            .filter_by(job_id=job_id)
            .order_by(JobEventRecord.id.asc())
            .all()
        )

    def mark_uploaded(
        self,
        job_id: int,
        *,
        input_path: str,
        model_id: int | None = None,
    ) -> JobRecord:
        job = self._get_required(job_id)
        job.status = "uploaded"
        job.input_path = input_path
        if model_id is not None:
            job.model_id = model_id
        job.cancel_requested = False
        self.session.flush()
        return job

    def mark_running(self, job_id: int) -> JobRecord:
        job = self._get_required(job_id)
        job.status = "running"
        job.error_message = None
        job.cancel_requested = False
        self.session.flush()
        return job

    def mark_completed(
        self,
        job_id: int,
        *,
        result_dir: str,
        result_zip_path: str,
    ) -> JobRecord:
        job = self._get_required(job_id)
        job.status = "completed"
        job.result_dir = result_dir
        job.result_zip_path = result_zip_path
        job.error_message = None
        job.cancel_requested = False
        self.session.flush()
        return job

    def mark_failed(self, job_id: int, *, error_message: str) -> JobRecord:
        job = self._get_required(job_id)
        job.status = "failed"
        job.error_message = error_message
        self.session.flush()
        return job

    def update_summary(self, job_id: int, *, summary_json: dict[str, Any]) -> JobRecord:
        job = self._get_required(job_id)
        job.summary_json = summary_json
        self.session.flush()
        return job

    def mark_canceled(self, job_id: int) -> JobRecord:
        job = self._get_required(job_id)
        job.status = "canceled"
        job.cancel_requested = False
        self.session.flush()
        return job

    def mark_cancel_requested(self, job_id: int) -> JobRecord:
        job = self._get_required(job_id)
        job.cancel_requested = True
        self.session.flush()
        return job

    def reset_for_retry(self, job_id: int) -> JobRecord:
        job = self._get_required(job_id)
        job.status = "created"
        job.cancel_requested = False
        job.error_message = None
        job.result_dir = None
        job.result_zip_path = None
        job.summary_json = None
        self.session.flush()
        return job

    def record_event(
        self,
        job_id: int,
        *,
        event_type: str,
        message: str,
        payload_json: dict[str, Any] | None = None,
    ) -> JobEventRecord:
        self._get_required(job_id)
        event = JobEventRecord(
            job_id=job_id,
            event_type=event_type,
            message=message,
            payload_json=payload_json,
        )
        self.session.add(event)
        self.session.flush()
        return event

    def _get_required(self, job_id: int) -> JobRecord:
        job = self.session.get(JobRecord, job_id)
        if job is None:
            raise LookupError(f"job not found: {job_id}")
        return job
