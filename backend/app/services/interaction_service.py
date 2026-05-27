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
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.behavior_log import BehaviorLogCreate, BehaviorLogInDB, BehaviorLogResponse
from app.models.feed_session import FeedSessionCreate, FeedSessionInDB, FeedSessionResponse
from app.models.interaction import (
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
from bson import ObjectId

from app.repositories.redis_client import add_seen_video

from app.utils.formula import (
    calculate_ema_vector,
    calculate_batch_ema_vector,
    calculate_fatigue_score,
    calculate_log_penalty,
    calculate_time_decay_metrics,
    determine_adaptive_state,
    get_interaction_weight,
)
from app.utils.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

# All formula constants and pure-computation functions now live in
# app.utils.formula (trending, interest_vector, fatigue sub-modules).


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
    # Interest Vector — Batch EMA update
    # ══════════════════════════════════════════════════════════════

    async def _batch_update_interest_vector(self, session_id: str, user_id: str) -> None:
        """
        Batch update user's interest_vector using Exponential Moving Average
        based on all interactions in the ended session.
        """
        try:
            interactions = await self._repo.find_by_session(session_id)
            if not interactions:
                return

            # Get unique video IDs
            video_ids = list({i["video_id"] for i in interactions})
            if not video_ids:
                return
            
            # Use find_many with $in operator
            videos = await self._video_repo.find_many({"_id": {"$in": [ObjectId(vid) for vid in video_ids if ObjectId.is_valid(vid)]}})
            video_map = {str(v.get("id", v.get("_id"))): v for v in videos}

            list_of_video_vecs = []
            list_of_weights = []

            for interaction in interactions:
                vid = interaction["video_id"]
                weight = get_interaction_weight(interaction["type"])
                
                if weight != 0.0 and vid in video_map:
                    video_vec = video_map[vid].get("embedding", [])
                    if video_vec:
                        list_of_video_vecs.append(video_vec)
                        list_of_weights.append(weight)

            if not list_of_video_vecs:
                return

            user = await self._user_repo.find_by_id(user_id)
            if not user:
                return

            current_vec: List[float] = user.get("interest_vector", [])

            if current_vec and len(current_vec) != len(list_of_video_vecs[0]):
                current_vec = []  # Reset if dimension mismatch

            new_vec = calculate_batch_ema_vector(current_vec, list_of_video_vecs, list_of_weights)

            await self._user_repo.update_interest_vector(user_id, new_vec)
            logger.info(
                f"📐 Batch Vector updated | user={user_id} | session={session_id} "
                f"| interactions={len(list_of_weights)}"
            )

        except Exception as exc:
            # Non-critical — log and continue.
            logger.error(f"Batch vector update failed for user={user_id}, session={session_id}: {exc}")

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

        # Calculate final overall session stats from all behavior logs
        logs = await self._log_repo.find_many({"session_id": session_id}, limit=2000)
        if logs:
            avg_watch_duration = sum(log.get("watch_duration", 0.0) for log in logs) / len(logs)
            avg_swipe_speed = sum(log.get("swipe_speed", 0.0) for log in logs) / len(logs)
            
            # Count unique video IDs watched in this session
            unique_video_ids = {log.get("video_id") for log in logs if log.get("video_id")}
            total_videos_watched = len(unique_video_ids)
            
            await self._session_repo.update_session_stats(session_id, {
                "avg_watch_duration": avg_watch_duration,
                "avg_swipe_speed": avg_swipe_speed,
                "total_videos_watched": total_videos_watched,
            })
            session["avg_watch_duration"] = avg_watch_duration
            session["avg_swipe_speed"] = avg_swipe_speed
            session["total_videos_watched"] = total_videos_watched

        await self._session_repo.end_session(session_id)
        session["ended_at"] = datetime.utcnow()
        
        # Trigger batch update of interest vector in the background
        asyncio.create_task(
            self._batch_update_interest_vector(session_id, session["user_id"])
        )
        
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
        Non-blocking: Immediately returns 201 Created and pushes DB insert to background.
        """
        now = datetime.utcnow()
        log_id = str(ObjectId())

        # ✅ FIX RACE CONDITION: Write seen_id to Redis BEFORE returning 201
        # This ensures GET /feed sees this video_id immediately (~1ms),
        # even though the MongoDB insert happens asynchronously in the background.
        await add_seen_video(data.session_id, data.video_id)

        # Fire and forget the actual insertion and metric updates
        asyncio.create_task(self._process_behavior_log_background(data, log_id, now))

        # Return immediately to client to prevent blocking
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
            consecutive_same_topic=0,  # Computed in background, return default for speed
        )

    async def _process_behavior_log_background(self, data: BehaviorLogCreate, log_id: str, now: datetime) -> None:
        """Background worker for behavior logs."""
        try:
            # 1. Calculate consecutive topics
            consecutive = await self._log_repo.get_consecutive_topic_count(
                data.session_id, data.topic, limit=10
            )

            # 2. Insert to DB
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
            
            log_dict = log_doc.model_dump()
            log_dict["_id"] = ObjectId(log_id)
            await self._log_repo.insert_one(log_dict)

            # 3. Update session metrics pipeline
            await self._update_session_metrics_pipeline(data.session_id, data.video_id)
        except Exception as exc:
            logger.error(f"Failed to process behavior log in background (id={log_id}): {exc}")

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

            # Compute per-log penalties via formula module
            log_penalties = [
                calculate_log_penalty(
                    watch_duration=log.get("watch_duration", 0.0),
                    swipe_speed=log.get("swipe_speed", 0.0),
                    is_interaction=log.get("is_interaction", False),
                    consecutive_same_topic=log.get("consecutive_same_topic", 0),
                )
                for log in logs
            ]

            high_count = session.get("high_intensity_count", 0)
            low_count = session.get("low_intensity_count", 0)

            fatigue_score = calculate_fatigue_score(log_penalties, high_count, low_count)
            adaptive_state = determine_adaptive_state(fatigue_score)

            stats = {
                "fatigue_score": fatigue_score,
                "adaptive_state": adaptive_state,
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
          2. Apply time-decay via :func:`calculate_time_decay_metrics`
          3. Sort by effective_score, return top N
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
            raw_score = video.get("trending_score", 0.0)

            metrics = calculate_time_decay_metrics(
                now=now,
                created_at=video.get("created_at", now),
                category=video.get("category", "_default"),
                raw_score=raw_score,
                view_count=video.get("view_count", 0),
                snapshot_at=video.get("snapshot_at"),
                snapshot_views=video.get("view_count_snapshot", 0),
                window_days=window_days,
            )

            enriched.append({
                **video,
                "raw_score": raw_score,
                **metrics,
            })

        # Re-sort by effective score (time-decayed)
        enriched.sort(key=lambda v: v["effective_score"], reverse=True)
        return enriched[:limit]

    # ══════════════════════════════════════════════════════════════
    # User vector status (diagnostic)
    # ══════════════════════════════════════════════════════════════

    async def get_user_vector_status(self, user_id: str) -> Dict[str, Any]:
        """Return a summary of the user's interest_vector (for debug/UI)."""
        import math

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
