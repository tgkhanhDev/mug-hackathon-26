"""
Interaction controller — API routes for:
  - Interactions (like/skip/comment/replay/share)
  - Feed sessions (start/end)
  - Behavior logs (raw per-video tracking)
  - Trending videos with time-decay
  - User vector status (diagnostic)
  - WebSocket /ws/stats/{video_id} (real-time counters)

Thin layer: validates request → calls service → returns response.
"""

import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.models.behavior_log import BehaviorLogCreate, BehaviorLogResponse
from app.models.feed_session import FeedSessionCreate, FeedSessionResponse
from app.models.interaction import InteractionCreate, InteractionResponse
from app.services.interaction_service import InteractionService
from app.utils.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Interactions"])


# ══════════════════════════════════════════════════════════════════
# Interactions — business events (like, skip, replay, comment, share)
# ══════════════════════════════════════════════════════════════════

@router.post(
    "/interactions",
    response_model=InteractionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record an interaction event",
    description=(
        "Log a user interaction (like/skip/comment/replay/share). "
        "Side effects: increments video counters, updates user interest_vector "
        "(EMA), and broadcasts real-time stats via WebSocket."
    ),
)
async def create_interaction(data: InteractionCreate):
    """POST /api/v1/interactions — Record a user interaction."""
    service = InteractionService()
    return await service.record_interaction(data)


# ══════════════════════════════════════════════════════════════════
# Feed Sessions — lifecycle
# ══════════════════════════════════════════════════════════════════

@router.post(
    "/sessions",
    response_model=FeedSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new feed session",
    description=(
        "Create a new feed session when the user opens the app. "
        "If an active session already exists, returns the existing one."
    ),
)
async def create_session(data: FeedSessionCreate):
    """POST /api/v1/sessions — Start a feed session."""
    service = InteractionService()
    return await service.create_session(data)


@router.get(
    "/sessions/{session_id}",
    response_model=FeedSessionResponse,
    summary="Get session details",
    description="Retrieve a feed session by its MongoDB ObjectId.",
)
async def get_session(session_id: str):
    """GET /api/v1/sessions/{session_id} — Get session details."""
    service = InteractionService()
    return await service.get_session(session_id)


@router.put(
    "/sessions/{session_id}/end",
    response_model=FeedSessionResponse,
    summary="End a feed session",
    description="Mark a feed session as ended (sets ended_at = now).",
)
async def end_session(session_id: str):
    """PUT /api/v1/sessions/{session_id}/end — End a session."""
    service = InteractionService()
    return await service.end_session(session_id)


# ══════════════════════════════════════════════════════════════════
# Behavior Logs — raw per-video passive tracking
# ══════════════════════════════════════════════════════════════════

@router.post(
    "/behavior-logs",
    response_model=BehaviorLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record raw behavior log",
    description=(
        "Log raw per-video behavior (swipe_speed, watch_duration, etc.) "
        "for fatigue score calculation. Does NOT update user interest_vector."
    ),
)
async def create_behavior_log(data: BehaviorLogCreate):
    """POST /api/v1/behavior-logs — Record a behavior log entry."""
    service = InteractionService()
    return await service.record_behavior_log(data)


# ══════════════════════════════════════════════════════════════════
# Trending — with time-decay
# ══════════════════════════════════════════════════════════════════

@router.get(
    "/videos/trending-decay",
    summary="Get trending videos with time-decay",
    description=(
        "Trending videos re-ranked with exponential time-decay. "
        "Videos that are old and no longer gaining engagement are demoted. "
        "Each video includes effective_score, decay_factor, velocity_7d, and is_trending."
    ),
)
async def get_trending_with_decay(
    limit: int = Query(default=10, ge=1, le=50, description="Number of trending videos"),
    window_days: int = Query(default=7, ge=1, le=90, description="Trend window in days"),
):
    """GET /api/v1/videos/trending-decay — Trending with time-decay."""
    service = InteractionService()
    return await service.get_trending_videos(limit=limit, window_days=window_days)


# ══════════════════════════════════════════════════════════════════
# User Vector Status (diagnostic)
# ══════════════════════════════════════════════════════════════════

@router.get(
    "/users/{user_id}/vector-status",
    summary="Check user interest vector status",
    description=(
        "Diagnostic endpoint: shows dimensions, magnitude, and freshness "
        "of the user's interest_vector. Useful for debugging recommendations."
    ),
)
async def get_vector_status(user_id: str):
    """GET /api/v1/users/{user_id}/vector-status — Vector status."""
    service = InteractionService()
    return await service.get_user_vector_status(user_id)


# ══════════════════════════════════════════════════════════════════
# WebSocket — real-time video stats
# ══════════════════════════════════════════════════════════════════

@router.websocket("/ws/stats/{video_id}")
async def ws_video_stats(websocket: WebSocket, video_id: str):
    """
    WS /ws/stats/{video_id} — Real-time like/view/comment counts.

    Flow:
      1. Client connects → receives current stats snapshot immediately
      2. Whenever any user likes/views/comments this video:
         → all subscribed clients receive updated counts
      3. Client disconnects when scrolling past the video
    """
    await ws_manager.connect(video_id, websocket)

    try:
        # Send initial snapshot
        from app.repositories.video_repository import VideoRepository
        repo = VideoRepository()
        video = await repo.find_by_id(video_id)

        if video:
            await websocket.send_json({
                "event": "stats_snapshot",
                "video_id": video_id,
                "like_count": video.get("like_count", 0),
                "view_count": video.get("view_count", 0),
                "comment_count": video.get("comment_count", 0),
            })

        # Keep connection alive — wait for client disconnect
        while True:
            # We don't expect messages FROM the client,
            # but we must await to detect disconnection.
            await websocket.receive_text()

    except WebSocketDisconnect:
        ws_manager.disconnect(video_id, websocket)
        logger.debug(f"WS client disconnected from video={video_id}")
    except Exception as exc:
        ws_manager.disconnect(video_id, websocket)
        logger.warning(f"WS error for video={video_id}: {exc}")
