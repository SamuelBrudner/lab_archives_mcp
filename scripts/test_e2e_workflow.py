#!/usr/bin/env python
"""End-to-end workflow test for vector backend.

This script tests the complete flow:
1. Chunk text
2. Generate embeddings
3. Upsert to Pinecone
4. Search and retrieve

Usage:
    python scripts/test_e2e_workflow.py

This script reads all required API keys from `conf/secrets.yml`. Optionally, override by
exporting `OPENAI_API_KEY` / `PINECONE_API_KEY` before running.
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, cast

# Add src to path
sys.path.insert(0, "src")

import yaml  # type: ignore[import-untyped]

from vector_backend.chunking import chunk_text
from vector_backend.config import load_config
from vector_backend.embedding import create_embedding_client
from vector_backend.index import PineconeIndex
from vector_backend.models import ChunkMetadata, EmbeddedChunk, SearchRequest


def load_secrets() -> dict[str, Any]:
    """Load credentials from `conf/secrets.yml`."""

    secrets_path = Path(__file__).parent.parent / "conf" / "secrets.yml"
    with secrets_path.open() as fh:
        loaded = yaml.safe_load(fh)
    return cast(dict[str, Any], loaded or {})


async def main() -> None:
    """Run end-to-end workflow."""
    print("=== Vector Backend End-to-End Test ===\n")

    # Ensure required keys are available for Hydra config and API clients
    secrets = load_secrets()
    os.environ.setdefault("OPENAI_API_KEY", secrets["OPENAI_API_KEY"])
    os.environ.setdefault("PINECONE_API_KEY", secrets["PINECONE_API_KEY"])

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
    api_key = config.index.api_key or os.environ.get("PINECONE_API_KEY")
    if not api_key:
        raise RuntimeError("Pinecone API key not configured")

    environment = config.index.environment or os.environ.get("PINECONE_ENVIRONMENT") or "us-east-1"

    index = PineconeIndex(
        index_name="labarchives-test",
        api_key=api_key,
        environment=environment,
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
    try:
        # Prime environment from secrets file when variables are not already set
        if not os.environ.get("OPENAI_API_KEY") or not os.environ.get("PINECONE_API_KEY"):
            secrets = load_secrets()
            os.environ.setdefault("OPENAI_API_KEY", secrets["OPENAI_API_KEY"])
            os.environ.setdefault("PINECONE_API_KEY", secrets["PINECONE_API_KEY"])

        missing = [
            name for name in ("OPENAI_API_KEY", "PINECONE_API_KEY") if not os.environ.get(name)
        ]
        if missing:
            print(
                "Error: missing required API keys and `conf/secrets.yml` is either absent "
                "or incomplete. Populate conf/secrets.yml or export the keys manually."
            )
            sys.exit(1)

        asyncio.run(main())
    except FileNotFoundError:
        print(
            "Error: conf/secrets.yml not found. Copy conf/secrets.example.yml and "
            "fill in your keys."
        )
        sys.exit(1)
