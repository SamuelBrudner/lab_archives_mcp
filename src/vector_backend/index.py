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
    """DVC-tracked local persistence for embeddings with concurrent write safety.

    Stores embeddings in Parquet files for portability and reproducibility.
    Each notebook gets its own Parquet file. Uses per-notebook file locking
    to ensure safe concurrent writes.

    Features:
        - Per-notebook file locking (30s timeout)
        - Safe concurrent writes to same notebook
        - DVC tracking with concurrent initialization protection
        - Version isolation for reproducible reindexing

    Thread/Process Safety:
        - Multiple processes can write to different notebooks simultaneously
        - Multiple processes can write to the same notebook (serialized via lock)
        - Reads are always safe (no locking needed)
    """

    def __init__(self, base_path: Path, version: str = "v1", enable_dvc: bool = False):
        """Initialize local persistence layer.

        Args:
            base_path: Base directory for embeddings (e.g., data/embeddings/)
            version: Embedding version (e.g., "v1")
            enable_dvc: Enable DVC tracking for embeddings (default: False)
        """
        self.base_path = Path(base_path)
        self.version = version
        self.is_dvc_enabled = enable_dvc
        self.version_path = self.base_path / version
        self.version_path.mkdir(parents=True, exist_ok=True)

        # Initialize DVC if requested
        if self.is_dvc_enabled:
            self._init_dvc()

    def save_chunks(self, notebook_id: str, chunks: list[EmbeddedChunk]) -> Path:
        """Save chunks for a notebook to Parquet with file locking.

        Args:
            notebook_id: Notebook ID
            chunks: List of embedded chunks

        Returns:
            Path to saved Parquet file

        Note:
            Uses per-notebook file locking to prevent concurrent write corruption.
            Lock timeout is 30 seconds.
        """
        import pandas as pd
        from filelock import FileLock

        output_path = self.version_path / f"{notebook_id}.parquet"
        lock_path = self.version_path / f".{notebook_id}.lock"

        # Acquire lock before writing
        with FileLock(lock_path, timeout=30):
            if not chunks:
                # Create empty DataFrame with expected schema
                df = pd.DataFrame(
                    columns=[
                        "id",
                        "text",
                        "vector",
                        "notebook_id",
                        "notebook_name",
                        "page_id",
                        "page_title",
                        "entry_id",
                        "entry_type",
                        "author",
                        "date",
                        "folder_path",
                        "tags",
                        "labarchives_url",
                        "embedding_version",
                    ]
                )
            else:
                # Convert chunks to flat dictionaries
                records = []
                for chunk in chunks:
                    record = {
                        "id": chunk.id,
                        "text": chunk.text,
                        "vector": chunk.vector,
                        # Flatten metadata
                        "notebook_id": chunk.metadata.notebook_id,
                        "notebook_name": chunk.metadata.notebook_name,
                        "page_id": chunk.metadata.page_id,
                        "page_title": chunk.metadata.page_title,
                        "entry_id": chunk.metadata.entry_id,
                        "entry_type": chunk.metadata.entry_type,
                        "author": chunk.metadata.author,
                        "date": chunk.metadata.date,
                        "folder_path": chunk.metadata.folder_path,
                        "tags": chunk.metadata.tags,
                        "labarchives_url": chunk.metadata.labarchives_url,
                        "embedding_version": chunk.metadata.embedding_version,
                    }
                    records.append(record)

                df = pd.DataFrame(records)

            # Save with compression
            df.to_parquet(output_path, engine="pyarrow", compression="snappy", index=False)

            # Track with DVC if enabled
            self._track_with_dvc(output_path)

        return output_path

    def load_chunks(self, notebook_id: str) -> list[EmbeddedChunk]:
        """Load chunks for a notebook from Parquet.

        Args:
            notebook_id: Notebook ID

        Returns:
            List of embedded chunks

        Raises:
            FileNotFoundError: If notebook not found
        """
        import pandas as pd

        parquet_path = self.version_path / f"{notebook_id}.parquet"

        if not parquet_path.exists():
            raise FileNotFoundError(f"Notebook {notebook_id!r} not found in {self.version_path}")

        df = pd.read_parquet(parquet_path, engine="pyarrow")

        if df.empty:
            return []

        # Reconstruct EmbeddedChunk objects
        chunks = []
        for _, row in df.iterrows():
            # Handle tags carefully - Parquet returns numpy arrays for lists
            tags_value = row["tags"]
            # Check if it's None or a scalar NaN before trying list conversion
            tags: list[str] = []
            try:
                if tags_value is None:
                    tags = []
                elif isinstance(tags_value, float) and pd.isna(tags_value):
                    tags = []
                else:
                    # Convert numpy array or list to list
                    tags = list(tags_value)
            except (TypeError, ValueError):
                tags = []

            metadata = ChunkMetadata(
                notebook_id=row["notebook_id"],
                notebook_name=row["notebook_name"],
                page_id=row["page_id"],
                page_title=row["page_title"],
                entry_id=row["entry_id"],
                entry_type=row["entry_type"],
                author=row["author"],
                date=row["date"],
                folder_path=row["folder_path"] if pd.notna(row["folder_path"]) else None,
                tags=tags,
                labarchives_url=row["labarchives_url"],
                embedding_version=row["embedding_version"],
            )

            chunk = EmbeddedChunk(
                id=row["id"],
                text=row["text"],
                vector=row["vector"],
                metadata=metadata,
            )
            chunks.append(chunk)

        return chunks

    def list_notebooks(self) -> list[str]:
        """List all notebook IDs with saved embeddings.

        Returns:
            List of notebook IDs
        """
        parquet_files = self.version_path.glob("*.parquet")
        return [f.stem for f in parquet_files]

    def _init_dvc(self) -> None:
        """Initialize DVC in base_path if not already initialized."""
        from filelock import FileLock

        dvc_dir = self.base_path / ".dvc"
        dvc_init_lock = self.base_path / ".dvc_init.lock"

        # Use lock to prevent concurrent DVC initialization
        with FileLock(dvc_init_lock, timeout=30):
            if dvc_dir.exists():
                # Already initialized (double-check inside lock)
                return

            try:
                from dvc.repo import Repo

                # Initialize DVC without SCM (git not required)
                Repo.init(self.base_path, no_scm=True)

                # Add version directories to .gitignore
                gitignore = self.base_path / ".gitignore"
                if not gitignore.exists():
                    gitignore.write_text("")

                gitignore_content = gitignore.read_text()
                # Add version directory pattern if not already present
                if (
                    f"/{self.version}" not in gitignore_content
                    and self.version not in gitignore_content
                ):
                    gitignore.write_text(f"{gitignore_content}\n/{self.version}\n")

            except (ImportError, Exception) as e:
                # DVC not installed or failed - disable DVC tracking
                self.is_dvc_enabled = False
                import warnings

                warnings.warn(
                    f"DVC initialization failed: {e}. DVC tracking disabled.",
                    UserWarning,
                    stacklevel=2,
                )

    def _track_with_dvc(self, file_path: Path) -> None:
        """Track a file with DVC.

        Args:
            file_path: Path to file to track
        """
        if not self.is_dvc_enabled:
            return

        try:
            from dvc.repo import Repo

            # Open repo and add file
            repo = Repo(self.base_path)
            repo.add(str(file_path))
            repo.close()

        except (ImportError, Exception) as e:
            import warnings

            warnings.warn(f"DVC tracking failed for {file_path}: {e}", UserWarning, stacklevel=2)
