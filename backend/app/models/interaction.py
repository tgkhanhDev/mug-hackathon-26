"""
Interaction model — Pydantic schemas for the `interactions` collection.

Append-only log of intentional user actions (like, skip, replay...).
Source of truth for updating interest_vector.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────
INTERACTION_TYPES = ["like", "skip", "comment", "replay", "share", "passive_view"]

# Trọng số update interest_vector theo interaction type
# Canonical definition lives in app.utils.formula.interest_vector;
# re-exported here for backward compatibility.
from app.utils.formula.interest_vector import INTERACTION_WEIGHTS  # noqa: F401, E402


# ── Request DTO ────────────────────────────────────────────────
class InteractionCreate(BaseModel):
    """Request body for creating an interaction event."""

    user_id: str = Field(..., description="Ref → users._id")
    video_id: str = Field(..., description="Ref → videos._id")
    session_id: str = Field(..., description="Ref → feed_sessions._id")
    type: str = Field(..., description=f"Enum: {', '.join(INTERACTION_TYPES)}")
    watch_duration: float = Field(default=0.0, ge=0, description="Thời gian xem (giây)")
    watch_percentage: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Tỉ lệ đã xem 0.0→1.0. >0.8 = tín hiệu tích cực mạnh",
    )
    swipe_speed: float = Field(default=0.0, ge=0, description="Tốc độ vuốt (px/giây)")
    replay_count: int = Field(default=0, ge=0, description="Số lần xem lại")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": "683a1b2c3d4e5f6a7b8c9d0e",
                    "video_id": "683a1b2c3d4e5f6a7b8c9d0f",
                    "session_id": "683a1b2c3d4e5f6a7b8c9d10",
                    "type": "like",
                    "watch_duration": 28.5,
                    "watch_percentage": 0.95,
                    "swipe_speed": 0.0,
                    "replay_count": 1,
                }
            ]
        }
    }


# ── Internal DB Document ──────────────────────────────────────
class InteractionInDB(BaseModel):
    """Full document structure stored in MongoDB."""

    user_id: str
    video_id: str
    session_id: str
    type: str
    watch_duration: float = 0.0
    watch_percentage: float = 0.0
    swipe_speed: float = 0.0
    replay_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Response DTO ───────────────────────────────────────────────
class InteractionResponse(BaseModel):
    """Response body returned from interaction endpoints."""

    id: str = Field(..., description="MongoDB ObjectId as string")
    user_id: str
    video_id: str
    session_id: str
    type: str
    watch_duration: float = 0.0
    watch_percentage: float = 0.0
    swipe_speed: float = 0.0
    replay_count: int = 0
    timestamp: datetime

    model_config = {"from_attributes": True}
