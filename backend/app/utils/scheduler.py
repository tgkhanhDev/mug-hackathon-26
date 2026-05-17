"""
Embedding scheduler — background job that generates embeddings for videos
that don't have one yet.

The schedule interval is configurable via API (no code changes needed).
Uses APScheduler with an in-memory job store.
"""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings

logger = logging.getLogger(__name__)

# ── Module-level scheduler instance ────────────────────────────
_scheduler: AsyncIOScheduler | None = None

JOB_ID = "embedding_generation_job"


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def _embedding_job() -> None:
    """
    Background job: find videos without embeddings and generate them.

    This runs on a configurable interval (default: every 60 minutes).
    """
    from app.repositories.video_repository import VideoRepository
    from app.utils.embedding import generate_embedding, build_embed_text

    logger.info(f"⏰ Embedding scheduler job started at {datetime.utcnow().isoformat()}")

    try:
        repo = VideoRepository()
        videos = await repo.find_without_embedding(limit=50)

        if not videos:
            logger.info("  ✅ No videos without embeddings found.")
            return

        count = 0
        for video in videos:
            embed_text = build_embed_text(
                title=video["title"],
                description=video["description"],
                category=video["category"],
                tags=video["tags"],
            )
            embedding = await generate_embedding(embed_text)
            await repo.update_embedding(video["id"], embedding)
            count += 1

        logger.info(f"  ✅ Generated embeddings for {count} videos.")

    except Exception as e:
        logger.error(f"  ❌ Embedding job error: {e}", exc_info=True)


def start_scheduler() -> None:
    """Start the scheduler with the configured interval."""
    scheduler = get_scheduler()

    interval_minutes = settings.EMBEDDING_SCHEDULE_INTERVAL_MINUTES
    scheduler.add_job(
        _embedding_job,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id=JOB_ID,
        name="Generate embeddings for videos",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        f"🕐 Embedding scheduler started — interval: every {interval_minutes} minutes"
    )


def stop_scheduler() -> None:
    """Stop the scheduler gracefully."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("🛑 Embedding scheduler stopped.")


def update_schedule_interval(minutes: int) -> dict:
    """
    Update the embedding job interval at runtime (via API, no code change needed).

    Args:
        minutes: New interval in minutes (must be >= 1).

    Returns:
        Dict with the new schedule info.
    """
    scheduler = get_scheduler()

    # Remove old job and add with new interval
    scheduler.reschedule_job(
        JOB_ID,
        trigger=IntervalTrigger(minutes=minutes),
    )

    logger.info(f"🔄 Embedding schedule updated — new interval: every {minutes} minutes")

    return {
        "job_id": JOB_ID,
        "interval_minutes": minutes,
        "message": f"Embedding job rescheduled to run every {minutes} minutes",
    }


def get_schedule_info() -> dict:
    """Get current scheduler status and next run time."""
    scheduler = get_scheduler()

    job = scheduler.get_job(JOB_ID)
    if job:
        return {
            "job_id": JOB_ID,
            "next_run_time": str(job.next_run_time) if job.next_run_time else None,
            "is_running": scheduler.running,
        }

    return {
        "job_id": JOB_ID,
        "next_run_time": None,
        "is_running": False,
    }


async def trigger_embedding_job_now() -> dict:
    """Manually trigger the embedding job immediately (on-demand)."""
    await _embedding_job()
    return {"message": "Embedding job triggered manually and completed."}
