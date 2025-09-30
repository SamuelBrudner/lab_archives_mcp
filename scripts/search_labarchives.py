#!/usr/bin/env python
"""Search indexed LabArchives content using semantic search.

Usage:
    python scripts/search_labarchives.py "What are the fly lines used?"
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import click
import yaml
from loguru import logger

from vector_backend.config import load_config
from vector_backend.embedding import create_embedding_client
from vector_backend.index import PineconeIndex
from vector_backend.models import SearchRequest

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="<level>{message}</level>")


def load_secrets():
    """Load secrets from conf/secrets.yml."""
    secrets_path = Path(__file__).parent.parent / "conf" / "secrets.yml"
    with open(secrets_path) as f:
        return yaml.safe_load(f)


async def search(query: str, top_k: int = 5):
    """Search indexed LabArchives content.

    Args:
        query: Natural language search query
        top_k: Number of results to return
    """
    logger.info("=" * 60)
    logger.info(f"🔍 Searching: '{query}'")
    logger.info("=" * 60)

    # Load secrets
    secrets = load_secrets()
    os.environ["OPENAI_API_KEY"] = secrets["OPENAI_API_KEY"]
    os.environ["PINECONE_API_KEY"] = secrets["PINECONE_API_KEY"]

    # Load configuration
    config = load_config("default")

    # Create embedding client
    embedding_client = create_embedding_client(config.embedding)

    # Create Pinecone index
    index = PineconeIndex(
        index_name="labarchives-test",
        api_key=secrets["PINECONE_API_KEY"],
        environment=secrets.get("PINECONE_ENVIRONMENT", "us-east-1"),
        namespace=None,
    )

    # Check health
    healthy = await index.health_check()
    if not healthy:
        logger.error("❌ Pinecone index is not healthy!")
        sys.exit(1)

    # Get stats
    stats = await index.stats()
    logger.info(f"Index contains {stats.total_chunks} chunks\n")

    # Generate query embedding
    logger.info("Generating query embedding...")
    query_vector = await embedding_client.embed_single(query)

    # Search
    logger.info(f"Searching for top {top_k} results...\n")
    search_request = SearchRequest(query=query, limit=top_k, filters=None)
    results = await index.search(request=search_request, query_vector=query_vector)

    # Display results
    if not results:
        logger.warning("No results found!")
        return

    logger.success(f"Found {len(results)} results:\n")

    for i, result in enumerate(results, 1):
        score = result.score
        chunk = result.chunk
        metadata = chunk.metadata
        text = chunk.text[:300] + "..." if len(chunk.text) > 300 else chunk.text

        logger.info(f"{'='*60}")
        logger.info(f"Result {i} (score: {score:.4f})")
        logger.info(f"{'='*60}")
        logger.info(f"📓 Notebook: {metadata.notebook_name}")
        logger.info(f"📄 Page: {metadata.page_title}")
        logger.info(f"🔗 URL: {metadata.labarchives_url}")
        logger.info(f"👤 Author: {metadata.author}")
        logger.info(f"📅 Date: {metadata.date}")
        logger.info(f"\n📝 Content:\n{text}")
        logger.info("")


@click.command()
@click.argument("query", type=str)
@click.option("--top-k", default=5, help="Number of results to return")
def cli(query: str, top_k: int):
    """Search indexed LabArchives content using semantic search."""
    asyncio.run(search(query, top_k))


if __name__ == "__main__":
    cli()
