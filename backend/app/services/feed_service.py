"""
Feed service — business logic for generating personalized feeds.
"""

import logging
from typing import List

from app.models.video import VideoResponse
from app.repositories.user_repository import UserRepository
from app.repositories.video_repository import VideoRepository
from app.repositories.interaction_repository import (
    FeedSessionRepository,
    InteractionRepository,
    BehaviorLogRepository,
)
from app.services.video_service import VideoService
from app.utils.exceptions import NotFoundException

logger = logging.getLogger(__name__)


class FeedService:
    """Business logic layer for feed generation."""

    def __init__(self):
        self._user_repo = UserRepository()
        self._video_repo = VideoRepository()
        self._session_repo = FeedSessionRepository()
        self._interaction_repo = InteractionRepository()
        self._log_repo = BehaviorLogRepository()

    async def get_feed(self, user_id: str, limit: int = 5) -> List[VideoResponse]:
        """
        Generate a personalized feed for a user.

        - Cold-start: If user interest_vector is empty, return top trending videos.
        - Personalized: Run Atlas Vector Search with the user's interest_vector.
        - Wellbeing-aware: Filters videos by intensity based on user's fatigue state.
        - Exploration: Mixes in a trending video to break filter bubble.
        """
        user = await self._user_repo.find_by_id(user_id)
        if not user:
            raise NotFoundException("User", user_id)

        # 1. Check active session fatigue state
        filter_stage = None
        active_session = await self._session_repo.find_active_session(user_id)
        if active_session:
            state = active_session.get("adaptive_state", "normal")
            if state == "exhausted":
                filter_stage = {"intensity_level": "low"}
            elif state == "warning":
                filter_stage = {"intensity_level": {"$in": ["low", "medium"]}}

        interest_vector = user.get("interest_vector", [])

        if not interest_vector or len(interest_vector) == 0:
            logger.info(f"❄️ Cold start feed for user: {user_id} (fetching trending videos)")
            docs = await self._video_repo.find_trending(limit=limit, filter_stage=filter_stage)
        else:
            logger.info(f"🌿 Personalized feed for user: {user_id} (running Vector Search)")
            # Perform Atlas Vector Search using the user's interest vector
            docs = await self._video_repo.vector_search(
                query_vector=interest_vector,
                limit=limit,
                num_candidates=max(limit * 10, 50),
                filter_stage=filter_stage,
                search_weight=10.0,    # Weight for vector similarity (0.0 to 1.0 scale)
                trending_weight=0.001, # Weight for dynamic trending score (can be 0 to 1000s)
            )

            # 2. Exploration Factor (if limit >= 3)
            if active_session and limit >= 3 and len(docs) > 0:
                session_id = active_session["id"]
                # Get already seen video IDs in this session from interactions
                seen_video_ids = await self._interaction_repo.find_video_ids_in_session(session_id)
                seen_set = set(seen_video_ids)

                # Also get seen from behavior logs
                behavior_docs = await self._log_repo.find_many(
                    filter={"session_id": session_id},
                    limit=500,
                )
                seen_set.update(d["video_id"] for d in behavior_docs)

                # Fetch candidate trending videos (with same intensity filter applied)
                trending_candidates = await self._video_repo.find_trending(
                    limit=30,
                    filter_stage=filter_stage,
                )

                # Select a trending video that hasn't been seen in this session
                # and is not already recommended in the first (limit - 1) positions of the feed
                first_positions_ids = {doc["id"] for doc in docs[:limit - 1]}
                
                exploration_video = None
                for cand in trending_candidates:
                    cand_id = cand["id"]
                    if cand_id not in seen_set and cand_id not in first_positions_ids:
                        exploration_video = cand
                        break

                if exploration_video:
                    # Replace the last video in the recommendation list
                    if len(docs) >= limit:
                        docs[limit - 1] = exploration_video
                    else:
                        docs[-1] = exploration_video
                    logger.info(
                        f"🚀 Exploration: Replaced last recommendation with trending video '{exploration_video.get('title')}' "
                        f"({exploration_video.get('id')}) to break filter bubble."
                    )

        return [VideoService._to_response(doc) for doc in docs]
