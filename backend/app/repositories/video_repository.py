"""
Video repository — data access for the `videos` collection.
"""

from typing import Any, Dict, List, Optional

from app.repositories.base import BaseRepository
from app.repositories.database import get_collection
from app.utils.formula.trending import build_trending_score_pipeline_stage


class VideoRepository(BaseRepository):
    """Data access layer for videos collection."""

    def __init__(self):
        super().__init__(get_collection("videos"))

    async def find_by_tags(
        self, tags: List[str], limit: int = 20, filter_stage: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Find videos that match any of the given tags sorted by dynamic trending_score."""
        match_filter = {"status": "completed", "tags": {"$in": tags}}
        if filter_stage:
            match_filter = {"$and": [match_filter, filter_stage]}

        pipeline = [
            {"$match": match_filter},
            build_trending_score_pipeline_stage(),
            {"$sort": {"trending_score": -1}},
            {"$limit": limit}
        ]
        return await self.aggregate(pipeline)

    async def find_trending(
        self, limit: int = 10, filter_stage: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Get top trending videos sorted by dynamic trending_score desc."""
        status_filter = {"status": "completed"}
        if filter_stage:
            match_filter = {"$and": [status_filter, filter_stage]}
        else:
            match_filter = status_filter

        pipeline = [
            {"$match": match_filter},
            build_trending_score_pipeline_stage(),
            {"$sort": {"trending_score": -1}},
            {"$limit": limit}
        ]
        return await self.aggregate(pipeline)

    async def find_without_embedding(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Find completed videos that don't have an embedding yet (for scheduler job fallback)."""
        return await self.find_many(
            filter={
                "status": "completed",
                "$or": [{"embedding": {"$exists": False}}, {"embedding": []}]
            },
            limit=limit,
        )

    async def update_embedding(self, video_id: str, embedding: List[float]) -> bool:
        """Update the embedding vector for a video."""
        from datetime import datetime
        return await self.update_one(video_id, {
            "embedding": embedding,
            "updated_at": datetime.utcnow(),
        })

    async def find_random_calming(
        self,
        exclude_ids: set,
        calming_categories: List[str] = None,
        intensity_level: str = "low",
        limit: int = 1,
    ) -> Optional[Dict[str, Any]]:
        """Find a random calming video for palette cleanser injection.

        Uses MongoDB $sample for true random selection from calming categories,
        excluding already-seen videos in the current session.
        """
        from bson import ObjectId

        if calming_categories is None:
            calming_categories = ["calming", "nature", "comedy", "music", "art"]

        match_filter: Dict[str, Any] = {
            "status": "completed",
            "category": {"$in": calming_categories},
            "intensity_level": intensity_level,
        }

        if exclude_ids:
            valid_oids = [ObjectId(vid) for vid in exclude_ids if ObjectId.is_valid(vid)]
            if valid_oids:
                match_filter["_id"] = {"$nin": valid_oids}

        pipeline = [
            {"$match": match_filter},
            {"$sample": {"size": limit}},
        ]
        results = await self.aggregate(pipeline)
        return results[0] if results else None

    async def vector_search(
        self,
        query_vector: List[float],
        limit: int = 10,
        num_candidates: int = 100,
        filter_stage: Optional[Dict[str, Any]] = None,
        search_weight: float = 100.0,
        trending_weight: float = 1.0,
        adaptive_state: str = "normal",
        num_exclude: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Perform $vectorSearch on the videos collection, calculating a combined
        total_score (search_score * search_weight + trending_score * trending_weight)
        and sorting by it.

        When adaptive_state is "exhausted", an intensity_rank field is added so
        that low-intensity videos always sort before higher-intensity ones.
        Requires a Vector Search Index named 'video_embedding_index' on Atlas.

        NOTE: filter_stage is inserted AFTER $vectorSearch (at index 1) as a $match
        post-filter — this is the correct Atlas Vector Search pattern.
        """
        # Over-fetch from $vectorSearch to compensate for post-filter $nin exclusion.
        # E.g.: need 5 videos, already excluded 5 → vectorSearch fetches 10 → 
        # post-filter removes 5 seen → 5 fresh remain.
        vs_limit = limit + num_exclude
        vs_candidates = max(vs_limit * 10, 50)
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "video_embedding_index",
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": vs_candidates,
                    "limit": vs_limit,
                }
            },
            {
                "$addFields": {
                    "search_score": {"$meta": "vectorSearchScore"},
                    **build_trending_score_pipeline_stage()["$addFields"],
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
        ]

        # Adaptive sorting: prioritize low-intensity when exhausted
        # Use $switch to avoid wrong alphabetical ordering: "high" < "low" < "medium"
        if adaptive_state == "exhausted":
            pipeline.append({
                "$addFields": {
                    "intensity_rank": {
                        "$switch": {
                            "branches": [
                                {"case": {"$eq": ["$intensity_level", "low"]}, "then": 0},
                                {"case": {"$eq": ["$intensity_level", "medium"]}, "then": 1},
                            ],
                            "default": 2  # high
                        }
                    }
                }
            })
            pipeline.append({"$sort": {"intensity_rank": 1, "total_score": -1}})
        else:
            pipeline.append({"$sort": {"total_score": -1}})

        # Post-filter: always require status="completed"
        status_filter = {"status": "completed"}
        combined_filter = {"$and": [status_filter, filter_stage]} if filter_stage else status_filter
        pipeline.insert(1, {"$match": combined_filter})

        # Final $limit: after post-filter exclusion, trim down to requested limit
        pipeline.append({"$limit": limit})

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
