import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.core.db import build_engine, create_all, session_scope
from backend.core.job_events_auth import JobEventsTokenService
from backend.db.models import ModelRecord
from backend.repositories.jobs import JobRepository
from backend.services import inference_adapter
from backend.services.job_service import JobService
from backend.schemas.jobs import PublicJobEventsTokenRequest
from backend.services.runtime_paths import RuntimePaths

from backend.api.routes.public_jobs import get_job_detections, get_job_image, issue_job_events_token
from backend.api.routes.admin_jobs import get_job_detections as admin_get_job_detections
from backend.api.routes.admin_jobs import get_job_image as admin_get_job_image


def _seed_completed_job(tmp_path: Path) -> tuple[JobService, str, str, int, Path]:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    runtime_paths = RuntimePaths(tmp_path / "runtime")
    runtime_paths.ensure()
    service = JobService(engine, runtime_paths=runtime_paths)

    receipt = service.create_public_job("person_filter")
    job_code = receipt["job_code"]
    access_token = receipt["access_token"]
    result_dir = runtime_paths.results / job_code
    result_dir.mkdir(parents=True, exist_ok=True)

    with session_scope(engine) as session:
        model = ModelRecord(onnx_path=str(tmp_path / "model.onnx"))
        session.add(model)
        session.flush()
        repo = JobRepository(session)
        job = repo.get_by_code(job_code)
        assert job is not None
        repo.mark_uploaded(job.id, input_path=str(tmp_path / "images"), model_id=model.id)
        repo.mark_completed(job.id, result_dir=str(result_dir), result_zip_path=str(tmp_path / "r.zip"))
        job_id = job.id

    return service, job_code, access_token, job_id, result_dir


def test_public_detections_returns_json(tmp_path: Path) -> None:
    service, job_code, access_token, _job_id, result_dir = _seed_completed_job(tmp_path)
    inference_adapter.write_detections_json(
        result_dir,
        [{"filename": "a.jpg", "detections": [{"label": "person", "confidence": 0.9, "bbox": [1, 2, 3, 4], "cls_id": 0}]}],
    )

    data = get_job_detections(job_code, access_token, service=service)
    assert data.images[0].filename == "a.jpg"
    assert data.images[0].detections[0].label == "person"


def test_public_detections_404_when_missing(tmp_path: Path) -> None:
    service, job_code, access_token, _job_id, _result_dir = _seed_completed_job(tmp_path)
    with pytest.raises(HTTPException) as exc:
        get_job_detections(job_code, access_token, service=service)
    assert exc.value.status_code == 404


def test_public_detections_404_for_bad_token(tmp_path: Path) -> None:
    service, job_code, _access_token, _job_id, result_dir = _seed_completed_job(tmp_path)
    inference_adapter.write_detections_json(result_dir, [])
    with pytest.raises(HTTPException) as exc:
        get_job_detections(job_code, "bad-token", service=service)
    assert exc.value.status_code == 404



def test_public_can_issue_short_lived_job_events_token(tmp_path: Path) -> None:
    service, job_code, access_token, job_id, _result_dir = _seed_completed_job(tmp_path)
    token_service = JobEventsTokenService("test-secret")

    response = issue_job_events_token(
        job_code,
        PublicJobEventsTokenRequest(access_token=access_token),
        service=service,
        token_service=token_service,
    )

    claims = token_service.verify(response.token, job_id)
    assert claims["purpose"] == "public-job-events"
    assert claims["job_id"] == job_id

    with pytest.raises(HTTPException) as bad_token_exc:
        issue_job_events_token(
            job_code,
            PublicJobEventsTokenRequest(access_token="bad-token"),
            service=service,
            token_service=token_service,
        )
    assert bad_token_exc.value.status_code == 404


