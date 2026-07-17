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
    worker_index: int = -1
    worker_process: Any = None
    created_at: float = field(default_factory=time.time)


@dataclass
class _WorkerSlot:
    request_queue: "mp.Queue[Dict[str, Any]]"
    process: Any
    restart_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


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

    @staticmethod
    def _process_alive(process: Any) -> bool:
        try:
            return bool(process.is_alive())
        except Exception:  # noqa: BLE001
            return False

    def _restart_slot_locked(
        self,
        idx: int,
        expected_process: Any = None,
        *,
        force: bool = False,
    ) -> None:
        with self._lock:
            if self._shutdown:
                return
        slot = self._slots[idx]
        if expected_process is not None and slot.process is not expected_process:
            return
        if not force and self._process_alive(slot.process):
            return

        old_process = slot.process
        old_queue = slot.request_queue
        logger.warning("检测到推理 worker(%d) 已退出，正在重启", idx)
        if force and self._process_alive(old_process):
            try:
                old_process.terminate()
            except Exception:  # noqa: BLE001
                pass
        # 回收旧进程，避免僵尸进程累积
        try:
            old_process.join(timeout=1.0)
        except Exception:  # noqa: BLE001
            pass
        gpu_index = idx if self._visible_gpu_count() >= 1 else None
        new_queue: "mp.Queue[Dict[str, Any]]" = self._ctx.Queue()
        proc = create_worker_process(new_queue, self._event_queue, gpu_index=gpu_index)
        proc.start()
        slot.request_queue = new_queue
        slot.process = proc
        try:
            old_queue.close()
        except Exception:  # noqa: BLE001
            pass

    def _restart_slot(self, idx: int, expected_process: Any = None) -> None:
        slot = self._slots[idx]
        with slot.restart_lock:
            self._restart_slot_locked(idx, expected_process=expected_process)

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
        # 锁内只做任务编号与 worker 选择，具体队列操作由 slot 锁保护。
        with self._lock:
            job_id = uuid.uuid4().hex
            idx = self._next_slot % len(self._slots)
            self._next_slot += 1

        slot = self._slots[idx]
        with slot.restart_lock:
            with self._lock:
                if self._shutdown:
                    raise RuntimeError("推理任务管理器已关闭")
            expected_process = slot.process
            if not self._process_alive(expected_process):
                self._restart_slot_locked(idx, expected_process=expected_process)
                slot = self._slots[idx]

            with self._lock:
                self._jobs[job_id] = JobState(
                    job_id=job_id,
                    worker_index=idx,
                    worker_process=slot.process,
                )
            try:
                slot.request_queue.put(
                    {"command": "infer", "job_id": job_id, "payload": payload}
                )
            except Exception as exc:  # noqa: BLE001
                message = "推理任务提交失败"
                with self._lock:
                    job = self._jobs.get(job_id)
                    if job is not None:
                        job.error = message
                        job.done = True
                        job.events.append(
                            {
                                "job_id": job_id,
                                "type": "error",
                                "data": {"message": message},
                            }
                        )
                self._restart_slot_locked(
                    idx,
                    expected_process=slot.process,
                    force=True,
                )
                raise RuntimeError(message) from exc
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
        restart_idx: Optional[int] = None
        restart_process: Any = None
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False

            if not job.done and 0 <= job.worker_index < len(self._slots):
                slot = self._slots[job.worker_index]
                process_changed = (
                    job.worker_process is not None and slot.process is not job.worker_process
                )
                if process_changed or not self._process_alive(job.worker_process):
                    message = "推理 worker 异常退出，任务未返回结果"
                    job.error = message
                    job.done = True
                    job.events.append(
                        {
                            "job_id": job_id,
                            "type": "error",
                            "data": {"message": message},
                        }
                    )
                    if not process_changed:
                        restart_idx = job.worker_index
                        restart_process = job.worker_process

            done = bool(job.done and not job.events)

        if restart_idx is not None:
            self._restart_slot(restart_idx, expected_process=restart_process)
        return done

    def drop(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)

    def worker_count(self) -> int:
        return len(self._slots)

    def shutdown(self) -> None:
        with self._lock:
            self._shutdown = True
        for slot in self._slots:
            with slot.restart_lock:
                try:
                    slot.request_queue.put({"command": "shutdown"})
                except Exception:  # noqa: BLE001
                    pass
                if self._process_alive(slot.process):
                    slot.process.join(timeout=2.0)


_JOB_MANAGER: Optional[InferenceJobManager] = None
_JOB_MANAGER_LOCK = threading.Lock()


def get_job_manager() -> InferenceJobManager:
    global _JOB_MANAGER  # noqa: PLW0603
    with _JOB_MANAGER_LOCK:
        if _JOB_MANAGER is None:
            _JOB_MANAGER = InferenceJobManager()
        return _JOB_MANAGER
