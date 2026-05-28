"""
Redis connection manager.
Provides an asynchronous client using redis.asyncio.
Also exposes Pub/Sub helpers for SSE-based session event streaming.
"""

import asyncio
import json
import logging
from typing import AsyncGenerator
from redis.asyncio import Redis
from app.config import settings

logger = logging.getLogger(__name__)

# Module-level singleton
redis_client: Redis | None = None


async def connect_redis() -> None:
    """
    Initialize Redis client and verify connection.
    Called during FastAPI lifespan startup.
    """
    global redis_client

    logger.info(f"Connecting to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}...")
    try:
        redis_client = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True,  # Automatically decode bytes to str
        )
        # Verify connection
        await redis_client.ping()
        logger.info(f"✅ Connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    except Exception as exc:
        logger.error(f"❌ Failed to connect to Redis: {exc}")
        redis_client = None
        raise exc


async def disconnect_redis() -> None:
    """Close Redis connection. Called during FastAPI lifespan shutdown."""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None
        logger.info("🔌 Redis connection closed.")


def get_redis() -> Redis:
    """Get the Redis client instance. Raises if not connected."""
    if redis_client is None:
        raise RuntimeError("Redis client not initialized. Call connect_redis() first.")
    return redis_client


# ══════════════════════════════════════════════════════════════
# Redis Pub/Sub — SSE session event streaming
# ══════════════════════════════════════════════════════════════

def _session_event_channel(session_id: str) -> str:
    """Build the Redis Pub/Sub channel name for a session."""
    return f"session:{session_id}:events"


async def publish_session_update(
    session_id: str, fatigue_score: float, adaptive_state: str
) -> None:
    """
    Publish a session fatigue update to the session's Redis Pub/Sub channel.
    Called by the interaction service after every fatigue recalculation.
    """
    try:
        r = get_redis()
    except RuntimeError:
        return  # Redis not initialised — skip gracefully

    payload = json.dumps({"fatigue_score": fatigue_score, "adaptive_state": adaptive_state})
    try:
        await r.publish(_session_event_channel(session_id), payload)
    except Exception as exc:
        logger.warning(f"Redis publish failed for session={session_id}: {exc}")


async def subscribe_session_events(
    session_id: str,
) -> AsyncGenerator[dict, None]:
    """
    Async generator that subscribes to the session's Redis Pub/Sub channel
    and yields parsed payloads until the caller stops iterating.
    """
    try:
        r = get_redis()
    except RuntimeError:
        return  # Redis not initialised — yield nothing

    pubsub = r.pubsub()
    channel = _session_event_channel(session_id)
    await pubsub.subscribe(channel)
    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=1.0
            )
            if message and message.get("data"):
                try:
                    yield json.loads(message["data"])
                except (json.JSONDecodeError, TypeError):
                    pass
            else:
                await asyncio.sleep(0.1)
    finally:
        try:
            await pubsub.unsubscribe(channel)
        except Exception:
            pass
