from pathlib import Path

from backend.core.db import build_engine, create_all, session_scope
from backend.repositories.jobs import JobRepository


def test_job_repository_persists_status_transitions(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)

    with session_scope(engine) as session:
        repo = JobRepository(session)
        job = repo.create_job(
            job_code="JOB-001",
            access_token_hash="hash",
            mode="person_filter",
        )
        assert job.status == "created"

        saved = repo.get_by_code("JOB-001")
        assert saved is not None
        assert saved.status == "created"

        repo.mark_uploaded(job.id, input_path="runtime/uploads/JOB-001/input.zip")
        saved = repo.get_by_code("JOB-001")
        assert saved is not None
        assert saved.status == "uploaded"
        assert saved.input_path == "runtime/uploads/JOB-001/input.zip"

        repo.mark_running(job.id)
        saved = repo.get_by_code("JOB-001")
        assert saved is not None
        assert saved.status == "running"

        repo.mark_completed(
            job.id,
            result_dir="runtime/results/JOB-001",
            result_zip_path="runtime/results/JOB-001.zip",
        )

        saved = repo.get_by_code("JOB-001")
        assert saved is not None
        assert saved.status == "completed"
        assert saved.result_dir == "runtime/results/JOB-001"
        assert saved.result_zip_path.endswith("JOB-001.zip")
