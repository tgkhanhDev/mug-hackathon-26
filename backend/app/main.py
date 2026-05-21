"""
GoTouchGrass Backend — FastAPI Application Entry Point.

Mindful Feed Recommendation Engine for short-form video platforms.
Architecture: N-Layer (Controller → Service → Repository)
Database: MongoDB Atlas with Vector Search
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.repositories.database import connect_db, disconnect_db
from app.utils.exceptions import AppException, app_exception_handler
from app.utils.scheduler import start_scheduler, stop_scheduler
from app.utils.embedding import is_mock_mode

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
    - Startup: connect to MongoDB, start embedding scheduler
    - Shutdown: stop scheduler, disconnect MongoDB
    """
    # ── Startup ────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("🌿 GoTouchGrass Backend starting up...")
    logger.info(f"   Database: {settings.DATABASE_NAME}")
    logger.info(f"   Embedding: {'🎲 MOCK MODE' if is_mock_mode() else '🤖 OpenAI'}")
    logger.info(f"   Port: {settings.PORT}")
    logger.info("=" * 60)

    await connect_db()
    start_scheduler()

    yield  # App is running

    # ── Shutdown ───────────────────────────────────────────
    logger.info("🛑 GoTouchGrass Backend shutting down...")
    stop_scheduler()
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
app.include_router(interaction_controller.router, prefix=API_PREFIX)


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
