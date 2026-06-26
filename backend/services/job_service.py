from __future__ import annotations

import hashlib
import hmac
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Any, BinaryIO, Mapping

from sqlalchemy.engine import Engine

from backend.core.config import settings
from backend.core.db import build_engine, create_all, session_scope
from backend.repositories.jobs import JobRepository
from backend.services.job_modes import get_mode_handler
from backend.services.job_presenter import JobPresenter
from backend.services.job_result_store import JobResultStore
from backend.services.job_upload_store import JobUploadStore, UploadTooLargeError
from backend.services.runtime_paths import RuntimePaths


__all__ = ["UploadTooLargeError"]  # 从 job_upload_store 重新导出，保持向后兼容


from backend.services.job_modes import (  # noqa: F401 — 重新导出，保持向后兼容
    DEFAULT_JOB_PAYLOAD,
    PERSON_FILTER_PAYLOAD,
    normalize_job_payload,
)


def build_job_event(
    *,
    event_type: str,
    message: str,
    payload_json: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "message": message,
        "payload_json": dict(payload_json or {}),
    }


class JobService:
    def __init__(self, engine: Engine, runtime_paths: RuntimePaths | None = None) -> None:
        self.engine = engine
        self.runtime_paths = runtime_paths or RuntimePaths(settings.resolve_runtime_root())
        self.upload_store = JobUploadStore(self.runtime_paths)

    def create_public_job(
        self,
        mode: str,
        *,
        model_id: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        handler = get_mode_handler(mode)
        payload_json = handler.build_payload(payload)
        access_token = self._generate_access_token()
        access_token_hash = self._hash_access_token(access_token)

        with session_scope(self.engine) as session:
            handler.validate_create(session, model_id)
            repo = JobRepository(session)
            job_code = self._generate_unique_job_code(repo)
            job = repo.create_job(
                job_code=job_code,
                access_token_hash=access_token_hash,
                mode=mode,
                model_id=model_id,
                payload_json=payload_json,
            )
            created_job_code = job.job_code
            created_status = job.status

        return {
            "job_code": created_job_code,
            "access_token": access_token,
            "status": created_status,
        }

    def get_public_job(self, job_code: str, access_token: str) -> dict[str, Any] | None:
        with session_scope(self.engine) as session:
            repo = JobRepository(session)
            job = repo.get_by_code(job_code)
            if job is None:
                return None
            if not self._verify_access_token(access_token, job.access_token_hash):
                return None
            events = repo.list_events(job.id)
            return JobPresenter.serialize_public_job(job, events)

    def get_public_job_id(self, job_code: str, access_token: str) -> int | None:
        with session_scope(self.engine) as session:
            repo = JobRepository(session)
            job = repo.get_by_code(job_code)
            if job is None:
                return None
            if not self._verify_access_token(access_token, job.access_token_hash):
                return None
            return job.id

    def get_public_job_event_snapshot(self, job_id: int, job_code: str) -> dict[str, Any] | None:
        with session_scope(self.engine) as session:
            repo = JobRepository(session)
            try:
                job = repo.get(job_id)
            except LookupError:
                return None
            if job.job_code != job_code:
                return None
            return JobPresenter.serialize_public_job(job, repo.list_events(job.id))

    def accept_public_job_upload(
        self,
        job_code: str,
        access_token: str,
        *,
        filename: str,
        file_obj: BinaryIO,
    ) -> tuple[int, dict[str, Any]]:
        self.runtime_paths.ensure()
        job_id, model_id = self._resolve_upload_targets(job_code, access_token)
        input_dir, upload_event = self.upload_store.persist_public_upload(
            job_code,
            filename,
            file_obj,
        )

        with session_scope(self.engine) as session:
            repo = JobRepository(session)
            job = repo.get(job_id)
            if job.status != "created":
                raise ValueError("job has already been uploaded or started")
            updated = repo.mark_uploaded(
                job.id,
                input_path=str(input_dir),
                model_id=model_id,
            )
            repo.record_event(job.id, **upload_event)
            return updated.id, JobPresenter.serialize_public_job(updated, repo.list_events(updated.id))

    def list_admin_jobs(self) -> list[dict[str, Any]]:
        with session_scope(self.engine) as session:
            repo = JobRepository(session)
            return [
                JobPresenter.serialize_admin_job(job, repo.list_events(job.id))
                for job in repo.list_jobs()
            ]

    def get_admin_job(self, job_id: int) -> dict[str, Any]:
        with session_scope(self.engine) as session:
            repo = JobRepository(session)
            job = repo.get(job_id)
            return JobPresenter.serialize_admin_job_detail(job, repo.list_events(job.id))

    def resolve_public_result_zip(self, job_code: str, access_token: str) -> Path | None:
        with session_scope(self.engine) as session:
            repo = JobRepository(session)
            job = repo.get_by_code(job_code)
            if job is None:
                return None
            if not self._verify_access_token(access_token, job.access_token_hash):
                return None
            return JobPresenter.resolve_result_zip(job)

    def _resolve_public_result_dir(self, job_code: str, access_token: str) -> Path | None:
        with session_scope(self.engine) as session:
            repo = JobRepository(session)
            job = repo.get_by_code(job_code)
            if job is None:
                return None
            if not self._verify_access_token(access_token, job.access_token_hash):
                return None
            return JobPresenter.resolve_result_dir(job)

    def _resolve_admin_result_dir(self, job_id: int) -> Path | None:
        with session_scope(self.engine) as session:
            repo = JobRepository(session)
            return JobPresenter.resolve_result_dir(repo.get(job_id))

    def resolve_admin_result_zip(self, job_id: int) -> Path:
        with session_scope(self.engine) as session:
            repo = JobRepository(session)
            return JobPresenter.resolve_result_zip(repo.get(job_id))

    def get_public_detections(self, job_code: str, access_token: str) -> dict[str, Any] | None:
        result_dir = self._resolve_public_result_dir(job_code, access_token)
        if result_dir is None:
            return None
        return JobResultStore.read_detections(result_dir)

    def get_admin_detections(self, job_id: int) -> dict[str, Any] | None:
        result_dir = self._resolve_admin_result_dir(job_id)
        if result_dir is None:
            return None
        return JobResultStore.read_detections(result_dir)

    def resolve_public_result_image(
        self,
        job_code: str,
        access_token: str,
        rel_path: str,
    ) -> Path | None:
        result_dir = self._resolve_public_result_dir(job_code, access_token)
        if result_dir is None:
            return None
        return JobResultStore.resolve_image(result_dir, rel_path)

    def resolve_admin_result_image(self, job_id: int, rel_path: str) -> Path | None:
        result_dir = self._resolve_admin_result_dir(job_id)
        if result_dir is None:
            return None
        return JobResultStore.resolve_image(result_dir, rel_path)

    def cancel_job(self, job_id: int) -> dict[str, Any]:
        with session_scope(self.engine) as session:
            repo = JobRepository(session)
            job = repo.get(job_id)
            if job.status in {"created", "uploaded"}:
                updated = repo.mark_canceled(job_id)
                return JobPresenter.serialize_admin_job(updated, repo.list_events(job_id))
            if job.status == "running":
                updated = repo.mark_cancel_requested(job_id)
                return JobPresenter.serialize_admin_job(updated, repo.list_events(job_id))
            return JobPresenter.serialize_admin_job(job, repo.list_events(job_id))

    def retry_job(self, job_id: int) -> dict[str, Any]:
        with session_scope(self.engine) as session:
            repo = JobRepository(session)
            job = repo.get(job_id)
            if job.status != "failed":
                raise ValueError("only failed jobs can be retried")
            updated = repo.reset_for_retry(job_id)
            return JobPresenter.serialize_admin_job(updated, repo.list_events(job_id))

    def _resolve_upload_targets(self, job_code: str, access_token: str) -> tuple[int, int]:
        with session_scope(self.engine) as session:
            job_repo = JobRepository(session)
            job = job_repo.get_by_code(job_code)
            if job is None:
                raise LookupError("job not found")
            if not self._verify_access_token(access_token, job.access_token_hash):
                raise LookupError("job not found")
            if job.status != "created":
                raise ValueError("job has already been uploaded or started")

            handler = get_mode_handler(job.mode)
            return job.id, handler.resolve_model_id_for_upload(session, job.model_id)

    def _generate_unique_job_code(self, repo: JobRepository) -> str:
        for _ in range(8):
            job_code = f"JOB-{secrets.token_hex(6).upper()}"
            if repo.get_by_code(job_code) is None:
                return job_code
        raise RuntimeError("failed to allocate unique job code")

    @staticmethod
    def _generate_access_token() -> str:
        return secrets.token_urlsafe(18)

    @staticmethod
    def _hash_access_token(access_token: str) -> str:
        return hashlib.sha256(access_token.encode("utf-8")).hexdigest()

    @classmethod
    def _verify_access_token(cls, access_token: str, access_token_hash: str) -> bool:
        return hmac.compare_digest(
            cls._hash_access_token(access_token),
            access_token_hash,
        )

# JobService 自身不再持有序列化细节，仅编排 use case（序列化 / 进度 / 路径委托 → JobPresenter）。


@lru_cache(maxsize=1)
def get_job_service() -> JobService:
    database_url = settings.resolve_database_url()
    if database_url.startswith("sqlite:///"):
        database_path = Path(database_url.removeprefix("sqlite:///"))
        if database_path != Path(":memory:"):
            database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = build_engine(database_url)
    create_all(engine)
    return JobService(engine)
