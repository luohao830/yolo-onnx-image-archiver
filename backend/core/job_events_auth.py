from __future__ import annotations

from functools import lru_cache
from typing import Any

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from backend.core.config import settings


class JobEventsTokenError(ValueError):
    """任务 SSE 订阅令牌无效或已过期。"""


class JobEventsTokenService:
    """签发短期、绑定任务的公开 SSE 订阅令牌。"""

    def __init__(self, secret_key: str, ttl_seconds: int = 300) -> None:
        self.ttl_seconds = ttl_seconds
        self.serializer = URLSafeTimedSerializer(
            secret_key=secret_key,
            salt="public-job-events",
        )

    def issue(self, job_id: int) -> str:
        return self.serializer.dumps(
            {
                "purpose": "public-job-events",
                "job_id": job_id,
            }
        )

    def verify(self, token: str, job_id: int | None = None) -> dict[str, Any]:
        try:
            payload = self.serializer.loads(token, max_age=self.ttl_seconds)
        except SignatureExpired as exc:
            raise JobEventsTokenError("job events token expired") from exc
        except BadSignature as exc:
            raise JobEventsTokenError("invalid job events token") from exc

        if not isinstance(payload, dict) or payload.get("purpose") != "public-job-events":
            raise JobEventsTokenError("invalid job events token")
        if not isinstance(payload.get("job_id"), int):
            raise JobEventsTokenError("invalid job events token")
        if job_id is not None and payload.get("job_id") != job_id:
            raise JobEventsTokenError("invalid job events token")
        return dict(payload)


@lru_cache(maxsize=1)
def get_job_events_token_service() -> JobEventsTokenService:
    return JobEventsTokenService(
        secret_key=settings.resolve_admin_token_secret(),
        ttl_seconds=settings.sse_token_ttl_seconds,
    )
