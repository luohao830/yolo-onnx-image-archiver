from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

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
    monkeypatch.setattr(settings, "admin_ip_whitelist", "")


def _request_for_client(
    host: str,
    forwarded_for: str | None = None,
    real_ip: str | None = None,
) -> Request:
    headers = []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode("utf-8")))
    if real_ip is not None:
        headers.append((b"x-real-ip", real_ip.encode("utf-8")))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/admin/login",
            "headers": headers,
            "client": (host, 12345),
        }
    )


def test_admin_login_returns_token_for_valid_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_admin_secret(monkeypatch)
    token_service = get_admin_token_service()

    response = admin_login(
        LoginRequest(secret="dev-secret"),
        request=_request_for_client("192.168.1.9"),
        token_service=token_service,
    )

    assert response.token
    claims = require_admin(
        credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials=response.token),
        token_service=token_service,
        request=_request_for_client("192.168.1.9"),
    )
    assert claims["role"] == "admin"


def test_admin_login_rejects_invalid_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_admin_secret(monkeypatch)

    with pytest.raises(HTTPException) as error:
        admin_login(
            LoginRequest(secret="bad-secret"),
            request=_request_for_client("192.168.1.9"),
            token_service=get_admin_token_service(),
        )

    assert error.value.status_code == 401


def test_require_admin_rejects_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_admin_secret(monkeypatch)

    with pytest.raises(HTTPException) as error:
        require_admin(
            credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad-token"),
            token_service=get_admin_token_service(),
            request=_request_for_client("192.168.1.9"),
        )

    assert error.value.status_code == 401


def test_admin_login_allows_whitelisted_ip_without_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_admin_secret(monkeypatch)
    monkeypatch.setattr(settings, "admin_ip_whitelist", "10.0.0.7,127.0.0.1")

    response = admin_login(
        LoginRequest(secret=""),
        request=_request_for_client("127.0.0.1"),
        token_service=get_admin_token_service(),
    )

    assert response.token


def test_require_admin_allows_whitelisted_ip_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_admin_secret(monkeypatch)
    monkeypatch.setattr(settings, "admin_ip_whitelist", "10.0.0.7")

    claims = require_admin(
        credentials=None,
        token_service=get_admin_token_service(),
        request=_request_for_client("192.168.1.20", real_ip="10.0.0.7"),
    )

    assert claims["role"] == "admin"
    assert claims["auth_method"] == "ip_whitelist"


def test_require_admin_does_not_trust_spoofed_forwarded_for(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_admin_secret(monkeypatch)
    monkeypatch.setattr(settings, "admin_ip_whitelist", "10.0.0.7")

    with pytest.raises(HTTPException) as error:
        require_admin(
            credentials=None,
            token_service=get_admin_token_service(),
            request=_request_for_client("192.168.1.20", forwarded_for="10.0.0.7"),
        )

    assert error.value.status_code == 401


def test_openapi_contains_admin_login_route() -> None:
    schema = app.openapi()

    assert "/api/admin/login" in schema["paths"]
    assert "post" in schema["paths"]["/api/admin/login"]
