#!/usr/bin/env python
"""Search indexed LabArchives content using semantic search.

Supports two modes:
- Chunk mode (default): Returns small, precise chunks
- Page mode (--full-page): Returns complete pages (parent-child retrieval)

Usage:
    python scripts/search_labarchives.py "What are the fly lines used?"
    python scripts/search_labarchives.py "gradient climbing" --full-page
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import click
import httpx
import yaml
from loguru import logger

from labarchives_mcp.auth import AuthenticationManager, Credentials
from labarchives_mcp.eln_client import LabArchivesClient
from vector_backend.config import load_config
from vector_backend.embedding import create_embedding_client
from vector_backend.index import PineconeIndex
from vector_backend.labarchives_indexer import clean_html
from vector_backend.models import SearchRequest

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="<level>{message}</level>")


def load_secrets():
    """Load secrets from conf/secrets.yml."""
    secrets_path = Path(__file__).parent.parent / "conf" / "secrets.yml"
    with open(secrets_path) as f:
        return yaml.safe_load(f)


async def fetch_full_page(
    notebook_id: str, page_id: str, client: LabArchivesClient, uid: str
) -> str:
    """Fetch and clean the full content of a LabArchives page.

    Args:
        notebook_id: LabArchives notebook ID
        page_id: LabArchives page ID (tree_id)
        client: LabArchivesClient instance
        uid: User ID

    Returns:
        Cleaned full page content as string
    """
    try:
        # Get all entries on the page
        entries = await client.get_page_entries(uid, notebook_id, page_id)

        # Combine all text entries
        full_text = []
        for entry in entries:
            entry_type = entry.get("part_type", "").lower().replace(" ", "_")
            content = entry.get("content", "")

            if entry_type == "text_entry" and content:
                cleaned = clean_html(content)
                if cleaned:
                    full_text.append(cleaned)
            elif entry_type in ["heading", "plain_text"] and content:
                full_text.append(content.strip())

        return "\n\n".join(full_text) if full_text else "(No text content on this page)"

    except Exception as e:
        logger.error(f"Failed to fetch full page: {e}")
        return f"(Error fetching page: {e})"


async def search(query: str, top_k: int = 5, full_page: bool = False):
    """Search indexed LabArchives content.

    Args:
        query: Natural language search query
        top_k: Number of results to return
        full_page: If True, fetch and display full page content (parent-child retrieval)
    """
    mode = "PAGE" if full_page else "CHUNK"
    logger.info("=" * 60)
    logger.info(f"🔍 Searching: '{query}' [Mode: {mode}]")
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

    # Initialize LabArchives client if full_page mode
    labarchives_client = None
    uid = None
    if full_page:
        logger.info("Fetching full pages from LabArchives...\n")
        credentials = Credentials(
            akid=secrets["LABARCHIVES_AKID"],
            password=secrets["LABARCHIVES_PASSWORD"],
            region=secrets.get("LABARCHIVES_REGION", "https://api.labarchives.com"),
            uid=secrets.get("LABARCHIVES_UID"),
        )
        http_client = httpx.AsyncClient()
        auth_manager = AuthenticationManager(http_client, credentials)
        labarchives_client = LabArchivesClient(http_client, auth_manager)
        uid = await auth_manager.ensure_uid()

    for i, result in enumerate(results, 1):
        score = result.score
        chunk = result.chunk
        metadata = chunk.metadata

        # Get text content
        if full_page:
            # Fetch full page content
            text = await fetch_full_page(
                metadata.notebook_id, metadata.page_id, labarchives_client, uid
            )
        else:
            # Use chunk text
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

    # Cleanup
    if labarchives_client:
        await http_client.aclose()


@click.command()
@click.argument("query", type=str)
@click.option("--top-k", default=5, help="Number of results to return")
@click.option(
    "--full-page",
    is_flag=True,
    help="Fetch and display full page content (parent-child retrieval)",
)
def cli(query: str, top_k: int, full_page: bool):
    """Search indexed LabArchives content using semantic search.

    By default, returns small precise chunks. Use --full-page to retrieve
    complete page content for each match (parent-child retrieval pattern).
    """
    asyncio.run(search(query, top_k, full_page))


if __name__ == "__main__":
    cli()
