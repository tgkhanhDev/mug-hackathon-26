"""
Kafka consumer worker — processes behavior-log messages in the background.

This module runs as an asyncio background task inside the FastAPI process.
It consumes messages from the `behavior_logs` topic, persists them to MongoDB,
updates session metrics (intensity → fatigue → SSE), and routes failures to
the dead-letter topic (`behavior_logs_dlq`).
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from bson import ObjectId

from app.kafka.kafka_client import create_consumer, send_to_dlq
from app.models.behavior_log import BehaviorLogInDB
from app.utils.formula import (
    calculate_fatigue_score,
    calculate_log_penalty,
    determine_adaptive_state,
)
from app.utils.redis import publish_session_update

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# Message handler
# ══════════════════════════════════════════════════════════════

async def _handle_message(msg: dict, log_repo, session_repo, video_repo) -> None:
    """
    Process a single behavior-log Kafka message.

    Pipeline:
      1. Compute consecutive-same-topic count
      2. Insert BehaviorLog document into MongoDB
      3. Update session intensity counters
      4. Re-calculate fatigue score and adaptive state
      5. Publish SSE update via Redis Pub/Sub
    """
    log_id = msg["log_id"]
    session_id = msg["session_id"]
    video_id = msg["video_id"]
    now = datetime.fromisoformat(msg["timestamp"])

    # ① Consecutive topic count
    consecutive = await log_repo.get_consecutive_topic_count(
        session_id, msg["topic"], limit=10
    )

    # ② Persist to MongoDB
    log_doc = BehaviorLogInDB(
        user_id=msg["user_id"],
        session_id=session_id,
        video_id=video_id,
        timestamp=now,
        swipe_speed=msg["swipe_speed"],
        watch_duration=msg["watch_duration"],
        is_interaction=msg["is_interaction"],
        topic=msg["topic"],
        consecutive_same_topic=consecutive,
    )
    log_dict = log_doc.model_dump()
    log_dict["_id"] = ObjectId(log_id)
    await log_repo.insert_one(log_dict)

    # ③ Update session intensity (high/low count based on video intensity_level)
    video = await video_repo.find_by_id(video_id)
    if video and video.get("intensity_level"):
        await session_repo.update_intensity_count(
            session_id, video["intensity_level"]
        )

    # ④ Re-calculate fatigue score
    session = await session_repo.find_by_id(session_id)
    if not session:
        return

    logs = await log_repo.get_recent_logs(session_id, limit=10)
    if not logs:
        return

    log_penalties = [
        calculate_log_penalty(
            watch_duration=log.get("watch_duration", 0.0),
            swipe_speed=log.get("swipe_speed", 0.0),
            is_interaction=log.get("is_interaction", False),
            consecutive_same_topic=log.get("consecutive_same_topic", 0),
        )
        for log in logs
    ]

    high_count = session.get("high_intensity_count", 0)
    low_count = session.get("low_intensity_count", 0)
    fatigue_score = calculate_fatigue_score(log_penalties, high_count, low_count)
    adaptive_state = determine_adaptive_state(fatigue_score)

    stats = {
        "fatigue_score": fatigue_score,
        "adaptive_state": adaptive_state,
        "updated_at": datetime.utcnow(),
    }
    await session_repo.update_session_stats(session_id, stats)
    logger.info(
        "✅ Kafka consumer processed log_id=%s | session=%s | fatigue=%.2f | state=%s",
        log_id, session_id, fatigue_score, adaptive_state,
    )

    # ⑤ Push SSE update (fire-and-forget)
    asyncio.create_task(
        publish_session_update(session_id, fatigue_score, adaptive_state)
    )


# ══════════════════════════════════════════════════════════════
# Consumer loop (runs as a background asyncio task)
# ══════════════════════════════════════════════════════════════

async def run_behavior_log_consumer() -> None:
    """
    Long-running consumer loop.

    Designed to be launched via `asyncio.create_task()` during FastAPI startup.
    Repositories are lazily initialised here (after connect_db has been called).
    If the Kafka broker is unreachable on first connect, it will retry with
    exponential back-off so the rest of the application can still start.
    """
    # Lazy import to avoid circular / premature DB access at module load time
    from app.repositories.behavior_log_repository import BehaviorLogRepository
    from app.repositories.feed_session_repository import FeedSessionRepository
    from app.repositories.video_repository import VideoRepository

    log_repo = BehaviorLogRepository()
    session_repo = FeedSessionRepository()
    video_repo = VideoRepository()

    consumer = None
    retry_delay = 2  # seconds, doubles on each retry up to 30s

    while True:
        try:
            if consumer is None:
                consumer = await create_consumer()
                retry_delay = 2  # reset on successful connect

            async for kafka_msg in consumer:
                try:
                    await _handle_message(kafka_msg.value, log_repo, session_repo, video_repo)
                except Exception as exc:
                    # Per-message failure → route to DLQ, keep consuming
                    logger.error(
                        "❌ Failed to process behavior log message: %s", exc,
                    )
                    try:
                        await send_to_dlq(kafka_msg.value, str(exc))
                    except Exception as dlq_exc:
                        logger.error("❌ DLQ routing also failed: %s", dlq_exc)

        except asyncio.CancelledError:
            logger.info("🛑 Behavior log consumer task cancelled — shutting down")
            break
        except Exception as exc:
            # Broker disconnect / network error → retry with back-off
            logger.error(
                "Kafka consumer error (retrying in %ds): %s", retry_delay, exc,
            )
            if consumer is not None:
                try:
                    await consumer.stop()
                except Exception:
                    pass
                consumer = None
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 30)

    # Graceful cleanup
    if consumer is not None:
        try:
            await consumer.stop()
        except Exception:
            pass
    logger.info("🛑 Behavior log consumer stopped")

