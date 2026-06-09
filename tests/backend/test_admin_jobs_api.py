from __future__ import annotations

from pathlib import Path

from backend.api.routes.admin_jobs import cancel_job, list_jobs, retry_job
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
