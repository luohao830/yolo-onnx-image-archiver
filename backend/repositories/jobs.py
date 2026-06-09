from __future__ import annotations

from sqlalchemy.orm import Session

from backend.db.models import JobRecord


class JobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_job(
        self,
        *,
        job_code: str,
        access_token_hash: str,
        mode: str,
    ) -> JobRecord:
        job = JobRecord(
            job_code=job_code,
            access_token_hash=access_token_hash,
            mode=mode,
            status="created",
        )
        self.session.add(job)
        self.session.flush()
        return job

    def get_by_code(self, job_code: str) -> JobRecord | None:
        return self.session.query(JobRecord).filter_by(job_code=job_code).one_or_none()

    def mark_uploaded(self, job_id: int, *, input_path: str) -> JobRecord:
        job = self._get_required(job_id)
        job.status = "uploaded"
        job.input_path = input_path
        self.session.flush()
        return job

    def mark_running(self, job_id: int) -> JobRecord:
        job = self._get_required(job_id)
        job.status = "running"
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
        self.session.flush()
        return job

    def _get_required(self, job_id: int) -> JobRecord:
        job = self.session.get(JobRecord, job_id)
        if job is None:
            raise LookupError(f"job not found: {job_id}")
        return job
