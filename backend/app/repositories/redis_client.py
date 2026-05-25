"""
Redis connection manager for the seen-set caching layer.

Provides async Redis client for:
  - Session seen-set (race condition fix): SADD/SMEMBERS on `session:{id}:seen`
  - TTL: 2 hours (matches max session lifetime)

Uses redis.asyncio for non-blocking I/O compatible with FastAPI's event loop.
"""

import logging
from typing import Optional, Set

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

# ── Module-level singleton ─────────────────────────────────────
_redis: Optional[aioredis.Redis] = None

# Key TTL constants
SESSION_SEEN_TTL = 7200  # 2 hours (max session lifetime)


async def connect_redis() -> None:
    """Initialize Redis connection. Called during FastAPI lifespan startup."""
    global _redis
    try:
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20,
        )
        # Verify connection
        await _redis.ping()
        logger.info(f"✅ Connected to Redis — {settings.REDIS_URL}")
    except Exception as exc:
        logger.warning(f"⚠️ Redis connection failed: {exc}. Falling back to MongoDB-only dedup.")
        _redis = None


async def disconnect_redis() -> None:
    """Close Redis connection. Called during FastAPI lifespan shutdown."""
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
        logger.info("🔌 Redis connection closed.")


def get_redis() -> Optional[aioredis.Redis]:
    """Get the Redis client instance. Returns None if Redis is unavailable."""
    return _redis


def is_redis_available() -> bool:
    """Check if Redis client is connected."""
    return _redis is not None


# ══════════════════════════════════════════════════════════════
# Session Seen-Set Operations
# ══════════════════════════════════════════════════════════════

def _seen_key(session_id: str) -> str:
    """Build the Redis key for a session's seen video set."""
    return f"session:{session_id}:seen"


async def add_seen_video(session_id: str, video_id: str) -> bool:
    """
    Add a video_id to the session's seen set in Redis.
    
    This is called SYNCHRONOUSLY (before returning 201) in record_behavior_log
    to fix the race condition between fire-and-forget DB insert and GET /feed.
    
    Returns True if successfully added, False if Redis unavailable.
    """
    r = get_redis()
    if r is None:
        return False
    try:
        key = _seen_key(session_id)
        await r.sadd(key, video_id)
        await r.expire(key, SESSION_SEEN_TTL)
        return True
    except Exception as exc:
        logger.warning(f"Redis SADD failed for session={session_id}: {exc}")
        return False


async def get_seen_videos(session_id: str) -> Set[str]:
    """
    Get all seen video IDs for a session from Redis.
    
    Returns an empty set if Redis is unavailable (caller falls back to MongoDB).
    """
    r = get_redis()
    if r is None:
        return set()
    try:
        key = _seen_key(session_id)
        members = await r.smembers(key)
        return set(members)
    except Exception as exc:
        logger.warning(f"Redis SMEMBERS failed for session={session_id}: {exc}")
        return set()


async def bulk_add_seen_videos(session_id: str, video_ids: Set[str]) -> bool:
    """
    Bulk-add multiple video IDs to the session's seen set.
    Used during session startup to seed Redis from MongoDB.
    """
    r = get_redis()
    if r is None or not video_ids:
        return False
    try:
        key = _seen_key(session_id)
        await r.sadd(key, *video_ids)
        await r.expire(key, SESSION_SEEN_TTL)
        return True
    except Exception as exc:
        logger.warning(f"Redis bulk SADD failed for session={session_id}: {exc}")
        return False
