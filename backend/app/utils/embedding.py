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

# Flag to track if we're using mock mode (active if no credentials provided)
_using_mock: bool = not (bool(settings.HF_API_TOKEN) or bool(settings.OPENAI_API_KEY))


def is_mock_mode() -> bool:
    """Check if we're using mock embeddings."""
    return _using_mock


async def generate_embedding(text: str) -> List[float]:
    """
    Generate an embedding vector for the given text.

    Attempts:
    1. Hugging Face Inference API (if HF_API_TOKEN or default model is preferred)
    2. OpenAI (if OPENAI_API_KEY is configured)
    3. Mock deterministic vector (if both fail or are unconfigured)
    """
    # 1. Try Hugging Face
    try:
        return await _generate_hf_embedding(text)
    except Exception as e:
        logger.warning(f"⚠️ Hugging Face embedding failed: {e}. Trying OpenAI...")

    # 2. Try OpenAI
    if settings.OPENAI_API_KEY:
        try:
            return await _generate_openai_embedding(text)
        except Exception as e:
            logger.warning(f"⚠️ OpenAI embedding failed: {e}. Falling back to mock...")

    # 3. Fall back to mock
    return _generate_mock_embedding(text)


async def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts in a single batch.
    """
    # 1. Try Hugging Face
    try:
        return await _generate_hf_embeddings_batch(texts)
    except Exception as e:
        logger.warning(f"⚠️ Hugging Face batch embedding failed: {e}. Trying OpenAI...")

    # 2. Try OpenAI
    if settings.OPENAI_API_KEY:
        try:
            return await _generate_openai_embeddings_batch(texts)
        except Exception as e:
            logger.warning(f"⚠️ OpenAI batch embedding failed: {e}. Falling back to mock...")

    # 3. Fall back to mock
    return [_generate_mock_embedding(t) for t in texts]


def build_embed_text(
    title: str, description: str, category: str, tags: List[str]
) -> str:
    """
    Build the input text for embedding generation.
    """
    return f"{title}. {description}. Category: {category}. Tags: {', '.join(tags)}"


# ── Hugging Face Implementation ────────────────────────────────

async def _generate_hf_embedding(text: str) -> List[float]:
    """Call Hugging Face Inference API for a single text."""
    import httpx
    import asyncio

    model = settings.EMBEDDING_MODEL
    api_url = f"https://router.huggingface.co/hf-inference/models/{model}/pipeline/feature-extraction"
    headers = {}
    if settings.HF_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.HF_API_TOKEN}"

    retries = 3
    delay = 5.0

    async with httpx.AsyncClient(timeout=15.0) as client:
        for attempt in range(retries):
            response = await client.post(api_url, headers=headers, json={"inputs": text})
            
            if response.status_code == 503:
                try:
                    data = response.json()
                    estimated_time = data.get("estimated_time", delay)
                    wait_time = min(estimated_time, 15.0)
                except Exception:
                    wait_time = delay
                logger.info(f"🤗 Hugging Face model is loading. Waiting {wait_time}s (attempt {attempt + 1}/{retries})...")
                await asyncio.sleep(wait_time)
                continue

            response.raise_for_status()
            result = response.json()

            if isinstance(result, list):
                if len(result) > 0 and isinstance(result[0], list):
                    if isinstance(result[0][0], float):
                        return result[0]
                    elif isinstance(result[0][0], list):
                        # Token level embeddings (3D list) -> Mean Pool
                        tokens = result[0]
                        num_tokens = len(tokens)
                        if num_tokens == 0:
                            raise ValueError("Empty token list from Hugging Face")
                        dim = len(tokens[0])
                        mean_vector = [0.0] * dim
                        for tok in tokens:
                            for idx, val in enumerate(tok):
                                mean_vector[idx] += val
                        return [val / num_tokens for val in mean_vector]
                elif len(result) > 0 and isinstance(result[0], float):
                    return result
            
            raise ValueError(f"Unexpected response format from Hugging Face: {result}")
        
        raise httpx.HTTPStatusError("Hugging Face model failed to load in time", request=response.request, response=response)


async def _generate_hf_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Call Hugging Face Inference API for a batch of texts."""
    import httpx
    import asyncio

    model = settings.EMBEDDING_MODEL
    api_url = f"https://router.huggingface.co/hf-inference/models/{model}/pipeline/feature-extraction"
    headers = {}
    if settings.HF_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.HF_API_TOKEN}"

    retries = 3
    delay = 5.0

    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(retries):
            response = await client.post(api_url, headers=headers, json={"inputs": texts})
            
            if response.status_code == 503:
                try:
                    data = response.json()
                    estimated_time = data.get("estimated_time", delay)
                    wait_time = min(estimated_time, 15.0)
                except Exception:
                    wait_time = delay
                logger.info(f"🤗 Hugging Face batch: model is loading. Waiting {wait_time}s (attempt {attempt + 1}/{retries})...")
                await asyncio.sleep(wait_time)
                continue

            response.raise_for_status()
            result = response.json()

            if isinstance(result, list):
                if len(result) > 0 and isinstance(result[0], list):
                    if isinstance(result[0][0], float):
                        return result
                    elif isinstance(result[0][0], list):
                        # Token level embeddings (3D list) -> Mean Pool for each
                        pooled_results = []
                        for tokens in result:
                            num_tokens = len(tokens)
                            if num_tokens == 0:
                                pooled_results.append([0.0] * settings.EMBEDDING_DIMENSIONS)
                                continue
                            dim = len(tokens[0])
                            mean_vector = [0.0] * dim
                            for tok in tokens:
                                for idx, val in enumerate(tok):
                                    mean_vector[idx] += val
                            pooled_results.append([val / num_tokens for val in mean_vector])
                        return pooled_results
            
            raise ValueError(f"Unexpected batch response format from Hugging Face: {result}")

        raise httpx.HTTPStatusError("Hugging Face model failed to load in time for batch", request=response.request, response=response)


# ── OpenAI Implementation ─────────────────────────────────────

async def _generate_openai_embedding(text: str) -> List[float]:
    """Call OpenAI embedding API for a single text."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding


async def _generate_openai_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Call OpenAI embedding API for a batch of texts."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    return [item.embedding for item in response.data]


# ── Mock Implementation ───────────────────────────────────────

def _generate_mock_embedding(text: str) -> List[float]:
    """
    Generate a deterministic mock embedding vector from text.
    """
    seed = hash(text) % (2**32)
    rng = random.Random(seed)
    vector = [rng.uniform(-1.0, 1.0) for _ in range(settings.EMBEDDING_DIMENSIONS)]

    magnitude = sum(x**2 for x in vector) ** 0.5
    if magnitude > 0:
        vector = [x / magnitude for x in vector]

    logger.debug(f"🎲 Generated mock embedding (dim={len(vector)}) for: {text[:50]}...")
    return vector
