"""
WebSocket Manager — Real-time video stats broadcaster.

Architecture: ONE WebSocket per user session (not per video).
The client sends subscribe/unsubscribe messages to indicate which
video they are currently watching. Stats updates are pushed only
for subscribed videos.

Design: Singleton in-process dict — no Redis needed at hackathon scale.
"""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Dict, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class VideoStatsWSManager:
    """
    Manages WebSocket connections grouped by session.

    Frontend connects ONCE when session starts, disconnects when session ends.
    Client sends JSON messages to subscribe/unsubscribe from video stats:
      {"action": "subscribe", "video_id": "abc123"}
      {"action": "unsubscribe", "video_id": "abc123"}
    Backend broadcasts stats updates to all sessions subscribed to that video.
    """

    def __init__(self):
        # session_id → WebSocket connection
        self._sessions: Dict[str, WebSocket] = {}
        # video_id → set of session_ids currently watching
        self._subscriptions: Dict[str, Set[str]] = defaultdict(set)
        # session_id → set of video_ids this session is subscribed to
        self._session_subs: Dict[str, Set[str]] = defaultdict(set)

    # ── Connection lifecycle ───────────────────────────────────────

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        """Accept and register a new session-level WebSocket connection."""
        await ws.accept()
        # Close existing connection for this session if any
        old_ws = self._sessions.get(session_id)
        if old_ws:
            try:
                await old_ws.close()
            except Exception:
                pass
            self._cleanup_session(session_id)
        self._sessions[session_id] = ws
        logger.debug(f"WS session connected | session={session_id} | total_sessions={len(self._sessions)}")

    def disconnect(self, session_id: str) -> None:
        """Remove a session WebSocket and all its subscriptions."""
        self._cleanup_session(session_id)
        self._sessions.pop(session_id, None)
        logger.debug(f"WS session disconnect | session={session_id}")

    def _cleanup_session(self, session_id: str) -> None:
        """Remove all video subscriptions for a session."""
        video_ids = self._session_subs.pop(session_id, set())
        for vid in video_ids:
            self._subscriptions[vid].discard(session_id)
            if not self._subscriptions[vid]:
                del self._subscriptions[vid]

    # ── Subscription management ────────────────────────────────────

    def subscribe(self, session_id: str, video_id: str) -> None:
        """Subscribe a session to stats updates for a specific video."""
        self._subscriptions[video_id].add(session_id)
        self._session_subs[session_id].add(video_id)
        logger.debug(f"WS subscribe  | session={session_id} → video={video_id}")

    def unsubscribe(self, session_id: str, video_id: str) -> None:
        """Unsubscribe a session from stats updates for a specific video."""
        self._subscriptions[video_id].discard(session_id)
        if not self._subscriptions[video_id]:
            del self._subscriptions[video_id]
        self._session_subs[session_id].discard(video_id)
        logger.debug(f"WS unsubscribe | session={session_id} ✕ video={video_id}")

    # ── Broadcasting ──────────────────────────────────────────────

    async def broadcast_stats(self, video_id: str, stats: Dict[str, Any]) -> None:
        """
        Push updated stats to all sessions currently subscribed to this video.

        stats format:
            {
              "like_count": 542,
              "view_count": 3201,
              "comment_count": 88,
            }
        """
        session_ids = self._subscriptions.get(video_id, set())
        if not session_ids:
            return

        dead: Set[str] = set()
        payload = {"event": "stats_update", "video_id": video_id, **stats}

        # Fire-and-forget to all subscribed sessions concurrently
        tasks = []
        session_list = list(session_ids)
        for sid in session_list:
            ws = self._sessions.get(sid)
            if ws:
                tasks.append(ws.send_json(payload))
            else:
                dead.add(sid)

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for sid, result in zip(
                [s for s in session_list if s not in dead], results
            ):
                if isinstance(result, Exception):
                    logger.warning(f"WS send failed for session={sid}: {result}")
                    dead.add(sid)

        for sid in dead:
            self.disconnect(sid)

        alive = len(session_ids) - len(dead)
        if alive > 0:
            logger.debug(
                f"WS broadcast  | video={video_id} "
                f"| sessions={alive} | {stats}"
            )

    # ── Diagnostics ───────────────────────────────────────────────

    def active_session_count(self) -> int:
        """Number of sessions that have an active WebSocket connection."""
        return len(self._sessions)

    def active_video_count(self) -> int:
        """Number of videos that currently have at least 1 subscriber."""
        return len(self._subscriptions)

    def subscriber_count(self, video_id: str) -> int:
        """Number of sessions subscribed to a specific video."""
        return len(self._subscriptions.get(video_id, set()))


# ── Singleton instance ─────────────────────────────────────────────
ws_manager = VideoStatsWSManager()
