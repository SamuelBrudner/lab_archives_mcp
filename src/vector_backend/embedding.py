"""Embedding client abstraction for model-agnostic vector generation.

Supports OpenAI API and extensible to local models (sentence-transformers, etc.).
All embedding calls are batched for efficiency and include retry logic.
"""

import asyncio
from typing import Protocol

import httpx
from loguru import logger
from openai import AsyncOpenAI, RateLimitError
from pydantic import BaseModel, Field


class EmbeddingConfig(BaseModel):
    """Configuration for embedding generation.

    Attributes:
        model: Model identifier (e.g., "openai/text-embedding-3-small")
        version: Version tag for reindexing triggers (e.g., "v1")
        dimensions: Expected embedding dimensionality
        batch_size: Number of texts to embed per API call
        max_retries: Maximum retry attempts for transient failures
        timeout_seconds: API request timeout
        api_key: API key for external services (set via env var)
    """

    model: str
    version: str
    dimensions: int = Field(ge=128, le=4096)
    batch_size: int = Field(default=100, ge=1, le=500)
    max_retries: int = Field(default=3, ge=1, le=10)
    timeout_seconds: float = Field(default=30.0, ge=1.0, le=300.0)
    api_key: str | None = None


class EmbeddingClient(Protocol):
    """Protocol for embedding client implementations."""

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Args:
            texts: List of input texts (max batch_size)

        Returns:
            List of embedding vectors (same order as inputs)

        Raises:
            ValueError: If batch size exceeds limit
            httpx.HTTPError: For API failures after retries
        """
        ...

    async def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        ...


class OpenAIEmbedding:
    """OpenAI embedding client with retry logic and batching."""

    def __init__(self, config: EmbeddingConfig):
        """Initialize OpenAI client.

        Args:
            config: Embedding configuration with API key
        """
        self.config = config
        self.client = AsyncOpenAI(api_key=config.api_key, timeout=config.timeout_seconds)

        # Extract model name (strip "openai/" prefix if present)
        self.model_name = (
            config.model.removeprefix("openai/")
            if config.model.startswith("openai/")
            else config.model
        )

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts with retry logic.

        Args:
            texts: List of input texts (max batch_size)

        Returns:
            List of embedding vectors (same order as inputs)

        Raises:
            ValueError: If batch size exceeds config limit
            httpx.HTTPError: For API failures after all retries
        """
        if len(texts) > self.config.batch_size:
            raise ValueError(f"Batch size {len(texts)} exceeds limit {self.config.batch_size}")

        if not texts:
            return []

        for attempt in range(self.config.max_retries):
            try:
                response = await self.client.embeddings.create(model=self.model_name, input=texts)

                # Extract vectors in original order
                embeddings = [item.embedding for item in response.data]

                # Validate dimensionality
                for i, emb in enumerate(embeddings):
                    if len(emb) != self.config.dimensions:
                        raise ValueError(
                            f"Expected {self.config.dimensions} dimensions, "
                            f"got {len(emb)} for text {i}"
                        )

                logger.debug(
                    f"Embedded {len(texts)} texts with {self.model_name} "
                    f"(attempt {attempt + 1}/{self.config.max_retries})"
                )
                return embeddings

            except httpx.TimeoutException as e:
                logger.warning(
                    f"Timeout embedding batch "
                    f"(attempt {attempt + 1}/{self.config.max_retries}): {e}"
                )
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(2**attempt)  # Exponential backoff
                else:
                    raise

            except RateLimitError as e:
                logger.warning(
                    f"Rate limited (attempt {attempt + 1}/{self.config.max_retries}): {e}"
                )
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(2 ** (attempt + 1))  # Longer backoff
                else:
                    raise

            except httpx.HTTPStatusError as e:
                # Non-retryable HTTP error
                logger.error(f"HTTP error embedding batch: {e}")
                raise

        raise RuntimeError("Exhausted all retry attempts")

    async def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        embeddings = await self.embed_batch([text])
        return embeddings[0]


class LocalEmbedding:
    """Placeholder for local embedding models (sentence-transformers, etc.).

    TODO: Implement using sentence-transformers or similar library.
    """

    def __init__(self, config: EmbeddingConfig):
        """Initialize local embedding model.

        Args:
            config: Embedding configuration
        """
        self.config = config
        raise NotImplementedError("Local embeddings not yet implemented. Use OpenAI for now.")

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using local model."""
        raise NotImplementedError

    async def embed_single(self, text: str) -> list[float]:
        """Generate embedding using local model."""
        raise NotImplementedError


def create_embedding_client(config: EmbeddingConfig) -> EmbeddingClient:
    """Factory function to create embedding client based on model config.

    Args:
        config: Embedding configuration

    Returns:
        Embedding client implementation

    Example:
        >>> config = EmbeddingConfig(
        ...     model="openai/text-embedding-3-small",
        ...     version="v1",
        ...     dimensions=1536,
        ...     api_key="sk-..."
        ... )
        >>> client = create_embedding_client(config)
    """
    if config.model.startswith("openai/"):
        return OpenAIEmbedding(config)
    elif config.model.startswith("local/"):
        return LocalEmbedding(config)
    else:
        raise ValueError(
            f"Unknown model prefix in {config.model!r}. " f"Expected 'openai/' or 'local/'"
        )
