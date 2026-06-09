from __future__ import annotations

from pathlib import Path

import yaml


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_backend_service_reserves_nvidia_gpu_devices() -> None:
    compose = yaml.safe_load((ROOT_DIR / "docker-compose.yml").read_text(encoding="utf-8"))

    backend = compose["services"]["backend"]
    devices = (
        backend["deploy"]["resources"]["reservations"]["devices"]
    )

    assert devices == [
        {
            "driver": "nvidia",
            "count": "all",
            "capabilities": ["gpu"],
        }
    ]