def test_public_image_serves_file_with_traversal_guard(tmp_path: Path) -> None:
    service, job_code, access_token, _job_id, result_dir = _seed_completed_job(tmp_path)
    img_path = result_dir / "person_画框" / "images" / "a.jpg"
    img_path.parent.mkdir(parents=True, exist_ok=True)
    img_path.write_bytes(b"img-bytes")

    rel = "person_画框/images/a.jpg"
    response = get_job_image(job_code, access_token, rel, service=service)
    assert Path(response.path) == img_path
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"

    with pytest.raises(HTTPException) as exc:
        get_job_image(job_code, access_token, "../../../etc/passwd", service=service)
    assert exc.value.status_code == 404


def test_admin_detections_and_image(tmp_path: Path) -> None:
    service, _job_code, _access_token, job_id, result_dir = _seed_completed_job(tmp_path)
    inference_adapter.write_detections_json(result_dir, [{"filename": "b.jpg", "detections": []}])

    data = admin_get_job_detections(job_id, admin={}, service=service)
    assert data.images[0].filename == "b.jpg"

    img_path = result_dir / "c.png"
    img_path.write_bytes(b"png-bytes")
    response = admin_get_job_image(job_id, "c.png", admin={}, service=service)
    assert Path(response.path) == img_path
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"


def test_read_detections_json_returns_none_when_absent(tmp_path: Path) -> None:
    assert inference_adapter.read_detections_json(tmp_path) is None


def test_build_job_summary_json_excludes_out_dir() -> None:
    summary = {"out_dir": "/x", "total": 3, "by_label": {"person": 3}, "used_imgsz": (640, 640)}
    result = inference_adapter.build_job_summary_json(summary)
    assert "out_dir" not in result
    assert result["total"] == 3
    assert result["used_imgsz"] == [640, 640]


def test_public_image_rejects_empty_rel_path(tmp_path: Path) -> None:
    service, job_code, access_token, _job_id, result_dir = _seed_completed_job(tmp_path)
    with pytest.raises(HTTPException) as exc:
        get_job_image(job_code, access_token, "", service=service)
    assert exc.value.status_code == 404



def test_public_and_admin_image_reject_non_image_files(tmp_path: Path) -> None:
    service, job_code, access_token, job_id, result_dir = _seed_completed_job(tmp_path)
    secret = result_dir / "_detections.json"
    secret.write_text('{"internal": true}', encoding="utf-8")

    with pytest.raises(HTTPException) as public_exc:
        get_job_image(job_code, access_token, "_detections.json", service=service)
    assert public_exc.value.status_code == 404

    with pytest.raises(HTTPException) as admin_exc:
        admin_get_job_image(job_id, "_detections.json", admin={}, service=service)
    assert admin_exc.value.status_code == 404


def test_public_image_rejects_traversal_attempts(tmp_path: Path) -> None:
    service, job_code, access_token, _job_id, result_dir = _seed_completed_job(tmp_path)
    for payload in (
        ".%2e/.%2e/etc/hostname",
        "....//....//etc/hostname",
        "foo/../../etc/hostname",
    ):
        with pytest.raises(HTTPException) as exc:
            get_job_image(job_code, access_token, payload, service=service)
        assert exc.value.status_code == 404


def test_public_detections_404_when_result_dir_absent(tmp_path: Path) -> None:
    """结果目录不存在时返回 404，不应抛内部错误。"""
    service, job_code, access_token, _job_id, _result_dir = _seed_completed_job(tmp_path)
    # result_dir 存在但从 db 返回 None — 已由 _seed 保证 result_dir 是空目录
    with pytest.raises(HTTPException) as exc:
        get_job_detections(job_code, access_token, service=service)
    assert exc.value.status_code == 404


def test_admin_image_rejects_traversal(tmp_path: Path) -> None:
    service, _job_code, _access_token, job_id, _result_dir = _seed_completed_job(tmp_path)
    with pytest.raises(HTTPException) as exc:
        admin_get_job_image(job_id, "../../../etc/passwd", admin={}, service=service)
    assert exc.value.status_code == 404
