"""
User service — business logic for user management.

Handles user creation (onboarding), interest vector initialization.
"""

import logging
from datetime import datetime
from typing import List

from app.models.user import UserCreate, UserResponse, UserInDB, UserListResponse
from app.repositories.user_repository import UserRepository
from app.repositories.video_repository import VideoRepository
from app.utils.embedding import generate_embedding
from app.utils.exceptions import (
    DuplicateException,
    NotFoundException,
    ValidationException,
)

logger = logging.getLogger(__name__)


class UserService:
    """Business logic layer for users."""

    def __init__(self):
        self._repo = UserRepository()
        self._video_repo = VideoRepository()

    async def create_user(self, data: UserCreate) -> UserResponse:
        """
        Create a new user (onboarding flow).

        1. Check username uniqueness
        2. Compute initial interest_vector = average embedding of videos matching interest_tags
        3. If no matching videos, generate embedding from tags text
        4. Insert into MongoDB
        """
        # Check duplicate
        existing = await self._repo.find_by_username(data.username)
        if existing:
            raise DuplicateException("User", "username")

        # Compute initial interest_vector from matching videos
        interest_vector = await self._compute_initial_vector(data.interest_tags)

        now = datetime.utcnow()

        doc = UserInDB(
            username=data.username,
            email=data.email,
            interest_tags=data.interest_tags,
            interest_vector=interest_vector,
            created_at=now,
            updated_at=now,
        )

        user_id = await self._repo.insert_one(doc.model_dump())
        logger.info(f"✅ Created user: {user_id} — {data.username}")

        return UserResponse(
            id=user_id,
            username=data.username,
            email=data.email,
            interest_tags=data.interest_tags,
            has_interest_vector=len(interest_vector) > 0,
            created_at=now,
            updated_at=now,
        )

    async def get_user_by_id(self, user_id: str) -> UserResponse:
        """Get a single user by ID."""
        doc = await self._repo.find_by_id(user_id)
        if not doc:
            raise NotFoundException("User", user_id)
        return self._to_response(doc)

    async def get_users(self, skip: int = 0, limit: int = 20) -> UserListResponse:
        """Get paginated list of users."""
        docs = await self._repo.find_many(skip=skip, limit=limit, sort=[("created_at", -1)])
        total = await self._repo.count()
        return UserListResponse(
            items=[self._to_response(doc) for doc in docs],
            total=total,
            skip=skip,
            limit=limit,
        )

    async def _compute_initial_vector(self, interest_tags: List[str]) -> List[float]:
        """
        Compute the initial interest_vector for a new user.

        Strategy:
        1. Find videos matching any of the user's interest_tags
        2. Average their embedding vectors
        3. If no videos found, generate embedding from tag text as fallback
        """
        import math
        videos = await self._video_repo.find_by_tags(interest_tags, limit=20)

        # Filter videos that have embeddings
        embeddings = [v["embedding"] for v in videos if v.get("embedding")]

        if embeddings:
            # Average the embedding vectors
            dim = len(embeddings[0])
            avg_vector = [0.0] * dim
            for emb in embeddings:
                for i in range(dim):
                    avg_vector[i] += emb[i]
            avg_vector = [x / len(embeddings) for x in avg_vector]
            
            # L2-normalize the averaged vector
            magnitude = math.sqrt(sum(x * x for x in avg_vector))
            if magnitude > 0:
                avg_vector = [x / magnitude for x in avg_vector]
                
            logger.info(
                f"  📐 Initial vector from {len(embeddings)} matching videos (L2-normalized)"
            )
            return avg_vector

        # Fallback: generate embedding from tag text
        tag_text = f"User interests: {', '.join(interest_tags)}"
        fallback_vector = await generate_embedding(tag_text)
        
        # L2-normalize the fallback vector
        magnitude = math.sqrt(sum(x * x for x in fallback_vector))
        if magnitude > 0:
            fallback_vector = [x / magnitude for x in fallback_vector]
            
        logger.info("  📐 Initial vector from tag text (no matching videos, L2-normalized)")
        return fallback_vector

    @staticmethod
    def _to_response(doc: dict) -> UserResponse:
        """Convert a MongoDB document to UserResponse."""
        interest_vector = doc.get("interest_vector", [])
        return UserResponse(
            id=doc["id"],
            username=doc["username"],
            email=doc.get("email", ""),
            interest_tags=doc["interest_tags"],
            has_interest_vector=len(interest_vector) > 0,
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        )
