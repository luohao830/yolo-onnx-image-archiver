from pathlib import Path
from io import BytesIO
import zipfile

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from backend.core.config import Settings, settings
from backend.core.db import build_engine, create_all, session_scope
from backend.db.models import JobRecord, ModelRecord
from backend.main import app
from backend.repositories.jobs import JobRepository

from backend.api.routes.public_jobs import (
    create_job,
    download_job_result,
    get_job,
    list_published_models,
    upload_job_file,
)
from backend.schemas.jobs import CreateJobRequest
import backend.services.job_service as job_service
from backend.services.job_service import JobService, get_job_service
from backend.services.runtime_paths import RuntimePaths
from backend.services.model_service import ModelService


class _FakeScheduler:
    def __init__(self) -> None:
        self.submitted: list[int] = []

    def submit(self, job_id: int) -> None:
        self.submitted.append(job_id)


def test_create_public_job_returns_receipt_and_persists_job(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    service = JobService(engine)

    receipt = create_job(CreateJobRequest(mode="person_filter"), service=service)

    assert receipt.job_code.startswith("JOB-")
    assert receipt.access_token
    assert receipt.status == "created"

    with session_scope(engine) as session:
        saved = JobRepository(session).get_by_code(receipt.job_code)
        assert saved is not None
        assert saved.mode == "person_filter"
        assert saved.status == "created"
        assert saved.access_token_hash != receipt.access_token


def test_get_public_job_returns_status_when_token_matches(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    service = JobService(engine)
    receipt = create_job(CreateJobRequest(mode="advanced"), service=service)

    payload = get_job(receipt.job_code, receipt.access_token, service=service)

    assert payload.job_code == receipt.job_code
    assert payload.mode == "advanced"
    assert payload.status == "created"
    assert payload.error_message is None


def test_upload_public_person_filter_archive_marks_uploaded_and_submits_job(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    service = JobService(engine, runtime_paths=RuntimePaths(tmp_path / "runtime"))
    receipt = create_job(CreateJobRequest(mode="person_filter"), service=service)
    scheduler = _FakeScheduler()
    archive = BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("nested/demo.jpg", b"image-bytes")
    archive.seek(0)

    with session_scope(engine) as session:
        session.add(
            ModelRecord(
                name="person-default",
                slug="person-default",
                onnx_path="models/person.onnx",
                model_kind="person_detector",
                enabled=True,
                visible_in_advanced_mode=True,
                is_default_person_model=True,
            )
        )

    payload = upload_job_file(
        receipt.job_code,
        receipt.access_token,
        file=UploadFile(file=archive, filename="images.zip"),
        service=service,
        scheduler=scheduler,
    )

    assert payload.status == "uploaded"
    assert payload.progress == 20
    assert payload.events[0].event_type == "uploaded"
    assert scheduler.submitted

    with session_scope(engine) as session:
        repo = JobRepository(session)
        saved = repo.get_by_code(receipt.job_code)
        assert saved is not None
        assert saved.model_id is not None
        assert saved.input_path is not None
        assert (Path(saved.input_path) / "nested" / "demo.jpg").read_bytes() == b"image-bytes"
        assert scheduler.submitted == [saved.id]


def test_upload_public_person_filter_rejects_archive_over_upload_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    service = JobService(engine, runtime_paths=RuntimePaths(tmp_path / "runtime"))
    receipt = create_job(CreateJobRequest(mode="person_filter"), service=service)
    scheduler = _FakeScheduler()
    monkeypatch.setattr(job_service, "MAX_UPLOAD_FILE_BYTES", 10, raising=False)
    archive = BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("demo.jpg", b"image-bytes")
    archive.seek(0)

    with session_scope(engine) as session:
        session.add(
            ModelRecord(
                name="person-default",
                slug="person-default",
                onnx_path="models/person.onnx",
                model_kind="person_detector",
                enabled=True,
                visible_in_advanced_mode=True,
                is_default_person_model=True,
            )
        )

    with pytest.raises(HTTPException) as exc_info:
        upload_job_file(
            receipt.job_code,
            receipt.access_token,
            file=UploadFile(file=archive, filename="images.zip"),
            service=service,
            scheduler=scheduler,
        )

    assert exc_info.value.status_code == 413
    assert scheduler.submitted == []


def test_get_public_job_returns_progress_events_and_download_state(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    service = JobService(engine)
    receipt = create_job(CreateJobRequest(mode="person_filter"), service=service)

    with session_scope(engine) as session:
        repo = JobRepository(session)
        saved = repo.get_by_code(receipt.job_code)
        assert saved is not None
        repo.mark_running(saved.id)
        repo.record_event(
            saved.id,
            event_type="running",
            message="任务开始执行",
            payload_json={
                "total": 10,
                "written": 4,
                "path": "/data/private/JOB-1",
            },
        )

    payload = get_job(receipt.job_code, receipt.access_token, service=service)

    assert payload.progress == 40
    assert payload.download_ready is False
    assert len(payload.events) == 1
    assert payload.events[0].event_type == "running"
    assert payload.events[0].message == "任务开始执行"
    assert payload.events[0].payload_json == {"total": 10, "written": 4}


def test_download_public_job_result_requires_completed_job_and_token(tmp_path: Path) -> None:
    result_zip = tmp_path / "result.zip"
    result_zip.write_bytes(b"zip-bytes")
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    service = JobService(engine)
    receipt = create_job(CreateJobRequest(mode="person_filter"), service=service)

    with session_scope(engine) as session:
        repo = JobRepository(session)
        saved = repo.get_by_code(receipt.job_code)
        assert saved is not None
        repo.mark_completed(saved.id, result_dir=str(tmp_path), result_zip_path=str(result_zip))

    response = download_job_result(receipt.job_code, receipt.access_token, service=service)

    assert Path(response.path) == result_zip

    with pytest.raises(HTTPException) as bad_token_error:
        download_job_result(receipt.job_code, "bad-token", service=service)

    assert bad_token_error.value.status_code == 404


def test_get_public_job_raises_404_for_bad_or_missing_access_token(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    service = JobService(engine)
    receipt = create_job(CreateJobRequest(mode="person_filter"), service=service)

    with pytest.raises(HTTPException) as bad_token_error:
        get_job(receipt.job_code, "bad-token", service=service)

    assert bad_token_error.value.status_code == 404

    with pytest.raises(HTTPException) as missing_job_error:
        get_job("JOB-404", receipt.access_token, service=service)

    assert missing_job_error.value.status_code == 404


def test_openapi_contains_public_job_routes() -> None:
    schema = app.openapi()

    assert "/api/jobs" in schema["paths"]
    assert "post" in schema["paths"]["/api/jobs"]
    assert "201" in schema["paths"]["/api/jobs"]["post"]["responses"]
    assert "/api/jobs/models" in schema["paths"]
    assert "get" in schema["paths"]["/api/jobs/models"]
    assert "/api/jobs/{job_code}" in schema["paths"]
    assert "get" in schema["paths"]["/api/jobs/{job_code}"]
    assert "/api/jobs/{job_code}/upload" in schema["paths"]
    assert "post" in schema["paths"]["/api/jobs/{job_code}/upload"]
    assert "/api/jobs/{job_code}/download" in schema["paths"]
    assert "get" in schema["paths"]["/api/jobs/{job_code}/download"]


def test_list_published_models_only_returns_enabled_advanced_models(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)

    with session_scope(engine) as session:
        session.add_all(
            [
                ModelRecord(
                    name="helmet-person-v1",
                    slug="helmet-person-v1",
                    onnx_path="models/helmet-person-v1.onnx",
                    model_kind="person_detector",
                    enabled=True,
                    visible_in_advanced_mode=True,
                ),
                ModelRecord(
                    name="hidden-model",
                    slug="hidden-model",
                    onnx_path="models/hidden-model.onnx",
                    model_kind="person_detector",
                    enabled=True,
                    visible_in_advanced_mode=False,
                ),
                ModelRecord(
                    name="disabled-model",
                    slug="disabled-model",
                    onnx_path="models/disabled-model.onnx",
                    model_kind="person_detector",
                    enabled=False,
                    visible_in_advanced_mode=True,
                ),
            ]
        )

    payload = list_published_models(service=ModelService(engine))

    assert len(payload) == 1
    assert payload[0].id == "1"
    assert payload[0].name == "helmet-person-v1"


def test_settings_default_database_url_is_stable_across_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original_url = Settings().resolve_database_url()

    monkeypatch.chdir(tmp_path)

    changed_url = Settings().resolve_database_url()

    assert changed_url == original_url


def test_get_job_service_uses_runtime_root_database_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / "runtime-root"
    original_runtime_root = settings.runtime_root
    original_database_url = settings.database_url
    get_job_service.cache_clear()
    monkeypatch.setattr(settings, "runtime_root", runtime_root)
    monkeypatch.setattr(settings, "database_url", None)

    try:
        service = get_job_service()
        expected_db_path = (runtime_root / "app.db").resolve()

        assert Path(service.engine.url.database) == expected_db_path
        assert expected_db_path.exists()
    finally:
        get_job_service.cache_clear()
        settings.runtime_root = original_runtime_root
        settings.database_url = original_database_url


def test_job_service_rejects_invalid_mode_without_persisting(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    service = JobService(engine)

    with pytest.raises(ValueError, match="unsupported job mode"):
        service.create_public_job("unsupported")

    with session_scope(engine) as session:
        assert session.query(JobRecord).count() == 0
