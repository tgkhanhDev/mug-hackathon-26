"""
Auth models — Pydantic schemas for authentication (register/login).

Stubs for Stage 2 implementation. JWT access + refresh token flow.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Request DTOs ───────────────────────────────────────────────
class RegisterRequest(BaseModel):
    """Request body for POST /api/v1/auth/register."""

    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: str = Field(default="", description="Email (optional)")
    password: str = Field(..., min_length=6, max_length=128, description="Plain text password")
    interest_tags: list[str] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="2 interest tags from onboarding",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "username": "tgkhanh_dev",
                    "email": "khanh@example.com",
                    "password": "securePass123",
                    "interest_tags": ["coding", "football"],
                }
            ]
        }
    }


class LoginRequest(BaseModel):
    """Request body for POST /api/v1/auth/login."""

    username: str = Field(..., description="Username")
    password: str = Field(..., description="Plain text password")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"username": "tgkhanh_dev", "password": "securePass123"}
            ]
        }
    }


# ── Response DTOs ──────────────────────────────────────────────
class TokenResponse(BaseModel):
    """JWT token pair response."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token TTL in seconds")
    user_id: str = Field(..., description="MongoDB ObjectId of the user as string")
    username: str = Field(..., description="Username of the user")


class RefreshTokenRequest(BaseModel):
    """Request body for POST /api/v1/auth/refresh."""

    refresh_token: str = Field(..., description="Valid refresh token")
