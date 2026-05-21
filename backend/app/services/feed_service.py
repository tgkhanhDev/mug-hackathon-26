"""
Feed service — business logic for generating personalized feeds.
"""

import logging
from typing import List

from app.models.video import VideoResponse
from app.repositories.user_repository import UserRepository
from app.repositories.video_repository import VideoRepository
from app.services.video_service import VideoService
from app.utils.exceptions import NotFoundException

logger = logging.getLogger(__name__)


class FeedService:
    """Business logic layer for feed generation."""

    def __init__(self):
        self._user_repo = UserRepository()
        self._video_repo = VideoRepository()

    async def get_feed(self, user_id: str, limit: int = 5) -> List[VideoResponse]:
        """
        Generate a personalized feed for a user.

        - Cold-start: If user interest_vector is empty, return top trending videos.
        - Personalized: Run Atlas Vector Search with the user's interest_vector.
        """
        user = await self._user_repo.find_by_id(user_id)
        if not user:
            raise NotFoundException("User", user_id)

        interest_vector = user.get("interest_vector", [])

        if not interest_vector or len(interest_vector) == 0:
            logger.info(f"❄️ Cold start feed for user: {user_id} (fetching trending videos)")
            docs = await self._video_repo.find_trending(limit=limit)
        else:
            logger.info(f"🌿 Personalized feed for user: {user_id} (running Vector Search)")
            # Perform Atlas Vector Search using the user's interest vector
            docs = await self._video_repo.vector_search(
                query_vector=interest_vector,
                limit=limit,
                num_candidates=max(limit * 10, 50),
                search_weight=10.0,    # Weight for vector similarity (0.0 to 1.0 scale)
                trending_weight=0.001, # Weight for dynamic trending score (can be 0 to 1000s)
            )

        return [VideoService._to_response(doc) for doc in docs]
