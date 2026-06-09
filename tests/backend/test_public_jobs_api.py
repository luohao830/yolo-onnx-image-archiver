from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.core.db import build_engine, create_all, session_scope
from backend.main import app
from backend.repositories.jobs import JobRepository

from backend.api.routes.public_jobs import create_job, get_job
from backend.schemas.jobs import CreateJobRequest
from backend.services.job_service import JobService


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
    assert "/api/jobs/{job_code}" in schema["paths"]
    assert "get" in schema["paths"]["/api/jobs/{job_code}"]
