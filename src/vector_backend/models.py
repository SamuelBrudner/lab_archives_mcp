"""Pydantic models for vector search data structures.

All data flowing through the vector backend is validated against these schemas.
This ensures fail-fast behavior and type safety throughout the pipeline.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ChunkMetadata(BaseModel):
    """Metadata for a single text chunk from LabArchives.

    Attributes:
        notebook_id: LabArchives notebook ID
        notebook_name: Human-readable notebook name
        page_id: LabArchives page tree_id
        page_title: Page title
        entry_id: LabArchives entry ID (eid)
        entry_type: Type of entry (text_entry, heading, plain_text, attachment_metadata)
        author: Entry author email
        date: Entry creation/modification date
        folder_path: Optional folder hierarchy path (e.g., "Project A/Experiments")
        tags: Optional list of user-defined tags
        labarchives_url: Direct URL to the entry in LabArchives web UI
        embedding_version: Embedding model version identifier (e.g., "openai-3-small-v1")
    """

    notebook_id: str
    notebook_name: str
    page_id: str
    page_title: str
    entry_id: str
    entry_type: str
    author: str
    date: datetime
    folder_path: str | None = None
    tags: list[str] = Field(default_factory=list)
    labarchives_url: str
    embedding_version: str

    @field_validator("entry_type")
    @classmethod
    def validate_entry_type(cls, v: str) -> str:
        """Ensure entry_type is one of the allowed values."""
        allowed = {"text_entry", "heading", "plain_text", "attachment_metadata"}
        if v not in allowed:
            raise ValueError(f"entry_type must be one of {allowed}, got {v!r}")
        return v

    @field_validator("labarchives_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Ensure URL is non-empty and looks vaguely like a URL."""
        if not v or not v.startswith(("http://", "https://")):
            raise ValueError(f"labarchives_url must be a valid HTTP(S) URL, got {v!r}")
        return v


class EmbeddedChunk(BaseModel):
    """A single embedded text chunk ready for vector index insertion.

    Attributes:
        id: Unique identifier using format: {notebook_id}_{page_id}_{entry_id}_{chunk_idx}
        text: Raw chunk text content (1-5000 characters)
        vector: Embedding vector (768-3072 dimensions depending on model)
        metadata: Associated metadata for filtering and display
    """

    id: str
    text: str = Field(min_length=1, max_length=5000)
    vector: list[float] = Field(min_length=768, max_length=3072)
    metadata: ChunkMetadata

    @field_validator("id")
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        """Ensure ID follows the required format."""
        parts = v.split("_")
        if len(parts) < 4:
            raise ValueError(f"ID must have format notebook_page_entry_chunk (4+ parts), got {v!r}")
        return v

    @field_validator("vector")
    @classmethod
    def validate_vector_values(cls, v: list[float]) -> list[float]:
        """Ensure vector contains valid finite floats."""
        import math

        for i, val in enumerate(v):
            if not math.isfinite(val):
                raise ValueError(f"Vector contains non-finite value at index {i}: {val}")
        return v


class SearchResult(BaseModel):
    """A single search result with similarity score.

    Attributes:
        chunk: The matched embedded chunk
        score: Similarity score (0.0-1.0, higher is better)
        rank: Result rank in the returned list (1-indexed)
    """

    chunk: EmbeddedChunk
    score: float = Field(ge=0.0, le=1.0)
    rank: int = Field(ge=1)


class SearchRequest(BaseModel):
    """A semantic search query request.

    Attributes:
        query: Natural language search query
        limit: Maximum number of results to return (default 10)
        min_score: Minimum similarity score threshold (default 0.0)
        filters: Optional metadata filters (e.g., {"notebook_id": "123"})
    """

    query: str = Field(min_length=1, max_length=1000)
    limit: int = Field(default=10, ge=1, le=100)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)
    filters: dict[str, str] | None = None


class IndexStats(BaseModel):
    """Statistics about the vector index.

    Attributes:
        total_chunks: Total number of chunks in the index
        total_notebooks: Number of unique notebooks indexed
        embedding_version: Current embedding version
        last_updated: Timestamp of last index update
        storage_size_mb: Approximate storage size in MB
    """

    total_chunks: int = Field(ge=0)
    total_notebooks: int = Field(ge=0)
    embedding_version: str
    last_updated: datetime
    storage_size_mb: float = Field(ge=0.0)
