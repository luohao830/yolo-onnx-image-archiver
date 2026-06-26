from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.api.routes.admin_jobs import (
    cancel_job,
    download_job_result,
    get_job_detail,
    issue_job_events_token,
    list_jobs,
    retry_job,
)
from backend.core.admin_auth import AdminTokenError, AdminTokenService
from backend.core.db import build_engine, create_all, session_scope
from backend.db.models import JobRecord
from backend.main import app
from backend.repositories.jobs import JobRepository
from backend.services.job_service import JobService


ADMIN_CLAIMS = {"role": "admin"}


def test_admin_can_list_jobs(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    service = JobService(engine)

    with session_scope(engine) as session:
        repo = JobRepository(session)
        repo.create_job(job_code="JOB-001", access_token_hash="hash-1", mode="person_filter")
        repo.create_job(job_code="JOB-002", access_token_hash="hash-2", mode="advanced")

    jobs = list_jobs(admin=ADMIN_CLAIMS, service=service)

    assert [job.job_code for job in jobs] == ["JOB-001", "JOB-002"]
    assert jobs[0].status == "created"
    assert jobs[1].mode == "advanced"
    assert jobs[0].progress == 0
    assert jobs[0].download_ready is False


def test_admin_can_get_job_detail_with_events_and_download_state(tmp_path: Path) -> None:
    result_zip = tmp_path / "result.zip"
    result_zip.write_bytes(b"zip-bytes")
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    service = JobService(engine)

    with session_scope(engine) as session:
        repo = JobRepository(session)
        job = repo.create_job(job_code="JOB-DONE", access_token_hash="hash", mode="advanced")
        repo.record_event(
            job.id,
            event_type="completed",
            message="输出结果压缩包已生成",
            payload_json={"total": 2, "written": 2, "path": "/data/private/result.zip"},
        )
        repo.mark_completed(job.id, result_dir=str(tmp_path), result_zip_path=str(result_zip))
        job_id = job.id

    detail = get_job_detail(job_id, admin=ADMIN_CLAIMS, service=service)

    assert detail.job_code == "JOB-DONE"
    assert detail.progress == 100
    assert detail.download_ready is True
    assert detail.result_zip_available is True
    assert detail.events[0].message == "输出结果压缩包已生成"
    assert detail.events[0].payload_json == {"total": 2, "written": 2}


def test_admin_can_issue_job_events_token(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    service = JobService(engine)
    token_service = AdminTokenService("test-secret")

    with session_scope(engine) as session:
        repo = JobRepository(session)
        job = repo.create_job(job_code="JOB-SSE", access_token_hash="hash", mode="advanced")
        job_id = job.id

    response = issue_job_events_token(
        job_id,
        admin=ADMIN_CLAIMS,
        service=service,
        token_service=token_service,
    )

    claims = token_service.verify_sse(response.token, job_id)
    assert claims["role"] == "admin"
    assert claims["purpose"] == "job-events"
    assert claims["job_id"] == job_id
    with pytest.raises(AdminTokenError):
        token_service.verify_sse(response.token, job_id + 1)


def test_admin_job_events_token_returns_404_for_missing_job(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    service = JobService(engine)

    with pytest.raises(HTTPException) as error:
        issue_job_events_token(
            404,
            admin=ADMIN_CLAIMS,
            service=service,
            token_service=AdminTokenService("test-secret"),
        )

    assert error.value.status_code == 404


def test_admin_can_download_completed_job_result(tmp_path: Path) -> None:
    result_zip = tmp_path / "result.zip"
    result_zip.write_bytes(b"zip-bytes")
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    service = JobService(engine)

    with session_scope(engine) as session:
        repo = JobRepository(session)
        job = repo.create_job(job_code="JOB-DONE", access_token_hash="hash", mode="advanced")
        repo.mark_completed(job.id, result_dir=str(tmp_path), result_zip_path=str(result_zip))
        job_id = job.id

    response = download_job_result(job_id, admin=ADMIN_CLAIMS, service=service)

    assert Path(response.path) == result_zip


def test_admin_can_cancel_queued_job(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    service = JobService(engine)

    with session_scope(engine) as session:
        repo = JobRepository(session)
        job = repo.create_job(job_code="JOB-QUEUED", access_token_hash="hash", mode="person_filter")
        job_id = job.id

    response = cancel_job(job_id, admin=ADMIN_CLAIMS, service=service)

    assert response.status == "canceled"
    assert response.cancel_requested is False

    with session_scope(engine) as session:
        saved = session.get(JobRecord, job_id)
        assert saved is not None
        assert saved.status == "canceled"
        assert saved.cancel_requested is False


def test_admin_can_mark_running_job_for_cancel(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    service = JobService(engine)

    with session_scope(engine) as session:
        repo = JobRepository(session)
        job = repo.create_job(job_code="JOB-RUNNING", access_token_hash="hash", mode="advanced")
        repo.mark_running(job.id)
        job_id = job.id

    response = cancel_job(job_id, admin=ADMIN_CLAIMS, service=service)

    assert response.status == "running"
    assert response.cancel_requested is True

    with session_scope(engine) as session:
        saved = session.get(JobRecord, job_id)
        assert saved is not None
        assert saved.status == "running"
        assert saved.cancel_requested is True


def test_admin_can_retry_failed_job(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    service = JobService(engine)

    with session_scope(engine) as session:
        repo = JobRepository(session)
        job = repo.create_job(job_code="JOB-FAILED", access_token_hash="hash", mode="advanced")
        repo.mark_failed(job.id, error_message="gpu unavailable")
        job_id = job.id

    response = retry_job(job_id, admin=ADMIN_CLAIMS, service=service)

    assert response.status == "created"
    assert response.error_message is None
    assert response.cancel_requested is False

    with session_scope(engine) as session:
        saved = session.get(JobRecord, job_id)
        assert saved is not None
        assert saved.status == "created"
        assert saved.error_message is None
        assert saved.cancel_requested is False


def test_openapi_contains_admin_job_routes() -> None:
    schema = app.openapi()

    assert "/api/admin/jobs" in schema["paths"]
    assert "get" in schema["paths"]["/api/admin/jobs"]
    assert "/api/admin/jobs/{job_id}/cancel" in schema["paths"]
    assert "post" in schema["paths"]["/api/admin/jobs/{job_id}/cancel"]
    assert "/api/admin/jobs/{job_id}/retry" in schema["paths"]
    assert "post" in schema["paths"]["/api/admin/jobs/{job_id}/retry"]
    assert "/api/admin/jobs/{job_id}/events-token" in schema["paths"]
    assert "post" in schema["paths"]["/api/admin/jobs/{job_id}/events-token"]
    assert "/api/admin/jobs/{job_id}" in schema["paths"]
    assert "get" in schema["paths"]["/api/admin/jobs/{job_id}"]
    assert "/api/admin/jobs/{job_id}/download" in schema["paths"]
    assert "get" in schema["paths"]["/api/admin/jobs/{job_id}/download"]
