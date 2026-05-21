"""
Video repository — data access for the `videos` collection.
"""

from typing import Any, Dict, List, Optional

from app.repositories.base import BaseRepository
from app.repositories.database import get_collection


class VideoRepository(BaseRepository):
    """Data access layer for videos collection."""

    def __init__(self):
        super().__init__(get_collection("videos"))

    async def find_by_tags(
        self, tags: List[str], limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Find videos that match any of the given tags sorted by dynamic trending_score."""
        pipeline = [
            {"$match": {"tags": {"$in": tags}}},
            {
                "$addFields": {
                    "trending_score": {
                        "$add": [
                            {"$multiply": [{"$ifNull": ["$view_count", 0]}, 1]},
                            {"$multiply": [{"$ifNull": ["$like_count", 0]}, 3]},
                            {"$multiply": [{"$ifNull": ["$comment_count", 0]}, 5]}
                        ]
                    }
                }
            },
            {"$sort": {"trending_score": -1}},
            {"$limit": limit}
        ]
        return await self.aggregate(pipeline)

    async def find_trending(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top trending videos sorted by dynamic trending_score desc."""
        pipeline = [
            {
                "$addFields": {
                    "trending_score": {
                        "$add": [
                            {"$multiply": [{"$ifNull": ["$view_count", 0]}, 1]},
                            {"$multiply": [{"$ifNull": ["$like_count", 0]}, 3]},
                            {"$multiply": [{"$ifNull": ["$comment_count", 0]}, 5]}
                        ]
                    }
                }
            },
            {"$sort": {"trending_score": -1}},
            {"$limit": limit}
        ]
        return await self.aggregate(pipeline)

    async def find_without_embedding(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Find videos that don't have an embedding yet (for scheduler job)."""
        return await self.find_many(
            filter={"$or": [{"embedding": {"$exists": False}}, {"embedding": []}]},
            limit=limit,
        )

    async def update_embedding(self, video_id: str, embedding: List[float]) -> bool:
        """Update the embedding vector for a video."""
        from datetime import datetime
        return await self.update_one(video_id, {
            "embedding": embedding,
            "updated_at": datetime.utcnow(),
        })

    async def vector_search(
        self,
        query_vector: List[float],
        limit: int = 10,
        num_candidates: int = 100,
        filter_stage: Optional[Dict[str, Any]] = None,
        search_weight: float = 100.0,
        trending_weight: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """
        Perform $vectorSearch on the videos collection, calculating a combined
        total_score (search_score * search_weight + trending_score * trending_weight)
        and sorting by it.
        Requires a Vector Search Index named 'video_embedding_index' on Atlas.
        """
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "video_embedding_index",
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": num_candidates,
                    "limit": limit,
                }
            },
            {
                "$addFields": {
                    "search_score": {"$meta": "vectorSearchScore"},
                    "trending_score": {
                        "$add": [
                            {"$multiply": [{"$ifNull": ["$view_count", 0]}, 1]},
                            {"$multiply": [{"$ifNull": ["$like_count", 0]}, 3]},
                            {"$multiply": [{"$ifNull": ["$comment_count", 0]}, 5]}
                        ]
                    }
                }
            },
            {
                "$addFields": {
                    "total_score": {
                        "$add": [
                            {"$multiply": ["$search_score", search_weight]},
                            {"$multiply": ["$trending_score", trending_weight]}
                        ]
                    }
                }
            },
            {
                "$sort": {
                    "total_score": -1
                }
            }
        ]

        # Optional post-filter (e.g., intensity_level filtering for fatigue)
        if filter_stage:
            pipeline.insert(1, {"$match": filter_stage})

        return await self.aggregate(pipeline)

    async def increment_counters(
        self, video_id: str, views: int = 0, likes: int = 0, comments: int = 0
    ) -> bool:
        """Increment view, like, and comment counters atomically on a video."""
        from bson import ObjectId
        if not ObjectId.is_valid(video_id):
            return False
        
        inc_data = {}
        if views > 0:
            inc_data["view_count"] = views
        if likes > 0:
            inc_data["like_count"] = likes
        if comments > 0:
            inc_data["comment_count"] = comments

        if not inc_data:
            return False

        result = await self.collection.update_one(
            {"_id": ObjectId(video_id)},
            {"$inc": inc_data}
        )
        return result.modified_count > 0
