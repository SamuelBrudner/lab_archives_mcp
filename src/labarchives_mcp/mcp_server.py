"""MCP server entry point for the LabArchives PoL implementation."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Coroutine
from importlib import metadata
from typing import Any, cast

import httpx
from loguru import logger

from .auth import AuthenticationManager, Credentials
from .eln_client import LabArchivesClient
from .transform import LabArchivesAPIError, translate_labarchives_fault

ResourceHandler = Callable[[], Awaitable[dict[str, Any]]]
ResourceDecorator = Callable[[ResourceHandler], ResourceHandler]

FastMCP: type[Any] | None = None

__all__ = [
    "run_server",
    "run",
    "__version__",
    "FastMCP",
    "AuthenticationManager",
    "Credentials",
    "LabArchivesClient",
    "httpx",
]


def _resolve_version() -> str:
    """Return the installed distribution version or fall back to the project default."""

    try:
        return metadata.version("labarchives-mcp-pol")
    except metadata.PackageNotFoundError:
        return "0.1.0"


__version__ = _resolve_version()


def _import_fastmcp() -> type[Any]:
    """Import FastMCP lazily so tests can stub the implementation."""

    global FastMCP
    if FastMCP is not None:
        return FastMCP

    try:
        import fastmcp
        from fastmcp import FastMCP as FastMCPClass

        # Disable banner for stdio transport compatibility
        fastmcp.settings.show_cli_banner = False
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised in tests
        raise ImportError(
            "FastMCP is required to run the LabArchives MCP server. Install `fastmcp` to proceed."
        ) from exc

    FastMCP = cast(type[Any], FastMCPClass)
    return FastMCP


async def run_server() -> None:
    """Run the MCP server event loop."""

    credentials = Credentials.from_file()
    fastmcp_class = _import_fastmcp()

    async with httpx.AsyncClient(base_url=str(credentials.region)) as http_client:
        auth_manager = AuthenticationManager(http_client, credentials)
        notebook_client = LabArchivesClient(http_client, auth_manager)

        server = _instantiate_fastmcp(
            fastmcp_class,
            server_id="labarchives-mcp-pol",
            name="LabArchives PoL Server",
            version=__version__,
            description="Proof-of-life MCP server exposing LabArchives notebooks.",
        )

        # Define resource
        resource_decorator = cast(ResourceDecorator, server.resource("labarchives://notebooks"))

        @resource_decorator
        async def list_notebooks_resource() -> dict[str, Any]:
            uid = await auth_manager.ensure_uid()
            try:
                notebooks = await notebook_client.list_notebooks(uid)
            except LabArchivesAPIError as error:
                translated = translate_labarchives_fault(error)
                return {
                    "resource": "labarchives://notebooks",
                    "error": translated,
                }

            return {
                "resource": "labarchives://notebooks",
                "list": [notebook.model_dump(by_alias=True) for notebook in notebooks],
            }

        # Also expose as a tool for better discovery
        @server.tool()  # type: ignore[misc]
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
            uid = await auth_manager.ensure_uid()
            notebooks = await notebook_client.list_notebooks(uid)
            return [notebook.model_dump(by_alias=True) for notebook in notebooks]

        @server.tool()  # type: ignore[misc]
        async def list_notebook_pages(notebook_id: str) -> list[dict[str, Any]]:
            """List all pages in a LabArchives notebook.

            Shows the notebook's table of contents - all pages and folders at the root level.

            Args:
                notebook_id: The notebook ID (nbid) from list_labarchives_notebooks

            Returns:
                List of pages and folders, each with:
                - tree_id: Unique identifier for the page/folder
                - title: Page or folder name
                - is_page: True if this is a page (can contain entries)
                - is_folder: True if this is a folder (contains sub-pages)
            """
            uid = await auth_manager.ensure_uid()
            tree_nodes = await notebook_client.get_notebook_tree(uid, notebook_id, parent_tree_id=0)

            return [
                {
                    "tree_id": node["tree_id"],
                    "title": node["display_text"],
                    "is_page": node["is_page"],
                    "is_folder": node["is_folder"],
                }
                for node in tree_nodes
            ]

        @server.tool()  # type: ignore[misc]
        async def read_notebook_page(notebook_id: str, page_id: str) -> dict[str, Any]:
            """Read all entries from a specific page in a LabArchives notebook.

            Returns the actual content: text entries, headings, and attachments from one page.
            Use list_notebook_pages first to find the page_id.

            Args:
                notebook_id: The notebook ID (nbid)
                page_id: The page tree_id from list_notebook_pages

            Returns:
                Dictionary with:
                - notebook_id: The notebook ID
                - page_id: The page ID
                - entries: List of entries, each containing:
                  - eid: Entry ID
                  - part_type: Type (text_entry, heading, plain_text, attachment, etc.)
                  - content: The entry content (for text entries and headings)
                  - created_at: Creation timestamp
                  - updated_at: Last modification timestamp
            """
            uid = await auth_manager.ensure_uid()
            entries = await notebook_client.get_page_entries(
                uid, notebook_id, int(page_id), include_data=True
            )

            return {"notebook_id": notebook_id, "page_id": page_id, "entries": entries}

        await server.run_async()


def run(main: Callable[[], Coroutine[Any, Any, None]] | None = None) -> None:
    """Synchronous helper for CLI entry points."""
    entry = main or run_server
    try:
        asyncio.run(entry())
    except KeyboardInterrupt:
        logger.warning("MCP server interrupted by user.")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled MCP server failure: {}", exc)
        raise


def _instantiate_fastmcp(class_: type[Any], **metadata: Any) -> Any:
    signature = inspect.signature(class_.__init__)
    parameters = signature.parameters

    filtered: dict[str, Any] = {key: value for key, value in metadata.items() if key in parameters}

    if "server_id" in metadata and "server_id" not in filtered and "id" in parameters:
        filtered["id"] = metadata["server_id"]

    if not filtered and any(
        param.kind == inspect.Parameter.VAR_KEYWORD for param in parameters.values()
    ):
        filtered = metadata

    return class_(**filtered)
