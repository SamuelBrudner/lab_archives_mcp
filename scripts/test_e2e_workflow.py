#!/usr/bin/env python
"""End-to-end workflow test for vector backend.

This script tests the complete flow:
1. Chunk text
2. Generate embeddings
3. Upsert to Pinecone
4. Search and retrieve

Usage:
    export OPENAI_API_KEY="sk-..."
    export PINECONE_API_KEY="..."
    python scripts/test_e2e_workflow.py
"""

import asyncio
import os
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, "src")

from vector_backend.chunking import chunk_text
from vector_backend.config import load_config
from vector_backend.embedding import create_embedding_client
from vector_backend.index import PineconeIndex
from vector_backend.models import ChunkMetadata, EmbeddedChunk, SearchRequest


async def main():
    """Run end-to-end workflow."""
    print("=== Vector Backend End-to-End Test ===\n")

    # Load config
    print("1. Loading configuration...")
    config = load_config("default")
    print(f"   ✓ Model: {config.embedding.model}")
    print(f"   ✓ Chunk size: {config.chunking.chunk_size} tokens\n")

    # Sample text
    text = """
    Protein aggregation in neurons is a hallmark of neurodegenerative diseases.
    Recent research has shown that misfolded proteins can spread between cells
    through prion-like mechanisms. This has important implications for understanding
    disease progression and developing therapeutic interventions.
    """

    # Chunk text
    print("2. Chunking text...")
    chunks = chunk_text(
        text,
        chunk_size=config.chunking.chunk_size,
        overlap=config.chunking.overlap,
    )
    print(f"   ✓ Created {len(chunks)} chunks")
    for i, chunk in enumerate(chunks):
        print(f"     Chunk {i}: {chunk.token_count} tokens\n")

    # Generate embeddings
    print("3. Generating embeddings...")
    embedding_client = create_embedding_client(config.embedding)
    vectors = await embedding_client.embed_batch([chunk.text for chunk in chunks])
    print(f"   ✓ Generated {len(vectors)} embeddings ({len(vectors[0])} dimensions)\n")

    # Create embedded chunks
    print("4. Creating embedded chunks...")
    embedded_chunks = []
    for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=False)):
        metadata = ChunkMetadata(
            notebook_id="test_notebook_e2e",
            notebook_name="E2E Test Notebook",
            page_id="test_page_001",
            page_title="Protein Aggregation Research",
            entry_id=f"entry_{i}",
            entry_type="text_entry",
            author="test@example.com",
            date=datetime.now(),
            labarchives_url="https://example.com/test",
            embedding_version=config.embedding.version,
        )

        embedded_chunk = EmbeddedChunk(
            id=f"test_notebook_e2e_test_page_001_entry_{i}_{chunk.chunk_index}",
            text=chunk.text,
            vector=vector,
            metadata=metadata,
        )
        embedded_chunks.append(embedded_chunk)

    print(f"   ✓ Created {len(embedded_chunks)} embedded chunks\n")

    # Connect to Pinecone
    print("5. Connecting to Pinecone...")
    index = PineconeIndex(
        index_name="labarchives-test",
        api_key=config.index.api_key or os.environ.get("PINECONE_API_KEY"),
        environment=config.index.environment,
        namespace="e2e-test",
    )

    healthy = await index.health_check()
    if not healthy:
        print("   ✗ Failed to connect to Pinecone!")
        return
    print("   ✓ Connected successfully\n")

    # Upsert chunks
    print("6. Upserting chunks to Pinecone...")
    await index.upsert(embedded_chunks)
    print("   ✓ Upserted successfully\n")

    # Wait for indexing
    print("7. Waiting for indexing (2 seconds)...")
    await asyncio.sleep(2)
    print("   ✓ Done\n")

    # Search
    print("8. Searching for 'protein misfolding'...")
    query_text = "protein misfolding and disease progression"
    query_vector = await embedding_client.embed_single(query_text)

    request = SearchRequest(query=query_text, limit=3)
    results = await index.search(request, query_vector=query_vector)

    print(f"   ✓ Found {len(results)} results\n")
    for result in results:
        print(f"   Score: {result.score:.4f}")
        print(f"   Text: {result.chunk.text[:100]}...")
        print()

    # Get stats
    print("9. Getting index statistics...")
    stats = await index.stats()
    print(f"   ✓ Total chunks in index: {stats.total_chunks}\n")

    # Cleanup
    print("10. Cleaning up test data...")
    await index.delete([chunk.id for chunk in embedded_chunks])
    print("   ✓ Deleted test chunks\n")

    print("=== End-to-End Test Complete! ===")


if __name__ == "__main__":
    # Check for required API keys
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        sys.exit(1)

    if not os.environ.get("PINECONE_API_KEY"):
        print("Error: PINECONE_API_KEY environment variable not set")
        sys.exit(1)

    asyncio.run(main())
