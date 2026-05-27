"""Search and vector-index sync tools."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from vector_backend.labarchives_indexer import clean_html
from vector_backend.models import SearchRequest, SearchResult

from ..schemas.tool_responses import (
    NotebookTreeNodeResponse,
    SearchResultResponse,
    SyncVectorIndexResponse,
)
from .context import ToolContext
from .decorators import register_context_tool


async def search_labarchives(
    context: ToolContext, query: str, limit: int = 5
) -> list[SearchResultResponse]:
    """Search indexed LabArchives notebooks semantically."""
    logger.info(f"search_labarchives called: query='{query}', limit={limit}")

    vector_runtime = context.get_vector_runtime()
    embedding_client = vector_runtime.get_embedding_client()
    index = await vector_runtime.get_index()
    logger.debug("Generating query embedding...")
    query_vector = await embedding_client.embed_single(query)

    candidate_k = max(min(limit * 3, 100), limit)
    search_request = SearchRequest(query=query, limit=candidate_k, filters=None)
    results = await index.search(request=search_request, query_vector=query_vector)

    if not results:
        logger.info("No results found")
        return []

    logger.info(f"Found {len(results)} results")

    seen_pages: set[tuple[str, str]] = set()
    unique_results: list[SearchResult] = []
    for result in results:
        key = (result.chunk.metadata.notebook_id, result.chunk.metadata.page_id)
        if key in seen_pages:
            continue
        seen_pages.add(key)
        unique_results.append(result)
        if len(unique_results) >= limit:
            break

    uid = await context.auth_manager.ensure_uid()
    output: list[SearchResultResponse] = []

    for result in unique_results:
        chunk = result.chunk
        metadata = chunk.metadata

        entries = await context.notebook_client.get_page_entries(
            uid, metadata.notebook_id, metadata.page_id
        )

        full_text: list[str] = []
        for entry in entries:
            entry_type = (entry.get("part_type") or "").lower().replace(" ", "_")
            entry_content = entry.get("content") or ""

            if entry_type == "text_entry" and entry_content:
                cleaned = clean_html(entry_content)
                if cleaned:
                    full_text.append(cleaned)
            elif entry_type in ["heading", "plain_text"] and entry_content:
                full_text.append(entry_content.strip())

        page_content = "\n\n".join(full_text) if full_text else "(No text content on this page)"

        output.append(
            {
                "score": result.score,
                "notebook_name": metadata.notebook_name,
                "page_title": metadata.page_title,
                "page_id": metadata.page_id,
                "notebook_id": metadata.notebook_id,
                "url": metadata.labarchives_url,
                "author": metadata.author,
                "date": str(metadata.date),
                "content": page_content,
            }
        )

    logger.success(f"Successfully returned {len(output)} search results")
    return output


async def sync_vector_index(
    context: ToolContext,
    *,
    force: bool = False,
    dry_run: bool = False,
    max_age_hours: int | None = None,
    notebook_id: str | None = None,
) -> SyncVectorIndexResponse:
    """Plan and optionally execute a vector-index sync."""
    from vector_backend.build_state import (
        build_record_from_config,
        compute_config_fingerprint,
        load_build_record,
        save_build_record,
    )
    from vector_backend.notebook_indexer import NotebookIndexer
    from vector_backend.sync import plan_sync, select_incremental_entries

    vector_runtime = context.get_vector_runtime()
    config = vector_runtime.get_config()
    record_path = Path(config.incremental_updates.last_indexed_file)
    record = load_build_record(record_path)
    current_fp = compute_config_fingerprint(config)

    decision = plan_sync(
        record,
        current_fp,
        config.embedding.version,
        force=force,
        max_age_hours=max_age_hours,
    )

    if dry_run or decision["action"] == "skip":
        return {
            "action": decision["action"],
            "reason": decision["reason"],
            "built_at": decision["built_at"],
            "dry_run": dry_run,
        }

    action = decision["action"]
    processed_pages = 0
    indexed_chunks = 0

    uid = await context.auth_manager.ensure_uid()
    nb_client = context.notebook_client

    built_at_dt = None
    if action == "incremental":
        built_at_str = decision.get("built_at")
        built_at_dt = (
            datetime.fromisoformat(built_at_str.replace("Z", "+00:00"))
            if built_at_str
            else datetime.now()
        )

    async def _collect_pages(nbid: str) -> list[NotebookTreeNodeResponse]:
        pages: list[NotebookTreeNodeResponse] = []

        async def _walk(parent: int | str = 0) -> None:
            parent_id: int | str = parent
            tree = await nb_client.get_notebook_tree(uid, nbid, parent_tree_id=parent_id)
            for node in tree:
                if node.get("is_page"):
                    pages.append(node)
                elif node.get("is_folder"):
                    next_parent = node.get("tree_id")
                    await _walk(str(next_parent) if next_parent is not None else 0)

        await _walk(0)
        return pages

    target_notebooks: list[str]
    if notebook_id:
        target_notebooks = [notebook_id]
    else:
        if built_at_dt is not None:
            _ = select_incremental_entries([], built_at_dt)
        return {
            "action": decision["action"],
            "reason": decision["reason"],
            "built_at": decision["built_at"],
            "dry_run": False,
            "processed_pages": 0,
            "indexed_chunks": 0,
        }

    embed_client = vector_runtime.get_embedding_client()
    index_client = await vector_runtime.get_index()
    indexer = NotebookIndexer(
        embedding_client=embed_client,
        vector_index=index_client,
        embedding_version=config.embedding.version,
        chunking_config=config.chunking,
    )

    base_url = str(context.credentials.region)

    for nbid in target_notebooks:
        pages = await _collect_pages(nbid)
        notebook_name = f"Notebook {nbid}"
        for node in pages:
            pid = str(node.get("tree_id"))
            title = node.get("display_text") or node.get("name") or pid
            entries = await nb_client.get_page_entries(uid, nbid, pid)

            entry_dicts: list[dict[str, Any]] = [dict(entry) for entry in entries]
            selected_entries = (
                select_incremental_entries(entry_dicts, built_at_dt)
                if built_at_dt
                else entry_dicts
            )
            if not selected_entries:
                continue

            page_data = {
                "notebook_id": nbid,
                "notebook_name": notebook_name,
                "page_id": pid,
                "page_title": title,
                "entries": selected_entries,
            }
            res = await indexer.index_page(
                page_data=page_data,
                author="unknown@example.com",
                labarchives_url=base_url,
            )
            processed_pages += 1
            indexed_chunks += int(res.get("indexed_count", 0))

    save_build_record(record_path, build_record_from_config(config))
    return {
        "action": decision["action"],
        "reason": decision["reason"],
        "built_at": decision["built_at"],
        "processed_pages": processed_pages,
        "indexed_chunks": indexed_chunks,
    }


def register_search_tools(server: Any, context: ToolContext) -> None:
    """Register search and vector sync tools."""
    for handler in (search_labarchives, sync_vector_index):
        register_context_tool(server, context, handler)
