from __future__ import annotations

from functools import lru_cache

from sqlalchemy.engine import Engine

from backend.core.db import create_all, session_scope
from backend.repositories.system_configs import SystemConfigRepository
from backend.services.job_service import get_job_service


DEFAULT_SYSTEM_CONFIGS: dict[str, int] = {
    "task_slots": 3,
    "gpu_slots": 1,
}


class ConfigService:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def list_configs(self) -> dict[str, int]:
        with session_scope(self.engine) as session:
            repo = SystemConfigRepository(session)
            configs = dict(DEFAULT_SYSTEM_CONFIGS)
            for item in repo.list_all():
                configs[item.key] = int(item.value)
            return configs

    def update_concurrency(self, task_slots: int, gpu_slots: int) -> dict[str, int]:
        with session_scope(self.engine) as session:
            repo = SystemConfigRepository(session)
            repo.set("task_slots", str(task_slots))
            repo.set("gpu_slots", str(gpu_slots))
        return self.list_configs()


@lru_cache(maxsize=1)
def get_config_service() -> ConfigService:
    job_service = get_job_service()
    create_all(job_service.engine)
    return ConfigService(job_service.engine)
