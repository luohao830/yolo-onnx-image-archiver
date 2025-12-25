from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    images_dir: Path = Path("/data/images")
    models_dir: Path = Path("/data/models")
    data_dir: Path = Path("/data/state")
    exports_dir: Path = Path("/data/exports")
    db_path: Path = Path("/data/state/app.db")
    default_imgsz: int = 640


DEFAULT_SETTINGS = Settings()

