from __future__ import annotations

from typing import Any


def require_admin() -> dict[str, Any]:
    return {"role": "admin", "auth_method": "internal"}
