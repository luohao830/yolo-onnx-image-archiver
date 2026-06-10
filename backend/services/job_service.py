from __future__ import annotations

import hashlib
import hmac
import secrets
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any, BinaryIO, Mapping

from sqlalchemy.engine import Engine

from backend.core.config import settings
from backend.core.db import build_engine, create_all, session_scope
from backend.repositories.jobs import JobRepository
from backend.repositories.models import ModelRepository
from backend.services.archive_ingest import SUPPORTED_IMAGE_SUFFIXES, extract_upload_archive
from backend.services.runtime_paths import RuntimePaths


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

SAFE_EVENT_PAYLOAD_KEYS = {
    "total",
    "written",
    "processed",
    "matched",
    "skipped",
    "error",
}

STATUS_PROGRESS = {
    "created": 5,
    "uploaded": 20,
    "running": 60,
    "completed": 100,
    "failed": 100,
    "canceled": 0,
}
MAX_UPLOAD_FILE_BYTES = 100 * 1024 * 1024 * 1024


class UploadTooLargeError(ValueError):
    pass


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
    def __init__(self, engine: Engine, runtime_paths: RuntimePaths | None = None) -> None:
        self.engine = engine
        self.runtime_paths = runtime_paths or RuntimePaths(settings.resolve_runtime_root())

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
            events = repo.list_events(job.id)
            return self._serialize_public_job(job, events)

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
        input_dir = self._persist_public_upload(job_code, filename, file_obj)

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
            repo.record_event(
                job.id,
                **build_job_event(
                    event_type="uploaded",
                    message="文件已接收，任务已进入队列",
                    payload_json={"total": self._count_input_images(input_dir)},
                ),
            )
            return updated.id, self._serialize_public_job(updated, repo.list_events(updated.id))

    def list_admin_jobs(self) -> list[dict[str, Any]]:
        with session_scope(self.engine) as session:
            repo = JobRepository(session)
            return [
                self._serialize_admin_job(job, repo.list_events(job.id))
                for job in repo.list_jobs()
            ]

    def get_admin_job(self, job_id: int) -> dict[str, Any]:
        with session_scope(self.engine) as session:
            repo = JobRepository(session)
            job = repo.get(job_id)
            return self._serialize_admin_job_detail(job, repo.list_events(job.id))

    def resolve_public_result_zip(self, job_code: str, access_token: str) -> Path | None:
        with session_scope(self.engine) as session:
            repo = JobRepository(session)
            job = repo.get_by_code(job_code)
            if job is None:
                return None
            if not self._verify_access_token(access_token, job.access_token_hash):
                return None
            return self._resolve_result_zip(job)

    def resolve_admin_result_zip(self, job_id: int) -> Path:
        with session_scope(self.engine) as session:
            repo = JobRepository(session)
            return self._resolve_result_zip(repo.get(job_id))

    def cancel_job(self, job_id: int) -> dict[str, Any]:
        with session_scope(self.engine) as session:
            repo = JobRepository(session)
            job = repo.get(job_id)
            if job.status in {"created", "uploaded"}:
                updated = repo.mark_canceled(job_id)
                return self._serialize_admin_job(updated, repo.list_events(job_id))
            if job.status == "running":
                updated = repo.mark_cancel_requested(job_id)
                return self._serialize_admin_job(updated, repo.list_events(job_id))
            return self._serialize_admin_job(job, repo.list_events(job_id))

    def retry_job(self, job_id: int) -> dict[str, Any]:
        with session_scope(self.engine) as session:
            repo = JobRepository(session)
            job = repo.get(job_id)
            if job.status != "failed":
                raise ValueError("only failed jobs can be retried")
            updated = repo.reset_for_retry(job_id)
            return self._serialize_admin_job(updated, repo.list_events(job_id))

    def _resolve_upload_targets(self, job_code: str, access_token: str) -> tuple[int, int]:
        with session_scope(self.engine) as session:
            job_repo = JobRepository(session)
            job = job_repo.get_by_code(job_code)
            if job is None:
                raise LookupError("job not found")
            if not self._verify_access_token(access_token, job.access_token_hash):
                raise LookupError("job not found")
            if job.mode != "person_filter":
                raise ValueError("only person_filter jobs accept public uploads")
            if job.status != "created":
                raise ValueError("job has already been uploaded or started")

            model = ModelRepository(session).get_default_person_model()
            if model is None:
                raise ValueError("default person model is not configured")
            return job.id, model.id

    def _persist_public_upload(self, job_code: str, filename: str, file_obj: BinaryIO) -> Path:
        safe_filename = Path(filename or "upload").name or "upload"
        suffix = Path(safe_filename).suffix.lower()
        if suffix != ".zip" and suffix not in SUPPORTED_IMAGE_SUFFIXES:
            raise ValueError("仅支持图片文件或 zip 压缩包")

        upload_dir = self.runtime_paths.uploads / job_code
        input_dir = self.runtime_paths.jobs / job_code / "input"
        upload_dir.mkdir(parents=True, exist_ok=True)
        raw_path = upload_dir / safe_filename

        self._copy_upload_with_size_limit(file_obj, raw_path)

        if input_dir.exists():
            shutil.rmtree(input_dir)

        if suffix == ".zip":
            extracted = extract_upload_archive(raw_path, input_dir)
            if not extracted:
                raise ValueError("压缩包内未找到支持的图片")
            return input_dir

        self._copy_single_image_to_input(raw_path, input_dir)
        return input_dir

    @staticmethod
    def _copy_upload_with_size_limit(file_obj: BinaryIO, raw_path: Path) -> None:
        written = 0
        try:
            with raw_path.open("wb") as dst:
                while True:
                    chunk = file_obj.read(1024 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > MAX_UPLOAD_FILE_BYTES:
                        raise UploadTooLargeError("上传文件大小不能超过 100G")
                    dst.write(chunk)
        except Exception:
            raw_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _copy_single_image_to_input(source: Path, input_dir: Path) -> None:
        input_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_input_dir = Path(tempfile.mkdtemp(prefix=f".{input_dir.name}-", dir=input_dir.parent))
        try:
            shutil.copy2(source, temp_input_dir / source.name)
            temp_input_dir.replace(input_dir)
        except Exception:
            shutil.rmtree(temp_input_dir, ignore_errors=True)
            raise

    @staticmethod
    def _count_input_images(input_dir: Path) -> int:
        return sum(
            1
            for path in input_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
        )

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

    @classmethod
    def _serialize_public_job(cls, job: Any, events: list[Any]) -> dict[str, Any]:
        return {
            "job_code": job.job_code,
            "mode": job.mode,
            "status": job.status,
            "progress": cls._calculate_progress(job, events),
            "events": [cls._serialize_event(event) for event in events],
            "error_message": job.error_message,
            "download_ready": cls._is_download_ready(job),
        }

    @classmethod
    def _serialize_admin_job(cls, job: Any, events: list[Any]) -> dict[str, Any]:
        return {
            "id": job.id,
            "job_code": job.job_code,
            "mode": job.mode,
            "status": job.status,
            "progress": cls._calculate_progress(job, events),
            "cancel_requested": bool(job.cancel_requested),
            "error_message": job.error_message,
            "result_zip_available": cls._has_result_zip(job),
            "download_ready": cls._is_download_ready(job),
        }

    @classmethod
    def _serialize_admin_job_detail(cls, job: Any, events: list[Any]) -> dict[str, Any]:
        payload = cls._serialize_admin_job(job, events)
        payload.update(
            {
                "input_path": job.input_path,
                "result_dir": job.result_dir,
                "events": [cls._serialize_event(event) for event in events],
            }
        )
        return payload

    @classmethod
    def _calculate_progress(cls, job: Any, events: list[Any]) -> int:
        if job.status == "completed":
            return 100

        event_progress = cls._calculate_event_progress(events)
        if event_progress is not None and job.status in {"running", "failed"}:
            return event_progress

        return cls._clamp_progress(STATUS_PROGRESS.get(job.status, 0))

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
            return cls._clamp_progress(round((written / total) * 100))
        return None

    @staticmethod
    def _clamp_progress(progress: int | float) -> int:
        return max(0, min(100, int(progress)))

    @classmethod
    def _serialize_event(cls, event: Any) -> dict[str, Any]:
        return {
            "id": event.id,
            "event_type": event.event_type,
            "message": event.message,
            "payload_json": cls._sanitize_event_payload(event.payload_json or {}),
        }

    @staticmethod
    def _sanitize_event_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in payload.items()
            if key in SAFE_EVENT_PAYLOAD_KEYS
        }

    @classmethod
    def _is_download_ready(cls, job: Any) -> bool:
        return job.status == "completed" and cls._has_result_zip(job)

    @staticmethod
    def _has_result_zip(job: Any) -> bool:
        return bool(job.result_zip_path and Path(job.result_zip_path).is_file())

    @classmethod
    def _resolve_result_zip(cls, job: Any) -> Path:
        if job.status != "completed":
            raise ValueError("job result is not ready")
        if not cls._has_result_zip(job):
            raise FileNotFoundError("job result archive not found")
        return Path(job.result_zip_path)


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
