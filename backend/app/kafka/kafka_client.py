"""
Kafka client — centralised producer / consumer helpers for the app.

Provides:
  - A singleton AIOKafkaProducer (lazy-init, reusable across requests)
  - A factory for AIOKafkaConsumer (one per worker loop)
  - send_behavior_log()  → produce to the main topic
  - send_to_dlq()        → produce failed messages to the dead-letter topic
  - start_producer() / stop_producer() lifecycle hooks
"""

import json
import logging
from typing import Optional

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

from app.config import settings

logger = logging.getLogger(__name__)

# ── Module-level singleton ─────────────────────────────────────
_producer: Optional[AIOKafkaProducer] = None


# ══════════════════════════════════════════════════════════════
# Producer
# ══════════════════════════════════════════════════════════════

async def start_producer() -> None:
    """Initialise and start the Kafka producer (call once at app startup)."""
    global _producer
    if _producer is not None:
        return

    _producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        # Ensure messages are durably written
        acks="all",
    )
    await _producer.start()
    logger.info(
        "✅ Kafka producer started (bootstrap=%s)",
        settings.KAFKA_BOOTSTRAP_SERVERS,
    )


async def stop_producer() -> None:
    """Gracefully flush & close the Kafka producer (call at app shutdown)."""
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None
        logger.info("🛑 Kafka producer stopped")


async def send_behavior_log(message: dict) -> None:
    """
    Produce a behavior-log message to the configured Kafka topic.

    Raises if the producer has not been started yet.
    """
    if _producer is None:
        logger.error("Kafka producer not initialised — dropping message %s", message.get("log_id"))
        return

    await _producer.send_and_wait(
        settings.KAFKA_BEHAVIOR_LOG_TOPIC,
        value=message,
    )
    logger.debug("📤 Sent behavior log to Kafka: log_id=%s", message.get("log_id"))


async def send_to_dlq(message: dict, error: str) -> None:
    """
    Forward a failed message to the dead-letter topic with error metadata.
    """
    if _producer is None:
        logger.error("Kafka producer not initialised — cannot send to DLQ")
        return

    dlq_message = {
        **message,
        "_dlq_error": error,
    }
    try:
        await _producer.send_and_wait(
            settings.KAFKA_BEHAVIOR_LOG_DLQ_TOPIC,
            value=dlq_message,
        )
        logger.warning("⚠️ Sent failed message to DLQ: log_id=%s error=%s", message.get("log_id"), error)
    except Exception as exc:
        # Last resort — if even the DLQ write fails, just log it
        logger.error("❌ DLQ send also failed for log_id=%s: %s", message.get("log_id"), exc)


# ══════════════════════════════════════════════════════════════
# Consumer
# ══════════════════════════════════════════════════════════════

async def create_consumer() -> AIOKafkaConsumer:
    """
    Create and start a new AIOKafkaConsumer for the behavior_logs topic.

    The caller is responsible for stopping the consumer when done.
    """
    consumer = AIOKafkaConsumer(
        settings.KAFKA_BEHAVIOR_LOG_TOPIC,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_CONSUMER_GROUP,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        enable_auto_commit=True,
        auto_offset_reset="latest",
    )
    await consumer.start()
    logger.info(
        "✅ Kafka consumer started (topic=%s, group=%s)",
        settings.KAFKA_BEHAVIOR_LOG_TOPIC,
        settings.KAFKA_CONSUMER_GROUP,
    )
    return consumer
