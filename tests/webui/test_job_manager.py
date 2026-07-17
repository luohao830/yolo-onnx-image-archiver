"""推理任务管理器在 worker 异常退出时的状态清理测试。"""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

import webui.job_manager as job_manager_module
import webui.processing as processing
from webui.job_manager import InferenceJobManager, JobState, _WorkerSlot


class _FakeQueue:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FailingQueue(_FakeQueue):
    def put(self, _item) -> None:
        raise OSError("queue closed")


class _FakeProcess:
    def __init__(self, alive: bool) -> None:
        self.alive = alive
        self.joined = False

    def is_alive(self) -> bool:
        return self.alive

    def join(self, timeout: float) -> None:
        self.joined = True

    def start(self) -> None:
        self.alive = True


class _FakeTimer:
    instances = []

    def __init__(self, _delay: float, function) -> None:
        self.function = function
        self.cancelled = False
        self.instances.append(self)

    def start(self) -> None:
        return

    def cancel(self) -> None:
        self.cancelled = True

    def run(self) -> None:
        self.function()


def test_job_done_marks_dead_worker_failed_and_restarts(monkeypatch) -> None:
    manager = InferenceJobManager.__new__(InferenceJobManager)
    process = _FakeProcess(alive=False)
    manager._lock = threading.Lock()
    manager._jobs = {
        "job-1": JobState(
            job_id="job-1",
            worker_index=0,
            worker_process=process,
        )
    }
    manager._slots = [_WorkerSlot(request_queue=object(), process=process)]

    restarted = []
    monkeypatch.setattr(
        manager,
        "_restart_slot",
        lambda idx, expected_process=None: restarted.append((idx, expected_process)),
    )

    assert manager.job_done("job-1") is False
    event = manager.poll_event("job-1", timeout_sec=0.0)
    assert event is not None
    assert event["type"] == "error"
    assert "worker 异常退出" in event["data"]["message"]
    assert restarted == [(0, process)]
    assert manager.job_done("job-1") is True


def test_restart_slot_isolates_old_request_queue(monkeypatch) -> None:
    manager = InferenceJobManager.__new__(InferenceJobManager)
    manager._lock = threading.Lock()
    manager._shutdown = False
    old_process = _FakeProcess(alive=False)
    old_queue = _FakeQueue()
    manager._slots = [_WorkerSlot(request_queue=old_queue, process=old_process)]
    manager._event_queue = object()
    manager._ctx = type("_Context", (), {"Queue": staticmethod(_FakeQueue)})()
    monkeypatch.setattr(manager, "_visible_gpu_count", lambda: 0)

    created = []

    def _create_worker(request_queue, _event_queue, gpu_index=None):
        process = _FakeProcess(alive=False)
        created.append((request_queue, gpu_index, process))
        return process

    monkeypatch.setattr(job_manager_module, "create_worker_process", _create_worker)

    manager._restart_slot(0, expected_process=old_process)

    slot = manager._slots[0]
    assert old_queue.closed is True
    assert slot.request_queue is created[0][0]
    assert slot.request_queue is not old_queue
    assert slot.process is created[0][2]


def test_submit_failure_marks_job_done_and_restarts_worker(monkeypatch) -> None:
    manager = InferenceJobManager.__new__(InferenceJobManager)
    old_process = _FakeProcess(alive=True)
    old_queue = _FailingQueue()
    manager._lock = threading.Lock()
    manager._shutdown = False
    manager._jobs = {}
    manager._next_slot = 0
    manager._slots = [_WorkerSlot(request_queue=old_queue, process=old_process)]
    manager._event_queue = object()
    manager._ctx = type("_Context", (), {"Queue": staticmethod(_FakeQueue)})()

    created = []

    def _create_worker(request_queue, _event_queue, gpu_index=None):
        process = _FakeProcess(alive=False)
        created.append((request_queue, gpu_index, process))
        return process

    monkeypatch.setattr(job_manager_module, "create_worker_process", _create_worker)

    with pytest.raises(RuntimeError, match="推理任务提交失败"):
        manager.submit({})

    assert len(manager._jobs) == 1
    job = next(iter(manager._jobs.values()))
    assert job.done is True
    assert job.error == "推理任务提交失败"
    assert job.events[0]["type"] == "error"
    assert old_queue.closed is True
    assert created


def test_old_delete_timer_cannot_remove_new_file(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "run.zip"
    path.write_text("old", encoding="utf-8")
    timers = []
    _FakeTimer.instances = timers
    monkeypatch.setattr(processing.threading, "Timer", _FakeTimer)
    monkeypatch.setattr(processing, "_DELETE_TIMERS", {})

    processing._schedule_delete(path, delay_sec=600)
    path.write_text("new", encoding="utf-8")
    processing._schedule_delete(path, delay_sec=600)

    timers[0].run()
    assert path.read_text(encoding="utf-8") == "new"
    timers[1].run()
    assert not path.exists()
