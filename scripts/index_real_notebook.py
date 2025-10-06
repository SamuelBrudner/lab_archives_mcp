#!/usr/bin/env python
"""Index a real LabArchives notebook using MCP server.

This script connects to the LabArchives API via the MCP server
and indexes notebook content into Pinecone.

Usage:
    # Set environment variables in conf/secrets.yml first, then:
    python scripts/index_real_notebook.py
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import httpx
import yaml  # type: ignore[import-untyped]
from loguru import logger

from vector_backend.build_state import (
    build_record_from_config,
    compute_config_fingerprint,
    load_build_record,
    save_build_record,
    should_rebuild,
)
from vector_backend.config import load_config
from vector_backend.embedding import create_embedding_client
from vector_backend.index import PineconeIndex
from vector_backend.notebook_indexer import NotebookIndexer

# Configure logging
logger.remove()
logger.add(
    sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>"
)


def load_secrets() -> dict[str, Any]:
    """Load secrets from conf/secrets.yml."""
    secrets_path = Path(__file__).parent.parent / "conf" / "secrets.yml"
    with open(secrets_path) as f:
        loaded = yaml.safe_load(f)
    return cast(dict[str, Any], loaded or {})


async def fetch_notebook_via_api(
    notebook_id: str, client: Any, auth_manager: Any, uid: str
) -> tuple[list[dict[str, Any]], str]:
    """Fetch notebook pages using LabArchives API client.

    Args:
        notebook_id: LabArchives notebook ID
        client: LabArchivesClient instance
        auth_manager: AuthenticationManager instance
        uid: User ID

    Returns:
        Tuple of (page_data_list, notebook_name)
    """
    logger.info(f"Fetching notebook {notebook_id}...")

    # Get all notebooks to find the one we want
    notebooks = await client.list_notebooks(uid)
    notebook = next((nb for nb in notebooks if nb.nbid == notebook_id), None)

    if not notebook:
        raise ValueError(f"Notebook {notebook_id} not found")

    notebook_name = notebook.name
    logger.info(f"Found notebook: {notebook_name}")

    # Recursively fetch all pages
    page_data_list = []

    async def fetch_pages_recursive(parent_tree_id: int | str = 0, depth: int = 0) -> None:
        """Recursively fetch pages from a folder."""
        indent = "  " * depth
        tree_items = await client.get_notebook_tree(uid, notebook_id, parent_tree_id=parent_tree_id)

        for item in tree_items:
            item_name = item.get("display_text") or item.get("name", "unknown")

            if item.get("is_page"):
                # This is a page - fetch its content
                page_id = item["tree_id"]
                logger.info(f"{indent}📄 {item_name}")

                try:
                    # Get page entries
                    entries = await client.get_page_entries(uid, notebook_id, page_id)

                    # Structure the data for indexing
                    page_data = {
                        "notebook_id": notebook_id,
                        "notebook_name": notebook_name,
                        "page_id": page_id,
                        "page_title": item_name,
                        "entries": entries,
                    }
                    page_data_list.append(page_data)

                except Exception as e:
                    logger.error(f"{indent}  ❌ Failed to fetch: {e}")
            else:
                # This is a folder - recurse into it
                folder_id = item["tree_id"]
                logger.info(f"{indent}📁 {item_name} (id: {folder_id[:20]}...)")
                await fetch_pages_recursive(parent_tree_id=folder_id, depth=depth + 1)

    # Start recursive fetch from root
    logger.info("Scanning notebook structure...")
    await fetch_pages_recursive(parent_tree_id=0)
    logger.info(f"Found {len(page_data_list)} pages total")

    return page_data_list, notebook_name


async def main() -> None:
    """Index LabArchives notebooks."""
    logger.info("=" * 60)
    logger.info("LabArchives Notebook Indexer")
    logger.info("=" * 60)

    # Load secrets
    logger.info("Loading secrets...")
    secrets = load_secrets()

    # Set environment variables
    os.environ["OPENAI_API_KEY"] = secrets["OPENAI_API_KEY"]
    os.environ["PINECONE_API_KEY"] = secrets["PINECONE_API_KEY"]

    # Load configuration
    config = load_config("default")
    logger.info(f"Config: {config.embedding.model}, chunk_size={config.chunking.chunk_size}")

    # Decide whether to rebuild based on build record
    record_path = Path(config.incremental_updates.last_indexed_file)
    current_fp = compute_config_fingerprint(config)
    previous = load_build_record(record_path)
    if previous and not should_rebuild(previous, current_fp, config.embedding.version):
        logger.info("No changes detected in config/embedding version; using existing index.\n")
        return

    # Create embedding client
    embedding_client = create_embedding_client(config.embedding)
    logger.info("✓ Created embedding client")

    # Create Pinecone index (using test index for now)
    index = PineconeIndex(
        index_name="labarchives-test",  # Use the test index we created earlier
        api_key=secrets["PINECONE_API_KEY"],
        environment=secrets.get("PINECONE_ENVIRONMENT", "us-east-1"),
        namespace=None,  # Use default namespace
    )

    # Check health
    healthy = await index.health_check()
    if not healthy:
        logger.error("❌ Pinecone index is not healthy!")
        sys.exit(1)
    logger.info("✓ Connected to Pinecone")

    # Get initial stats
    initial_stats = await index.stats()
    logger.info(f"Current index size: {initial_stats.total_chunks} chunks")

    # Create indexer
    indexer = NotebookIndexer(
        embedding_client=embedding_client,
        vector_index=index,
        embedding_version=config.embedding.version,
        chunking_config=config.chunking,
    )
    logger.info("✓ Created notebook indexer")

    # Initialize LabArchives client
    from labarchives_mcp.auth import AuthenticationManager, Credentials
    from labarchives_mcp.eln_client import LabArchivesClient

    credentials = Credentials(
        akid=secrets["LABARCHIVES_AKID"],
        password=secrets["LABARCHIVES_PASSWORD"],
        region=secrets.get("LABARCHIVES_REGION", "https://api.labarchives.com"),
        uid=secrets.get("LABARCHIVES_UID"),
    )

    async with httpx.AsyncClient() as http_client:
        auth_manager = AuthenticationManager(http_client, credentials)
        client = LabArchivesClient(http_client, auth_manager)

        # Get user ID
        uid = await auth_manager.ensure_uid()
        logger.info(f"✓ Authenticated as user {uid}")

        # Get all notebooks
        logger.info("\nFetching your notebooks...")
        notebooks = await client.list_notebooks(uid)

        logger.info(f"\nYou have {len(notebooks)} notebooks:")
        for i, nb in enumerate(notebooks, 1):
            logger.info(f"  {i}. {nb.name} (ID: {nb.nbid})")

        # Find the "Temporal Integration of Odor Signal" notebook
        if not notebooks:
            logger.error("No notebooks found!")
            sys.exit(1)

        notebook_to_index = next(
            (nb for nb in notebooks if "Temporal Integration" in nb.name),
            notebooks[0],  # Fallback to first notebook if not found
        )
        notebook_id = notebook_to_index.nbid

        logger.info(f"\nIndexing notebook: {notebook_to_index.name}")
        logger.info("=" * 60)

        # Fetch and index pages
        pages, notebook_name = await fetch_notebook_via_api(notebook_id, client, auth_manager, uid)

    total_indexed = 0
    total_skipped = 0

    for i, page in enumerate(pages, 1):
        logger.info(f"\n[{i}/{len(pages)}] Processing: {page['page_title']}")

        result = await indexer.index_page(
            page_data=page,
            author=secrets.get("LABARCHIVES_USER", "unknown@example.com"),
            labarchives_url=f"https://mynotebook.labarchives.com/share/{notebook_id}/{page['page_id']}",
        )

        total_indexed += result["indexed_count"]
        total_skipped += result["skipped_count"]

        logger.info(
            f"  ✓ Indexed {result['indexed_count']} chunks, "
            f"skipped {result['skipped_count']} entries"
        )

    # Final stats
    final_stats = await index.stats()

    logger.info("\n" + "=" * 60)
    logger.success("🎉 Indexing Complete!")
    logger.info(f"  Notebook: {notebook_name}")
    logger.info(f"  Pages processed: {len(pages)}")
    logger.info(f"  Chunks indexed: {total_indexed}")
    logger.info(f"  Entries skipped: {total_skipped}")
    logger.info(f"  Total index size: {initial_stats.total_chunks} → {final_stats.total_chunks}")
    # Persist build record for future runs
    try:
        save_build_record(record_path, build_record_from_config(config))
        logger.info(f"Saved build record to {record_path}")
    except Exception as e:
        logger.warning(f"Failed to save build record: {e}")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Error: {e}")
        sys.exit(1)
