from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.core.db import build_engine, create_all, session_scope
from backend.db.models import JobEventRecord, ModelRecord
from backend.repositories.jobs import JobRepository
from backend.repositories.models import ModelRepository
from backend.services.runtime_paths import RuntimePaths
from backend.workers.progress_writer import ProgressEventWriter
from backend.workers.task_runner import TaskRunResult, TaskRunner


class _DummyGpuGate:
    def acquire(self):
        return self

    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyProgressRecorder:
    """记录所有写入的事件，不做真实 DB 操作。"""

    def __init__(self) -> None:
        self.events: list[tuple[int, dict]] = []

    def __call__(self, job_id: int, event: dict) -> None:
        self.events.append((job_id, event))


def _make_runner(*, engine, gpu_gate=None, progress_recorder=None, runtime_paths=None, event_bus=None, tmp_path=None):
    """构造一个新签名 TaskRunner 的便捷工厂。"""
    return TaskRunner(
        engine=engine,
        event_bus=event_bus or MagicMock(),
        progress_recorder=progress_recorder or _DummyProgressRecorder(),
        gpu_gate=gpu_gate or _DummyGpuGate(),
        runtime_paths=runtime_paths or RuntimePaths(tmp_path / "runtime") if tmp_path else RuntimePaths(Path("/tmp/runtime")),
    )


# ── Mock 引擎 + 真实 journey 测试 ──


def test_task_runner_persists_completion_with_real_repositories(monkeypatch, tmp_path: Path) -> None:
    summary = {"out_dir": str(tmp_path / "results"), "total": 4, "written": 4}
    monkeypatch.setattr("backend.workers.task_runner.inference_adapter.run_job_inference", MagicMock(return_value=summary))
    monkeypatch.setattr("backend.workers.task_runner.inference_adapter.package_job_output", MagicMock(return_value=str(tmp_path / "results.zip")))
    monkeypatch.setattr("backend.workers.task_runner.inference_adapter.build_job_summary_json", lambda s: {"total": s["total"], "written": s["written"]})

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

    runner = _make_runner(engine=engine, runtime_paths=runtime_paths, tmp_path=tmp_path)
    runner.run(job_id=job_id)

    with session_scope(engine) as session:
        saved = JobRepository(session).get(job_id)
        events = session.query(JobEventRecord).filter_by(job_id=job_id).order_by(JobEventRecord.id).all()
        assert saved.status == "completed"
        assert saved.input_path == str(images_dir)
        assert saved.result_dir == str(tmp_path / "results")
        assert saved.result_zip_path == str(tmp_path / "results.zip")
        assert saved.error_message is None
        assert [e.event_type for e in events] == ["running", "completed"]
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
    monkeypatch.setattr("backend.workers.task_runner.inference_adapter.run_job_inference", MagicMock(side_effect=RuntimeError("gpu unavailable")))
    monkeypatch.setattr("backend.workers.task_runner.inference_adapter.package_job_output", MagicMock())
    monkeypatch.setattr("backend.workers.task_runner.inference_adapter.build_job_summary_json", MagicMock())

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

    runner = _make_runner(engine=engine, runtime_paths=runtime_paths, tmp_path=tmp_path)
    runner.run(job_id=job_id)

    with session_scope(engine) as session:
        saved = JobRepository(session).get(job_id)
        events = session.query(JobEventRecord).filter_by(job_id=job_id).order_by(JobEventRecord.id).all()
        assert saved.status == "failed"
        assert saved.error_message == "gpu unavailable"
        assert saved.result_dir is None
        assert saved.result_zip_path is None
        assert [e.event_type for e in events] == ["running", "failed"]
        assert events[0].message == "任务开始执行"
        assert events[0].payload_json == {
            "job_code": "JOB-101",
            "out_dir": str(tmp_path / "runtime" / "results" / "JOB-101"),
        }
        assert events[1].message == "任务执行失败"
        assert events[1].payload_json == {"error": "gpu unavailable"}


def test_task_runner_marks_failed_when_model_is_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("backend.workers.task_runner.inference_adapter.run_job_inference", MagicMock())
    monkeypatch.setattr("backend.workers.task_runner.inference_adapter.package_job_output", MagicMock())
    monkeypatch.setattr("backend.workers.task_runner.inference_adapter.build_job_summary_json", MagicMock())

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

    runner = _make_runner(engine=engine, runtime_paths=runtime_paths, tmp_path=tmp_path)
    runner.run(job_id=job_id)

    with session_scope(engine) as session:
        saved = JobRepository(session).get(job_id)
        events = session.query(JobEventRecord).filter_by(job_id=job_id).order_by(JobEventRecord.id).all()
        assert saved.status == "failed"
        assert saved.error_message == "job model is missing"
        assert [e.event_type for e in events] == ["running", "failed"]
        assert events[1].payload_json == {"error": "job model is missing"}


