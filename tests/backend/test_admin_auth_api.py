from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from backend.core.config import settings
from backend.main import app

from backend.api.deps import require_admin
from backend.api.routes.admin_auth import LoginRequest, admin_login
from backend.core.admin_auth import get_admin_token_service


def _set_admin_secret(monkeypatch: pytest.MonkeyPatch, secret: str = "dev-secret") -> None:
    get_admin_token_service.cache_clear()
    monkeypatch.setattr(settings, "admin_secret", secret)
    monkeypatch.setattr(settings, "admin_token_secret", None)
    monkeypatch.setattr(settings, "admin_token_ttl_seconds", 3600)


def test_admin_login_returns_token_for_valid_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_admin_secret(monkeypatch)
    token_service = get_admin_token_service()

    response = admin_login(LoginRequest(secret="dev-secret"), token_service=token_service)

    assert response.token
    claims = require_admin(
        credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials=response.token),
        token_service=token_service,
    )
    assert claims["role"] == "admin"


def test_admin_login_rejects_invalid_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_admin_secret(monkeypatch)

    with pytest.raises(HTTPException) as error:
        admin_login(LoginRequest(secret="bad-secret"), token_service=get_admin_token_service())

    assert error.value.status_code == 401


def test_require_admin_rejects_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_admin_secret(monkeypatch)

    with pytest.raises(HTTPException) as error:
        require_admin(
            credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad-token"),
            token_service=get_admin_token_service(),
        )

    assert error.value.status_code == 401


def test_openapi_contains_admin_login_route() -> None:
    schema = app.openapi()

    assert "/api/admin/login" in schema["paths"]
    assert "post" in schema["paths"]["/api/admin/login"]
