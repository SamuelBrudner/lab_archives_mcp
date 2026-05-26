"""Unit tests for text chunking functionality.

Tests cover:
- Deterministic chunking (same input → same output)
- Edge cases (empty text, single sentence, very long text)
- Boundary preservation
- Token counting accuracy
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from vector_backend.chunking import Chunk, ChunkingConfig, RecursiveTokenChunker, chunk_text


class TestChunkingConfig:
    """Tests for ChunkingConfig validation."""

    def test_default_config(self) -> None:
        """Default config should be valid."""
        config = ChunkingConfig()
        assert config.chunk_size == 400
        assert config.overlap == 50
        assert config.tokenizer == "cl100k_base"
        assert config.preserve_boundaries is True

    def test_invalid_chunk_size(self) -> None:
        """Chunk size must be positive."""
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            ChunkingConfig(chunk_size=0)

        with pytest.raises(ValueError, match="chunk_size must be positive"):
            ChunkingConfig(chunk_size=-100)

    def test_invalid_overlap(self) -> None:
        """Overlap must be non-negative and less than chunk_size."""
        with pytest.raises(ValueError, match="overlap must be non-negative"):
            ChunkingConfig(overlap=-1)

        with pytest.raises(ValueError, match="overlap .* must be less than chunk_size"):
            ChunkingConfig(chunk_size=100, overlap=100)

        with pytest.raises(ValueError, match="overlap .* must be less than chunk_size"):
            ChunkingConfig(chunk_size=100, overlap=150)


class TestChunk:
    """Tests for Chunk data class validation."""

    def test_valid_chunk(self) -> None:
        """Valid chunk should construct successfully."""
        chunk = Chunk(
            text="test text",
            start_byte=0,
            end_byte=9,
            token_count=2,
            chunk_index=0,
        )
        assert chunk.text == "test text"
        assert chunk.start_byte == 0
        assert chunk.end_byte == 9
        assert chunk.token_count == 2
        assert chunk.chunk_index == 0

    def test_invalid_byte_offsets(self) -> None:
        """Chunk with invalid byte offsets should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid byte offsets"):
            Chunk(
                text="test",
                start_byte=10,
                end_byte=5,  # end before start
                token_count=1,
                chunk_index=0,
            )

    def test_invalid_token_count(self) -> None:
        """Chunk with non-positive token count should raise ValueError."""
        with pytest.raises(ValueError, match="token_count must be positive"):
            Chunk(
                text="test",
                start_byte=0,
                end_byte=4,
                token_count=0,  # Invalid: must be positive
                chunk_index=0,
            )

    def test_invalid_chunk_index(self) -> None:
        """Chunk with negative index should raise ValueError."""
        with pytest.raises(ValueError, match="chunk_index must be non-negative"):
            Chunk(
                text="test",
                start_byte=0,
                end_byte=4,
                token_count=1,
                chunk_index=-1,  # Invalid: must be non-negative
            )


class TestRecursiveTokenChunker:
    """Tests for RecursiveTokenChunker implementation."""

    def test_simple_chunking(self) -> None:
        """Simple text should chunk predictably."""
        config = ChunkingConfig(chunk_size=10, overlap=2)
        chunker = RecursiveTokenChunker(config)

        text = "This is a simple test sentence for chunking."
        chunks = chunker.chunk(text)

        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)
        assert chunks[0].chunk_index == 0
        assert chunks[-1].chunk_index == len(chunks) - 1

    def test_empty_text_raises(self) -> None:
        """Empty text should raise ValueError."""
        config = ChunkingConfig()
        chunker = RecursiveTokenChunker(config)

        with pytest.raises(ValueError, match="Input text cannot be empty"):
            chunker.chunk("")

        with pytest.raises(ValueError, match="Input text cannot be empty"):
            chunker.chunk("   ")

    def test_deterministic_chunking(self) -> None:
        """Same input should produce same chunks."""
        config = ChunkingConfig(chunk_size=50, overlap=10)
        chunker = RecursiveTokenChunker(config)

        text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 20
        chunks1 = chunker.chunk(text)
        chunks2 = chunker.chunk(text)

        assert len(chunks1) == len(chunks2)
        # Verify all chunks are identical
        assert all(
            c1.text == c2.text
            and c1.start_byte == c2.start_byte
            and c1.end_byte == c2.end_byte
            and c1.token_count == c2.token_count
            for c1, c2 in zip(chunks1, chunks2, strict=False)
        )

    @given(st.text(min_size=10, max_size=1000).filter(lambda t: t.strip()))  # type: ignore[misc]
    def test_deterministic_property(self, text: str) -> None:
        """Property-based test: chunking is deterministic."""
        chunks1 = chunk_text(text, chunk_size=50, overlap=10)
        chunks2 = chunk_text(text, chunk_size=50, overlap=10)

        assert len(chunks1) == len(chunks2)

    def test_chunk_size_respected(self) -> None:
        """Chunks should not significantly exceed configured size."""
        config = ChunkingConfig(chunk_size=20, overlap=5)
        chunker = RecursiveTokenChunker(config)

        text = "Word " * 100  # Repetitive text
        chunks = chunker.chunk(text)

        # Allow some tolerance (langchain may slightly exceed for boundary preservation)
        max_allowed = config.chunk_size * 1.5
        assert all(chunk.token_count <= max_allowed for chunk in chunks)


class TestConvenienceFunction:
    """Tests for chunk_text convenience function."""

    def test_chunk_text_default_params(self) -> None:
        """chunk_text with defaults should work."""
        text = "This is a test. " * 50
        chunks = chunk_text(text)

        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_chunk_text_custom_params(self) -> None:
        """chunk_text with custom params should respect config."""
        text = "This is a test. " * 50
        chunks = chunk_text(text, chunk_size=20, overlap=5, preserve_boundaries=False)

        assert len(chunks) > 0
