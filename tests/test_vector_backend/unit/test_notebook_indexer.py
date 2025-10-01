"""Unit tests for end-to-end notebook indexing workflow."""

from unittest.mock import AsyncMock

import pytest

from vector_backend.notebook_indexer import NotebookIndexer, index_notebook


class TestNotebookIndexer:
    """Tests for NotebookIndexer class."""

    @pytest.fixture
    def mock_embedding_client(self):
        """Mock embedding client."""
        client = AsyncMock()
        client.embed_batch = AsyncMock(return_value=[[0.1] * 1536, [0.2] * 1536])
        return client

    @pytest.fixture
    def mock_index(self):
        """Mock vector index."""
        index = AsyncMock()
        index.upsert = AsyncMock()
        return index

    @pytest.fixture
    def sample_page_data(self):
        """Sample LabArchives page data."""
        return {
            "notebook_id": "nb_123",
            "notebook_name": "Research Notebook",
            "page_id": "page_456",
            "page_title": "Experiment 1",
            "entries": [
                {
                    "eid": "entry_1",
                    "part_type": "heading",
                    "content": "Methods",
                    "created_at": "2025-09-30T10:00:00Z",
                    "updated_at": "2025-09-30T10:00:00Z",
                },
                {
                    "eid": "entry_2",
                    "part_type": "text_entry",
                    "content": "<p>We used <b>protein</b> extraction protocols.</p>",
                    "created_at": "2025-09-30T11:00:00Z",
                    "updated_at": "2025-09-30T11:00:00Z",
                },
                {
                    "eid": "entry_3",
                    "part_type": "attachment",
                    "content": "data.xlsx",
                    "created_at": "2025-09-30T12:00:00Z",
                    "updated_at": "2025-09-30T12:00:00Z",
                },
            ],
        }

    @pytest.mark.asyncio
    async def test_index_page_success(self, mock_embedding_client, mock_index, sample_page_data):
        """Should successfully index a page with multiple entries."""
        indexer = NotebookIndexer(
            embedding_client=mock_embedding_client,
            vector_index=mock_index,
            embedding_version="v1",
        )

        result = await indexer.index_page(
            page_data=sample_page_data,
            author="test@example.com",
            labarchives_url="https://example.com/notebook",
        )

        # Should have indexed 2 entries (heading + text_entry, skipped attachment)
        assert result["indexed_count"] == 2
        assert result["skipped_count"] == 1
        assert result["page_id"] == "page_456"

        # Should have called embed_batch once with 2 texts
        mock_embedding_client.embed_batch.assert_called_once()
        call_args = mock_embedding_client.embed_batch.call_args[0][0]
        assert len(call_args) == 2
        assert "Methods" in call_args[0]
        assert "protein" in call_args[1]

        # Should have upserted 2 chunks
        mock_index.upsert.assert_called_once()
        upserted_chunks = mock_index.upsert.call_args[0][0]
        assert len(upserted_chunks) == 2

    @pytest.mark.asyncio
    async def test_index_page_skips_all_non_text(self, mock_embedding_client, mock_index):
        """Should handle page with no indexable content."""
        indexer = NotebookIndexer(
            embedding_client=mock_embedding_client,
            vector_index=mock_index,
            embedding_version="v1",
        )

        page_data = {
            "notebook_id": "nb_123",
            "notebook_name": "Research Notebook",
            "page_id": "page_789",
            "page_title": "Images Only",
            "entries": [
                {
                    "eid": "entry_1",
                    "part_type": "image",
                    "content": "image1.jpg",
                    "created_at": "2025-09-30T10:00:00Z",
                    "updated_at": "2025-09-30T10:00:00Z",
                },
                {
                    "eid": "entry_2",
                    "part_type": "attachment",
                    "content": "file.pdf",
                    "created_at": "2025-09-30T11:00:00Z",
                    "updated_at": "2025-09-30T11:00:00Z",
                },
            ],
        }

        result = await indexer.index_page(
            page_data=page_data,
            author="test@example.com",
            labarchives_url="https://example.com/notebook",
        )

        assert result["indexed_count"] == 0
        assert result["skipped_count"] == 2

        # Should not call embedding or indexing
        mock_index.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_index_page_with_chunking(self, mock_embedding_client, mock_index):
        """Should chunk long text entries."""
        from vector_backend.chunking import ChunkingConfig

        indexer = NotebookIndexer(
            embedding_client=mock_embedding_client,
            vector_index=mock_index,
            embedding_version="v1",
            chunking_config=ChunkingConfig(
                chunk_size=50,  # Small chunk size to force chunking
                overlap=10,  # Must be less than chunk_size
            ),
        )

        # Long text that will be chunked
        long_text = " ".join(["word"] * 100)  # 100 words

        page_data = {
            "notebook_id": "nb_123",
            "notebook_name": "Research Notebook",
            "page_id": "page_999",
            "page_title": "Long Entry",
            "entries": [
                {
                    "eid": "entry_1",
                    "part_type": "text_entry",
                    "content": f"<p>{long_text}</p>",
                    "created_at": "2025-09-30T10:00:00Z",
                    "updated_at": "2025-09-30T10:00:00Z",
                },
            ],
        }

        # Mock embeddings for multiple chunks
        mock_embedding_client.embed_batch = AsyncMock(return_value=[[0.1] * 1536] * 3)  # 3 chunks

        result = await indexer.index_page(
            page_data=page_data,
            author="test@example.com",
            labarchives_url="https://example.com/notebook",
        )

        # Should have created multiple chunks
        assert result["indexed_count"] > 1


class TestConvenienceFunction:
    """Tests for index_notebook convenience function."""

    @pytest.mark.asyncio
    async def test_index_notebook_convenience(self):
        """Should provide convenient interface for indexing."""
        # This is a placeholder - actual test would mock MCP calls
        # For now, just verify the function exists and has right signature
        assert callable(index_notebook)
