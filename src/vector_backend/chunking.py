"""Text chunking strategies for semantic search.

Implements configurable chunking with token-aware splitting and boundary preservation.
All chunking is deterministic: same input + config → same chunks.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import Any, Protocol

import tiktoken

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:  # pragma: no cover - compatibility with older LangChain releases
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
    except ImportError:

        class RecursiveCharacterTextSplitter:  # type: ignore[no-redef]
            """Minimal offline fallback for LangChain's recursive text splitter."""

            def __init__(
                self,
                chunk_size: int,
                chunk_overlap: int,
                length_function: Callable[[str], int],
                separators: list[str] | None = None,
            ) -> None:
                self.chunk_size = chunk_size
                self.chunk_overlap = chunk_overlap
                self.length_function = length_function
                self.separators = separators or [""]

            def split_text(self, text: str) -> list[str]:
                """Split text deterministically using recursive separators."""
                splits = self._split_text(text, self.separators)
                return self._merge_splits(splits)

            def _split_text(self, text: str, separators: list[str]) -> list[str]:
                if self.length_function(text) <= self.chunk_size:
                    return [text]
                if not separators or separators[0] == "":
                    return self._split_by_window(text)

                separator = separators[0]
                if separator not in text:
                    return self._split_text(text, separators[1:])

                splits: list[str] = []
                for part in self._split_with_separator(text, separator):
                    if not part.strip():
                        continue
                    if self.length_function(part) <= self.chunk_size:
                        splits.append(part)
                    else:
                        splits.extend(self._split_text(part, separators[1:]))
                return splits

            @staticmethod
            def _split_with_separator(text: str, separator: str) -> list[str]:
                pieces = text.split(separator)
                parts = [
                    piece + separator if idx < len(pieces) - 1 else piece
                    for idx, piece in enumerate(pieces)
                ]
                return [part for part in parts if part]

            def _merge_splits(self, splits: list[str]) -> list[str]:
                chunks: list[str] = []
                current = ""

                for split in splits:
                    candidate = current + split
                    if current and self.length_function(candidate) > self.chunk_size:
                        chunks.append(current.strip())
                        overlap = self._suffix_with_token_limit(current, self.chunk_overlap)
                        current = overlap + split
                        if self.length_function(current) > self.chunk_size:
                            current = split
                    else:
                        current = candidate

                if current.strip():
                    chunks.append(current.strip())
                return chunks

            def _split_by_window(self, text: str) -> list[str]:
                chunks: list[str] = []
                start = 0

                while start < len(text):
                    end = self._max_end_with_token_limit(text, start)
                    chunk = text[start:end].strip()
                    if chunk:
                        chunks.append(chunk)
                    if end >= len(text):
                        break

                    overlap_start = (
                        start
                        + len(text[start:end])
                        - len(self._suffix_with_token_limit(text[start:end], self.chunk_overlap))
                    )
                    start = end if overlap_start <= start else overlap_start

                return chunks

            def _max_end_with_token_limit(self, text: str, start: int) -> int:
                low = start + 1
                high = len(text)
                best = low

                while low <= high:
                    midpoint = (low + high) // 2
                    if self.length_function(text[start:midpoint]) <= self.chunk_size:
                        best = midpoint
                        low = midpoint + 1
                    else:
                        high = midpoint - 1

                return best

            def _suffix_with_token_limit(self, text: str, token_limit: int) -> str:
                if token_limit <= 0 or not text:
                    return ""
                if self.length_function(text) <= token_limit:
                    return text

                low = 0
                high = len(text)
                while low < high:
                    midpoint = (low + high) // 2
                    if self.length_function(text[midpoint:]) > token_limit:
                        low = midpoint + 1
                    else:
                        high = midpoint
                return text[low:]


class _TokenEncoding(Protocol):
    """Encoding interface used for token counting."""

    def encode(self, text: str, disallowed_special: Any = ()) -> list[int]:
        """Encode text into token IDs."""
        ...


class _FallbackEncoding:
    """Deterministic token counter used only when tiktoken data is unavailable offline."""

    _token_pattern = re.compile(r"\w+|[^\w\s]", re.UNICODE)

    def encode(self, text: str, disallowed_special: Any = ()) -> list[int]:
        """Approximate token IDs using word/punctuation groups."""
        del disallowed_special
        token_count = 0
        for match in self._token_pattern.finditer(text):
            token_count += max(1, (len(match.group(0)) + 3) // 4)
        return list(range(token_count))


@cache
def _get_token_encoding(tokenizer: str) -> _TokenEncoding:
    try:
        return tiktoken.get_encoding(tokenizer)
    except Exception:
        return _FallbackEncoding()


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
        self.encoding = _get_token_encoding(config.tokenizer)

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
