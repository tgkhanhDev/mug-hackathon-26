"""
Feed Session model — Pydantic schemas for the `feed_sessions` collection.

Tracks an entire browsing session: fatigue score, adaptive state, intensity counts.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────
ADAPTIVE_STATES = ["normal", "warning", "exhausted"]


# ── Request DTO ────────────────────────────────────────────────
class FeedSessionCreate(BaseModel):
    """Request body to start a new feed session."""

    user_id: str = Field(..., description="Ref → users._id")

    model_config = {
        "json_schema_extra": {
            "examples": [{"user_id": "683a1b2c3d4e5f6a7b8c9d0e"}]
        }
    }


# ── Internal DB Document ──────────────────────────────────────
class FeedSessionInDB(BaseModel):
    """Full document structure stored in MongoDB."""

    user_id: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = Field(
        default=None, description="null = session đang active"
    )
    total_videos_watched: int = Field(default=0, description="Số video đã xem trong session")
    fatigue_score: float = Field(
        default=0.0,
        description="Điểm mệt mỏi 0-100. Tăng khi swipe nhanh, watch ngắn, passive scroll",
    )
    adaptive_state: str = Field(
        default="normal",
        description="State machine: normal (<40), warning (40-70), exhausted (>70)",
    )
    high_intensity_count: int = Field(default=0, description="Số video intensity=high đã xem")
    low_intensity_count: int = Field(default=0, description="Số video intensity=low đã xem")
    avg_watch_duration: float = Field(default=0.0, description="Trung bình thời gian xem (giây)")
    avg_swipe_speed: float = Field(default=0.0, description="Trung bình tốc độ vuốt (px/giây)")


# ── Response DTO ───────────────────────────────────────────────
class FeedSessionResponse(BaseModel):
    """Response body returned from session endpoints."""

    id: str = Field(..., description="MongoDB ObjectId as string")
    user_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    total_videos_watched: int = 0
    fatigue_score: float = 0.0
    adaptive_state: str = "normal"
    high_intensity_count: int = 0
    low_intensity_count: int = 0
    avg_watch_duration: float = 0.0
    avg_swipe_speed: float = 0.0

    model_config = {"from_attributes": True}
