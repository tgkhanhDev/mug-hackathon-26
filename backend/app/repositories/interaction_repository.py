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
        await videos_col.update_one(
            {"_id": ObjectId(video_id)},
            [
                {"$set": {
                    "view_count": {"$add": [{"$ifNull": ["$view_count", 0]}, inc_payload.get("view_count", 0)]},
                    "like_count": {
                        "$add": [
                            {"$ifNull": ["$like_count", 0]},
                            1 if inc_payload.get("like_count") else 0,
                        ]
                    },
                    "comment_count": {
                        "$add": [
                            {"$ifNull": ["$comment_count", 0]},
                            1 if inc_payload.get("comment_count") else 0,
                        ]
                    },
                    "updated_at": "$$NOW",
                }},
                {"$set": {
                    "trending_score": {
                        "$add": [
                            {"$multiply": [{"$ifNull": ["$view_count", 0]}, 1]},
                            {"$multiply": [{"$ifNull": ["$like_count", 0]}, 3]},
                            {"$multiply": [{"$ifNull": ["$comment_count", 0]}, 5]},
                        ]
                    }
                }},
            ],
        )


# ══════════════════════════════════════════════════════════════════
# Feed Session Repository
# ══════════════════════════════════════════════════════════════════

class FeedSessionRepository(BaseRepository):
    """Data access layer for the `feed_sessions` collection."""

    def __init__(self):
        super().__init__(get_collection("feed_sessions"))

    async def find_active_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Find the currently active session (ended_at is null)."""
        return await self.find_one({"user_id": user_id, "ended_at": None})

    async def end_session(self, session_id: str) -> bool:
        """Mark a session as ended."""
        return await self.update_one(session_id, {"ended_at": datetime.utcnow()})

    async def increment_videos_watched(self, session_id: str) -> None:
        """Atomically increment total_videos_watched counter."""
        if not ObjectId.is_valid(session_id):
            return
        col = get_collection("feed_sessions")
        await col.update_one(
            {"_id": ObjectId(session_id)},
            {"$inc": {"total_videos_watched": 1}},
        )

    async def update_session_stats(
        self, session_id: str, stats: Dict[str, Any]
    ) -> bool:
        """Update session aggregate stats (fatigue_score, adaptive_state, etc.)."""
        return await self.update_one(session_id, stats)

    async def update_intensity_count(
        self, session_id: str, intensity_level: str
    ) -> None:
        """Increment high/low intensity video count for the session."""
        if not ObjectId.is_valid(session_id):
            return
        col = get_collection("feed_sessions")
        field = (
            "high_intensity_count"
            if intensity_level == "high"
            else "low_intensity_count"
        )
        await col.update_one(
            {"_id": ObjectId(session_id)},
            {"$inc": {field: 1}},
        )


# ══════════════════════════════════════════════════════════════════
# Behavior Log Repository
# ══════════════════════════════════════════════════════════════════

class BehaviorLogRepository(BaseRepository):
    """Data access layer for the `behavior_logs` time-series collection."""

    def __init__(self):
        super().__init__(get_collection("behavior_logs"))

    async def get_recent_logs(
        self, session_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get the N most-recent behavior logs for a session (for fatigue calc)."""
        return await self.find_many(
            filter={"session_id": session_id},
            limit=limit,
            sort=[("timestamp", -1)],
        )

    async def get_consecutive_topic_count(
        self, session_id: str, topic: str, limit: int = 10
    ) -> int:
        """
        Count how many consecutive videos share the same topic
        in the most recent logs of a session.
        """
        recent = await self.find_many(
            filter={"session_id": session_id},
            limit=limit,
            sort=[("timestamp", -1)],
        )
        count = 0
        for log in recent:
            if log.get("topic") == topic:
                count += 1
            else:
                break
        return count
