"""
Behavior Log model — Pydantic schemas for the `behavior_logs` collection.

Time-series log of raw per-video behavior for Fatigue Score calculation
via Aggregation Pipeline (sliding window on last 10-20 logs).
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ── Request DTO ────────────────────────────────────────────────
class BehaviorLogCreate(BaseModel):
    """Request body for logging raw behavior per video view."""

    user_id: str = Field(..., description="Ref → users._id")
    session_id: str = Field(..., description="Ref → feed_sessions._id")
    video_id: str = Field(..., description="Ref → videos._id")
    swipe_speed: float = Field(default=0.0, ge=0, description="px/giây khi vuốt qua video này")
    watch_duration: float = Field(default=0.0, ge=0, description="Số giây đã xem")
    is_interaction: bool = Field(
        default=False,
        description="true nếu user có like/comment/replay. false = passive scroll",
    )
    topic: str = Field(..., description="Tag chủ đề chính của video (tags[0])")
    consecutive_same_topic: int = Field(
        default=0, ge=0,
        description="Số video cùng topic liên tiếp. Cao → emotional saturation",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": "683a1b2c3d4e5f6a7b8c9d0e",
                    "session_id": "683a1b2c3d4e5f6a7b8c9d10",
                    "video_id": "683a1b2c3d4e5f6a7b8c9d0f",
                    "swipe_speed": 850.0,
                    "watch_duration": 5.2,
                    "is_interaction": False,
                    "topic": "sigma",
                    "consecutive_same_topic": 4,
                }
            ]
        }
    }


# ── Internal DB Document ──────────────────────────────────────
class BehaviorLogInDB(BaseModel):
    """Full document structure stored in MongoDB (Time-Series collection)."""

    user_id: str
    session_id: str
    video_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    swipe_speed: float = 0.0
    watch_duration: float = 0.0
    is_interaction: bool = False
    topic: str = ""
    consecutive_same_topic: int = 0


# ── Response DTO ───────────────────────────────────────────────
class BehaviorLogResponse(BaseModel):
    """Response body returned from behavior log endpoints."""

    id: str = Field(..., description="MongoDB ObjectId as string")
    user_id: str
    session_id: str
    video_id: str
    timestamp: datetime
    swipe_speed: float = 0.0
    watch_duration: float = 0.0
    is_interaction: bool = False
    topic: str = ""
    consecutive_same_topic: int = 0

    model_config = {"from_attributes": True}
