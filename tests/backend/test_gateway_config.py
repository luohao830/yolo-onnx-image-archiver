from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIN_UPLOAD_LIMIT_BYTES = 1024 * 1024 * 1024


def test_gateway_upload_body_limit_matches_backend_archive_limit() -> None:
    config = (PROJECT_ROOT / "gateway" / "nginx.conf").read_text(encoding="utf-8")
    match = re.search(r"client_max_body_size\s+(\d+)([kKmMgG]?)\s*;", config)

    assert match is not None
    assert _to_bytes(int(match.group(1)), match.group(2)) >= MIN_UPLOAD_LIMIT_BYTES


def _to_bytes(value: int, unit: str) -> int:
    multipliers = {
        "": 1,
        "k": 1024,
        "m": 1024 * 1024,
        "g": 1024 * 1024 * 1024,
    }
    return value * multipliers[unit.lower()]
