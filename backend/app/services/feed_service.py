"""
Feed service — business logic for generating personalized feeds.
"""

import logging
from typing import Any, Dict, List, Optional

from bson import ObjectId

from app.models.video import VideoResponse
from app.repositories.user_repository import UserRepository
from app.repositories.video_repository import VideoRepository
from app.repositories.behavior_log_repository import BehaviorLogRepository
from app.repositories.feed_session_repository import FeedSessionRepository
from app.repositories.interaction_repository import InteractionRepository
from app.services.video_service import VideoService
from app.utils.exceptions import NotFoundException

logger = logging.getLogger(__name__)


def _merge_filters(
    filter_a: Optional[Dict[str, Any]],
    filter_b: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Merge two MongoDB filter dicts with $and if both exist."""
    if not filter_a and not filter_b:
        return None
    if not filter_a:
        return filter_b
    if not filter_b:
        return filter_a
    return {"$and": [filter_a, filter_b]}


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
        - Deduplication: Excludes videos already seen in the current session.
        - Exploration: Mixes in a trending video to break filter bubble.
        """
        user = await self._user_repo.find_by_id(user_id)
        if not user:
            raise NotFoundException("User", user_id)

        # 1. Check active session fatigue state → intensity filter
        intensity_filter: Optional[Dict[str, Any]] = None
        active_session = await self._session_repo.find_active_session(user_id)
        if active_session:
            state = active_session.get("adaptive_state", "normal")
            if state == "exhausted":
                intensity_filter = {"intensity_level": "low"}
            elif state == "warning":
                intensity_filter = {"intensity_level": {"$in": ["low", "medium"]}}

        # 2. Collect seen video IDs early — used to dedup the ENTIRE feed pipeline
        seen_ids_filter: Optional[Dict[str, Any]] = None
        seen_set: set = set()
        session_id: Optional[str] = None

        if active_session:
            session_id = active_session["id"]

            # From explicit interactions (like, skip, replay, …)
            seen_video_ids = await self._interaction_repo.find_video_ids_in_session(session_id)
            seen_set.update(seen_video_ids)

            # From passive behavior logs
            behavior_docs = await self._log_repo.find_many(
                filter={"session_id": session_id},
                limit=500,
            )
            seen_set.update(d["video_id"] for d in behavior_docs)

            if seen_set:
                valid_object_ids = [
                    ObjectId(vid) for vid in seen_set if ObjectId.is_valid(vid)
                ]
                if valid_object_ids:
                    seen_ids_filter = {"_id": {"$nin": valid_object_ids}}
                    logger.debug(
                        f"🚫 Dedup filter: excluding {len(valid_object_ids)} already-seen videos "
                        f"for user {user_id} in session {session_id}"
                    )

        # 3. Combine intensity filter + dedup filter into a single pipeline filter
        combined_filter = _merge_filters(intensity_filter, seen_ids_filter)

        # 4. Generate feed (cold-start or personalized)
        interest_vector = user.get("interest_vector", [])

        if not interest_vector or len(interest_vector) == 0:
            logger.info(f"❄️ Cold start feed for user: {user_id} (fetching trending videos)")
            docs = await self._video_repo.find_trending(limit=limit, filter_stage=combined_filter)
        else:
            logger.info(f"🌿 Personalized feed for user: {user_id} (running Vector Search)")
            docs = await self._video_repo.vector_search(
                query_vector=interest_vector,
                limit=limit,
                num_candidates=max(limit * 10, 50),
                filter_stage=combined_filter,
                search_weight=10.0,
                trending_weight=0.001,
            )

            # 5. Exploration Factor (inject one trending video to break filter bubble)
            if active_session and limit >= 3 and len(docs) > 0:
                # Fetch trending candidates using combined_filter (already excludes seen videos)
                trending_candidates = await self._video_repo.find_trending(
                    limit=30,
                    filter_stage=combined_filter,
                )

                # Exclude videos already in the first (limit-1) positions of the feed
                first_positions_ids = {doc["id"] for doc in docs[:limit - 1]}

                exploration_video = None
                for cand in trending_candidates:
                    if cand["id"] not in first_positions_ids:
                        exploration_video = cand
                        break

                if exploration_video:
                    if len(docs) >= limit:
                        docs[limit - 1] = exploration_video
                    else:
                        docs.append(exploration_video)
                    logger.info(
                        f"🚀 Exploration: Injected trending video '{exploration_video.get('title')}' "
                        f"({exploration_video.get('id')}) to break filter bubble."
                    )

        return [VideoService._to_response(doc) for doc in docs]
