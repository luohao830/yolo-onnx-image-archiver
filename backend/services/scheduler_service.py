from __future__ import annotations

from functools import lru_cache

from sqlalchemy.engine import Engine

from backend.core.config import settings
from backend.core.db import session_scope
from backend.repositories.jobs import JobRepository
from backend.services.config_service import ConfigService
from backend.services.event_bus import EventBus, get_event_bus
from backend.services.job_service import get_job_service
from backend.services.runtime_paths import RuntimePaths
from backend.workers.gpu_gate import GpuGate
from backend.workers.scheduler import Scheduler
from backend.workers.task_runner import TaskRunner


class DatabaseProgressRecorder:
    """在短事务中写入进度事件并发布 SSE。"""

    def __init__(self, engine: Engine, event_bus: EventBus | None) -> None:
        self._engine = engine
        self._event_bus = event_bus

    def __call__(self, job_id: int, event: dict) -> None:
        with session_scope(self._engine) as session:
            record = JobRepository(session).record_event(job_id, **event)
            if self._event_bus is not None:
                payload = {
                    "id": getattr(record, "id", None),
                    "job_id": job_id,
                    "event_type": event["event_type"],
                    "message": event["message"],
                    "payload_json": event.get("payload_json") or {},
                }
                try:
                    self._event_bus.publish(f"job:{job_id}", payload)
                except Exception:  # noqa: BLE001
                    pass


class DatabaseTaskRunner:
    """三阶段事务边界：mark_running → 推理（无 DB session）→ 写终态。"""

    def __init__(
        self,
        *,
        engine: Engine,
        gpu_gate: GpuGate,
        runtime_paths: RuntimePaths,
    ) -> None:
        self.engine = engine
        self.gpu_gate = gpu_gate
        self.runtime_paths = runtime_paths

    def run(self, job_id: int) -> None:
        event_bus = get_event_bus()
        progress_recorder = DatabaseProgressRecorder(self.engine, event_bus)

        runner = TaskRunner(
            engine=self.engine,
            event_bus=event_bus,
            progress_recorder=progress_recorder,
            gpu_gate=self.gpu_gate,
            runtime_paths=self.runtime_paths,
        )
        runner.run(job_id)


@lru_cache(maxsize=1)
def get_job_scheduler() -> Scheduler:
    job_service = get_job_service()
    configs = ConfigService(job_service.engine).list_configs()
    runtime_paths = RuntimePaths(settings.resolve_runtime_root())
    gpu_gate = GpuGate(configs["gpu_slots"])
    scheduler = Scheduler(
        runner_factory=lambda: DatabaseTaskRunner(
            engine=job_service.engine,
            gpu_gate=gpu_gate,
            runtime_paths=runtime_paths,
        ),
        slots=configs["task_slots"],
    )
    scheduler.start()
    return scheduler
