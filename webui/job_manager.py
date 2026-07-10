from __future__ import annotations

import multiprocessing as mp
import queue
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

from webui.infer_worker import create_worker_process, detect_available_gpus
from webui.utils import get_logger


logger = get_logger(__name__)


@dataclass
class JobState:
    job_id: str
    events: Deque[Dict[str, Any]] = field(default_factory=deque)
    done: bool = False
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)


@dataclass
class _WorkerSlot:
    request_queue: "Any"
    process: Any
    alive: bool = True


class InferenceJobManager:
    """多 worker 推理任务管理器。

    启动时按可见 GPU 数量创建 N 个推理 worker 进程，每个 worker 绑定一块 GPU
    （通过 CUDA_VISIBLE_DEVICES 限定可见性），任务按 round-robin 分配到各 worker，
    实现“任务级多 GPU 分流”——不同任务在不同 GPU 上并发执行，单 GPU 环境退化为 1 个 worker。
    无 GPU 环境创建 1 个 CPU worker。
    """

    def __init__(self) -> None:
        self._ctx = mp.get_context("spawn")
        self._event_queue: "mp.Queue[Dict[str, Any]]" = self._ctx.Queue()
        self._lock = threading.Lock()
        self._jobs: Dict[str, JobState] = {}
        self._shutdown = False
        self._slots: List[_WorkerSlot] = []
        self._next_slot = 0
        self._collector = threading.Thread(target=self._collect_events, daemon=True, name="infer-job-events")
        self._build_workers()
        self._collector.start()

    def _gpu_count(self) -> int:
        try:
            n = detect_available_gpus()
        except Exception:  # noqa: BLE001
            n = 0
        # 至少 1 个 worker；0 表示无 GPU，用 1 个 CPU worker。
        return max(1, n)

    def _build_workers(self) -> None:
        n = self._gpu_count()
        has_gpu = self._visible_gpu_count() >= 1
        for idx in range(n):
            request_queue: "mp.Queue[Dict[str, Any]]" = self._ctx.Queue()
            # 有 GPU：给每个 worker 分配一个 GPU 索引；无 GPU：统一 None（CPU）。
            gpu_index = idx if has_gpu else None
            proc = create_worker_process(request_queue, self._event_queue, gpu_index=gpu_index)
            proc.start()
            self._slots.append(_WorkerSlot(request_queue=request_queue, process=proc))
        logger.info(
            "推理 worker 池已启动：worker 数 %d，GPU 可见 %d 块",
            len(self._slots),
            self._visible_gpu_count(),
        )

    def _visible_gpu_count(self) -> int:
        try:
            return detect_available_gpus()
        except Exception:  # noqa: BLE001
            return 0

    def _next_target_slot(self) -> _WorkerSlot:
        # 跳过已退出 worker，必要时重启。
        for _ in range(len(self._slots)):
            idx = self._next_slot % len(self._slots)
            self._next_slot += 1
            slot = self._slots[idx]
            if not slot.alive or not slot.process.is_alive():
                self._restart_slot(idx)
                slot = self._slots[idx]
            return slot
        slot = self._slots[0]
        return slot

    def _restart_slot(self, idx: int) -> None:
        slot = self._slots[idx]
        logger.warning("检测到推理 worker(%d) 已退出，正在重启", idx)
        gpu_index = idx if self._visible_gpu_count() >= 1 else None
        proc = create_worker_process(slot.request_queue, self._event_queue, gpu_index=gpu_index)
        proc.start()
        slot.process = proc
        slot.alive = True

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
            job_id = uuid.uuid4().hex
            self._jobs[job_id] = JobState(job_id=job_id)
            slot = self._next_target_slot()
        slot.request_queue.put({"command": "infer", "job_id": job_id, "payload": payload})
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

    def worker_count(self) -> int:
        return len(self._slots)

    def shutdown(self) -> None:
        self._shutdown = True
        for slot in self._slots:
            try:
                slot.request_queue.put({"command": "shutdown"})
            except Exception:  # noqa: BLE001
                pass
            if slot.process.is_alive():
                slot.process.join(timeout=2.0)


_JOB_MANAGER: Optional[InferenceJobManager] = None
_JOB_MANAGER_LOCK = threading.Lock()


def get_job_manager() -> InferenceJobManager:
    global _JOB_MANAGER  # noqa: PLW0603
    with _JOB_MANAGER_LOCK:
        if _JOB_MANAGER is None:
            _JOB_MANAGER = InferenceJobManager()
        return _JOB_MANAGER