from __future__ import annotations

from functools import lru_cache
from typing import Any

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from backend.core.config import settings


class AdminTokenError(ValueError):
    """管理员令牌无效或已过期。"""


class AdminTokenService:
    def __init__(self, secret_key: str, ttl_seconds: int = 3600) -> None:
        self.ttl_seconds = ttl_seconds
        self.serializer = URLSafeTimedSerializer(
            secret_key=secret_key,
            salt="admin-auth",
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

        if not isinstance(payload, dict) or payload.get("role") != "admin":
            raise AdminTokenError("invalid admin token")
        return dict(payload)


@lru_cache(maxsize=1)
def get_admin_token_service() -> AdminTokenService:
    return AdminTokenService(
        secret_key=settings.resolve_admin_token_secret(),
        ttl_seconds=settings.admin_token_ttl_seconds,
    )
