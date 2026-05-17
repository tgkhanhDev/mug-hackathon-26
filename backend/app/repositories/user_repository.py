"""
User repository — data access for the `users` collection.
"""

from typing import Any, Dict, List, Optional

from app.repositories.base import BaseRepository
from app.repositories.database import get_collection


class UserRepository(BaseRepository):
    """Data access layer for users collection."""

    def __init__(self):
        super().__init__(get_collection("users"))

    async def find_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Find a user by unique username."""
        return await self.find_one({"username": username})

    async def update_interest_vector(
        self, user_id: str, vector: List[float]
    ) -> bool:
        """Update the user's interest_vector (dynamic, changes over time)."""
        from datetime import datetime
        return await self.update_one(user_id, {
            "interest_vector": vector,
            "updated_at": datetime.utcnow(),
        })
