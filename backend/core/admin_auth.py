from __future__ import annotations

import ipaddress
from functools import lru_cache
from typing import Any

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from starlette.requests import Request

from backend.core.config import settings


class AdminTokenError(ValueError):
    """管理员令牌无效或已过期。"""


class AdminTokenService:
    def __init__(self, secret_key: str, ttl_seconds: int = 3600, sse_ttl_seconds: int = 300) -> None:
        self.ttl_seconds = ttl_seconds
        self.sse_ttl_seconds = sse_ttl_seconds
        self.serializer = URLSafeTimedSerializer(
            secret_key=secret_key,
            salt="admin-auth",
        )
        self.sse_serializer = URLSafeTimedSerializer(
            secret_key=secret_key,
            salt="admin-sse-events",
        )

    def issue(self) -> str:
        return self.serializer.dumps({"role": "admin"})

    def verify(self, token: str) -> dict[str, Any]:
        try:
            payload = self.serializer.loads(token, max_age=self.ttl_seconds)
        except SignatureExpired as exc:
            raise AdminTokenError("admin token expired") from exc
        except BadSignature as exc:
            raise AdminTokenError("invalid admin token") from exc

        if not isinstance(payload, dict) or payload.get("role") != "admin" or payload.get("purpose") is not None:
            raise AdminTokenError("invalid admin token")
        return dict(payload)

    def issue_sse(self, job_id: int) -> str:
        return self.sse_serializer.dumps(
            {
                "role": "admin",
                "purpose": "job-events",
                "job_id": job_id,
            }
        )

    def verify_sse(self, token: str, job_id: int) -> dict[str, Any]:
        try:
            payload = self.sse_serializer.loads(token, max_age=self.sse_ttl_seconds)
        except SignatureExpired as exc:
            raise AdminTokenError("admin sse token expired") from exc
        except BadSignature as exc:
            raise AdminTokenError("invalid admin sse token") from exc

        if (
            not isinstance(payload, dict)
            or payload.get("role") != "admin"
            or payload.get("purpose") != "job-events"
            or payload.get("job_id") != job_id
        ):
            raise AdminTokenError("invalid admin sse token")
        return dict(payload)


def is_admin_ip_whitelisted(request: Request) -> bool:
    client_ip = _resolve_client_ip(request)
    if not client_ip:
        return False

    try:
        address = ipaddress.ip_address(client_ip)
    except ValueError:
        return False

    for entry in _configured_admin_ip_whitelist():
        try:
            if "/" in entry:
                if address in ipaddress.ip_network(entry, strict=False):
                    return True
            elif address == ipaddress.ip_address(entry):
                return True
        except ValueError:
            continue

    return False


def _resolve_client_ip(request: Request) -> str:
    direct_client_ip = request.client.host if request.client is not None else ""
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip and _is_trusted_proxy_client(direct_client_ip):
        return real_ip
    return direct_client_ip


def _is_trusted_proxy_client(client_ip: str) -> bool:
    if not client_ip:
        return False
    try:
        address = ipaddress.ip_address(client_ip)
    except ValueError:
        return False

    for entry in _configured_admin_trusted_proxy_cidrs():
        try:
            if "/" in entry:
                if address in ipaddress.ip_network(entry, strict=False):
                    return True
            elif address == ipaddress.ip_address(entry):
                return True
        except ValueError:
            continue

    return False


def _configured_admin_ip_whitelist() -> list[str]:
    return [
        item.strip()
        for item in settings.admin_ip_whitelist.split(",")
        if item.strip()
    ]


def _configured_admin_trusted_proxy_cidrs() -> list[str]:
    return [
        item.strip()
        for item in settings.admin_trusted_proxy_cidrs.split(",")
        if item.strip()
    ]


@lru_cache(maxsize=1)
def get_admin_token_service() -> AdminTokenService:
    return AdminTokenService(
        secret_key=settings.resolve_admin_token_secret(),
        ttl_seconds=settings.admin_token_ttl_seconds,
    )
