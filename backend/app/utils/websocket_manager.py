"""
WebSocket Manager — Real-time video stats broadcaster.

Manages per-video WebSocket channels so multiple clients watching
the same video receive live like/view/comment count updates.

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
    Manages WebSocket connections grouped by video_id.

    Frontend connects when a video enters the viewport,
    disconnects when scrolling to the next clip.
    Backend broadcasts stats updates after every interaction event.
    """

    def __init__(self):
        # video_id → set of active WebSocket connections
        self._connections: Dict[str, Set[WebSocket]] = defaultdict(set)

    # ── Connection lifecycle ───────────────────────────────────────

    async def connect(self, video_id: str, ws: WebSocket) -> None:
        """Accept and register a new WebSocket connection for a video."""
        await ws.accept()
        self._connections[video_id].add(ws)
        logger.debug(
            f"WS connected  | video={video_id} | "
            f"total={len(self._connections[video_id])}"
        )

    def disconnect(self, video_id: str, ws: WebSocket) -> None:
        """Remove a WebSocket connection (called on client disconnect)."""
        self._connections[video_id].discard(ws)
        if not self._connections[video_id]:
            del self._connections[video_id]
        logger.debug(f"WS disconnect | video={video_id}")

    # ── Broadcasting ──────────────────────────────────────────────

    async def broadcast_stats(self, video_id: str, stats: Dict[str, Any]) -> None:
        """
        Push updated stats to all clients currently watching this video.

        stats format:
            {
              "event": "stats_update",
              "video_id": "...",
              "like_count": 542,
              "view_count": 3201,
              "comment_count": 88,
            }
        """
        connections = self._connections.get(video_id, set())
        if not connections:
            return

        dead: Set[WebSocket] = set()
        payload = {"event": "stats_update", "video_id": video_id, **stats}

        # Fire-and-forget to all subscribers concurrently
        results = await asyncio.gather(
            *[ws.send_json(payload) for ws in connections],
            return_exceptions=True,
        )

        for ws, result in zip(list(connections), results):
            if isinstance(result, Exception):
                logger.warning(f"WS send failed → removing dead connection: {result}")
                dead.add(ws)

        for ws in dead:
            self.disconnect(video_id, ws)

        if connections - dead:
            logger.debug(
                f"WS broadcast  | video={video_id} "
                f"| clients={len(connections) - len(dead)} | {stats}"
            )

    # ── Diagnostics ───────────────────────────────────────────────

    def active_video_count(self) -> int:
        """Number of videos that currently have at least 1 active subscriber."""
        return len(self._connections)

    def subscriber_count(self, video_id: str) -> int:
        """Number of active WebSocket connections for a specific video."""
        return len(self._connections.get(video_id, set()))


# ── Singleton instance ─────────────────────────────────────────────
# Imported by both the controller (to attach WS routes)
# and the service (to broadcast after interaction events).
ws_manager = VideoStatsWSManager()
