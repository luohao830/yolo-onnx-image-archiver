from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用基础配置。"""

    model_config = SettingsConfigDict(env_prefix="YOLO_PLATFORM_", extra="ignore")
    runtime_root: Path = Path("runtime")
    database_url: str | None = None

    def resolve_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.runtime_root / 'app.db').resolve()}"


settings = Settings()
