"""
Embedding utility — generates vector embeddings for text.

Uses OpenAI text-embedding-3-small (1536-dim) when API key is available,
falls back to mock random vectors for development/testing.
"""

import logging
import random
from typing import List

from app.config import settings

logger = logging.getLogger(__name__)

# Flag to track if we're using mock mode
_using_mock: bool = not bool(settings.OPENAI_API_KEY)


def is_mock_mode() -> bool:
    """Check if we're using mock embeddings (no OpenAI key)."""
    return _using_mock


async def generate_embedding(text: str) -> List[float]:
    """
    Generate a 1536-dimensional embedding vector for the given text.

    If OPENAI_API_KEY is set → calls OpenAI text-embedding-3-small.
    If not set → returns a deterministic mock vector (seeded from text hash).

    Args:
        text: Input text to embed (e.g., "title. description. Category: X. Tags: a, b")

    Returns:
        List of 1536 floats representing the embedding vector.
    """
    if _using_mock:
        return _generate_mock_embedding(text)

    return await _generate_openai_embedding(text)


async def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts in a single batch.

    More efficient than calling generate_embedding() in a loop when using
    OpenAI (single API call for up to 2048 texts).
    """
    if _using_mock:
        return [_generate_mock_embedding(t) for t in texts]

    return await _generate_openai_embeddings_batch(texts)


def build_embed_text(
    title: str, description: str, category: str, tags: List[str]
) -> str:
    """
    Build the input text for embedding generation.

    Format: "{title}. {description}. Category: {category}. Tags: {tag1, tag2, ...}"
    This rich context ensures $vectorSearch finds semantically related videos.
    """
    return f"{title}. {description}. Category: {category}. Tags: {', '.join(tags)}"


# ── OpenAI Implementation ─────────────────────────────────────

async def _generate_openai_embedding(text: str) -> List[float]:
    """Call OpenAI embedding API for a single text."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


async def _generate_openai_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Call OpenAI embedding API for a batch of texts."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


# ── Mock Implementation ───────────────────────────────────────

def _generate_mock_embedding(text: str) -> List[float]:
    """
    Generate a deterministic mock embedding vector from text.

    Uses hash of text as random seed so the same text always produces
    the same vector — important for consistent test results.
    """
    seed = hash(text) % (2**32)
    rng = random.Random(seed)
    vector = [rng.uniform(-1.0, 1.0) for _ in range(settings.EMBEDDING_DIMENSIONS)]

    # Normalize to unit vector (cosine similarity works best with normalized vectors)
    magnitude = sum(x**2 for x in vector) ** 0.5
    if magnitude > 0:
        vector = [x / magnitude for x in vector]

    logger.debug(f"🎲 Generated mock embedding (dim={len(vector)}) for: {text[:50]}...")
    return vector
