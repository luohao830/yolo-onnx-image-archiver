from __future__ import annotations

import multiprocessing as mp
import queue
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional

from webui.infer_worker import create_worker_process
from webui.utils import get_logger


logger = get_logger(__name__)


@dataclass
class JobState:
    job_id: str
    events: Deque[Dict[str, Any]] = field(default_factory=deque)
    done: bool = False
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)


class InferenceJobManager:
    def __init__(self) -> None:
        self._ctx = mp.get_context("spawn")
        self._request_queue: "mp.Queue[Dict[str, Any]]" = self._ctx.Queue()
        self._event_queue: "mp.Queue[Dict[str, Any]]" = self._ctx.Queue()
        self._worker = create_worker_process(self._request_queue, self._event_queue)
        self._lock = threading.Lock()
        self._jobs: Dict[str, JobState] = {}
        self._shutdown = False
        self._worker.start()
        self._collector = threading.Thread(target=self._collect_events, daemon=True, name="infer-job-events")
        self._collector.start()

    def _ensure_worker_alive(self) -> None:
        if self._worker.is_alive():
            return
        logger.warning("检测到推理 worker 已退出，正在重启")
        self._worker = create_worker_process(self._request_queue, self._event_queue)
        self._worker.start()

    def _collect_events(self) -> None:
        while not self._shutdown:
            try:
                event = self._event_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if not isinstance(event, dict):
                continue

            job_id = str(event.get("job_id", ""))
            if not job_id:
                continue

            with self._lock:
                job = self._jobs.get(job_id)
                if job is None:
                    continue
                job.events.append(event)
                event_type = event.get("type")
                if event_type == "result":
                    job.done = True
                elif event_type == "error":
                    job.done = True
                    job.error = str((event.get("data") or {}).get("message", "推理失败"))

    def submit(self, payload: Dict[str, Any]) -> str:
        with self._lock:
            self._ensure_worker_alive()
            job_id = uuid.uuid4().hex
            self._jobs[job_id] = JobState(job_id=job_id)
        self._request_queue.put({"command": "infer", "job_id": job_id, "payload": payload})
        return job_id

    def poll_event(self, job_id: str, timeout_sec: float = 0.2) -> Optional[Dict[str, Any]]:
        deadline = time.time() + max(timeout_sec, 0.0)
        while True:
            with self._lock:
                job = self._jobs.get(job_id)
                if job is None:
                    return None
                if job.events:
                    return job.events.popleft()
                if job.done:
                    return None
            if time.time() >= deadline:
                return None
            time.sleep(0.05)

    def job_done(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            return bool(job and job.done and not job.events)

    def drop(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)

    def shutdown(self) -> None:
        self._shutdown = True
        try:
            self._request_queue.put({"command": "shutdown"})
        except Exception:  # noqa: BLE001
            pass
        if self._worker.is_alive():
            self._worker.join(timeout=2.0)


_JOB_MANAGER: Optional[InferenceJobManager] = None
_JOB_MANAGER_LOCK = threading.Lock()


def get_job_manager() -> InferenceJobManager:
    global _JOB_MANAGER  # noqa: PLW0603
    with _JOB_MANAGER_LOCK:
        if _JOB_MANAGER is None:
            _JOB_MANAGER = InferenceJobManager()
        return _JOB_MANAGER
