"""
Feed controller — API route handlers for generating personalized feeds.
"""

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
):
    """GET /api/v1/feed/{user_id} — Get personalized video feed."""
    service = FeedService()
    return await service.get_feed(user_id=user_id, limit=limit)
