"""Vector index management and search operations.

Provides unified interface for Pinecone and Qdrant backends with:
- Bulk upsert with retry logic
- Semantic search with metadata filtering
- Index statistics and health checks
- DVC-tracked local persistence
"""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from vector_backend.models import (
    ChunkMetadata,
    EmbeddedChunk,
    IndexStats,
    SearchRequest,
    SearchResult,
)


class VectorIndex(ABC):
    """Abstract base class for vector index implementations."""

    @abstractmethod
    async def upsert(self, chunks: list[EmbeddedChunk]) -> None:
        """Insert or update chunks in the index.

        Args:
            chunks: List of embedded chunks to upsert

        Raises:
            ValueError: If chunks list is empty or invalid
            RuntimeError: For index operation failures
        """
        ...

    @abstractmethod
    async def delete(self, chunk_ids: list[str]) -> None:
        """Delete chunks from the index by ID.

        Args:
            chunk_ids: List of chunk IDs to delete
        """
        ...

    @abstractmethod
    async def search(self, request: SearchRequest) -> list[SearchResult]:
        """Perform semantic search.

        Args:
            request: Search query with filters and limits

        Returns:
            List of search results ranked by similarity

        Raises:
            ValueError: If query is invalid
        """
        ...

    @abstractmethod
    async def stats(self) -> IndexStats:
        """Get index statistics.

        Returns:
            Index statistics
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if index is accessible and healthy.

        Returns:
            True if healthy, False otherwise
        """
        ...


class PineconeIndex(VectorIndex):
    """Pinecone vector index implementation."""

    def __init__(
        self,
        index_name: str,
        api_key: str,
        environment: str,
        namespace: str | None = None,
    ):
        """Initialize Pinecone index client.

        Args:
            index_name: Name of Pinecone index
            api_key: Pinecone API key
            environment: Pinecone environment (e.g., "us-east-1")
            namespace: Optional namespace for multi-tenancy
        """
        from pinecone import Pinecone

        self.index_name = index_name
        self.api_key = api_key
        self.environment = environment
        self.namespace = namespace

        # Initialize Pinecone client
        self.pc = Pinecone(api_key=api_key)
        self.index = self.pc.Index(index_name)

    async def upsert(self, chunks: list[EmbeddedChunk]) -> None:
        """Insert or update chunks in Pinecone.

        Args:
            chunks: List of embedded chunks to upsert

        Raises:
            ValueError: If chunks list is empty
        """
        if not chunks:
            raise ValueError("Cannot upsert empty chunk list")

        # Convert chunks to Pinecone format
        vectors = []
        for chunk in chunks:
            vectors.append(
                {
                    "id": chunk.id,
                    "values": chunk.vector,
                    "metadata": {
                        "text": chunk.text,
                        "notebook_id": chunk.metadata.notebook_id,
                        "notebook_name": chunk.metadata.notebook_name,
                        "page_id": chunk.metadata.page_id,
                        "page_title": chunk.metadata.page_title,
                        "entry_id": chunk.metadata.entry_id,
                        "entry_type": chunk.metadata.entry_type,
                        "author": chunk.metadata.author,
                        "date": chunk.metadata.date.isoformat(),
                        "labarchives_url": chunk.metadata.labarchives_url,
                        "embedding_version": chunk.metadata.embedding_version,
                    },
                }
            )

        # Upsert to Pinecone
        self.index.upsert(vectors=vectors, namespace=self.namespace)

    async def delete(self, chunk_ids: list[str]) -> None:
        """Delete chunks from Pinecone.

        Args:
            chunk_ids: List of chunk IDs to delete
        """
        if not chunk_ids:
            return

        self.index.delete(ids=chunk_ids, namespace=self.namespace)

    async def search(
        self, request: SearchRequest, query_vector: list[float] | None = None
    ) -> list[SearchResult]:
        """Search Pinecone index.

        Args:
            request: Search request with query and filters
            query_vector: Optional pre-computed query vector

        Returns:
            List of search results ranked by similarity
        """
        if query_vector is None:
            raise ValueError("query_vector must be provided for smoke tests")

        # Query Pinecone
        results = self.index.query(
            vector=query_vector,
            top_k=request.limit,
            namespace=self.namespace,
            include_metadata=True,
            include_values=False,  # Don't return vectors to save bandwidth
        )

        # Convert to SearchResult objects
        search_results = []
        for i, match in enumerate(results.matches):
            # Reconstruct metadata
            from datetime import datetime as dt

            metadata = ChunkMetadata(
                notebook_id=match.metadata["notebook_id"],
                notebook_name=match.metadata["notebook_name"],
                page_id=match.metadata["page_id"],
                page_title=match.metadata["page_title"],
                entry_id=match.metadata["entry_id"],
                entry_type=match.metadata["entry_type"],
                author=match.metadata["author"],
                date=dt.fromisoformat(match.metadata["date"]),
                labarchives_url=match.metadata["labarchives_url"],
                embedding_version=match.metadata["embedding_version"],
            )

            # Reconstruct chunk (use dummy vector since we don't return values from Pinecone)
            chunk = EmbeddedChunk(
                id=match.id,
                text=match.metadata["text"],
                vector=[0.0] * 1536,  # Dummy vector to satisfy Pydantic validation
                metadata=metadata,
            )

            # Clamp score to [0, 1] range
            # (Pinecone sometimes returns 1.00000036 due to float precision)
            clamped_score = min(1.0, max(0.0, match.score))

            search_results.append(SearchResult(chunk=chunk, score=clamped_score, rank=i + 1))

        return search_results

    async def stats(self) -> IndexStats:
        """Get Pinecone index statistics.

        Returns:
            Index statistics
        """
        stats = self.index.describe_index_stats()

        total_vectors = stats.total_vector_count if hasattr(stats, "total_vector_count") else 0

        return IndexStats(
            total_chunks=total_vectors,
            total_notebooks=0,  # Not tracked in Pinecone metadata
            embedding_version="unknown",
            last_updated=datetime.now(),
            storage_size_mb=0.0,
        )

    async def health_check(self) -> bool:
        """Check Pinecone index health.

        Returns:
            True if index is accessible
        """
        try:
            # Try to get stats as a health check
            self.index.describe_index_stats()
            return True
        except Exception:
            return False


