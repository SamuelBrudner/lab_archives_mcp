"""Integration smoke tests for Pinecone vector index.

These tests require:
- PINECONE_API_KEY environment variable
- PINECONE_ENVIRONMENT environment variable
- Active Pinecone index (will use test index: 'labarchives-test')

Run with: pytest tests/test_vector_backend/integration/ -v -m integration
"""

import os
from datetime import datetime

import pytest

from vector_backend.config import IndexConfig
from vector_backend.index import PineconeIndex
from vector_backend.models import ChunkMetadata, EmbeddedChunk, SearchRequest

pytestmark = pytest.mark.integration


@pytest.fixture
def pinecone_config():
    """Pinecone configuration for testing."""
    api_key = os.environ.get("PINECONE_API_KEY")
    environment = os.environ.get("PINECONE_ENVIRONMENT", "us-east-1")

    if not api_key:
        pytest.skip("PINECONE_API_KEY not set")

    return IndexConfig(
        backend="pinecone",
        index_name="labarchives-test",
        namespace="test",
        api_key=api_key,
        environment=environment,
    )


@pytest.fixture
async def pinecone_index(pinecone_config):
    """Create Pinecone index client for testing."""
    index = PineconeIndex(
        index_name=pinecone_config.index_name,
        api_key=pinecone_config.api_key,
        environment=pinecone_config.environment,
        namespace=pinecone_config.namespace,
    )

    await index.health_check()
    yield index


@pytest.fixture
def sample_chunk():
    """Sample embedded chunk for testing."""
    metadata = ChunkMetadata(
        notebook_id="test_nb_001",
        notebook_name="Test Notebook",
        page_id="test_page_001",
        page_title="Test Page",
        entry_id="test_entry_001",
        entry_type="text_entry",
        author="test@example.com",
        date=datetime(2025, 9, 30),
        labarchives_url="https://example.com/test",
        embedding_version="test-v1",
    )

    return EmbeddedChunk(
        id="test_nb_001_test_page_001_test_entry_001_0",
        text="This is a test chunk about protein aggregation.",
        vector=[0.1] * 1536,
        metadata=metadata,
    )


class TestPineconeConnection:
    """Test basic Pinecone connectivity."""

    @pytest.mark.asyncio
    async def test_health_check(self, pinecone_index):
        """Should connect to Pinecone successfully."""
        is_healthy = await pinecone_index.health_check()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_stats_retrieval(self, pinecone_index):
        """Should retrieve index statistics."""
        stats = await pinecone_index.stats()
        assert stats.total_chunks >= 0


class TestPineconeUpsert:
    """Test upserting chunks to Pinecone."""

    @pytest.mark.asyncio
    async def test_upsert_single_chunk(self, pinecone_index, sample_chunk):
        """Should upsert a single chunk successfully."""
        await pinecone_index.upsert([sample_chunk])

    @pytest.mark.asyncio
    async def test_upsert_empty_raises(self, pinecone_index):
        """Should raise error for empty chunk list."""
        with pytest.raises(ValueError):
            await pinecone_index.upsert([])


class TestPineconeSearch:
    """Test semantic search in Pinecone."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, pinecone_index, sample_chunk):
        """Should return search results."""
        import asyncio

        await pinecone_index.upsert([sample_chunk])
        await asyncio.sleep(5)  # Increased wait time for indexing

        request = SearchRequest(query="protein aggregation", limit=5)
        results = await pinecone_index.search(request, query_vector=sample_chunk.vector)

        assert len(results) > 0


class TestPineconeDelete:
    """Test deleting chunks from Pinecone."""

    @pytest.mark.asyncio
    async def test_delete_by_id(self, pinecone_index, sample_chunk):
        """Should delete chunks by ID."""
        import asyncio

        await pinecone_index.upsert([sample_chunk])
        await asyncio.sleep(1)

        await pinecone_index.delete([sample_chunk.id])
