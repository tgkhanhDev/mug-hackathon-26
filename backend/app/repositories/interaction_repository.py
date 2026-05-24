"""
Interaction repository — data access for:
  - `interactions`  collection (business events: like, skip, replay...)
  - `feed_sessions` collection (per-session stats + fatigue)
  - `behavior_logs` collection (time-series raw behavior)
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId

from app.repositories.base import BaseRepository
from app.repositories.database import get_collection
from app.utils.formula.trending import build_trending_score_update_pipeline


# ══════════════════════════════════════════════════════════════════
# Interaction Repository
# ══════════════════════════════════════════════════════════════════

class InteractionRepository(BaseRepository):
    """Data access layer for the `interactions` collection."""

    def __init__(self):
        super().__init__(get_collection("interactions"))

    async def find_by_user(
        self,
        user_id: str,
        limit: int = 50,
        interaction_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get recent interactions for a user, optionally filtered by type.
        Sorted newest-first.
        """
        filter_: Dict[str, Any] = {"user_id": user_id}
        if interaction_types:
            filter_["type"] = {"$in": interaction_types}
        return await self.find_many(
            filter=filter_,
            limit=limit,
            sort=[("timestamp", -1)],
        )

    async def find_liked_video_ids(self, user_id: str, limit: int = 100) -> List[str]:
        """
        Return video_ids the user interacted with positively
        (like, replay, comment, share) — used for interest_vector update.
        """
        docs = await self.find_by_user(
            user_id,
            limit=limit,
            interaction_types=["like", "replay", "comment", "share"],
        )
        return [d["video_id"] for d in docs]

    async def find_video_ids_in_session(self, session_id: str) -> List[str]:
        """Return all video_ids the user has seen in a given session (for dedup)."""
        docs = await self.find_many(
            filter={"session_id": session_id},
            limit=500,
        )
        return list({d["video_id"] for d in docs})

    async def find_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Return all interactions in a given session."""
        return await self.find_many({"session_id": session_id})

    async def increment_video_counters(
        self, video_id: str, interaction_type: str
    ) -> None:
        """
        Atomically increment view/like/comment counters on the video document
        and recalculate trending_score.
        Formula: trending_score = view_count*1 + like_count*3 + comment_count*5
        """
        if not ObjectId.is_valid(video_id):
            return

        videos_col = get_collection("videos")
        inc_field = {
            "like": "like_count",
            "comment": "comment_count",
            "replay": "view_count",
            "share": "view_count",
            "skip": None,
        }.get(interaction_type)

        # Always count as a view
        inc_payload: Dict[str, int] = {"view_count": 1}
        if inc_field and inc_field != "view_count":
            inc_payload[inc_field] = 1

        # Pipeline update: $inc counters then recalculate trending_score
        pipeline = build_trending_score_update_pipeline(inc_payload)
        await videos_col.update_one(
            {"_id": ObjectId(video_id)},
            pipeline,
        )

