"""Unit tests for embedding generation."""

import httpx
import pytest
import respx
from httpx import Response
from openai import RateLimitError

from vector_backend.embedding import EmbeddingConfig, OpenAIEmbedding, create_embedding_client


@pytest.fixture
def embedding_config() -> EmbeddingConfig:
    """Standard embedding configuration for tests."""
    return EmbeddingConfig(
        model="openai/text-embedding-3-small",
        version="v1",
        dimensions=1536,
        batch_size=100,
        max_retries=3,
        timeout_seconds=10.0,
        api_key="sk-test-key",
    )


class TestEmbeddingConfig:
    """Tests for EmbeddingConfig validation."""

    def test_valid_config(self, embedding_config):
        """Valid config should construct."""
        assert embedding_config.model == "openai/text-embedding-3-small"
        assert embedding_config.dimensions == 1536

    def test_invalid_dimensions(self):
        """Dimensions must be in valid range."""
        with pytest.raises(ValueError):
            EmbeddingConfig(model="test", version="v1", dimensions=50, api_key="test")

        with pytest.raises(ValueError):
            EmbeddingConfig(model="test", version="v1", dimensions=5000, api_key="test")

    def test_invalid_batch_size(self):
        """Batch size must be positive and reasonable."""
        with pytest.raises(ValueError):
            EmbeddingConfig(model="test", version="v1", dimensions=1536, batch_size=0)

        with pytest.raises(ValueError):
            EmbeddingConfig(model="test", version="v1", dimensions=1536, batch_size=1000)


class TestOpenAIEmbedding:
    """Tests for OpenAI embedding client."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_embed_single_success(self, embedding_config):
        """Single text should embed successfully."""
        # Mock OpenAI API response
        respx.post("https://api.openai.com/v1/embeddings").mock(
            return_value=Response(
                200,
                json={
                    "data": [{"embedding": [0.1] * 1536, "index": 0}],
                    "model": "text-embedding-3-small",
                    "usage": {"total_tokens": 5},
                },
            )
        )

        client = OpenAIEmbedding(embedding_config)
        vector = await client.embed_single("Test text")

        assert len(vector) == 1536
        assert all(isinstance(v, float) for v in vector)

    @pytest.mark.asyncio
    @respx.mock
    async def test_embed_batch_success(self, embedding_config):
        """Batch of texts should embed in order."""
        respx.post("https://api.openai.com/v1/embeddings").mock(
            return_value=Response(
                200,
                json={
                    "data": [
                        {"embedding": [0.1] * 1536, "index": 0},
                        {"embedding": [0.2] * 1536, "index": 1},
                        {"embedding": [0.3] * 1536, "index": 2},
                    ],
                    "model": "text-embedding-3-small",
                    "usage": {"total_tokens": 15},
                },
            )
        )

        client = OpenAIEmbedding(embedding_config)
        vectors = await client.embed_batch(["Text 1", "Text 2", "Text 3"])

        assert len(vectors) == 3
        assert all(len(v) == 1536 for v in vectors)
        # Check vectors are distinct
        assert vectors[0] != vectors[1]
        assert vectors[1] != vectors[2]

    @pytest.mark.asyncio
    async def test_batch_size_exceeded(self, embedding_config):
        """Batch size over limit should raise ValueError."""
        client = OpenAIEmbedding(embedding_config)

        with pytest.raises(ValueError, match="Batch size .* exceeds limit"):
            await client.embed_batch(["text"] * 101)  # Exceeds 100

    @pytest.mark.asyncio
    @respx.mock
    async def test_retry_on_rate_limit(self, embedding_config):
        """Rate limit (429) should trigger retry with backoff."""
        # First call: rate limited
        # Second call: success
        respx.post("https://api.openai.com/v1/embeddings").mock(
            side_effect=[
                Response(429, json={"error": {"message": "Rate limit exceeded"}}),
                Response(
                    200,
                    json={
                        "data": [{"embedding": [0.1] * 1536, "index": 0}],
                        "model": "text-embedding-3-small",
                    },
                ),
            ]
        )

        embedding_config.max_retries = 3
        client = OpenAIEmbedding(embedding_config)
        vector = await client.embed_single("Test")

        assert len(vector) == 1536
        # Should have made 2 requests (1 failure + 1 success)
        assert len(respx.calls) == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_exhausted_retries_raises(self, embedding_config):
        """Exhausting retries should raise error."""
        # All calls fail with rate limit
        respx.post("https://api.openai.com/v1/embeddings").mock(
        )

        embedding_config.max_retries = 2
        client = OpenAIEmbedding(embedding_config)

        # OpenAI SDK may wrap the error
        with pytest.raises((httpx.HTTPStatusError, RateLimitError)):
            await client.embed_single("Test")

    @pytest.mark.asyncio
    @respx.mock
    async def test_dimension_mismatch_raises(self, embedding_config):
        respx.post("https://api.openai.com/v1/embeddings").mock(
            return_value=Response(
                200,
                json={
                    "data": [{"embedding": [0.1] * 768, "index": 0}],  # Wrong size!
                    "model": "text-embedding-3-small",
                },
            )
        )

        client = OpenAIEmbedding(embedding_config)

        with pytest.raises(ValueError, match="Expected 1536 dimensions"):
            await client.embed_single("Test")

    @pytest.mark.asyncio
    async def test_empty_batch_returns_empty(self, embedding_config):
        """Empty batch should return empty list without API call."""
        client = OpenAIEmbedding(embedding_config)
        vectors = await client.embed_batch([])

        assert vectors == []


class TestCreateEmbeddingClient:
    """Tests for factory function."""

    def test_create_openai_client(self):
        """OpenAI model prefix should create OpenAI client."""
        config = EmbeddingConfig(
            model="openai/text-embedding-3-small",
            version="v1",
            dimensions=1536,
            api_key="test",
        )
        client = create_embedding_client(config)

        assert isinstance(client, OpenAIEmbedding)

    def test_create_local_client_not_implemented(self):
        """Local model prefix should raise NotImplementedError."""
        config = EmbeddingConfig(model="local/bge-large", version="v1", dimensions=1024)

        with pytest.raises(NotImplementedError):
            create_embedding_client(config)

    def test_unknown_model_prefix_raises(self):
        """Unknown model prefix should raise ValueError."""
        config = EmbeddingConfig(model="unknown/model", version="v1", dimensions=1536)

        with pytest.raises(ValueError, match="Unknown model prefix"):
            create_embedding_client(config)
