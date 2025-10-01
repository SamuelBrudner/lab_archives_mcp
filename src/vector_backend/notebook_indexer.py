"""End-to-end notebook indexing workflow.

Combines text extraction, chunking, embedding, and vector indexing.
"""

from datetime import datetime
from typing import Any

from loguru import logger

from vector_backend.chunking import ChunkingConfig, RecursiveTokenChunker
from vector_backend.embedding import EmbeddingClient
from vector_backend.index import VectorIndex
from vector_backend.labarchives_indexer import extract_text_from_entry
from vector_backend.models import ChunkMetadata, EmbeddedChunk


class NotebookIndexer:
    """Indexes LabArchives notebook pages into vector store.

    Handles the complete workflow:
    1. Extract text from entries
    2. Chunk long text
    3. Generate embeddings
    4. Store in vector index
    """

    def __init__(
        self,
        embedding_client: EmbeddingClient,
        vector_index: VectorIndex,
        embedding_version: str,
        chunking_config: ChunkingConfig | None = None,
    ):
        """Initialize notebook indexer.

        Args:
            embedding_client: Client for generating embeddings
            vector_index: Vector index for storage
            embedding_version: Version identifier for embeddings
            chunking_config: Configuration for text chunking (uses defaults if None)
        """
        self.embedding_client = embedding_client
        self.vector_index = vector_index
        self.embedding_version = embedding_version

        # Initialize chunker with provided config or defaults
        self.chunker = RecursiveTokenChunker(chunking_config or ChunkingConfig())

    async def index_page(
        self,
        page_data: dict[str, Any],
        author: str,
        labarchives_url: str,
    ) -> dict[str, Any]:
        """Index a single LabArchives page.

        Args:
            page_data: Page data dictionary containing:
                - notebook_id: Notebook ID
                - notebook_name: Notebook name
                - page_id: Page ID (tree_id)
                - page_title: Page title
                - entries: List of entry dictionaries
            author: Author email
            labarchives_url: URL to the notebook

        Returns:
            Dictionary with indexing results:
                - indexed_count: Number of chunks indexed
                - skipped_count: Number of entries skipped
                - page_id: Page ID that was indexed
        """
        notebook_id = page_data["notebook_id"]
        notebook_name = page_data["notebook_name"]
        page_id = page_data["page_id"]
        page_title = page_data["page_title"]
        entries = page_data["entries"]

        logger.info(
            f"Indexing page '{page_title}' (ID: {page_id}) " f"from notebook '{notebook_name}'"
        )

        # Extract text from all entries
        indexable_entries = []
        skipped_count = 0

        for entry_dict in entries:
            indexable_entry = extract_text_from_entry(entry_dict)
            if indexable_entry:
                indexable_entries.append((indexable_entry, entry_dict))
            else:
                skipped_count += 1
                entry_type = entry_dict.get("part_type", "unknown")
                logger.info(
                    f"  Skipped entry {entry_dict.get('eid', 'unknown')[:20]} "
                    f"(type: {entry_type})"
                )

        # If no indexable content, return early
        if not indexable_entries:
            logger.warning(f"No indexable content found on page {page_id}")
            return {
                "indexed_count": 0,
                "skipped_count": skipped_count,
                "page_id": page_id,
            }

        # Chunk all entries first
        all_chunks_with_metadata = []

        for indexable_entry, entry_dict in indexable_entries:
            # Chunk the text
            chunks = self.chunker.chunk(indexable_entry.text)

            # Store chunks with their entry metadata for later
            for chunk in chunks:
                all_chunks_with_metadata.append((chunk, indexable_entry, entry_dict))

        # Batch embed all chunks at once
        all_chunk_texts = [chunk.text for chunk, _, _ in all_chunks_with_metadata]
        all_vectors = await self.embedding_client.embed_batch(all_chunk_texts)

        # Create embedded chunks
        embedded_chunks = []
        for (chunk, indexable_entry, entry_dict), vector in zip(
            all_chunks_with_metadata, all_vectors, strict=False
        ):
            # Parse entry date
            created_at_str = entry_dict.get("created_at", "")
            try:
                entry_date = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                entry_date = datetime.now()

            # Create metadata
            metadata = ChunkMetadata(
                notebook_id=notebook_id,
                notebook_name=notebook_name,
                page_id=page_id,
                page_title=page_title,
                entry_id=indexable_entry.entry_id,
                entry_type=indexable_entry.entry_type.value,
                author=author,
                date=entry_date,
                labarchives_url=labarchives_url,
                embedding_version=self.embedding_version,
            )

            # Create embedded chunk
            chunk_id = f"{notebook_id}_{page_id}_{indexable_entry.entry_id}_{chunk.chunk_index}"
            embedded_chunk = EmbeddedChunk(
                id=chunk_id,
                text=chunk.text,
                vector=vector,
                metadata=metadata,
            )
            embedded_chunks.append(embedded_chunk)

        # Upsert to vector index
        if embedded_chunks:
            await self.vector_index.upsert(embedded_chunks)
            logger.info(
                f"Indexed {len(embedded_chunks)} chunks from {len(indexable_entries)} "
                f"entries on page '{page_title}'"
            )

        return {
            "indexed_count": len(embedded_chunks),
            "skipped_count": skipped_count,
            "page_id": page_id,
        }


async def index_notebook(
    notebook_id: str,
    page_ids: list[str] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Convenience function for indexing a notebook.

    Args:
        notebook_id: LabArchives notebook ID
        page_ids: Optional list of specific page IDs to index.
                 If None, indexes all pages.
        **kwargs: Additional arguments passed to NotebookIndexer

    Returns:
        Dictionary with indexing statistics

    Note:
        This is a placeholder. Full implementation will integrate
        with LabArchives MCP server to fetch notebook data.
    """
    # TODO: Implement full notebook indexing
    # This will require integrating with the LabArchives MCP server
    # to fetch notebook and page data
    raise NotImplementedError(
        "Full notebook indexing not yet implemented. "
        "Use NotebookIndexer.index_page() directly for now."
    )
