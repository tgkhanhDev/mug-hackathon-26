"""
Video controller — API route handlers for video management.

Thin layer: validates request → calls service → returns response.
"""

from fastapi import APIRouter, Query, status

from app.models.video import VideoCreate, VideoResponse, VideoListResponse
from app.services.video_service import VideoService

router = APIRouter(prefix="/videos", tags=["Videos"])


@router.post(
    "",
    response_model=VideoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new video",
    description="Admin endpoint to push a new video into the system. "
    "Automatically generates embedding vector and calculates trending score.",
)
async def create_video(data: VideoCreate):
    """POST /api/v1/videos — Create a new video."""
    service = VideoService()
    return await service.create_video(data)


@router.get(
    "",
    response_model=VideoListResponse,
    summary="List videos",
    description="Get a paginated list of all videos, ordered by creation date (newest first).",
)
async def list_videos(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
):
    """GET /api/v1/videos — List videos with pagination."""
    service = VideoService()
    return await service.get_videos(skip=skip, limit=limit)


@router.get(
    "/trending",
    response_model=list[VideoResponse],
    summary="Get trending videos",
    description="Get top videos sorted by trending_score (view*1 + like*3 + comment*5).",
)
async def get_trending(
    limit: int = Query(default=10, ge=1, le=50, description="Number of trending videos"),
):
    """GET /api/v1/videos/trending — Get trending videos."""
    service = VideoService()
    return await service.get_trending_videos(limit=limit)


@router.get(
    "/{video_id}",
    response_model=VideoResponse,
    summary="Get video by ID",
    description="Retrieve a single video by its MongoDB ObjectId.",
)
async def get_video(video_id: str):
    """GET /api/v1/videos/{video_id} — Get a single video."""
    service = VideoService()
    return await service.get_video_by_id(video_id)
