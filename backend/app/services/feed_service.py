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
from app.repositories.redis_client import get_seen_videos, is_redis_available, bulk_add_seen_videos
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

    @staticmethod
    def _get_adaptive_weights(adaptive_state: str) -> tuple[float, float]:
        """Return (search_weight, trending_weight) based on fatigue state.

        - normal:    Maximize personalization (high search, low trending)
        - warning:   Balance personal + calming content
        - exhausted: Prioritize trending/calming over vector similarity
        """
        if adaptive_state == "exhausted":
            return (5.0, 0.5)
        elif adaptive_state == "warning":
            return (7.0, 0.1)
        else:  # "normal"
            return (10.0, 0.001)

    def __init__(self):
        self._user_repo = UserRepository()
        self._video_repo = VideoRepository()
        self._session_repo = FeedSessionRepository()
        self._interaction_repo = InteractionRepository()
        self._log_repo = BehaviorLogRepository()

    async def get_feed(self, user_id: str, limit: int = 5, exclude_ids: List[str] = None) -> List[VideoResponse]:
        """
        Generate a personalized feed for a user.

        - Cold-start: If user interest_vector is empty, return top trending videos.
        - Personalized: Run Atlas Vector Search with the user's interest_vector.
        - Wellbeing-aware: Filters videos by intensity based on user's fatigue state.
        - Deduplication: Excludes videos already seen in the current session.
        - Exploration: Mixes in a trending video to break filter bubble.
        - Fallback: If combined filter yields 0 results, progressively relax constraints.

        Args:
            exclude_ids: Video IDs already displayed on the client (sent by FE).
                         These are merged with session-based seen IDs for dedup.
        """
        user = await self._user_repo.find_by_id(user_id)
        if not user:
            raise NotFoundException("User", user_id)

        # 1. Check active session fatigue state → intensity filter + adaptive_state
        intensity_filter: Optional[Dict[str, Any]] = None
        active_session = await self._session_repo.find_active_session(user_id)

        adaptive_state = "normal"
        if active_session:
            adaptive_state = active_session.get("adaptive_state", "normal")
            if adaptive_state == "exhausted":
                intensity_filter = {"intensity_level": "low"}
            elif adaptive_state == "warning":
                intensity_filter = {"intensity_level": {"$in": ["low", "medium"]}}

        # 2. Collect seen video IDs early — used to dedup the ENTIRE feed pipeline
        seen_ids_filter: Optional[Dict[str, Any]] = None
        seen_set: set = set()
        session_id: Optional[str] = None

        # 2a. Merge FE-provided exclude IDs (videos already displayed on client)
        #     This is the PRIMARY dedup source — FE always knows what it has shown.
        if exclude_ids:
            seen_set.update(exclude_ids)

        # 2b. Read seen_set from Redis (always up-to-date, ~1ms)
        #     Falls back to MongoDB queries if Redis is unavailable.
        if active_session:
            session_id = active_session["id"]

            redis_seen = await get_seen_videos(session_id)
            if redis_seen:
                # Redis has authoritative seen data — use it directly
                seen_set.update(redis_seen)
                logger.info(
                    f"🔴 Redis seen-set: {len(redis_seen)} videos for session {session_id}"
                )
            else:
                # Fallback: Redis unavailable or empty → query MongoDB
                # From explicit interactions (like, skip, replay, …)
                seen_video_ids = await self._interaction_repo.find_video_ids_in_session(session_id)
                seen_set.update(seen_video_ids)

                # From passive behavior logs
                behavior_docs = await self._log_repo.find_many(
                    filter={"session_id": session_id},
                    limit=500,
                )
                seen_set.update(d["video_id"] for d in behavior_docs)

                # Seed Redis with MongoDB data for future requests
                if seen_set and is_redis_available():
                    await bulk_add_seen_videos(session_id, seen_set)
                    logger.info(
                        f"🔁 Seeded Redis with {len(seen_set)} seen videos from MongoDB"
                    )

        # 2c. Build the $nin filter from the combined seen set
        if seen_set:
            valid_object_ids = [
                ObjectId(vid) for vid in seen_set if ObjectId.is_valid(vid)
            ]
            if valid_object_ids:
                seen_ids_filter = {"_id": {"$nin": valid_object_ids}}
                logger.info(
                    f"🚫 Dedup filter: excluding {len(valid_object_ids)} already-seen videos "
                    f"for user {user_id} (FE exclude={len(exclude_ids or [])}, "
                    f"session={len(seen_set) - len(exclude_ids or [])})"
                )

        # 3. Combine intensity filter + dedup filter into a single pipeline filter
        combined_filter = _merge_filters(intensity_filter, seen_ids_filter)

        # 4. Generate feed with progressive fallback strategy
        # Fallback ladder: full filter → dedup-only → no filter (avoid total empty)
        interest_vector = user.get("interest_vector", [])
        search_weight, trending_weight = self._get_adaptive_weights(adaptive_state)

        docs = await self._fetch_feed(
            interest_vector=interest_vector,
            user_id=user_id,
            limit=limit,
            adaptive_state=adaptive_state,
            search_weight=search_weight,
            trending_weight=trending_weight,
            filter_stage=combined_filter,
            num_exclude=len(seen_set),
        )

        # Fallback 1: intensity filter too strict → drop it, keep dedup only
        if len(docs) < limit and intensity_filter is not None:
            logger.info(
                f"⚠️ Feed too small ({len(docs)}/{limit}) with intensity filter "
                f"— relaxing to dedup-only for user {user_id}"
            )
            docs = await self._fetch_feed(
                interest_vector=interest_vector,
                user_id=user_id,
                limit=limit,
                adaptive_state=adaptive_state,
                search_weight=search_weight,
                trending_weight=trending_weight,
                filter_stage=seen_ids_filter,  # dedup only, no intensity constraint
                num_exclude=len(seen_set),
            )

        # Fallback 2: still empty → user has seen everything → drop dedup filter too
        if len(docs) == 0 and seen_ids_filter is not None:
            logger.info(
                f"♻️ Feed empty after relaxing intensity filter "
                f"— dropping dedup filter (user has seen all available videos): {user_id}"
            )
            docs = await self._fetch_feed(
                interest_vector=interest_vector,
                user_id=user_id,
                limit=limit,
                adaptive_state=adaptive_state,
                search_weight=search_weight,
                trending_weight=trending_weight,
                filter_stage=None,  # no filter at all
            )

        # 5. Exploration Factor (inject one trending video to break filter bubble)
        if interest_vector and active_session and limit >= 3 and len(docs) > 0:
            # Use the best available filter for exploration candidates
            explore_filter = combined_filter if docs else None
            trending_candidates = await self._video_repo.find_trending(
                limit=30,
                filter_stage=explore_filter,
            )

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

        # 6. Palette Cleanser Injection (exhausted state only)
        if adaptive_state == "exhausted" and limit >= 3 and len(docs) >= 2:
            cleanser = await self._video_repo.find_random_calming(
                exclude_ids=seen_set | {doc["id"] for doc in docs},
                calming_categories=["calming", "nature"],
                intensity_level="low",
            )
            if cleanser:
                docs.insert(1, cleanser)  # Position 2 (index 1)
                # Trim to respect original limit
                if len(docs) > limit:
                    docs = docs[:limit]
                logger.info(
                    f"🍃 Palette cleanser injected: '{cleanser.get('title')}' "
                    f"(category={cleanser.get('category')})"
                )

        return [VideoService._to_response(doc) for doc in docs]

    async def _fetch_feed(
        self,
        interest_vector: List[float],
        user_id: str,
        limit: int,
        adaptive_state: str,
        search_weight: float,
        trending_weight: float,
        filter_stage: Optional[Dict[str, Any]],
        num_exclude: int = 0,
    ) -> List[Dict[str, Any]]:
        """Internal helper — run either cold-start trending or vector search."""
        if not interest_vector:
            logger.info(f"❄️ Cold start feed for user: {user_id} (fetching trending videos)")
            return await self._video_repo.find_trending(
                limit=limit,
                filter_stage=filter_stage,
            )
        else:
            logger.info(
                f"🌿 Personalized feed for user: {user_id} | state={adaptive_state} "
                f"| weights=({search_weight}, {trending_weight}) | exclude={num_exclude}"
            )
            return await self._video_repo.vector_search(
                query_vector=interest_vector,
                limit=limit,
                filter_stage=filter_stage,
                search_weight=search_weight,
                trending_weight=trending_weight,
                adaptive_state=adaptive_state,
                num_exclude=num_exclude,
            )
