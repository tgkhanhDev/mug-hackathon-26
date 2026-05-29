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

import json
import logging

from fastapi import APIRouter, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse

from app.models.behavior_log import BehaviorLogCreate, BehaviorLogResponse
from app.models.feed_session import FeedSessionCreate, FeedSessionResponse
from app.models.interaction import InteractionCreate, InteractionResponse
from app.services.interaction_service import InteractionService
from app.utils.redis import subscribe_session_events
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


@router.get(
    "/sessions/{session_id}/events",
    summary="Stream session events via SSE",
    description=(
        "Server-Sent Events endpoint that pushes real-time fatigue_score and "
        "adaptive_state updates whenever the backend recalculates session metrics. "
        "No authentication required (hackathon/demo). "
        "The stream stays open; the client must close the connection when done."
    ),
)
async def session_events_sse(session_id: str, request: Request):
    """GET /api/v1/sessions/{session_id}/events — Real-time SSE session stream."""

    async def event_generator():
        async for payload in subscribe_session_events(session_id):
            if await request.is_disconnected():
                break
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",    # Disable nginx buffering
        },
    )


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
# WebSocket — real-time video stats (1 connection per session)
# ══════════════════════════════════════════════════════════════════

@router.websocket("/ws/stats/{session_id}")
async def ws_session_stats(websocket: WebSocket, session_id: str):
    """
    WS /ws/stats/{session_id} — Single connection per user session.

    Flow:
      1. Client connects once when session starts
      2. Client sends JSON messages to subscribe/unsubscribe from video stats:
         {"action": "subscribe", "video_id": "abc123"}
         {"action": "unsubscribe", "video_id": "abc123"}
      3. When subscribing, client receives an immediate stats snapshot
      4. Whenever any user interacts with a subscribed video,
         this client receives updated counts
      5. Connection closes when session ends or client disconnects
    """
    await ws_manager.connect(session_id, websocket)

    try:
        from app.repositories.video_repository import VideoRepository
        repo = VideoRepository()

        while True:
            # Wait for subscribe/unsubscribe messages from client
            raw = await websocket.receive_text()

            try:
                import json
                msg = json.loads(raw)
                action = msg.get("action")
                video_id = msg.get("video_id")

                if not video_id:
                    continue

                if action == "subscribe":
                    ws_manager.subscribe(session_id, video_id)
                    # Send immediate stats snapshot for this video
                    video = await repo.find_by_id(video_id)
                    if video:
                        await websocket.send_json({
                            "event": "stats_snapshot",
                            "video_id": video_id,
                            "like_count": video.get("like_count", 0),
                            "view_count": video.get("view_count", 0),
                            "comment_count": video.get("comment_count", 0),
                        })

                elif action == "unsubscribe":
                    ws_manager.unsubscribe(session_id, video_id)

            except (json.JSONDecodeError, AttributeError):
                logger.debug(f"WS received non-JSON message from session={session_id}")

    except WebSocketDisconnect:
        ws_manager.disconnect(session_id)
        logger.debug(f"WS client disconnected | session={session_id}")
    except Exception as exc:
        ws_manager.disconnect(session_id)
        logger.warning(f"WS error for session={session_id}: {exc}")

