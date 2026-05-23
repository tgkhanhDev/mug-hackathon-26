"""
Interaction service — business logic for all user interaction events.

Responsibilities:
  1. Persist interaction events (like/skip/replay/comment/share)
  2. Atomically increment video counters (view/like/comment)
  3. Update user interest_vector via Exponential Moving Average (EMA)
  4. Broadcast real-time stats via WebSocket
  5. Manage feed sessions lifecycle
  6. Record raw behavior logs for fatigue calculation
  7. Compute time-decay trending scores
"""

import asyncio
import logging
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.models.behavior_log import BehaviorLogCreate, BehaviorLogInDB, BehaviorLogResponse
from app.models.feed_session import FeedSessionCreate, FeedSessionInDB, FeedSessionResponse
from app.models.interaction import (
    INTERACTION_WEIGHTS,
    INTERACTION_TYPES,
    InteractionCreate,
    InteractionInDB,
    InteractionResponse,
)
from app.repositories.behavior_log_repository import BehaviorLogRepository
from app.repositories.feed_session_repository import FeedSessionRepository
from app.repositories.interaction_repository import InteractionRepository
from app.repositories.user_repository import UserRepository
from app.repositories.video_repository import VideoRepository
from app.utils.exceptions import NotFoundException, ValidationException
from app.utils.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────
# EMA momentum: how much we preserve the existing vector
# 0.85 = keep 85% old, blend 15% new signal
EMA_MOMENTUM = 0.85

# Time-decay half-life in hours, per video category
HALF_LIFE_HOURS: Dict[str, float] = {
    "entertainment": 168.0,   # 7 days
    "sports":        120.0,   # 5 days
    "gaming":        168.0,   # 7 days
    "lifestyle":     336.0,   # 14 days
    "education":     720.0,   # 30 days
    "calming":       720.0,   # 30 days
    "nature":        720.0,   # 30 days
    "cooking":       336.0,   # 14 days
    "_default":      168.0,   # 7 days fallback
}

# Minimum views/day for a video to still be considered "trending"
MIN_VELOCITY_VIEWS_PER_DAY = 10


