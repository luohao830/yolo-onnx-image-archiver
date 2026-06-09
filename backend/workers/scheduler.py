from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from typing import Protocol


class Runner(Protocol):
    def run(self, job_id: int) -> None:
        ...


class Scheduler:
    def __init__(self, runner_factory: Callable[[], Runner], slots: int) -> None:
        if slots < 1:
            raise ValueError("scheduler slots must be positive")
        self.runner_factory = runner_factory
        self.slots = slots
        self.queue: queue.Queue[int] = queue.Queue()
        self._threads: list[threading.Thread] = []
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._pending: set[int] = set()
        self._cancelled: set[int] = set()

    def start(self) -> None:
        if self._threads:
            return
        for _ in range(self.slots):
            thread = threading.Thread(target=self._loop, daemon=True)
            thread.start()
            self._threads.append(thread)

    def submit(self, job_id: int) -> None:
        with self._lock:
            self._pending.add(job_id)
            self._cancelled.discard(job_id)
        self.queue.put(job_id)

    def cancel_pending(self, job_id: int) -> bool:
        with self._lock:
            if job_id not in self._pending:
                return False
            self._pending.remove(job_id)
            self._cancelled.add(job_id)
            return True

    def stop(self) -> None:
        self._stop_event.set()
        for thread in self._threads:
            thread.join()

    def _loop(self) -> None:
        runner = self.runner_factory()
        while not self._stop_event.is_set():
            try:
                job_id = self.queue.get(timeout=0.05)
            except queue.Empty:
                continue

            try:
                if not self._claim(job_id):
                    continue
                runner.run(job_id)
            finally:
                self.queue.task_done()

    def _claim(self, job_id: int) -> bool:
        with self._lock:
            if job_id in self._cancelled:
                self._cancelled.remove(job_id)
                return False
            if job_id not in self._pending:
                return False
            self._pending.remove(job_id)
            return True
