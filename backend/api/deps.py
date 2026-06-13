from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.admin_auth import AdminTokenError, AdminTokenService, get_admin_token_service, is_admin_ip_whitelisted


admin_bearer = HTTPBearer(auto_error=False)


def require_admin(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(admin_bearer)],
    token_service: Annotated[AdminTokenService, Depends(get_admin_token_service)],
) -> dict[str, Any]:
    if is_admin_ip_whitelisted(request):
        return {"role": "admin", "auth_method": "ip_whitelist"}

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="admin token required",
        )

    try:
        return token_service.verify(credentials.credentials)
    except AdminTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
