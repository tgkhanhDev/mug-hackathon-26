"""
MongoDB Atlas connection manager.

Lives in the repository layer because it's the data access concern.
Uses motor (async MongoDB driver) for non-blocking I/O.
"""

import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import CollectionInvalid

from app.config import settings

logger = logging.getLogger(__name__)

# ── Module-level singletons ────────────────────────────────────
_client: AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None


async def connect_db() -> None:
    """
    Initialize MongoDB connection and create collections + indexes.
    Called during FastAPI lifespan startup.
    """
    global _client, _database

    logger.info("Connecting to MongoDB Atlas...")
    _client = AsyncIOMotorClient(settings.MONGODB_URI)
    _database = _client[settings.DATABASE_NAME]

    # Verify connection
    await _client.admin.command("ping")
    logger.info(f"✅ Connected to MongoDB — database: {settings.DATABASE_NAME}")

    # Initialize collections and indexes
    await _init_collections()
    await _create_indexes()


async def disconnect_db() -> None:
    """Close MongoDB connection. Called during FastAPI lifespan shutdown."""
    global _client, _database
    if _client:
        _client.close()
        _client = None
        _database = None
        logger.info("🔌 MongoDB connection closed.")


def get_database() -> AsyncIOMotorDatabase:
    """Get the database instance. Raises if not connected."""
    if _database is None:
        raise RuntimeError("Database not initialized. Call connect_db() first.")
    return _database


def get_collection(name: str):
    """Get a collection by name from the current database."""
    db = get_database()
    return db[name]


# ── Private helpers ────────────────────────────────────────────

async def _init_collections() -> None:
    """
    Create collections if they don't exist.
    behavior_logs is created as a Time-Series collection.
    """
    db = get_database()
    existing = await db.list_collection_names()

    # Regular collections
    for col_name in ["videos", "users", "interactions", "feed_sessions"]:
        if col_name not in existing:
            await db.create_collection(col_name)
            logger.info(f"  📦 Created collection: {col_name}")

    # Time-Series collection for behavior_logs
    if "behavior_logs" not in existing:
        try:
            await db.create_collection(
                "behavior_logs",
                timeseries={
                    "timeField": "timestamp",
                    "metaField": "session_id",
                    "granularity": "seconds",
                },
            )
            logger.info("  📦 Created Time-Series collection: behavior_logs")
        except CollectionInvalid:
            logger.warning("  ⚠️  behavior_logs collection already exists (non-timeseries)")


async def _create_indexes() -> None:
    """Create regular indexes as defined in the ERD schema."""
    db = get_database()

    # ── videos indexes ─────────────────────────────────────
    videos = db["videos"]
    await videos.create_index([("trending_score", -1)])
    await videos.create_index([("tags", 1), ("category", 1)])
    await videos.create_index([("intensity_level", 1)])

    # ── users indexes ──────────────────────────────────────
    users = db["users"]
    await users.create_index([("username", 1)], unique=True)

    # ── interactions indexes ───────────────────────────────
    interactions = db["interactions"]
    await interactions.create_index([("user_id", 1), ("timestamp", -1)])
    await interactions.create_index([("session_id", 1)])
    await interactions.create_index([("video_id", 1)])

    # ── feed_sessions indexes ──────────────────────────────
    feed_sessions = db["feed_sessions"]
    await feed_sessions.create_index([("user_id", 1), ("started_at", -1)])
    await feed_sessions.create_index([("user_id", 1), ("ended_at", 1)])

    # ── behavior_logs indexes ──────────────────────────────
    behavior_logs = db["behavior_logs"]
    await behavior_logs.create_index([("session_id", 1), ("timestamp", 1)])
    await behavior_logs.create_index([("user_id", 1), ("timestamp", -1)])

    logger.info("  🔑 All indexes created/verified.")
