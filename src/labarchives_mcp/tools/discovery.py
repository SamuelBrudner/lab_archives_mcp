"""Notebook discovery and page-reading tools."""

from __future__ import annotations

from typing import Any

from loguru import logger

from .context import ToolContext
from .decorators import tool
from .utils import _extract_labarchives_page_links


async def list_labarchives_notebooks(context: ToolContext) -> list[dict[str, Any]]:
    """List all LabArchives notebooks for the authenticated user."""
    uid = await context.auth_manager.ensure_uid()
    notebooks = await context.notebook_client.list_notebooks(uid)
    return [notebook.model_dump(by_alias=True) for notebook in notebooks]


async def list_notebook_pages(
    context: ToolContext, notebook_id: str, folder_id: str | None = None
) -> list[dict[str, Any]]:
    """List all pages and folders in a LabArchives notebook."""
    logger.info(
        f"list_notebook_pages called with notebook_id={notebook_id}, folder_id={folder_id}"
    )

    uid = await context.auth_manager.ensure_uid()
    logger.debug(f"Obtained UID: {uid[:20]}...")

    parent_tree_id: int | str
    if folder_id:
        parent_tree_id = folder_id
        logger.debug(f"Using folder_id as parent_tree_id: {folder_id}")
    else:
        parent_tree_id = 0

    logger.debug(f"Fetching tree for notebook {notebook_id}, parent_tree_id={parent_tree_id}")
    tree_nodes = await context.notebook_client.get_notebook_tree(
        uid, notebook_id, parent_tree_id=parent_tree_id
    )
    logger.info(f"Retrieved {len(tree_nodes)} nodes from notebook tree")

    result = [
        {
            "tree_id": node["tree_id"],
            "title": node["display_text"],
            "is_page": node["is_page"],
            "is_folder": node["is_folder"],
        }
        for node in tree_nodes
    ]
    logger.success(f"Successfully listed {len(result)} pages/folders")
    return result


async def read_notebook_page(
    context: ToolContext,
    notebook_id: str,
    page_id: str,
    track_visit: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Read all entries from a specific page in a LabArchives notebook."""
    logger.info(f"read_notebook_page called with notebook_id={notebook_id}, page_id={page_id}")

    uid = await context.auth_manager.ensure_uid()
    logger.debug(f"Obtained UID: {uid[:20]}...")

    logger.debug(f"Fetching entries for page {page_id} in notebook {notebook_id}")

    entries = await context.notebook_client.get_page_entries(
        uid, notebook_id, page_id, include_data=True
    )
    logger.info(f"Retrieved {len(entries)} entries from page")

    for i, entry in enumerate(entries[:3]):
        logger.debug(
            f"Entry {i}: type={entry.get('part_type')}, "
            f"eid={entry.get('eid')}, "
            f"has_content={bool(entry.get('content'))}"
        )

    page_title = "Unknown Title"
    tracked = False
    if track_visit and not dry_run:
        context.state_manager.log_visit(notebook_id, page_id, page_title)
        context.state_manager.log_page_content_links(
            notebook_id,
            page_id,
            _extract_labarchives_page_links(entries),
        )
        tracked = True

    active_context = context.state_manager.get_active_context()
    return {
        "notebook_id": notebook_id,
        "page_id": page_id,
        "entries": entries,
        "tracked_in_project": active_context.name if active_context else None,
        "tracked": tracked,
        "dry_run": dry_run,
    }


_list_labarchives_notebooks = list_labarchives_notebooks
_list_notebook_pages = list_notebook_pages
_read_notebook_page = read_notebook_page


def register_discovery_tools(server: Any, context: ToolContext) -> None:
    """Register notebook discovery and reading tools."""

    @tool(server)
    async def list_labarchives_notebooks() -> list[dict[str, Any]]:
        """List all LabArchives notebooks for the authenticated user.

        Returns a list of notebooks with metadata including:
        - nbid: Notebook ID
        - name: Notebook name
        - owner: Owner email
        - owner_name: Owner full name
        - created_at: Creation timestamp (ISO 8601)
        - modified_at: Last modification timestamp (ISO 8601)
        """
        return await _list_labarchives_notebooks(context)

    @tool(server)
    async def list_notebook_pages(
        notebook_id: str, folder_id: str | None = None
    ) -> list[dict[str, Any]]:
        """List all pages and folders in a LabArchives notebook.

        Shows the table of contents at the specified level. Pass folder_id to navigate
        into folders and see their contents.
        """
        return await _list_notebook_pages(context, notebook_id, folder_id)

    @tool(server)
    async def read_notebook_page(
        notebook_id: str,
        page_id: str,
        track_visit: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Read all entries from a specific page in a LabArchives notebook."""
        return await _read_notebook_page(
            context,
            notebook_id,
            page_id,
            track_visit=track_visit,
            dry_run=dry_run,
        )
