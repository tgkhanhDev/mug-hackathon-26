"""
Feed Session repository — data access for the `feed_sessions` collection.
"""

from app.repositories.base import BaseRepository
from app.repositories.database import get_collection
from bson import ObjectId
from datetime import datetime
from typing import Any, Dict, List, Optional
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
