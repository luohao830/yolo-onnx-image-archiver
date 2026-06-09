from pathlib import Path

from backend.core.db import build_engine, create_all, session_scope
from backend.repositories.jobs import JobRepository


def test_job_repository_persists_status_transitions(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    input_path = "runtime/uploads/JOB-001/input.zip"
    result_dir = "runtime/results/JOB-001"
    result_zip_path = "runtime/results/JOB-001.zip"

    with session_scope(engine) as session:
        repo = JobRepository(session)
        job = repo.create_job(
            job_code="JOB-001",
            access_token_hash="hash",
            mode="person_filter",
        )
        assert job.status == "created"
        job_id = job.id

    with session_scope(engine) as session:
        repo = JobRepository(session)
        saved = repo.get_by_code("JOB-001")
        assert saved is not None
        assert saved.status == "created"
        assert saved.input_path is None
        assert saved.result_dir is None
        assert saved.result_zip_path is None

    with session_scope(engine) as session:
        repo = JobRepository(session)
        repo.mark_uploaded(job_id, input_path=input_path)

    with session_scope(engine) as session:
        repo = JobRepository(session)
        saved = repo.get_by_code("JOB-001")
        assert saved is not None
        assert saved.status == "uploaded"
        assert saved.input_path == input_path

    with session_scope(engine) as session:
        repo = JobRepository(session)
        repo.mark_running(job_id)

    with session_scope(engine) as session:
        repo = JobRepository(session)
        saved = repo.get_by_code("JOB-001")
        assert saved is not None
        assert saved.status == "running"
        assert saved.input_path == input_path

    with session_scope(engine) as session:
        repo = JobRepository(session)
        repo.mark_completed(
            job_id,
            result_dir=result_dir,
            result_zip_path=result_zip_path,
        )

    with session_scope(engine) as session:
        repo = JobRepository(session)
        saved = repo.get_by_code("JOB-001")
        assert saved is not None
        assert saved.status == "completed"
        assert saved.input_path == input_path
        assert saved.result_dir == result_dir
        assert saved.result_zip_path == result_zip_path
