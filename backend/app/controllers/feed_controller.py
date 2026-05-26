"""
Feed controller — API route handlers for generating personalized feeds.
"""

from typing import List, Optional

from fastapi import APIRouter, Query, status

from app.models.video import VideoResponse
from app.services.feed_service import FeedService

router = APIRouter(prefix="/feed", tags=["Feed"])


@router.get(
    "/{user_id}",
    response_model=list[VideoResponse],
    summary="Get personalized feed",
    description="Retrieve a list of recommended videos for a user based on interest vector matching (Atlas Vector Search). Falls back to trending videos for new users.",
)
async def get_personalized_feed(
    user_id: str,
    limit: int = Query(default=5, ge=1, le=50, description="Number of videos to fetch"),
    exclude: Optional[str] = Query(default=None, description="Comma-separated video IDs to exclude (already displayed on client)"),
):
    """GET /api/v1/feed/{user_id} — Get personalized video feed."""
    # Parse comma-separated exclude IDs sent by the frontend
    exclude_ids: List[str] = []
    if exclude:
        exclude_ids = [vid.strip() for vid in exclude.split(",") if vid.strip()]

    service = FeedService()
    return await service.get_feed(user_id=user_id, limit=limit, exclude_ids=exclude_ids)

