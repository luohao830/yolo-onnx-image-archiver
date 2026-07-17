"""推理任务管理器在 worker 异常退出时的状态清理测试。"""
from __future__ import annotations

import threading
from pathlib import Path

import webui.processing as processing
from webui.job_manager import InferenceJobManager, JobState, _WorkerSlot


class _FakeProcess:
    def __init__(self, alive: bool) -> None:
        self.alive = alive
        self.joined = False

    def is_alive(self) -> bool:
        return self.alive

    def join(self, timeout: float) -> None:
        self.joined = True


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
