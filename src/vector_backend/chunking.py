"""Text chunking strategies for semantic search.

Implements configurable chunking with token-aware splitting and boundary preservation.
All chunking is deterministic: same input + config → same chunks.
"""

from dataclasses import dataclass
from typing import Protocol

import tiktoken
from langchain.text_splitter import RecursiveCharacterTextSplitter


@dataclass(frozen=True)
class ChunkingConfig:
    """Configuration for text chunking.

    Attributes:
        chunk_size: Target chunk size in tokens
        overlap: Number of overlapping tokens between chunks
        tokenizer: Tokenizer name (tiktoken encoding, e.g., "cl100k_base")
        preserve_boundaries: If True, adjust chunk boundaries to sentence ends
    """

    chunk_size: int = 400
    overlap: int = 50
    tokenizer: str = "cl100k_base"
    preserve_boundaries: bool = True

    def __post_init__(self) -> None:
        """Validate configuration parameters."""
        if self.chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive, got {self.chunk_size}")
        if self.overlap < 0:
            raise ValueError(f"overlap must be non-negative, got {self.overlap}")
        if self.overlap >= self.chunk_size:
            raise ValueError(
                f"overlap ({self.overlap}) must be less than chunk_size ({self.chunk_size})"
            )


@dataclass(frozen=True)
class Chunk:
    """A single text chunk with position information.

    Attributes:
        text: Chunk text content
        start_byte: Starting character offset in original text
            (Note: named 'byte' for legacy reasons)
        end_byte: Ending character offset in original text
            (Note: named 'byte' for legacy reasons)
        token_count: Number of tokens in this chunk
        chunk_index: 0-indexed position in the list of chunks

    Note:
        Despite the naming, start_byte and end_byte are character positions, not byte positions.
        This ensures correct handling of multi-byte Unicode characters.
    """

    text: str
    start_byte: int
    end_byte: int
    token_count: int
    chunk_index: int

    def __post_init__(self) -> None:
        """Validate chunk properties."""
        if not self.text:
            raise ValueError("Chunk text cannot be empty")
        if self.start_byte < 0 or self.end_byte <= self.start_byte:
            raise ValueError(f"Invalid byte offsets: start={self.start_byte}, end={self.end_byte}")
        if self.token_count <= 0:
            raise ValueError(f"token_count must be positive, got {self.token_count}")
        if self.chunk_index < 0:
            raise ValueError(f"chunk_index must be non-negative, got {self.chunk_index}")


class Chunker(Protocol):
    """Protocol for text chunking implementations."""

    def chunk(self, text: str) -> list[Chunk]:
        """Split text into overlapping chunks.

        Args:
            text: Input text to chunk

        Returns:
            List of Chunk objects in order
        """
        ...


class RecursiveTokenChunker:
    """Token-aware recursive text chunker.

    Uses langchain's RecursiveCharacterTextSplitter with tiktoken for accurate
    token counting. Respects sentence boundaries when preserve_boundaries=True.
    """

    def __init__(self, config: ChunkingConfig):
        """Initialize chunker with configuration.

        Args:
            config: Chunking configuration
        """
        self.config = config
        self.encoding = tiktoken.get_encoding(config.tokenizer)

        # Langchain splitter with custom token counter
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.overlap,
            length_function=self._count_tokens,
            separators=["\n\n", "\n", ". ", " ", ""] if config.preserve_boundaries else None,
        )

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken.

        Args:
            text: Input text

        Returns:
            Token count
        """
        return len(self.encoding.encode(text, disallowed_special=()))

    def chunk(self, text: str) -> list[Chunk]:
        """Split text into overlapping chunks.

        Args:
            text: Input text to chunk

        Returns:
            List of Chunk objects in order

        Raises:
            ValueError: If input text is empty
        """
        if not text or not text.strip():
            raise ValueError("Input text cannot be empty")

        # Use langchain to split text
        text_chunks = self.splitter.split_text(text)

        # Convert to Chunk objects with character offsets
        # Note: We use character positions, not byte positions, to handle Unicode correctly
        chunks: list[Chunk] = []
        current_pos = 0

        for idx, chunk_text in enumerate(text_chunks):
            # Find chunk in original text (accounting for overlap)
            start_char = text.find(chunk_text, current_pos)
            if start_char == -1:
                # Fallback: chunk might be modified by splitter, use current position
                start_char = max(0, current_pos)

            end_char = start_char + len(chunk_text)

            # Ensure positions are valid
            if start_char < 0 or end_char > len(text):
                # Skip chunks with invalid positions (edge case with modified text)
                continue

            token_count = self._count_tokens(chunk_text)

            chunks.append(
                Chunk(
                    text=chunk_text,
                    start_byte=start_char,  # Note: These are character positions, not bytes
                    end_byte=end_char,
                    token_count=token_count,
                    chunk_index=idx,
                )
            )

            # Move position forward (accounting for overlap)
            # Ensure current_pos never goes negative
            current_pos = max(0, start_char + len(chunk_text) - self.config.overlap)

        return chunks


def chunk_text(
    text: str,
    chunk_size: int = 400,
    overlap: int = 50,
    tokenizer: str = "cl100k_base",
    preserve_boundaries: bool = True,
) -> list[Chunk]:
    """Convenience function to chunk text with default config.

    Args:
        text: Input text to chunk
        chunk_size: Target chunk size in tokens
        overlap: Number of overlapping tokens
        tokenizer: Tokenizer name
        preserve_boundaries: Whether to respect sentence boundaries

    Returns:
        List of Chunk objects

    Example:
        >>> chunks = chunk_text("Long text here...", chunk_size=400, overlap=50)
        >>> len(chunks)
        3
    """
    config = ChunkingConfig(
        chunk_size=chunk_size,
        overlap=overlap,
        tokenizer=tokenizer,
        preserve_boundaries=preserve_boundaries,
    )
    chunker = RecursiveTokenChunker(config)
    return chunker.chunk(text)
