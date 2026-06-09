from __future__ import annotations

import hashlib
import hmac
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from sqlalchemy.engine import Engine

from backend.core.config import settings
from backend.core.db import build_engine, create_all, session_scope
from backend.repositories.jobs import JobRepository


DEFAULT_JOB_PAYLOAD: dict[str, Any] = {
    "recursive": True,
    "batch": 16,
    "imgsz": None,
    "conf": 0.25,
    "iou": 0.45,
    "copy_fallback": False,
    "preprocess_workers": 4,
    "prefetch_batches": 2,
    "allowed_class_ids": None,
    "unmatched_label": "no_detection",
    "force_class_names": None,
    "draw_boxes": False,
    "save_txt": False,
    "execution_device": "auto",
}

PERSON_FILTER_PAYLOAD: dict[str, Any] = {
    "allowed_class_ids": [0],
    "unmatched_label": "no_person",
    "force_class_names": ["person"],
}


def normalize_job_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    normalized = dict(DEFAULT_JOB_PAYLOAD)
    if payload:
        normalized.update(dict(payload))
    if normalized["allowed_class_ids"] is not None:
        normalized["allowed_class_ids"] = list(normalized["allowed_class_ids"])
    if normalized["force_class_names"] is not None:
        normalized["force_class_names"] = list(normalized["force_class_names"])
    return normalized


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
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def create_public_job(self, mode: str) -> dict[str, str]:
        payload_json = self._build_payload_for_mode(mode)
        access_token = self._generate_access_token()
        access_token_hash = self._hash_access_token(access_token)

        with session_scope(self.engine) as session:
            repo = JobRepository(session)
            job_code = self._generate_unique_job_code(repo)
            job = repo.create_job(
                job_code=job_code,
                access_token_hash=access_token_hash,
                mode=mode,
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
            return {
                "job_code": job.job_code,
                "mode": job.mode,
                "status": job.status,
                "error_message": job.error_message,
            }

    def list_admin_jobs(self) -> list[dict[str, Any]]:
        with session_scope(self.engine) as session:
            repo = JobRepository(session)
            return [self._serialize_admin_job(job) for job in repo.list_jobs()]

    def cancel_job(self, job_id: int) -> dict[str, Any]:
        with session_scope(self.engine) as session:
            repo = JobRepository(session)
            job = repo.get(job_id)
            if job.status in {"created", "uploaded"}:
                return self._serialize_admin_job(repo.mark_canceled(job_id))
            if job.status == "running":
                return self._serialize_admin_job(repo.mark_cancel_requested(job_id))
            return self._serialize_admin_job(job)

    def retry_job(self, job_id: int) -> dict[str, Any]:
        with session_scope(self.engine) as session:
            repo = JobRepository(session)
            job = repo.get(job_id)
            if job.status != "failed":
                raise ValueError("only failed jobs can be retried")
            return self._serialize_admin_job(repo.reset_for_retry(job_id))

    def _generate_unique_job_code(self, repo: JobRepository) -> str:
        for _ in range(8):
            job_code = f"JOB-{secrets.token_hex(6).upper()}"
            if repo.get_by_code(job_code) is None:
                return job_code
        raise RuntimeError("failed to allocate unique job code")

    def _build_payload_for_mode(self, mode: str) -> dict[str, Any]:
        if mode == "person_filter":
            return normalize_job_payload(PERSON_FILTER_PAYLOAD)
        if mode == "advanced":
            return normalize_job_payload(None)
        raise ValueError(f"unsupported job mode: {mode}")

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

    @staticmethod
    def _serialize_admin_job(job: Any) -> dict[str, Any]:
        return {
            "id": job.id,
            "job_code": job.job_code,
            "mode": job.mode,
            "status": job.status,
            "cancel_requested": bool(job.cancel_requested),
            "error_message": job.error_message,
        }


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
