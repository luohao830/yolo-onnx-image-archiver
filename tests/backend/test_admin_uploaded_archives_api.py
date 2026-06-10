from __future__ import annotations

from pathlib import Path

from backend.api.routes.admin_uploads import (
    DeleteUploadedArchivesRequest,
    delete_uploaded_archives,
    list_uploaded_archives,
)
from backend.core.db import build_engine, create_all
from backend.repositories.uploaded_archives import UploadedArchiveRepository
from backend.services.job_service import JobService
from backend.services.runtime_paths import RuntimePaths


def test_admin_lists_and_deletes_uploaded_archives(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    runtime_paths = RuntimePaths(tmp_path / "runtime")
    runtime_paths.ensure()
    raw_path = runtime_paths.upload_archives / ("a" * 64) / "archive.zip"
    extracted_path = runtime_paths.upload_archives / ("a" * 64) / "extracted"
    raw_path.parent.mkdir(parents=True)
    extracted_path.mkdir()
    raw_path.write_bytes(b"zip-bytes")
    (extracted_path / "demo.jpg").write_bytes(b"image")

    service = JobService(engine, runtime_paths=runtime_paths)
    archive = UploadedArchiveRepository.create_for_engine(
        engine,
        content_sha256="a" * 64,
        original_filename="images.zip",
        archive_path=str(raw_path),
        extracted_path=str(extracted_path),
        size_bytes=9,
        image_count=1,
    )

    listed = list_uploaded_archives(admin={"role": "admin"}, service=service)

    assert len(listed) == 1
    assert listed[0].content_sha256 == "a" * 64
    assert listed[0].original_filename == "images.zip"

    result = delete_uploaded_archives(
        payload=DeleteUploadedArchivesRequest(ids=[archive.id]),
        admin={"role": "admin"},
        service=service,
    )

    assert result.deleted == 1
    assert not raw_path.exists()
    assert not extracted_path.exists()
    assert list_uploaded_archives(admin={"role": "admin"}, service=service) == []
