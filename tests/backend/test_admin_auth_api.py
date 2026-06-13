from __future__ import annotations

from backend.api.deps import require_admin


def test_require_admin_allows_internal_single_machine_access() -> None:
    claims = require_admin()

    assert claims == {"role": "admin", "auth_method": "internal"}
