from __future__ import annotations

from functools import lru_cache

from sqlalchemy.engine import Engine

from backend.core.config import settings
from backend.core.db import session_scope
from backend.repositories.jobs import JobRepository
from backend.repositories.models import ModelRepository
from backend.services.config_service import ConfigService
from backend.services.event_bus import get_event_bus
from backend.services.job_service import get_job_service
from backend.services.runtime_paths import RuntimePaths
from backend.workers.gpu_gate import GpuGate
from backend.workers.scheduler import Scheduler
from backend.workers.task_runner import TaskRunner


class DatabaseTaskRunner:
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
        with session_scope(self.engine) as session:
            runner = TaskRunner(
                job_repo=JobRepository(session),
                model_repo=ModelRepository(session),
                config_repo=None,
                gpu_gate=self.gpu_gate,
                runtime_paths=self.runtime_paths,
                commit_progress=session.commit,
                event_bus=get_event_bus(),
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