class InteractionService:
    """Business logic layer for all interaction-related operations."""

    def __init__(self):
        self._repo = InteractionRepository()
        self._session_repo = FeedSessionRepository()
        self._log_repo = BehaviorLogRepository()
        self._user_repo = UserRepository()
        self._video_repo = VideoRepository()

    # ══════════════════════════════════════════════════════════════
    # Interaction — record event + side effects
    # ══════════════════════════════════════════════════════════════

    async def record_interaction(self, data: InteractionCreate) -> InteractionResponse:
        """
        Main entry point: persist 1 interaction event and trigger all side effects.

        Side effects (run in parallel via asyncio.gather):
          ① Insert interaction document
          ② Increment video counters (atomic pipeline update)
          ③ Update user interest_vector (EMA)
          ④ Increment session.total_videos_watched
          ⑤ Broadcast updated stats via WebSocket
        """
        if data.type not in INTERACTION_TYPES:
            raise ValidationException(
                f"Invalid interaction type '{data.type}'. "
                f"Must be one of: {', '.join(INTERACTION_TYPES)}"
            )

        # Validate foreign keys exist
        user = await self._user_repo.find_by_id(data.user_id)
        if not user:
            raise NotFoundException("User", data.user_id)

        video = await self._video_repo.find_by_id(data.video_id)
        if not video:
            raise NotFoundException("Video", data.video_id)

        now = datetime.utcnow()
        doc = InteractionInDB(
            user_id=data.user_id,
            video_id=data.video_id,
            session_id=data.session_id,
            type=data.type,
            watch_duration=data.watch_duration,
            watch_percentage=data.watch_percentage,
            swipe_speed=data.swipe_speed,
            replay_count=data.replay_count,
            timestamp=now,
        )

        # ── Run all side effects in parallel ──────────────────────
        interaction_id, *_ = await asyncio.gather(
            self._repo.insert_one(doc.model_dump()),
            self._repo.increment_video_counters(data.video_id, data.type),
            self._update_interest_vector(data.user_id, data.video_id, data.type, video),
            self._session_repo.increment_videos_watched(data.session_id),
        )

        logger.info(
            f"✅ Interaction | user={data.user_id} | video={data.video_id} "
            f"| type={data.type} | id={interaction_id}"
        )

        # Fetch fresh counts after increment then broadcast
        # (non-blocking — fire and forget the WS broadcast)
        asyncio.create_task(
            self._broadcast_video_stats(data.video_id)
        )

        return InteractionResponse(
            id=interaction_id,
            user_id=data.user_id,
            video_id=data.video_id,
            session_id=data.session_id,
            type=data.type,
            watch_duration=data.watch_duration,
            watch_percentage=data.watch_percentage,
            swipe_speed=data.swipe_speed,
            replay_count=data.replay_count,
            timestamp=now,
        )

    # ══════════════════════════════════════════════════════════════
    # Interest Vector — EMA update
    # ══════════════════════════════════════════════════════════════

    async def _update_interest_vector(
        self,
        user_id: str,
        video_id: str,
        interaction_type: str,
        video: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Update user's interest_vector using Exponential Moving Average.

        Formula:
            new_vec = α * current_vec + (1-α) * weight * video_embedding
            then L2-normalize for cosine similarity correctness.

        α = EMA_MOMENTUM = 0.85
        weight = INTERACTION_WEIGHTS[type]  (like=1.0, skip=-0.3, ...)
        """
        weight = INTERACTION_WEIGHTS.get(interaction_type, 0.0)
        if weight == 0.0:
            return  # Neutral signal — no update needed

        try:
            # Fetch in parallel if video not already passed
            if video is None:
                user, video = await asyncio.gather(
                    self._user_repo.find_by_id(user_id),
                    self._video_repo.find_by_id(video_id),
                )
            else:
                user = await self._user_repo.find_by_id(user_id)

            if not user or not video:
                return

            current_vec: List[float] = user.get("interest_vector", [])
            video_vec: List[float] = video.get("embedding", [])

            if not video_vec:
                logger.debug(f"Video {video_id} has no embedding — skipping vector update")
                return

            if not current_vec or len(current_vec) != len(video_vec):
                # No existing vector or dimension mismatch — use video embedding as-is
                current_vec = video_vec

            α = EMA_MOMENTUM
            new_vec = [
                α * c + (1.0 - α) * weight * v
                for c, v in zip(current_vec, video_vec)
            ]

            # L2-normalize so cosine distance works correctly in $vectorSearch
            magnitude = math.sqrt(sum(x * x for x in new_vec))
            if magnitude > 0:
                new_vec = [x / magnitude for x in new_vec]

            await self._user_repo.update_interest_vector(user_id, new_vec)
            logger.debug(
                f"📐 Vector updated | user={user_id} | type={interaction_type} "
                f"| weight={weight} | α={α}"
            )

        except Exception as exc:
            # Non-critical — log and continue. Don't fail the whole interaction.
            logger.error(f"Vector update failed for user={user_id}: {exc}")

    # ══════════════════════════════════════════════════════════════
    # WebSocket — broadcast fresh stats
    # ══════════════════════════════════════════════════════════════

    async def _broadcast_video_stats(self, video_id: str) -> None:
        """Fetch latest video counters and push to all WS subscribers."""
        try:
            video = await self._video_repo.find_by_id(video_id)
            if not video:
                return
            await ws_manager.broadcast_stats(
                video_id,
                {
                    "like_count": video.get("like_count", 0),
                    "view_count": video.get("view_count", 0),
                    "comment_count": video.get("comment_count", 0),
                },
            )
        except Exception as exc:
            logger.warning(f"WS broadcast failed for video={video_id}: {exc}")

    # ══════════════════════════════════════════════════════════════
    # Feed Session — lifecycle
    # ══════════════════════════════════════════════════════════════

    async def create_session(self, data: FeedSessionCreate) -> FeedSessionResponse:
        """
        Start a new feed session for a user.
        If an active session already exists (ended_at=null), return it.
        """
        # Check for existing active session
        existing = await self._session_repo.find_active_session(data.user_id)
        if existing:
            logger.info(f"Reusing active session {existing['id']} for user={data.user_id}")
            return self._session_to_response(existing)

        now = datetime.utcnow()
        doc = FeedSessionInDB(user_id=data.user_id, started_at=now)
        session_id = await self._session_repo.insert_one(doc.model_dump())
        logger.info(f"✅ New session {session_id} for user={data.user_id}")

        return FeedSessionResponse(
            id=session_id,
            user_id=data.user_id,
            started_at=now,
        )

    async def end_session(self, session_id: str) -> FeedSessionResponse:
        """Mark a session as ended (sets ended_at = now)."""
        session = await self._session_repo.find_by_id(session_id)
        if not session:
            raise NotFoundException("FeedSession", session_id)

        await self._session_repo.end_session(session_id)
        session["ended_at"] = datetime.utcnow()
        return self._session_to_response(session)

    async def get_session(self, session_id: str) -> FeedSessionResponse:
        """Get a feed session by ID."""
        session = await self._session_repo.find_by_id(session_id)
        if not session:
            raise NotFoundException("FeedSession", session_id)
        return self._session_to_response(session)

    # ══════════════════════════════════════════════════════════════
    # Behavior Log — raw per-video passive tracking
    # ══════════════════════════════════════════════════════════════

    async def record_behavior_log(self, data: BehaviorLogCreate) -> BehaviorLogResponse:
        """
        Record raw behavior for a single video view.
        Used by fatigue engine — does NOT update interest_vector.

        Also updates session intensity counters if video intensity is known.
        """
        # Lookup consecutive same-topic count from recent logs
        consecutive = await self._log_repo.get_consecutive_topic_count(
            data.session_id, data.topic, limit=10
        )

        now = datetime.utcnow()
        log_doc = BehaviorLogInDB(
            user_id=data.user_id,
            session_id=data.session_id,
            video_id=data.video_id,
            timestamp=now,
            swipe_speed=data.swipe_speed,
            watch_duration=data.watch_duration,
            is_interaction=data.is_interaction,
            topic=data.topic,
            consecutive_same_topic=consecutive,
        )

        log_id = await self._log_repo.insert_one(log_doc.model_dump())

        # Update session intensity counters and calculate fatigue (fire-and-forget)
        asyncio.create_task(
            self._update_session_metrics_pipeline(data.session_id, data.video_id)
        )

        return BehaviorLogResponse(
            id=log_id,
            user_id=data.user_id,
            session_id=data.session_id,
            video_id=data.video_id,
            timestamp=now,
            swipe_speed=data.swipe_speed,
            watch_duration=data.watch_duration,
            is_interaction=data.is_interaction,
            topic=data.topic,
            consecutive_same_topic=consecutive,
        )

    async def _update_session_metrics_pipeline(self, session_id: str, video_id: str) -> None:
        """Update session intensity counters first, then compute fatigue score and state."""
        try:
            # 1. Update intensity count
            await self._update_session_intensity(session_id, video_id)
            # 2. Update fatigue and state
            await self._update_session_fatigue_and_state(session_id)
        except Exception as exc:
            logger.error(f"Error in session metrics pipeline: {exc}")

    async def _update_session_intensity(self, session_id: str, video_id: str) -> None:
        """Update high/low intensity counts for the session based on video's intensity_level."""
        try:
            video = await self._video_repo.find_by_id(video_id)
            if video and video.get("intensity_level"):
                await self._session_repo.update_intensity_count(
                    session_id, video["intensity_level"]
                )
        except Exception as exc:
            logger.warning(f"Intensity count update failed: {exc}")

    async def _update_session_fatigue_and_state(self, session_id: str) -> None:
        """
        Calculate fatigue score based on the last 10 behavior logs
        and transition the session's adaptive state.
        """
        try:
            if not session_id:
                return

            # Fetch session to get dopamine intensity counters
            session = await self._session_repo.find_by_id(session_id)
            if not session:
                return

            # Get the 10 most recent behavior logs
            logs = await self._log_repo.get_recent_logs(session_id, limit=10)
            if not logs:
                return

            log_points_list = []
            for log in logs:
                # 1. Watch duration penalty
                watch_dur = log.get("watch_duration", 0.0)
                if watch_dur < 2.0:
                    duration_penalty = 30
                elif watch_dur < 5.0:
                    duration_penalty = 15
                elif watch_dur < 15.0:
                    duration_penalty = 5
                else:
                    duration_penalty = 0

                # 2. Swipe speed penalty
                swipe_spd = log.get("swipe_speed", 0.0)
                if swipe_spd > 800.0:
                    swipe_penalty = 20
                elif swipe_spd > 400.0:
                    swipe_penalty = 10
                else:
                    swipe_penalty = 0

                # 3. Passive scroll penalty
                passive_penalty = 15 if not log.get("is_interaction", False) else 0

                # 4. Consecutive topic penalty
                consecutive_count = log.get("consecutive_same_topic", 0) + 1
                if consecutive_count >= 5:
                    consecutive_penalty = 25
                elif consecutive_count >= 3:
                    consecutive_penalty = 15
                else:
                    consecutive_penalty = 0

                log_points_list.append(duration_penalty + swipe_penalty + passive_penalty + consecutive_penalty)

            avg_log_points = sum(log_points_list) / len(logs)

            # Dopamine Intensity Penalty
            high_count = session.get("high_intensity_count", 0)
            low_count = session.get("low_intensity_count", 0)
            total_intensity_count = high_count + low_count
            dopamine_penalty = 10.0 * (high_count / total_intensity_count) if total_intensity_count > 0 else 0.0

            fatigue_score = min(100.0, max(0.0, avg_log_points + dopamine_penalty))

            # Calculate averages for logging/storing
            avg_watch_duration = sum(log.get("watch_duration", 0.0) for log in logs) / len(logs)
            avg_swipe_speed = sum(log.get("swipe_speed", 0.0) for log in logs) / len(logs)

            # Adaptive State Machine
            if fatigue_score < 40.0:
                adaptive_state = "normal"
            elif fatigue_score <= 70.0:
                adaptive_state = "warning"
            else:
                adaptive_state = "exhausted"

            stats = {
                "fatigue_score": fatigue_score,
                "adaptive_state": adaptive_state,
                "avg_watch_duration": avg_watch_duration,
                "avg_swipe_speed": avg_swipe_speed,
                "updated_at": datetime.utcnow()
            }
            await self._session_repo.update_session_stats(session_id, stats)
            logger.info(f"Updated session {session_id} fatigue: {fatigue_score:.2f} | state: {adaptive_state}")

        except Exception as exc:
            logger.error(f"Failed to calculate fatigue for session {session_id}: {exc}")

    # ══════════════════════════════════════════════════════════════
    # Trending — Time-Decay Score
    # ══════════════════════════════════════════════════════════════

    async def get_trending_videos(
        self,
        limit: int = 10,
        window_days: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        Return trending videos with time-decay applied.

        Algorithm:
          1. Fetch top N*3 videos by raw trending_score
          2. Apply time-decay: effective_score = raw_score * e^(-λ * age_hours)
             λ = ln(2) / half_life_hours   (category-specific)
          3. Mark videos as is_trending=False if velocity < threshold
          4. Sort by effective_score, return top N

        This naturally demotes "zombie" videos that accumulated high raw scores
        long ago but are no longer generating fresh engagement.
        """
        # Fetch a wider candidate pool for re-ranking
        candidates = await self._video_repo.find_many(
            filter={},
            limit=limit * 3,
            sort=[("trending_score", -1)],
        )

        now = datetime.utcnow()
        enriched = []

        for video in candidates:
            created_at: datetime = video.get("created_at", now)
            age_hours = max(0.0, (now - created_at).total_seconds() / 3600)

            category = video.get("category", "_default")
            half_life = HALF_LIFE_HOURS.get(category, HALF_LIFE_HOURS["_default"])

            # Decay constant λ = ln(2) / half_life
            lam = math.log(2) / half_life
            decay_factor = math.exp(-lam * age_hours)

            raw_score = video.get("trending_score", 0.0)
            effective_score = raw_score * decay_factor

            # Velocity check: views/day from snapshot
            # Use view_count_snapshot + snapshot_at if available (set by scheduler)
            # Fallback: assume uniform distribution over age
            snapshot_views = video.get("view_count_snapshot", 0)
            snapshot_at: Optional[datetime] = video.get("snapshot_at")
            view_count = video.get("view_count", 0)

            if snapshot_at and snapshot_views is not None:
                elapsed_days = max(
                    0.01,
                    (now - snapshot_at).total_seconds() / 86400,
                )
                velocity_7d = (view_count - snapshot_views) / elapsed_days
            elif age_hours > 0:
                velocity_7d = view_count / (age_hours / 24)
            else:
                velocity_7d = view_count

            # A video is out-of-trend if growth velocity is below threshold
            # OR if it's older than window_days and its effective score is low
            is_trending = (
                velocity_7d >= MIN_VELOCITY_VIEWS_PER_DAY
                and age_hours <= window_days * 24 * 4  # generous 4x window
            )

            enriched.append({
                **video,
                "raw_score": raw_score,
                "effective_score": round(effective_score, 2),
                "age_hours": round(age_hours, 1),
                "decay_factor": round(decay_factor, 4),
                "velocity_7d": round(velocity_7d, 1),
                "is_trending": is_trending,
            })

        # Re-sort by effective score (time-decayed)
        enriched.sort(key=lambda v: v["effective_score"], reverse=True)
        return enriched[:limit]

    # ══════════════════════════════════════════════════════════════
    # User vector status (diagnostic)
    # ══════════════════════════════════════════════════════════════

    async def get_user_vector_status(self, user_id: str) -> Dict[str, Any]:
        """Return a summary of the user's interest_vector (for debug/UI)."""
        user = await self._user_repo.find_by_id(user_id)
        if not user:
            raise NotFoundException("User", user_id)

        vec = user.get("interest_vector", [])
        magnitude = math.sqrt(sum(x * x for x in vec)) if vec else 0.0

        return {
            "user_id": user_id,
            "username": user.get("username"),
            "interest_tags": user.get("interest_tags", []),
            "vector_dimensions": len(vec),
            "vector_magnitude": round(magnitude, 6),
            "has_vector": len(vec) > 0,
            "updated_at": user.get("updated_at"),
        }

    # ══════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════

    @staticmethod
    def _session_to_response(doc: Dict[str, Any]) -> FeedSessionResponse:
        return FeedSessionResponse(
            id=doc["id"],
            user_id=doc["user_id"],
            started_at=doc["started_at"],
            ended_at=doc.get("ended_at"),
            total_videos_watched=doc.get("total_videos_watched", 0),
            fatigue_score=doc.get("fatigue_score", 0.0),
            adaptive_state=doc.get("adaptive_state", "normal"),
            high_intensity_count=doc.get("high_intensity_count", 0),
            low_intensity_count=doc.get("low_intensity_count", 0),
            avg_watch_duration=doc.get("avg_watch_duration", 0.0),
            avg_swipe_speed=doc.get("avg_swipe_speed", 0.0),
        )
