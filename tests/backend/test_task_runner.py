from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call

from backend.core.db import build_engine, create_all, session_scope
from backend.db.models import JobEventRecord, ModelRecord
from backend.repositories.jobs import JobRepository
from backend.repositories.models import ModelRepository
from backend.services.runtime_paths import RuntimePaths
from backend.workers.task_runner import ProgressEventWriter, TaskRunner


def test_task_runner_marks_completed(monkeypatch, tmp_path: Path) -> None:
    summary = {"out_dir": str(tmp_path / "results"), "total": 2, "written": 2}

    monkeypatch.setattr("backend.services.inference_adapter.run_job_inference", lambda *args, **kwargs: summary)
    monkeypatch.setattr("backend.services.inference_adapter.package_job_output", lambda out_dir: str(tmp_path / "results.zip"))

    job_repo = MagicMock()
    job_repo.get.return_value = SimpleNamespace(
        id=1,
        job_code="JOB-001",
        model_id=10,
        input_path=str(tmp_path / "images"),
        payload_json={"recursive": True, "batch": 8, "imgsz": None, "conf": 0.25, "iou": 0.45},
    )
    model_repo = MagicMock()
    model_repo.get.return_value = SimpleNamespace(onnx_path=str(tmp_path / "model.onnx"))
    config_repo = MagicMock()
    gpu_gate = MagicMock()
    gpu_gate.acquire.return_value.__enter__.return_value = None
    gpu_gate.acquire.return_value.__exit__.return_value = None

    runner = TaskRunner(
        job_repo=job_repo,
        model_repo=model_repo,
        config_repo=config_repo,
        gpu_gate=gpu_gate,
        runtime_paths=RuntimePaths(tmp_path / "runtime"),
    )
    runner.run(job_id=1)

    job_repo.mark_running.assert_called_once_with(1)
    job_repo.mark_completed.assert_called_once_with(
        1,
        result_dir=str(tmp_path / "results"),
        result_zip_path=str(tmp_path / "results.zip"),
    )
    job_repo.record_event.assert_has_calls(
        [
            call(
                1,
                event_type="running",
                message="任务开始执行",
                payload_json={
                    "job_code": "JOB-001",
                    "out_dir": str(tmp_path / "runtime" / "results" / "JOB-001"),
                },
            ),
            call(
                1,
                event_type="completed",
                message="任务执行完成",
                payload_json={
                    "result_dir": str(tmp_path / "results"),
                    "result_zip_path": str(tmp_path / "results.zip"),
                    "total": 2,
                    "written": 2,
                    "detections_ready": False,
                },
            ),
        ]
    )


