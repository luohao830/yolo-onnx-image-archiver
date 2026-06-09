from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """应用基础配置。"""

    model_config = SettingsConfigDict(env_prefix="YOLO_PLATFORM_", extra="ignore")
    runtime_root: Path = PROJECT_ROOT / "runtime"
    database_url: str | None = None

    def resolve_runtime_root(self) -> Path:
        if self.runtime_root.is_absolute():
            return self.runtime_root
        return (PROJECT_ROOT / self.runtime_root).resolve()

    def resolve_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.resolve_runtime_root() / 'app.db').resolve()}"


settings = Settings()
