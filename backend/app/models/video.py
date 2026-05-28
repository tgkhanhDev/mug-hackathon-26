"""
Video model — Pydantic schemas for the `videos` collection.

Stores video metadata + vector embedding for $vectorSearch.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Enums as Literals ──────────────────────────────────────────
CATEGORY_ENUM = [
    "lifestyle", "education", "entertainment", "sports",
    "calming", "nature", "gaming", "cooking",
    "animals", "art", "music", "comedy",
    "fashion", "automotive", "space",
]


INTENSITY_ENUM = ["high", "medium", "low"]


# ── Request DTO ────────────────────────────────────────────────
class VideoCreate(BaseModel):
    """Request body for POST /api/v1/videos."""

    title: str = Field(..., min_length=1, max_length=500, description="Tiêu đề video")
    description: str = Field(..., min_length=1, max_length=2000, description="Mô tả ngắn nội dung video")
    url: Optional[str] = Field(default="", description="URL video (S3, CDN, hoặc YouTube link)")
    thumbnail_url: str = Field(default="", description="URL ảnh thumbnail")
    tags: Optional[List[str]] = Field(default=None, max_length=10, description="Mảng tags phân loại nội dung")
    category: Optional[str] = Field(default=None, description=f"Nhóm lớn. Enum: {', '.join(CATEGORY_ENUM)}")
    intensity_level: Optional[str] = Field(default=None, description=f"Mức dopamine. Enum: {', '.join(INTENSITY_ENUM)}")
    creator_id: str = Field(..., min_length=1, description="ID định danh creator (string slug)")
    view_count: int = Field(default=0, ge=0, description="Tổng lượt xem")
    like_count: int = Field(default=0, ge=0, description="Tổng lượt like")
    comment_count: int = Field(default=0, ge=0, description="Tổng comment")
    duration: Optional[float] = Field(default=None, description="Thời lượng video (giây)")
    width: Optional[int] = Field(default=None, description="Chiều rộng video (pixel)")
    height: Optional[int] = Field(default=None, description="Chiều cao video (pixel)")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "10 Coding Memes Only Devs Understand 😂",
                    "description": "Relatable content for programmers who debug at 3AM.",
                    "url": "https://cdn.example.com/video-001.mp4",
                    "thumbnail_url": "https://cdn.example.com/thumb-001.jpg",
                    "tags": ["coding", "meme", "programmer"],
                    "category": "entertainment",
                    "intensity_level": "high",
                    "creator_id": "creator_devjokes",
                    "view_count": 3200,
                    "like_count": 540,
                    "comment_count": 87,
                }
            ]
        }
    }


# ── Internal DB Document ──────────────────────────────────────
class VideoInDB(BaseModel):
    """Full document structure stored in MongoDB."""

    title: str
    description: str
    url: str = ""
    thumbnail_url: str = ""
    tags: List[str] = Field(default_factory=list)
    category: str = ""
    intensity_level: str = ""
    status: str = Field(default="processing", description="processing, completed, failed")
    embedding: List[float] = Field(default_factory=list, description="Vector 1536-dim từ OpenAI")
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    trending_score: float = Field(default=0.0, description="view*1 + like*3 + comment*5")
    creator_id: str
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Response DTO ───────────────────────────────────────────────
class VideoResponse(BaseModel):
    """Response body returned from video endpoints."""

    id: str = Field(..., description="MongoDB ObjectId as string")
    title: str
    description: str
    url: str = ""
    thumbnail_url: str = ""
    tags: List[str] = Field(default_factory=list)
    category: str = ""
    intensity_level: str = ""
    status: str = "processing"
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    trending_score: float = 0.0
    creator_id: str
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    has_embedding: bool = Field(default=False, description="True nếu đã có embedding vector")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}



class VideoListResponse(BaseModel):
    """Paginated list response."""

    items: List[VideoResponse]
    total: int
    skip: int
    limit: int
