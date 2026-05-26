"""
Redis connection manager.
Provides an asynchronous client using redis.asyncio.
"""

import logging
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
