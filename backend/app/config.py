"""
Application configuration — loads environment variables via pydantic-settings.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Global application settings loaded from .env file."""

    # ── MongoDB Atlas ──────────────────────────────────────────
    MONGODB_URI: str = Field(
        ...,
        description="MongoDB connection string (read from .env)",
    )
    DATABASE_NAME: str = Field(
        default="gotouchgrass",
        description="Database name",
    )

    # ── Redis (Seen-Set Cache) ─────────────────────────────────
    REDIS_HOST: str = Field(
        default="redis",
        description="Redis hostname (Docker service name)",
    )
    REDIS_PORT: int = Field(
        default=6379,
        description="Redis port",
    )
    REDIS_DB: int = Field(
        default=0,
        description="Redis DB index",
    )
    # Optional: keep URL for compatibility
    REDIS_URL: str = Field(
        default="redis://redis:6379/0",
        description="Redis connection URL for backward compatibility",
    )

    # ── Celery Asynchronous Task Queue ─────────────────────────
    CELERY_BROKER_URL: str = Field(
        default="amqp://guest:guest@localhost:5672//",
        description="RabbitMQ connection URL broker for Celery tasks",
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/0",
        description="Redis result backend URL for Celery tasks",
    )


    # ── Hugging Face / OpenAI Embedding ────────────────────────
    HF_API_TOKEN: str = Field(
        default="",
        description="Hugging Face API Token (leave empty to try without token)",
    )
    OPENAI_API_KEY: str = Field(
        default="",
        description="OpenAI API key (leave empty to use Hugging Face or mock)",
    )
    EMBEDDING_MODEL: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Embedding model name (e.g. sentence-transformers/all-MiniLM-L6-v2 or text-embedding-3-small)",
    )
    EMBEDDING_DIMENSIONS: int = Field(
        default=384,
        description="Embedding vector dimensions (e.g. 384 for all-MiniLM-L6-v2, 1536 for OpenAI)",
    )

    # ── JWT Auth ───────────────────────────────────────────────
    JWT_SECRET_KEY: str = Field(
        default="dev-secret-key-change-in-production",
        description="Secret key for JWT token signing",
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="JWT signing algorithm",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        description="Access token expiry in minutes",
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7,
        description="Refresh token expiry in days",
    )

    # ── Embedding Scheduler ────────────────────────────────────
    EMBEDDING_SCHEDULE_INTERVAL_MINUTES: int = Field(
        default=60,
        description="Interval in minutes for the embedding generation job",
    )

    # ── Server ─────────────────────────────────────────────────
    PORT: int = Field(default=8033, description="Server port")

    # ── MinIO Configuration (Dedicated Local Storage) ──────────
    MINIO_ENDPOINT_URL: str = Field(
        default="http://localhost:9000",
        description="MinIO Endpoint URL"
    )
    MINIO_ACCESS_KEY: str = Field(
        default="minioadmin", 
        description="MinIO Access Key (username)"
    )
    MINIO_SECRET_KEY: str = Field(
        default="minioadmin", 
        description="MinIO Secret Key (password)"
    )
    MINIO_REGION: str = Field(
        default="us-east-1", 
        description="MinIO Region constraint"
    )
    MINIO_BUCKET_NAME: str = Field(
        default="gotouchgrass-media", 
        description="MinIO Bucket name"
    )
    MINIO_USE_SSL: bool = Field(
        default=False,
        description="Use SSL/HTTPS when connecting to MinIO"
    )

    # ── Kafka ──────────────────────────────────────────────────
    KAFKA_BOOTSTRAP_SERVERS: str = Field(
        default="localhost:9092",
        description="Kafka bootstrap servers (comma-separated)",
    )
    KAFKA_BEHAVIOR_LOG_TOPIC: str = Field(
        default="behavior_logs",
        description="Kafka topic for behavior log messages",
    )
    KAFKA_BEHAVIOR_LOG_DLQ_TOPIC: str = Field(
        default="behavior_logs_dlq",
        description="Dead-letter topic for failed behavior log messages",
    )
    KAFKA_CONSUMER_GROUP: str = Field(
        default="behavior_log_worker",
        description="Kafka consumer group ID for the behavior log worker",
    )

    # ── Pexels Crawler ─────────────────────────────────────────
    PEXELS_API_KEY: str = Field(
        default="",
        description="Pexels API Key for crawler"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


# Singleton instance
settings = Settings()

