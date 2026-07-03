from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """应用基础配置。"""

    model_config = SettingsConfigDict(env_prefix="YOLO_PLATFORM_", extra="ignore")
    runtime_root: Path = PROJECT_ROOT / "runtime"
    database_url: str | None = None
    admin_secret: str = "dev-secret"
    admin_token_secret: str | None = None
    admin_token_ttl_seconds: int = 3600
    sse_token_ttl_seconds: int = 300
    sse_token_secret: str | None = None
    admin_ip_whitelist: str = ""
    admin_trusted_proxy_cidrs: str = "127.0.0.1/32,::1/128"

    def resolve_runtime_root(self) -> Path:
        """解析并返回运行时根目录的绝对路径。

        当配置值为绝对路径时直接返回；否则以项目根目录为基准拼接后再解析为绝对路径。
        """
        if self.runtime_root.is_absolute():
            return self.runtime_root
        return (PROJECT_ROOT / self.runtime_root).resolve()

    def resolve_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.resolve_runtime_root() / 'app.db').resolve()}"

    def resolve_admin_token_secret(self) -> str:
        return self.admin_token_secret or self.admin_secret

    def resolve_sse_token_secret(self) -> str:
        return self.sse_token_secret or self.resolve_admin_token_secret()


settings = Settings()
