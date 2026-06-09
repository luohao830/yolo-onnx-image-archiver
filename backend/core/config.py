from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用基础配置。"""

    model_config = SettingsConfigDict(env_prefix="YOLO_PLATFORM_", extra="ignore")


settings = Settings()
