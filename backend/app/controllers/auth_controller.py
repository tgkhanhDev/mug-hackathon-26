"""
Auth controller — API route handlers for authentication.

Stub endpoints for register/login/refresh. Ready for Stage 2 integration.
No auth middleware applied yet (Day 1 = open endpoints).
"""

from fastapi import APIRouter, status, Depends

from app.models.auth import (
    LoginRequest,
    RegisterRequest,
    RefreshTokenRequest,
    TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Register with username, password, and 2 interest tags. "
    "Returns JWT access + refresh token pair.",
)
async def register(data: RegisterRequest, service: AuthService = Depends()):
    """POST /api/v1/auth/register — Register and get tokens."""
    return await service.register(data)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login",
    description="Authenticate with username and password. "
    "Returns JWT access + refresh token pair.",
)
async def login(data: LoginRequest, service: AuthService = Depends()):
    """POST /api/v1/auth/login — Login and get tokens."""
    return await service.login(data)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh tokens",
    description="Use a valid refresh token to get a new access + refresh token pair.",
)
async def refresh(data: RefreshTokenRequest, service: AuthService = Depends()):
    """POST /api/v1/auth/refresh — Refresh token pair."""
    return await service.refresh_tokens(data.refresh_token)
