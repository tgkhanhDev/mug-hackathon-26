"""
GoTouchGrass Backend — FastAPI Application Entry Point.

Mindful Feed Recommendation Engine for short-form video platforms.
Architecture: N-Layer (Controller → Service → Repository)
Database: MongoDB Atlas with Vector Search
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.repositories.database import connect_db, disconnect_db
from app.repositories.redis_client import connect_redis, disconnect_redis, is_redis_available
from app.utils.exceptions import AppException, app_exception_handler
from app.utils.scheduler import start_scheduler, stop_scheduler
from app.utils.embedding import is_mock_mode
from app.kafka.kafka_client import start_producer, stop_producer
from app.workers.behavior_log_consumer import run_behavior_log_consumer

# ── Controllers ────────────────────────────────────────────────
from app.controllers import video_controller
from app.controllers import user_controller
from app.controllers import auth_controller
from app.controllers import scheduler_controller
from app.controllers import upload_controller
from app.controllers import feed_controller
from app.controllers import interaction_controller

# ── Logging Setup ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup/shutdown) ────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    - Startup: connect to MongoDB, Redis, Kafka; start scheduler & consumer
    - Shutdown: stop consumer, Kafka, scheduler; disconnect Redis & MongoDB
    """
    # ── Startup ────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("🌿 GoTouchGrass Backend starting up...")
    logger.info(f"   Database: {settings.DATABASE_NAME}")
    logger.info(f"   Redis: {settings.REDIS_URL}")
    logger.info(f"   Kafka: {settings.KAFKA_BOOTSTRAP_SERVERS}")
    logger.info(f"   Embedding: {'🎲 MOCK MODE' if is_mock_mode() else '🤖 OpenAI'}")
    logger.info(f"   Port: {settings.PORT}")
    logger.info("=" * 60)

    await connect_db()
    await connect_redis()
    start_scheduler()

    # ── Kafka ──────────────────────────────────────────────
    try:
        await start_producer()
        kafka_consumer_task = asyncio.create_task(run_behavior_log_consumer())
        logger.info("✅ Kafka producer & consumer background task started")
    except Exception as exc:
        kafka_consumer_task = None
        logger.warning(f"⚠️ Kafka startup failed (app will run without Kafka): {exc}")

    yield  # App is running

    # ── Shutdown ───────────────────────────────────────────
    logger.info("🛑 GoTouchGrass Backend shutting down...")

    # Cancel Kafka consumer background task
    if kafka_consumer_task is not None:
        kafka_consumer_task.cancel()
        try:
            await kafka_consumer_task
        except asyncio.CancelledError:
            pass

    await stop_producer()
    stop_scheduler()
    await disconnect_redis()
    await disconnect_db()


# ── FastAPI App ────────────────────────────────────────────────
app = FastAPI(
    title="GoTouchGrass API",
    description=(
        "🌿 Wellbeing-aware AI Recommendation Engine for short-form video. "
        "Detects doomscrolling, calculates Fatigue Score, and rebalances feed "
        "with calming content using MongoDB Vector Search."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS Middleware ────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception Handlers ────────────────────────────────────────
app.add_exception_handler(AppException, app_exception_handler)

# ── Register Routers ──────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(video_controller.router, prefix=API_PREFIX)
app.include_router(user_controller.router, prefix=API_PREFIX)
app.include_router(auth_controller.router, prefix=API_PREFIX)
app.include_router(scheduler_controller.router, prefix=API_PREFIX)
app.include_router(upload_controller.router, prefix=API_PREFIX)
app.include_router(interaction_controller.router, prefix=API_PREFIX)
app.include_router(feed_controller.router, prefix=API_PREFIX)


# ── Health Check ───────────────────────────────────────────────
@app.get(
    "/health",
    tags=["System"],
    summary="Health check",
    description="Verify the API server is running and database is connected.",
)
async def health_check():
    """GET /health — System health check."""
    from app.repositories.database import get_database

    try:
        db = get_database()
        # Quick ping to verify DB connection
        await db.command("ping")
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return {
        "status": "healthy",
        "service": "GoTouchGrass API",
        "version": "0.1.0",
        "database": db_status,
        "embedding_mode": "mock" if is_mock_mode() else "openai",
        "port": settings.PORT,
    }


# ── Root ───────────────────────────────────────────────────────
@app.get("/", tags=["System"])
async def root():
    """GET / — Welcome message."""
    return {
        "message": "🌿 Welcome to GoTouchGrass API",
        "docs": "/docs",
        "health": "/health",
    }
