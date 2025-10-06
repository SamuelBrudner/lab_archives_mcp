"""Vector search backend for LabArchives semantic search.

This package provides vector embedding, indexing, and retrieval functionality
independent of the MCP server interface. The MCP server in `labarchives_mcp`
consumes this backend as a service layer.

Architecture:
    - chunking: Text splitting with configurable strategies
    - embedding: Model-agnostic embedding client (OpenAI, local models)
    - indexing: Pinecone/Qdrant integration with DVC-tracked persistence
    - retrieval: Semantic search with metadata filtering
    - models: Pydantic schemas for chunks, embeddings, search results

Usage:
    >>> from vector_backend import VectorIndex
    >>> index = VectorIndex.from_config("conf/vector_search/default.yaml")
    >>> results = index.search("protein aggregation in neurons", limit=10)
"""

__version__ = "0.2.1"

from vector_backend.models import BuildRecord, ChunkMetadata, EmbeddedChunk, SearchResult

__all__ = [
    "ChunkMetadata",
    "EmbeddedChunk",
    "SearchResult",
    "BuildRecord",
]
