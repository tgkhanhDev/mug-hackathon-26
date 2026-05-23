
from app.repositories.base import BaseRepository
from app.repositories.database import get_collection
from bson import ObjectId
from datetime import datetime
from typing import Any, Dict, List, Optional

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