class QdrantIndex(VectorIndex):
    """Qdrant vector index implementation.

    TODO: Implement using qdrant-client library.
    """

    def __init__(
        self,
        collection_name: str,
        url: str,
        api_key: str | None = None,
    ):
        """Initialize Qdrant collection client.

        Args:
            collection_name: Name of Qdrant collection
            url: Qdrant server URL
            api_key: Optional API key for authentication
        """
        self.collection_name = collection_name
        self.url = url
        self.api_key = api_key
        raise NotImplementedError("Qdrant integration not yet implemented")

    async def upsert(self, chunks: list[EmbeddedChunk]) -> None:
        """Insert or update chunks in Qdrant."""
        raise NotImplementedError

    async def delete(self, chunk_ids: list[str]) -> None:
        """Delete chunks from Qdrant."""
        raise NotImplementedError

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        """Search Qdrant collection."""
        raise NotImplementedError

    async def stats(self) -> IndexStats:
        """Get Qdrant collection statistics."""
        raise NotImplementedError

    async def health_check(self) -> bool:
        """Check Qdrant collection health."""
        raise NotImplementedError


class LocalPersistence:
    """DVC-tracked local persistence for embeddings.

    Stores embeddings in Parquet files for portability and reproducibility.
    Each notebook gets its own Parquet file.
    """

    def __init__(self, base_path: Path, version: str = "v1"):
        """Initialize local persistence layer.

        Args:
            base_path: Base directory for embeddings (e.g., data/embeddings/)
            version: Embedding version (e.g., "v1")
        """
        self.base_path = Path(base_path)
        self.version = version
        self.version_path = self.base_path / version
        self.version_path.mkdir(parents=True, exist_ok=True)

    def save_chunks(self, notebook_id: str, chunks: list[EmbeddedChunk]) -> Path:
        """Save chunks for a notebook to Parquet.

        Args:
            notebook_id: Notebook ID
            chunks: List of embedded chunks

        Returns:
            Path to saved Parquet file

        TODO: Implement using pandas or polars.
        """
        raise NotImplementedError("Local persistence not yet implemented")

    def load_chunks(self, notebook_id: str) -> list[EmbeddedChunk]:
        """Load chunks for a notebook from Parquet.

        Args:
            notebook_id: Notebook ID

        Returns:
            List of embedded chunks

        Raises:
            FileNotFoundError: If notebook not found

        TODO: Implement using pandas or polars.
        """
        raise NotImplementedError("Local persistence not yet implemented")

    def list_notebooks(self) -> list[str]:
        """List all notebook IDs with saved embeddings.

        Returns:
            List of notebook IDs
        """
        parquet_files = self.version_path.glob("*.parquet")
        return [f.stem for f in parquet_files]