def test_task_runner_marks_failed_when_inference_raises(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("backend.services.inference_adapter.run_job_inference", MagicMock(side_effect=RuntimeError("boom")))
    package_job_output = MagicMock()
    monkeypatch.setattr("backend.services.inference_adapter.package_job_output", package_job_output)

    job_repo = MagicMock()
    job_repo.get.return_value = SimpleNamespace(
        id=1,
        job_code="JOB-002",
        model_id=10,
        input_path=str(tmp_path / "images"),
        payload_json=None,
    )
    model_repo = MagicMock()
    model_repo.get.return_value = SimpleNamespace(onnx_path=str(tmp_path / "model.onnx"))
    config_repo = MagicMock()
    gpu_gate = MagicMock()
    gpu_gate.acquire.return_value.__enter__.return_value = None
    gpu_gate.acquire.return_value.__exit__.return_value = None

    runner = TaskRunner(
        job_repo=job_repo,
        model_repo=model_repo,
        config_repo=config_repo,
        gpu_gate=gpu_gate,
        runtime_paths=RuntimePaths(tmp_path / "runtime"),
    )
    runner.run(job_id=1)

    job_repo.mark_failed.assert_called_once_with(1, error_message="boom")
    job_repo.mark_completed.assert_not_called()
    package_job_output.assert_not_called()
    job_repo.record_event.assert_has_calls(
        [
            call(
                1,
                event_type="running",
                message="任务开始执行",
                payload_json={
                    "job_code": "JOB-002",
                    "out_dir": str(tmp_path / "runtime" / "results" / "JOB-002"),
                },
            ),
            call(
                1,
                event_type="failed",
                message="任务执行失败",
                payload_json={"error": "boom"},
            ),
        ]
    )


def test_task_runner_packages_output_from_summary_directory(monkeypatch, tmp_path: Path) -> None:
    summary = {"out_dir": str(tmp_path / "summary-results"), "total": 3, "written": 3}
    run_job_inference = MagicMock(return_value=summary)
    package_job_output = MagicMock(return_value=str(tmp_path / "summary-results.zip"))
    monkeypatch.setattr("backend.services.inference_adapter.run_job_inference", run_job_inference)
    monkeypatch.setattr("backend.services.inference_adapter.package_job_output", package_job_output)

    job_repo = MagicMock()
    job_repo.get.return_value = SimpleNamespace(
        id=1,
        job_code="JOB-003",
        model_id=10,
        input_path=str(tmp_path / "images"),
        payload_json={"draw_boxes": True, "save_txt": True},
    )
    model_repo = MagicMock()
    model_repo.get.return_value = SimpleNamespace(onnx_path=str(tmp_path / "model.onnx"))
    config_repo = MagicMock()
    gpu_gate = MagicMock()
    gpu_gate.acquire.return_value.__enter__.return_value = None
    gpu_gate.acquire.return_value.__exit__.return_value = None

    runner = TaskRunner(
        job_repo=job_repo,
        model_repo=model_repo,
        config_repo=config_repo,
        gpu_gate=gpu_gate,
        runtime_paths=RuntimePaths(tmp_path / "runtime"),
    )
    runner.run(job_id=1)

    run_job_inference.assert_called_once()
    call_kwargs = run_job_inference.call_args.kwargs
    assert call_kwargs["model_path"] == tmp_path / "model.onnx"
    assert call_kwargs["images_dir"] == tmp_path / "images"
    assert call_kwargs["out_dir"] == tmp_path / "runtime" / "results" / "JOB-003"
    assert call_kwargs["payload"]["draw_boxes"] is True
    assert call_kwargs["payload"]["save_txt"] is True
    assert call_kwargs["payload"]["batch"] == 16
    assert call_kwargs["payload"]["copy_fallback"] is False
    package_job_output.assert_called_once_with(tmp_path / "summary-results")


def test_task_runner_persists_completion_with_real_repositories(monkeypatch, tmp_path: Path) -> None:
    summary = {"out_dir": str(tmp_path / "results"), "total": 4, "written": 4}
    monkeypatch.setattr("backend.services.inference_adapter.run_job_inference", MagicMock(return_value=summary))
    monkeypatch.setattr("backend.services.inference_adapter.package_job_output", MagicMock(return_value=str(tmp_path / "results.zip")))

    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    runtime_paths = RuntimePaths(tmp_path / "runtime")
    job_id = None

    with session_scope(engine) as session:
        model = ModelRecord(onnx_path=str(tmp_path / "model.onnx"))
        session.add(model)
        session.flush()

        job_repo = JobRepository(session)
        job = job_repo.create_job(
            job_code="JOB-100",
            access_token_hash="hash",
            mode="person_filter",
            model_id=model.id,
            payload_json={"recursive": False, "batch": 4},
        )
        job_repo.mark_uploaded(job.id, input_path=str(images_dir))
        job_id = job.id

    with session_scope(engine) as session:
        runner = TaskRunner(
            job_repo=JobRepository(session),
            model_repo=ModelRepository(session),
            config_repo=MagicMock(),
            gpu_gate=_DummyGpuGate(),
            runtime_paths=runtime_paths,
        )
        runner.run(job_id=job_id)

    with session_scope(engine) as session:
        saved = JobRepository(session).get(job_id)
        events = session.query(JobEventRecord).filter_by(job_id=job_id).order_by(JobEventRecord.id).all()
        assert saved.status == "completed"
        assert saved.input_path == str(images_dir)
        assert saved.result_dir == str(tmp_path / "results")
        assert saved.result_zip_path == str(tmp_path / "results.zip")
        assert saved.error_message is None
        assert [event.event_type for event in events] == ["running", "completed"]
        assert events[0].message == "任务开始执行"
        assert events[0].payload_json == {
            "job_code": "JOB-100",
            "out_dir": str(tmp_path / "runtime" / "results" / "JOB-100"),
        }
        assert events[1].message == "任务执行完成"
        assert events[1].payload_json == {
            "result_dir": str(tmp_path / "results"),
            "result_zip_path": str(tmp_path / "results.zip"),
            "total": 4,
            "written": 4,
            "detections_ready": False,
        }
        assert saved.summary_json == {"total": 4, "written": 4}


def test_task_runner_persists_failure_with_real_repositories(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("backend.services.inference_adapter.run_job_inference", MagicMock(side_effect=RuntimeError("gpu unavailable")))
    monkeypatch.setattr("backend.services.inference_adapter.package_job_output", MagicMock())

    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    runtime_paths = RuntimePaths(tmp_path / "runtime")
    job_id = None

    with session_scope(engine) as session:
        model = ModelRecord(onnx_path=str(tmp_path / "model.onnx"))
        session.add(model)
        session.flush()

        job_repo = JobRepository(session)
        job = job_repo.create_job(
            job_code="JOB-101",
            access_token_hash="hash",
            mode="advanced",
            model_id=model.id,
            payload_json={"execution_device": "cpu"},
        )
        job_repo.mark_uploaded(job.id, input_path=str(images_dir))
        job_id = job.id

    with session_scope(engine) as session:
        runner = TaskRunner(
            job_repo=JobRepository(session),
            model_repo=ModelRepository(session),
            config_repo=MagicMock(),
            gpu_gate=_DummyGpuGate(),
            runtime_paths=runtime_paths,
        )
        runner.run(job_id=job_id)

    with session_scope(engine) as session:
        saved = JobRepository(session).get(job_id)
        events = session.query(JobEventRecord).filter_by(job_id=job_id).order_by(JobEventRecord.id).all()
        assert saved.status == "failed"
        assert saved.error_message == "gpu unavailable"
        assert saved.result_dir is None
        assert saved.result_zip_path is None
        assert [event.event_type for event in events] == ["running", "failed"]
        assert events[0].message == "任务开始执行"
        assert events[0].payload_json == {
            "job_code": "JOB-101",
            "out_dir": str(tmp_path / "runtime" / "results" / "JOB-101"),
        }
        assert events[1].message == "任务执行失败"
        assert events[1].payload_json == {"error": "gpu unavailable"}


def test_task_runner_marks_failed_when_model_is_missing(monkeypatch, tmp_path: Path) -> None:
    run_job_inference = MagicMock()
    package_job_output = MagicMock()
    monkeypatch.setattr("backend.services.inference_adapter.run_job_inference", run_job_inference)
    monkeypatch.setattr("backend.services.inference_adapter.package_job_output", package_job_output)

    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    runtime_paths = RuntimePaths(tmp_path / "runtime")
    job_id = None

    with session_scope(engine) as session:
        job_repo = JobRepository(session)
        job = job_repo.create_job(
            job_code="JOB-102",
            access_token_hash="hash",
            mode="person_filter",
            model_id=None,
            payload_json=None,
        )
        job_repo.mark_uploaded(job.id, input_path=str(images_dir))
        job_id = job.id

    with session_scope(engine) as session:
        runner = TaskRunner(
            job_repo=JobRepository(session),
            model_repo=ModelRepository(session),
            config_repo=MagicMock(),
            gpu_gate=_DummyGpuGate(),
            runtime_paths=runtime_paths,
        )
        runner.run(job_id=job_id)

    with session_scope(engine) as session:
        saved = JobRepository(session).get(job_id)
        events = session.query(JobEventRecord).filter_by(job_id=job_id).order_by(JobEventRecord.id).all()
        assert saved.status == "failed"
        assert saved.error_message == "job model is missing"
        assert [event.event_type for event in events] == ["running", "failed"]
        assert events[1].payload_json == {"error": "job model is missing"}

    run_job_inference.assert_not_called()
    package_job_output.assert_not_called()


def test_progress_event_writer_does_not_mark_counting_as_written() -> None:
    record_event = MagicMock()
    writer = ProgressEventWriter(job_id=7, record_event=record_event, throttle_seconds=0)

    writer(SimpleNamespace(stage="counting", processed=5, total=5))

    record_event.assert_called_once()
    payload = record_event.call_args.args[1]["payload_json"]
    assert payload == {
        "stage": "counting",
        "processed": 5,
        "total": 5,
        "progress": 100,
    }


def test_task_runner_commits_after_recording_events(monkeypatch, tmp_path: Path) -> None:
    summary = {"out_dir": str(tmp_path / "results"), "total": 1, "written": 1}
    monkeypatch.setattr("backend.services.inference_adapter.run_job_inference", MagicMock(return_value=summary))
    monkeypatch.setattr("backend.services.inference_adapter.package_job_output", MagicMock(return_value=str(tmp_path / "results.zip")))

    job_repo = MagicMock()
    job_repo.get.return_value = SimpleNamespace(
        id=1,
        job_code="JOB-004",
        model_id=10,
        input_path=str(tmp_path / "images"),
        payload_json=None,
    )
    model_repo = MagicMock()
    model_repo.get.return_value = SimpleNamespace(onnx_path=str(tmp_path / "model.onnx"))
    commit_progress = MagicMock()

    runner = TaskRunner(
        job_repo=job_repo,
        model_repo=model_repo,
        config_repo=MagicMock(),
        gpu_gate=_DummyGpuGate(),
        runtime_paths=RuntimePaths(tmp_path / "runtime"),
        commit_progress=commit_progress,
    )
    runner.run(job_id=1)

    assert commit_progress.call_count == 2


def test_task_runner_persists_summary_json(monkeypatch, tmp_path: Path) -> None:
    summary = {
        "out_dir": str(tmp_path / "results"),
        "total": 5,
        "written": 5,
        "by_label": {"person": 4, "no_person": 1},
        "elapsed_sec": 1.23,
        "inference_sec": 0.8,
        "preprocess_sec": 0.2,
        "postprocess_sec": 0.1,
        "hardlink_sec": 0.05,
        "draw_sec": 0.0,
        "drawn": 0,
        "txt_written": 0,
        "hardlinked": 5,
        "copied": 0,
        "failed": 0,
        "used_batch": 16,
        "used_imgsz": (640, 640),
        "cuda_enabled": False,
        "providers": ["CPUExecutionProvider"],
    }
    monkeypatch.setattr("backend.services.inference_adapter.run_job_inference", MagicMock(return_value=summary))
    monkeypatch.setattr("backend.services.inference_adapter.package_job_output", MagicMock(return_value=str(tmp_path / "results.zip")))

    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    runtime_paths = RuntimePaths(tmp_path / "runtime")

    with session_scope(engine) as session:
        model = ModelRecord(onnx_path=str(tmp_path / "model.onnx"))
        session.add(model)
        session.flush()
        job = JobRepository(session).create_job(
            job_code="JOB-SUM",
            access_token_hash="hash",
            mode="person_filter",
            model_id=model.id,
            payload_json={"recursive": False, "batch": 4},
        )
        JobRepository(session).mark_uploaded(job.id, input_path=str(images_dir))
        job_id = job.id

    with session_scope(engine) as session:
        runner = TaskRunner(
            job_repo=JobRepository(session),
            model_repo=ModelRepository(session),
            config_repo=MagicMock(),
            gpu_gate=_DummyGpuGate(),
            runtime_paths=runtime_paths,
        )
        runner.run(job_id=job_id)

    with session_scope(engine) as session:
        saved = JobRepository(session).get(job_id)
        assert saved.status == "completed"
        assert saved.summary_json is not None
        assert saved.summary_json["by_label"] == {"person": 4, "no_person": 1}
        assert saved.summary_json["used_imgsz"] == [640, 640]
        assert saved.summary_json["providers"] == ["CPUExecutionProvider"]
        assert saved.summary_json["cuda_enabled"] is False
        assert "out_dir" not in saved.summary_json


class _DummyGpuGate:
    def acquire(self):
        return self

    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False
