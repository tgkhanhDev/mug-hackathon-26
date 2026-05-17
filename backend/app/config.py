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

    # ── OpenAI Embedding ───────────────────────────────────────
    OPENAI_API_KEY: str = Field(
        default="",
        description="OpenAI API key (leave empty to use mock embedding)",
    )
    EMBEDDING_MODEL: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model name",
    )
    EMBEDDING_DIMENSIONS: int = Field(
        default=1536,
        description="Embedding vector dimensions",
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

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


# Singleton instance
settings = Settings()
