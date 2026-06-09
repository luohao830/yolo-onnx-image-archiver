from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.core.admin_auth import AdminTokenService, get_admin_token_service
from backend.core.config import settings


router = APIRouter(prefix="/admin", tags=["admin-auth"])


class LoginRequest(BaseModel):
    secret: str


class LoginResponse(BaseModel):
    token: str


@router.post("/login", response_model=LoginResponse)
def admin_login(
    payload: LoginRequest,
    token_service: Annotated[AdminTokenService, Depends(get_admin_token_service)],
) -> LoginResponse:
    if not hmac.compare_digest(payload.secret, settings.admin_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid secret",
        )
    return LoginResponse(token=token_service.issue())
