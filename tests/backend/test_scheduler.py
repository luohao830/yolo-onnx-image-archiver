import threading
import time

from backend.workers.gpu_gate import GpuGate
from backend.workers.scheduler import Scheduler


def test_gpu_gate_only_allows_one_holder() -> None:
    gate = GpuGate(limit=1)
    timeline: list[str] = []

    def worker(name: str) -> None:
        with gate.acquire():
            timeline.append(f"{name}-start")
            time.sleep(0.05)
            timeline.append(f"{name}-end")

    t1 = threading.Thread(target=worker, args=("a",))
    t2 = threading.Thread(target=worker, args=("b",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert timeline in (
        ["a-start", "a-end", "b-start", "b-end"],
        ["b-start", "b-end", "a-start", "a-end"],
    )


def test_scheduler_respects_worker_slots() -> None:
    runner = _BlockingRunner(expected_jobs=3)
    scheduler = Scheduler(runner_factory=lambda: runner, slots=2)

    scheduler.start()
    scheduler.submit(1)
    scheduler.submit(2)
    scheduler.submit(3)

    assert runner.two_started.wait(timeout=1)
    time.sleep(0.05)
    assert runner.max_running == 2
    assert len(runner.started_jobs) == 2

    runner.release.set()
    assert runner.all_done.wait(timeout=1)
    scheduler.stop()

    assert sorted(runner.finished_jobs) == [1, 2, 3]


def test_scheduler_stop_exits_when_queue_is_empty() -> None:
    scheduler = Scheduler(runner_factory=_IdleRunner, slots=1)

    scheduler.start()
    time.sleep(0.05)
    scheduler.stop()

    assert len(scheduler._threads) == 1
    assert not any(thread.is_alive() for thread in scheduler._threads)


def test_scheduler_can_cancel_pending_job() -> None:
    runner = _SingleBlockingRunner()
    scheduler = Scheduler(runner_factory=lambda: runner, slots=1)

    scheduler.start()
    scheduler.submit(10)
    scheduler.submit(20)

    assert runner.started.wait(timeout=1)
    assert scheduler.cancel_pending(20) is True
    assert scheduler.cancel_pending(20) is False

    runner.release.set()
    assert runner.finished.wait(timeout=1)
    time.sleep(0.1)
    scheduler.stop()

    assert runner.executed_jobs == [10]


class _BlockingRunner:
    def __init__(self, *, expected_jobs: int) -> None:
        self.expected_jobs = expected_jobs
        self.started_jobs: list[int] = []
        self.finished_jobs: list[int] = []
        self.max_running = 0
        self._running = 0
        self._lock = threading.Lock()
        self.two_started = threading.Event()
        self.all_done = threading.Event()
        self.release = threading.Event()

    def run(self, job_id: int) -> None:
        with self._lock:
            self.started_jobs.append(job_id)
            self._running += 1
            self.max_running = max(self.max_running, self._running)
            if self._running == 2:
                self.two_started.set()

        self.release.wait(timeout=1)

        with self._lock:
            self.finished_jobs.append(job_id)
            self._running -= 1
            if len(self.finished_jobs) == self.expected_jobs:
                self.all_done.set()


class _SingleBlockingRunner:
    def __init__(self) -> None:
        self.executed_jobs: list[int] = []
        self.started = threading.Event()
        self.finished = threading.Event()
        self.release = threading.Event()

    def run(self, job_id: int) -> None:
        self.executed_jobs.append(job_id)
        self.started.set()
        self.release.wait(timeout=1)
        self.finished.set()


class _IdleRunner:
    def run(self, job_id: int) -> None:
        raise AssertionError(f"unexpected job execution: {job_id}")
