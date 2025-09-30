"""Unit tests for Pydantic models.

Tests validate:
- Field constraints
- Custom validators
- Fail-fast behavior for invalid data
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from vector_backend.models import ChunkMetadata, EmbeddedChunk, IndexStats, SearchRequest


class TestChunkMetadata:
    """Tests for ChunkMetadata validation."""

    def test_valid_metadata(self):
        """Valid metadata should construct successfully."""
        metadata = ChunkMetadata(
            notebook_id="123",
            notebook_name="Test Notebook",
            page_id="456",
            page_title="Test Page",
            entry_id="789",
            entry_type="text_entry",
            author="test@example.com",
            date=datetime(2025, 9, 30, 12, 0, 0),
            labarchives_url="https://labarchives.com/notebook/123/page/456",
            embedding_version="v1",
        )
        assert metadata.notebook_id == "123"
        assert metadata.entry_type == "text_entry"

    def test_invalid_entry_type(self):
        """Invalid entry_type should raise ValidationError."""
        with pytest.raises(ValidationError, match="entry_type must be one of"):
            ChunkMetadata(
                notebook_id="123",
                notebook_name="Test",
                page_id="456",
                page_title="Test",
                entry_id="789",
                entry_type="invalid_type",
                author="test@example.com",
                date=datetime.now(),
                labarchives_url="https://example.com",
                embedding_version="v1",
            )

    def test_invalid_url(self):
        """Invalid URL should raise ValidationError."""
        with pytest.raises(ValidationError, match="labarchives_url must be a valid"):
            ChunkMetadata(
                notebook_id="123",
                notebook_name="Test",
                page_id="456",
                page_title="Test",
                entry_id="789",
                entry_type="text_entry",
                author="test@example.com",
                date=datetime.now(),
                labarchives_url="not-a-url",
                embedding_version="v1",
            )

    def test_optional_fields(self):
        """Optional fields should work with defaults."""
        metadata = ChunkMetadata(
            notebook_id="123",
            notebook_name="Test",
            page_id="456",
            page_title="Test",
            entry_id="789",
            entry_type="text_entry",
            author="test@example.com",
            date=datetime.now(),
            labarchives_url="https://example.com",
            embedding_version="v1",
        )
        assert metadata.folder_path is None
        assert metadata.tags == []


class TestEmbeddedChunk:
    """Tests for EmbeddedChunk validation."""

    def test_valid_chunk(self):
        """Valid chunk should construct successfully."""
        metadata = ChunkMetadata(
            notebook_id="123",
            notebook_name="Test",
            page_id="456",
            page_title="Test",
            entry_id="789",
            entry_type="text_entry",
            author="test@example.com",
            date=datetime.now(),
            labarchives_url="https://example.com",
            embedding_version="v1",
        )
        chunk = EmbeddedChunk(
            id="123_456_789_0",
            text="Test chunk text",
            vector=[0.1] * 1536,
            metadata=metadata,
        )
        assert chunk.id == "123_456_789_0"
        assert len(chunk.vector) == 1536

    def test_invalid_id_format(self):
        """Invalid ID format should raise ValidationError."""
        metadata = ChunkMetadata(
            notebook_id="123",
            notebook_name="Test",
            page_id="456",
            page_title="Test",
            entry_id="789",
            entry_type="text_entry",
            author="test@example.com",
            date=datetime.now(),
            labarchives_url="https://example.com",
            embedding_version="v1",
        )
        with pytest.raises(ValidationError, match="ID must have format"):
            EmbeddedChunk(
                id="invalid",
                text="Test",
                vector=[0.1] * 1536,
                metadata=metadata,
            )

    def test_text_length_constraints(self):
        """Text must be 1-5000 characters."""
        metadata = ChunkMetadata(
            notebook_id="123",
            notebook_name="Test",
            page_id="456",
            page_title="Test",
            entry_id="789",
            entry_type="text_entry",
            author="test@example.com",
            date=datetime.now(),
            labarchives_url="https://example.com",
            embedding_version="v1",
        )

        # Empty text
        with pytest.raises(ValidationError):
            EmbeddedChunk(
                id="123_456_789_0",
                text="",
                vector=[0.1] * 1536,
                metadata=metadata,
            )

        # Too long text
        with pytest.raises(ValidationError):
            EmbeddedChunk(
                id="123_456_789_0",
                text="x" * 5001,
                vector=[0.1] * 1536,
                metadata=metadata,
            )

    def test_vector_dimension_constraints(self):
        """Vector must be 768-3072 dimensions."""
        metadata = ChunkMetadata(
            notebook_id="123",
            notebook_name="Test",
            page_id="456",
            page_title="Test",
            entry_id="789",
            entry_type="text_entry",
            author="test@example.com",
            date=datetime.now(),
            labarchives_url="https://example.com",
            embedding_version="v1",
        )

        # Too few dimensions
        with pytest.raises(ValidationError):
            EmbeddedChunk(
                id="123_456_789_0",
                text="Test",
                vector=[0.1] * 100,
                metadata=metadata,
            )

        # Too many dimensions
        with pytest.raises(ValidationError):
            EmbeddedChunk(
                id="123_456_789_0",
                text="Test",
                vector=[0.1] * 5000,
                metadata=metadata,
            )

    def test_non_finite_vector_values(self):
        """Non-finite vector values should raise ValidationError."""
        metadata = ChunkMetadata(
            notebook_id="123",
            notebook_name="Test",
            page_id="456",
            page_title="Test",
            entry_id="789",
            entry_type="text_entry",
            author="test@example.com",
            date=datetime.now(),
            labarchives_url="https://example.com",
            embedding_version="v1",
        )

        # Infinity
        with pytest.raises(ValidationError, match="non-finite value"):
            EmbeddedChunk(
                id="123_456_789_0",
                text="Test",
                vector=[float("inf")] * 1536,
                metadata=metadata,
            )

        # NaN
        with pytest.raises(ValidationError, match="non-finite value"):
            EmbeddedChunk(
                id="123_456_789_0",
                text="Test",
                vector=[float("nan")] * 1536,
                metadata=metadata,
            )


class TestSearchRequest:
    """Tests for SearchRequest validation."""

    def test_valid_request(self):
        """Valid search request should construct."""
        req = SearchRequest(query="test query", limit=10)
        assert req.query == "test query"
        assert req.limit == 10
        assert req.min_score == 0.0

    def test_query_length_constraints(self):
        """Query must be 1-1000 characters."""
        with pytest.raises(ValidationError):
            SearchRequest(query="")

        with pytest.raises(ValidationError):
            SearchRequest(query="x" * 1001)

    def test_limit_constraints(self):
        """Limit must be 1-100."""
        with pytest.raises(ValidationError):
            SearchRequest(query="test", limit=0)

        with pytest.raises(ValidationError):
            SearchRequest(query="test", limit=101)

    def test_min_score_constraints(self):
        """Min score must be 0.0-1.0."""
        with pytest.raises(ValidationError):
            SearchRequest(query="test", min_score=-0.1)

        with pytest.raises(ValidationError):
            SearchRequest(query="test", min_score=1.1)


class TestIndexStats:
    """Tests for IndexStats validation."""

    def test_valid_stats(self):
        """Valid stats should construct."""
        stats = IndexStats(
            total_chunks=1000,
            total_notebooks=10,
            embedding_version="v1",
            last_updated=datetime.now(),
            storage_size_mb=50.5,
        )
        assert stats.total_chunks == 1000
        assert stats.total_notebooks == 10

    def test_non_negative_constraints(self):
        """Counts and sizes must be non-negative."""
        with pytest.raises(ValidationError):
            IndexStats(
                total_chunks=-1,
                total_notebooks=10,
                embedding_version="v1",
                last_updated=datetime.now(),
                storage_size_mb=50.0,
            )
