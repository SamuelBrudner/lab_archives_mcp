"""MCP server entry point for the LabArchives PoL implementation."""

from __future__ import annotations

import asyncio
import inspect
import os
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


def _is_upload_enabled() -> bool:
    """Check if upload functionality should be enabled.

    Returns:
        True if LABARCHIVES_ENABLE_UPLOAD is not set or is "true" (case-insensitive).
        False if LABARCHIVES_ENABLE_UPLOAD is set to "false" (case-insensitive).
    """
    env_value = os.environ.get("LABARCHIVES_ENABLE_UPLOAD", "true")
    return env_value.lower() != "false"


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
        async def list_notebook_pages(
            notebook_id: str, folder_id: str | None = None
        ) -> list[dict[str, Any]]:
            """List all pages and folders in a LabArchives notebook.

            Shows the table of contents at the specified level. Pass folder_id to navigate
            into folders and see their contents.

            Args:
                notebook_id: The notebook ID (nbid) from list_labarchives_notebooks
                folder_id: Optional tree_id of a folder to list its contents.
                          If None, lists root level of notebook.

            Returns:
                List of pages and folders, each with:
                - tree_id: Unique identifier (use this as folder_id to navigate deeper)
                - title: Page or folder name
                - is_page: True if this is a page (can be read with read_notebook_page)
                - is_folder: True if this is a folder (can be navigated with folder_id)
            """
            logger.info(
                f"list_notebook_pages called with notebook_id={notebook_id}, "
                f"folder_id={folder_id}"
            )

            try:
                uid = await auth_manager.ensure_uid()
                logger.debug(f"Obtained UID: {uid[:20]}...")

                # parent_tree_id can be either 0 (root) or a base64-encoded tree_id
                parent_tree_id: int | str
                if folder_id:
                    # Use the folder_id (tree_id) directly as parent_tree_id
                    parent_tree_id = folder_id
                    logger.debug(f"Using folder_id as parent_tree_id: {folder_id}")
                else:
                    parent_tree_id = 0

                logger.debug(
                    f"Fetching tree for notebook {notebook_id}, parent_tree_id={parent_tree_id}"
                )
                tree_nodes = await notebook_client.get_notebook_tree(
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

            except Exception as exc:
                logger.error(f"Failed to list notebook pages: {exc}", exc_info=True)
                raise

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
            logger.info(
                f"read_notebook_page called with notebook_id={notebook_id}, page_id={page_id}"
            )

            try:
                uid = await auth_manager.ensure_uid()
                logger.debug(f"Obtained UID: {uid[:20]}...")

                logger.debug(f"Fetching entries for page {page_id} in notebook {notebook_id}")

                entries = await notebook_client.get_page_entries(
                    uid, notebook_id, page_id, include_data=True
                )
                logger.info(f"Retrieved {len(entries)} entries from page")

                for i, entry in enumerate(entries[:3]):  # Log first 3 entries
                    logger.debug(
                        f"Entry {i}: type={entry.get('part_type')}, "
                        f"eid={entry.get('eid')}, "
                        f"has_content={bool(entry.get('content'))}"
                    )

                result = {"notebook_id": notebook_id, "page_id": page_id, "entries": entries}
                logger.success(f"Successfully read page with {len(entries)} entries")
                return result

            except Exception as exc:
                logger.error(f"Failed to read notebook page: {exc}", exc_info=True)
                raise

        @server.tool()  # type: ignore[misc]
        async def search_labarchives(query: str, limit: int = 5) -> list[dict[str, Any]]:
            """Search your indexed LabArchives notebooks semantically.

            Uses vector search to find relevant pages based on natural language queries.
            Returns full page content with metadata for each match.

            Args:
                query: Natural language search query (e.g., "fly lines used in experiments")
                limit: Maximum number of results to return (default 5)

            Returns:
                List of search results, each containing:
                - score: Similarity score (0-1, higher is better)
                - notebook_name: Name of the notebook
                - page_title: Title of the page
                - page_id: Page identifier (tree_id)
                - notebook_id: Notebook identifier
                - url: Direct link to the page in LabArchives
                - author: Page author
                - date: Last modified date
                - content: Full page text content (cleaned HTML)
            """
            import os

            import yaml  # type: ignore[import-untyped]

            from vector_backend.config import load_config
            from vector_backend.embedding import create_embedding_client
            from vector_backend.index import PineconeIndex
            from vector_backend.labarchives_indexer import clean_html
            from vector_backend.models import SearchRequest

            logger.info(f"search_labarchives called: query='{query}', limit={limit}")

            try:
                # Load secrets using same logic as Credentials.from_file()
                from pathlib import Path

                import aiofiles  # type: ignore[import-untyped]

                env_path = os.environ.get("LABARCHIVES_CONFIG_PATH")
                secrets_path = Path(env_path) if env_path else Path("conf/secrets.yml")

                async with aiofiles.open(secrets_path) as f:
                    content = await f.read()
                    secrets = yaml.safe_load(content)

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

                # Quick health check so we fail fast instead of hanging
                healthy = await index.health_check()
                if not healthy:
                    raise RuntimeError(
                        "Pinecone index not reachable. Check network, API key, or environment."
                    )

                # Generate query embedding
                logger.debug("Generating query embedding...")
                query_vector = await embedding_client.embed_single(query)

                # Search
                search_request = SearchRequest(query=query, limit=limit, filters=None)
                results = await index.search(request=search_request, query_vector=query_vector)

                if not results:
                    logger.info("No results found")
                    return []

                logger.info(f"Found {len(results)} results")

                # Fetch full page content for each result
                uid = await auth_manager.ensure_uid()
                output = []

                for result in results:
                    chunk = result.chunk
                    metadata = chunk.metadata

                    # Fetch full page content
                    try:
                        entries = await notebook_client.get_page_entries(
                            uid, metadata.notebook_id, metadata.page_id
                        )

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

                        page_content = (
                            "\n\n".join(full_text)
                            if full_text
                            else "(No text content on this page)"
                        )

                    except Exception as e:
                        logger.warning(f"Failed to fetch full page content: {e}")
                        page_content = f"(Error fetching page: {e})"

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

            except Exception as exc:
                logger.error(f"Failed to search LabArchives: {exc}", exc_info=True)
                raise

        # Conditionally register upload tool based on environment variable
        if _is_upload_enabled():
            logger.info("Upload functionality is ENABLED (LABARCHIVES_ENABLE_UPLOAD)")

            @server.tool()  # type: ignore[misc]
            async def upload_to_labarchives(
                notebook_id: str,
                page_title: str,
                file_path: str,
                git_commit_sha: str,
                git_branch: str,
                git_repo_url: str,
                python_version: str,
                executed_at: str,
                parent_folder_id: str | None = None,
                caption: str | None = None,
                git_is_dirty: bool = False,
                allow_dirty_git: bool = False,
                dependencies: dict[str, str] | None = None,
                as_page_text: bool = True,
            ) -> dict[str, Any]:
                """Upload a file to LabArchives with code provenance metadata.

                Creates a new page, then either stores the file contents as the
                page text (default, Markdown → HTML) or uploads the file as an attachment, and
                adds metadata about code version, execution context, and dependencies.

                Args:
                    notebook_id: LabArchives notebook ID
                    page_title: Title for the new page
                    file_path: Path to file to upload (e.g., analysis.ipynb)
                    git_commit_sha: Full 40-character Git commit SHA
                    git_branch: Git branch name (e.g., "main")
                    git_repo_url: Git repository URL
                    python_version: Python version (e.g., "3.11.8")
                    executed_at: Execution timestamp (ISO 8601, e.g., "2025-09-30T12:00:00Z")
                    parent_folder_id: Optional folder tree_id to upload into
                    caption: Optional caption for the attachment
                    git_is_dirty: True if uncommitted changes exist
                    allow_dirty_git: Allow upload despite dirty Git (not recommended)
                    dependencies: Key package versions (e.g., {"numpy": "1.26.0"})
                    as_page_text: If True, store file contents as page text instead of attachment

                Returns:
                    Dictionary with:
                    - page_tree_id: Created page ID
                    - entry_id: Attachment entry ID
                    - page_url: LabArchives web URL
                    - created_at: Upload timestamp
                    - file_size_bytes: File size
                    - filename: Uploaded filename
                """
                from datetime import datetime
                from pathlib import Path

                from labarchives_mcp.models.upload import ProvenanceMetadata, UploadRequest

                logger.info(
                    f"upload_to_labarchives called: file={file_path}, "
                    f"notebook={notebook_id}, title={page_title}"
                )

                try:
                    uid = await auth_manager.ensure_uid()
                    logger.debug(f"Obtained UID: {uid[:20]}...")

                    # Validate file exists
                    file_path_obj = Path(file_path)
                    if not file_path_obj.exists():
                        raise FileNotFoundError(f"File not found: {file_path}")

                    # Parse execution timestamp
                    executed_at_dt = datetime.fromisoformat(executed_at.replace("Z", "+00:00"))

                    # Build metadata
                    import platform

                    metadata = ProvenanceMetadata(
                        git_commit_sha=git_commit_sha,
                        git_branch=git_branch,
                        git_repo_url=git_repo_url,
                        git_is_dirty=git_is_dirty,
                        code_version=None,
                        executed_at=executed_at_dt,
                        python_version=python_version,
                        dependencies=dependencies or {},
                        os_name=platform.system(),
                        hostname=platform.node(),
                    )

                    # Build upload request
                    upload_request = UploadRequest(
                        notebook_id=notebook_id,
                        parent_folder_id=parent_folder_id,
                        page_title=page_title,
                        file_path=file_path_obj,
                        caption=caption,
                        change_description=None,
                        metadata=metadata,
                        allow_dirty_git=allow_dirty_git,
                        create_as_text=as_page_text,
                    )

                    # Execute upload
                    result = await notebook_client.upload_to_labarchives(uid, upload_request)
                    logger.success(
                        f"Successfully uploaded {result.filename} to page {result.page_tree_id}"
                    )

                    return {
                        "page_tree_id": result.page_tree_id,
                        "entry_id": result.entry_id,
                        "page_url": result.page_url,
                        "created_at": result.created_at.isoformat(),
                        "file_size_bytes": result.file_size_bytes,
                        "filename": result.filename,
                    }

                except Exception as exc:
                    logger.error(f"Failed to upload to LabArchives: {exc}", exc_info=True)
                    raise

        else:
            logger.info("Upload functionality is DISABLED (LABARCHIVES_ENABLE_UPLOAD=false)")

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
