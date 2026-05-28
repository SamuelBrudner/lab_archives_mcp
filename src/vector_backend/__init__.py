"""Vector search backend for LabArchives semantic search.

This package provides vector embedding, indexing, and retrieval functionality
independent of the MCP server interface. The MCP server in `labarchives_mcp`
consumes this backend as a service layer.

Architecture:
    - chunking: Text splitting with configurable strategies
    - embedding: OpenAI embedding client, with local models left as an extension point
    - indexing: Pinecone integration with local Parquet persistence
    - retrieval: Semantic search with metadata filtering
    - models: Pydantic schemas for chunks, embeddings, search results

Usage:
    >>> from vector_backend import PineconeIndex, SearchRequest
    >>> index = PineconeIndex(index_name="labarchives", api_key="...", environment="us-east-1")
    >>> results = await index.search(SearchRequest(query="protein aggregation", limit=10))
"""

__version__ = "0.5.0"

from vector_backend.index import PineconeIndex, QdrantIndex, VectorIndex
from vector_backend.models import (
    BuildRecord,
    ChunkMetadata,
    EmbeddedChunk,
    SearchRequest,
    SearchResult,
)

__all__ = [
    "VectorIndex",
    "PineconeIndex",
    "QdrantIndex",
    "ChunkMetadata",
    "EmbeddedChunk",
    "SearchRequest",
    "SearchResult",
    "BuildRecord",
]
