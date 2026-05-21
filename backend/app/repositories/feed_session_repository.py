"""
Feed Session repository — data access for the `feed_sessions` collection.
"""

from app.repositories.base import BaseRepository
from app.repositories.database import get_collection


class FeedSessionRepository(BaseRepository):
    """Data access layer for feed_sessions collection."""

    def __init__(self):
        super().__init__(get_collection("feed_sessions"))
