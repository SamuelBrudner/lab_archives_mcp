#!/usr/bin/env python
"""Index a LabArchives notebook into Pinecone vector store.

This script fetches notebook data from LabArchives and indexes it for semantic search.

Usage:
    python scripts/index_labarchives_notebook.py --notebook-id <nbid>

Populate `conf/secrets.yml` with the required LabArchives, OpenAI, and Pinecone
credentials. Environment variables are optional overrides.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, cast

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import click
import yaml  # type: ignore[import-untyped]
from loguru import logger

from vector_backend.config import load_config
from vector_backend.embedding import create_embedding_client
from vector_backend.index import PineconeIndex
from vector_backend.notebook_indexer import NotebookIndexer

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO")


def load_secrets() -> dict[str, Any]:
    """Load credentials from `conf/secrets.yml`."""

    secrets_path = Path(__file__).parent.parent / "conf" / "secrets.yml"
    with secrets_path.open() as fh:
        loaded = yaml.safe_load(fh)
    return cast(dict[str, Any], loaded or {})


async def fetch_notebook_pages(notebook_id: str) -> list[dict[str, Any]]:
    """Fetch pages from a LabArchives notebook using MCP.

    For now, this is a placeholder. In production, this would:
    1. Use mcp2_list_notebook_pages to get page list
    2. Use mcp2_read_notebook_page for each page
    3. Return structured page data

    Args:
        notebook_id: LabArchives notebook ID

    Returns:
        List of page data dictionaries
    """
    logger.warning("Using mock data - MCP integration not yet implemented")

    # Mock data for testing
    return [
        {
            "notebook_id": notebook_id,
            "notebook_name": "Test Notebook",
            "page_id": "page_001",
            "page_title": "Test Page",
            "entries": [
                {
                    "eid": "entry_1",
                    "part_type": "heading",
                    "content": "Research Methods",
                    "created_at": "2025-09-30T10:00:00Z",
                    "updated_at": "2025-09-30T10:00:00Z",
                },
                {
                    "eid": "entry_2",
                    "part_type": "text_entry",
                    "content": (
                        "<p>This is a test entry about "
                        "<b>protein aggregation</b> in neurons.</p>"
                    ),
                    "created_at": "2025-09-30T11:00:00Z",
                    "updated_at": "2025-09-30T11:00:00Z",
                },
            ],
        }
    ]


async def main(notebook_id: str, author: str | None = None) -> None:
    """Index a LabArchives notebook.

    Args:
        notebook_id: LabArchives notebook ID (nbid)
        author: Optional author email (default: fetched from LabArchives)
    """
    logger.info(f"Starting indexing for notebook ID: {notebook_id}")

    try:
        secrets = load_secrets()
    except FileNotFoundError as exc:
        logger.error(
            "conf/secrets.yml not found. Copy conf/secrets.example.yml and supply " "credentials."
        )
        raise SystemExit(1) from exc

    # Seed environment so Hydra resolves API keys
    os.environ.setdefault("OPENAI_API_KEY", secrets.get("OPENAI_API_KEY", ""))
    os.environ.setdefault("PINECONE_API_KEY", secrets.get("PINECONE_API_KEY", ""))

    # Load configuration
    config = load_config("default")
    logger.info(f"Loaded config: {config.embedding.model}, chunk_size={config.chunking.chunk_size}")

    # Create embedding client
    embedding_client = create_embedding_client(config.embedding)
    logger.info("Created embedding client")

    # Create Pinecone index
    pinecone_api_key = config.index.api_key or os.environ.get("PINECONE_API_KEY")
    if not pinecone_api_key:
        logger.error(
            "Missing Pinecone credentials. Populate conf/secrets.yml or export " "PINECONE_API_KEY."
        )
        raise SystemExit(1)

    index = PineconeIndex(
        index_name=config.index.index_name,
        api_key=pinecone_api_key,
        environment=config.index.environment or secrets.get("PINECONE_ENVIRONMENT", "us-east-1"),
        namespace="production",  # Use production namespace
    )

    # Check health
    healthy = await index.health_check()
    if not healthy:
        logger.error("Pinecone index is not healthy!")
        sys.exit(1)
    logger.info("Connected to Pinecone")

    # Create indexer
    indexer = NotebookIndexer(
        embedding_client=embedding_client,
        vector_index=index,
        embedding_version=config.embedding.version,
        chunking_config=config.chunking,
    )
    logger.info("Created notebook indexer")

    # Fetch notebook pages
    logger.info("Fetching notebook pages...")
    pages = await fetch_notebook_pages(notebook_id)
    logger.info(f"Found {len(pages)} pages to index")

    # Index each page
    total_indexed = 0
    total_skipped = 0

    for page in pages:
        result = await indexer.index_page(
            page_data=page,
            author=author or "unknown@example.com",
            labarchives_url=f"https://mynotebook.labarchives.com/share/{notebook_id}",
        )

        total_indexed += result["indexed_count"]
        total_skipped += result["skipped_count"]

        logger.info(
            f"Page '{page['page_title']}': "
            f"indexed {result['indexed_count']} chunks, "
            f"skipped {result['skipped_count']} entries"
        )

    # Summary
    logger.success(
        f"\n{'='*60}\n"
        f"Indexing Complete!\n"
        f"  Total chunks indexed: {total_indexed}\n"
        f"  Total entries skipped: {total_skipped}\n"
        f"  Pages processed: {len(pages)}\n"
        f"{'='*60}"
    )

    # Get index stats
    stats = await index.stats()
    logger.info(f"Index now contains {stats.total_chunks} total chunks")


@click.command()  # type: ignore[misc]
@click.option(  # type: ignore[misc]
    "--notebook-id",
    required=True,
    help="LabArchives notebook ID (nbid)",
)
@click.option(  # type: ignore[misc]
    "--author",
    help="Author email (optional)",
)
def cli(notebook_id: str, author: str | None) -> None:
    """Index a LabArchives notebook into Pinecone."""
    if not os.environ.get("OPENAI_API_KEY") or not os.environ.get("PINECONE_API_KEY"):
        try:
            secrets = load_secrets()
        except FileNotFoundError as exc:
            logger.error(
                "conf/secrets.yml not found. Copy conf/secrets.example.yml and supply "
                "credentials."
            )
            raise SystemExit(1) from exc

        os.environ.setdefault("OPENAI_API_KEY", secrets.get("OPENAI_API_KEY", ""))
        os.environ.setdefault("PINECONE_API_KEY", secrets.get("PINECONE_API_KEY", ""))

    missing = [name for name in ("OPENAI_API_KEY", "PINECONE_API_KEY") if not os.environ.get(name)]
    if missing:
        logger.error(
            "Missing required API keys: %s. Populate conf/secrets.yml or export them.",
            ", ".join(missing),
        )
        sys.exit(1)

    # Run indexing
    asyncio.run(main(notebook_id, author))


if __name__ == "__main__":
    cli()
