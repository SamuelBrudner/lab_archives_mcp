from __future__ import annotations

from datetime import UTC, datetime

from vector_backend.index import VectorIndex
from vector_backend.models import EmbeddedChunk, IndexStats, SearchRequest, SearchResult


class StructuralIndex:
    async def upsert(self, chunks: list[EmbeddedChunk]) -> None:
        self.chunks = chunks

    async def delete(self, chunk_ids: list[str]) -> None:
        self.deleted = chunk_ids

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        self.last_request = request
        return []

    async def stats(self) -> IndexStats:
        return IndexStats(
            total_chunks=0,
            total_notebooks=0,
            embedding_version="test",
            last_updated=datetime.now(UTC),
            storage_size_mb=0.0,
        )

    async def health_check(self) -> bool:
        return True


def test_vector_index_accepts_structural_implementations() -> None:
    index: VectorIndex = StructuralIndex()

    assert isinstance(index, VectorIndex)