def test_task_runner_persists_summary_json(monkeypatch, tmp_path: Path) -> None:
    summary = {
        "out_dir": str(tmp_path / "results"),
        "total": 5, "written": 5,
        "by_label": {"person": 4, "no_person": 1},
        "elapsed_sec": 1.23, "inference_sec": 0.8,
        "preprocess_sec": 0.2, "postprocess_sec": 0.1,
        "hardlink_sec": 0.05, "draw_sec": 0.0,
        "drawn": 0, "txt_written": 0,
        "hardlinked": 5, "copied": 0, "failed": 0,
        "used_batch": 16, "used_imgsz": (640, 640),
        "cuda_enabled": False, "providers": ["CPUExecutionProvider"],
    }
    monkeypatch.setattr("backend.workers.task_runner.inference_adapter.run_job_inference", MagicMock(return_value=summary))
    monkeypatch.setattr("backend.workers.task_runner.inference_adapter.package_job_output", MagicMock(return_value=str(tmp_path / "results.zip")))

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
            job_code="JOB-SUM", access_token_hash="hash", mode="person_filter",
            model_id=model.id, payload_json={"recursive": False, "batch": 4},
        )
        JobRepository(session).mark_uploaded(job.id, input_path=str(images_dir))
        job_id = job.id

    runner = _make_runner(engine=engine, runtime_paths=runtime_paths, tmp_path=tmp_path)
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


def test_task_runner_packages_output_from_summary_directory(monkeypatch, tmp_path: Path) -> None:
    summary = {"out_dir": str(tmp_path / "summary-results"), "total": 3, "written": 3}
    run_job_inference = MagicMock(return_value=summary)
    package_job_output = MagicMock(return_value=str(tmp_path / "summary-results.zip"))
    monkeypatch.setattr("backend.workers.task_runner.inference_adapter.run_job_inference", run_job_inference)
    monkeypatch.setattr("backend.workers.task_runner.inference_adapter.package_job_output", package_job_output)
    monkeypatch.setattr("backend.workers.task_runner.inference_adapter.build_job_summary_json", lambda s: {"total": s["total"], "written": s["written"]})

    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    runtime_paths = RuntimePaths(tmp_path / "runtime")
    model = ModelRecord(onnx_path=str(tmp_path / "model.onnx"))
    with session_scope(engine) as session:
        session.add(model)
        session.flush()
        job = JobRepository(session).create_job(
            job_code="JOB-003", access_token_hash="hash", mode="person_filter",
            model_id=model.id, payload_json={"draw_boxes": True, "save_txt": True},
        )
        JobRepository(session).mark_uploaded(job.id, input_path=str(images_dir))
        job_id = job.id

    runner = _make_runner(engine=engine, runtime_paths=runtime_paths, tmp_path=tmp_path)
    runner.run(job_id=job_id)

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


# ── ProgressEventWriter 单元测试 ──


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


# ── TaskRunResult 单元测试 ──


def test_task_run_result_defaults() -> None:
    result = TaskRunResult(success=False)
    assert result.success is False
    assert result.summary is None
    assert result.zip_path is None
    assert result.detections == []
    assert result.events == []
    assert result.error_message is None


def test_task_run_result_success_path() -> None:
    result = TaskRunResult(
        success=True,
        summary={"total": 5},
        zip_path="/tmp/z.zip",
        detections=[{"det": 1}],
    )
    result.events.append({"event_type": "running", "message": "start"})
    assert result.success is True
    assert result.summary == {"total": 5}
    assert result.zip_path == "/tmp/z.zip"
    assert len(result.detections) == 1


# ── 三阶段事务边界验证 ──


def test_task_runner_phase1_writes_running_event(monkeypatch, tmp_path: Path) -> None:
    """mark_running + running event commit 在推理前独立完成。"""
    monkeypatch.setattr(
        "backend.workers.task_runner.inference_adapter.run_job_inference",
        MagicMock(return_value={"out_dir": str(tmp_path / "results"), "total": 1, "written": 1}),
    )
    monkeypatch.setattr(
        "backend.workers.task_runner.inference_adapter.package_job_output",
        MagicMock(return_value=str(tmp_path / "results.zip")),
    )
    monkeypatch.setattr(
        "backend.workers.task_runner.inference_adapter.build_job_summary_json",
        lambda s: {"total": s.get("total", 0), "written": s.get("written", 0)},
    )

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
            job_code="JOB-PH1", access_token_hash="h", mode="person_filter",
            model_id=model.id, payload_json={"batch": 4},
        )
        JobRepository(session).mark_uploaded(job.id, input_path=str(images_dir))
        job_id = job.id

    runner = _make_runner(engine=engine, runtime_paths=runtime_paths, tmp_path=tmp_path)
    runner.run(job_id=job_id)

    with session_scope(engine) as session:
        events = session.query(JobEventRecord).filter_by(job_id=job_id).order_by(JobEventRecord.id).all()
        assert events[0].event_type == "running"
        assert events[0].message == "任务开始执行"


def test_task_runner_fast_fail_does_not_reach_inference(monkeypatch, tmp_path: Path) -> None:
    """model_id=None 在阶段 2 前置校验中被 fast-fail，不应调用推理。"""
    run_inf = MagicMock()
    monkeypatch.setattr("backend.workers.task_runner.inference_adapter.run_job_inference", run_inf)

    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    runtime_paths = RuntimePaths(tmp_path / "runtime")

    with session_scope(engine) as session:
        job = JobRepository(session).create_job(
            job_code="JOB-NOMODEL", access_token_hash="h", mode="person_filter",
            model_id=None, payload_json=None,
        )
        JobRepository(session).mark_uploaded(job.id, input_path=str(tmp_path / "images"))
        job_id = job.id

    runner = _make_runner(engine=engine, runtime_paths=runtime_paths, tmp_path=tmp_path)
    runner.run(job_id=job_id)

    run_inf.assert_not_called()

    with session_scope(engine) as session:
        saved = JobRepository(session).get(job_id)
        assert saved.status == "failed"
        assert saved.error_message == "job model is missing"
