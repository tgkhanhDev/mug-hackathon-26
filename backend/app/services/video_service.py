"""
Video service — business logic for video management.

Handles embedding generation, trending score calculation, and CRUD orchestration.
"""

import logging
from datetime import datetime
from typing import List, Optional

from app.models.video import VideoCreate, VideoResponse, VideoInDB, VideoListResponse
from app.repositories.video_repository import VideoRepository
from app.utils.embedding import generate_embedding, build_embed_text
from app.utils.exceptions import NotFoundException, ValidationException

logger = logging.getLogger(__name__)


class VideoService:
    """Business logic layer for videos."""

    def __init__(self):
        self._repo = VideoRepository()

    async def create_video_async(self, data: VideoCreate) -> VideoResponse:
        """
        Create a new video placeholder document asynchronously.
        Inserts it with status 'processing'.
        """
        now = datetime.utcnow()

        # Build placeholder DB document
        doc = VideoInDB(
            title=data.title,
            description=data.description,
            url="",
            thumbnail_url="",
            tags=[],
            category="",
            intensity_level="",
            status="processing",
            embedding=[],
            view_count=data.view_count,
            like_count=data.like_count,
            comment_count=data.comment_count,
            trending_score=0.0,
            creator_id=data.creator_id,
            duration=None,
            width=None,
            height=None,
            created_at=now,
            updated_at=now,
        )

        # Insert placeholder
        video_id = await self._repo.insert_one(doc.model_dump())
        logger.info(f"✅ Created video placeholder: {video_id} (status: processing)")

        # We return the response immediately
        return VideoResponse(
            id=video_id,
            title=data.title,
            description=data.description,
            url="",
            thumbnail_url="",
            tags=[],
            category="",
            intensity_level="",
            status="processing",
            view_count=data.view_count,
            like_count=data.like_count,
            comment_count=data.comment_count,
            trending_score=0.0,
            creator_id=data.creator_id,
            duration=None,
            width=None,
            height=None,
            has_embedding=False,
            created_at=now,
            updated_at=now,
        )

    async def create_video(self, data: VideoCreate) -> VideoResponse:
        """
        Create a new video document.

        1. Validate category & intensity_level enums
        2. Build embedding text from title + description + category + tags
        3. Generate embedding vector (mock or OpenAI)
        4. Calculate trending_score = view*1 + like*3 + comment*5
        5. Insert into MongoDB
        6. Return VideoResponse
        """
        from app.models.video import CATEGORY_ENUM, INTENSITY_ENUM

        # Predict category, tags, and intensity_level if missing
        if not data.category or not data.tags or not data.intensity_level:
            from app.utils.classifier import predict_all_metadata
            pred_category, pred_tags, pred_intensity = await predict_all_metadata(
                description=data.description,
                title=data.title
            )
            if not data.category:
                data.category = pred_category
            if not data.tags:
                data.tags = pred_tags
            if not data.intensity_level:
                data.intensity_level = pred_intensity

        # Validate enums
        if data.category not in CATEGORY_ENUM:
            raise ValidationException(
                f"Invalid category '{data.category}'. Must be one of: {', '.join(CATEGORY_ENUM)}"
            )
        if data.intensity_level not in INTENSITY_ENUM:
            raise ValidationException(
                f"Invalid intensity_level '{data.intensity_level}'. Must be one of: {', '.join(INTENSITY_ENUM)}"
            )

        # Build embedding
        embed_text = build_embed_text(
            title=data.title,
            description=data.description,
            category=data.category,
            tags=data.tags,
        )
        embedding = await generate_embedding(embed_text)

        # Calculate trending score
        trending_score = (
            data.view_count * 1
            + data.like_count * 3
            + data.comment_count * 5
        )

        now = datetime.utcnow()

        # Build internal document
        doc = VideoInDB(
            title=data.title,
            description=data.description,
            url=data.url,
            thumbnail_url=data.thumbnail_url,
            tags=data.tags,
            category=data.category,
            intensity_level=data.intensity_level,
            embedding=embedding,
            view_count=data.view_count,
            like_count=data.like_count,
            comment_count=data.comment_count,
            trending_score=trending_score,
            creator_id=data.creator_id,
            duration=data.duration,
            width=data.width,
            height=data.height,
            created_at=now,
            updated_at=now,
        )

        # Insert
        video_id = await self._repo.insert_one(doc.model_dump())

        logger.info(f"✅ Created video: {video_id} — {data.title}")

        return VideoResponse(
            id=video_id,
            title=data.title,
            description=data.description,
            url=data.url,
            thumbnail_url=data.thumbnail_url,
            tags=data.tags,
            category=data.category,
            intensity_level=data.intensity_level,
            view_count=data.view_count,
            like_count=data.like_count,
            comment_count=data.comment_count,
            trending_score=trending_score,
            creator_id=data.creator_id,
            duration=data.duration,
            width=data.width,
            height=data.height,
            has_embedding=len(embedding) > 0,
            created_at=now,
            updated_at=now,
        )

    async def get_video_by_id(self, video_id: str) -> VideoResponse:
        """Get a single video by ID."""
        doc = await self._repo.find_by_id(video_id)
        if not doc:
            raise NotFoundException("Video", video_id)
        return self._to_response(doc)

    async def get_videos(
        self, skip: int = 0, limit: int = 20
    ) -> VideoListResponse:
        """Get paginated list of completed videos."""
        docs = await self._repo.find_many(
            filter={"status": "completed"},
            skip=skip,
            limit=limit,
            sort=[("created_at", -1)],
        )
        total = await self._repo.count(filter={"status": "completed"})

        return VideoListResponse(
            items=[self._to_response(doc) for doc in docs],
            total=total,
            skip=skip,
            limit=limit,
        )

    async def get_trending_videos(self, limit: int = 10) -> List[VideoResponse]:
        """Get top trending videos."""
        docs = await self._repo.find_trending(limit=limit)
        return [self._to_response(doc) for doc in docs]

    async def train_classification_model(self) -> dict:
        """Fetch all video data and train/fine-tune classification model."""
        from app.utils.classifier import train_classifier
        return await train_classifier()

    @staticmethod
    def _to_response(doc: dict) -> VideoResponse:
        """Convert a MongoDB document to VideoResponse."""
        embedding = doc.get("embedding", [])
        return VideoResponse(
            id=doc["id"],
            title=doc["title"],
            description=doc["description"],
            url=doc["url"],
            thumbnail_url=doc.get("thumbnail_url", ""),
            tags=doc["tags"],
            category=doc["category"],
            intensity_level=doc["intensity_level"],
            status=doc.get("status", "completed"),
            view_count=doc.get("view_count", 0),
            like_count=doc.get("like_count", 0),
            comment_count=doc.get("comment_count", 0),
            trending_score=doc.get("trending_score", 0.0),
            creator_id=doc["creator_id"],
            duration=doc.get("duration"),
            width=doc.get("width"),
            height=doc.get("height"),
            has_embedding=len(embedding) > 0,
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        )
