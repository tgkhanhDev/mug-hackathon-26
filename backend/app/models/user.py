"""
User model — Pydantic schemas for the `users` collection.

Stores user profile + interest vector for $vectorSearch personalization.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Request DTO ────────────────────────────────────────────────
class UserCreate(BaseModel):
    """Request body for POST /api/v1/users (onboarding)."""

    username: str = Field(..., min_length=1, max_length=100, description="Tên hiển thị, unique")
    email: str = Field(default="", description="Email người dùng")
    interest_tags: List[str] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="2 tags user chọn trong onboarding screen",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "username": "tgkhanh_dev",
                    "email": "khanh@example.com",
                    "interest_tags": ["coding", "football"],
                }
            ]
        }
    }


# ── Internal DB Document ──────────────────────────────────────
class UserInDB(BaseModel):
    """Full document structure stored in MongoDB."""

    username: str
    email: str = ""
    password_hash: str = Field(default="", description="Hashed password (for auth stage)")
    interest_tags: List[str]
    interest_vector: List[float] = Field(
        default_factory=list,
        description="Vector 1536-dim. Khởi tạo = trung bình embedding videos matching interest_tags",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Response DTO ───────────────────────────────────────────────
class UserResponse(BaseModel):
    """Response body returned from user endpoints."""

    id: str = Field(..., description="MongoDB ObjectId as string")
    username: str
    email: str = ""
    interest_tags: List[str]
    has_interest_vector: bool = Field(
        default=False, description="True nếu đã có interest_vector"
    )
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """Paginated list response."""

    items: List[UserResponse]
    total: int
    skip: int
    limit: int
