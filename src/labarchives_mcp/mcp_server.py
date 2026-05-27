"""MCP server entry point for the LabArchives PoL implementation."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Coroutine
from importlib import metadata
from typing import Any, cast

import httpx
from loguru import logger

from .auth import AuthenticationManager, Credentials
from .eln_client import LabArchivesClient
from .settings import Settings
from .state import StateManager
from .tools import ToolContext, register_mcp_surface
from .tools.utils import _extract_labarchives_page_links, _paginate_items
from .tools.validation import validate_graph_task

# Lazy import keeps FastMCP monkeypatchable in tests and preserves a clear missing-dependency error.
FastMCP: type[Any] | None = None
_background_tasks: set[asyncio.Task[None]] = set()

__all__ = [
    "run_server",
    "run",
    "__version__",
    "FastMCP",
    "AuthenticationManager",
    "Credentials",
    "Settings",
    "LabArchivesClient",
    "httpx",
    "_extract_labarchives_page_links",
    "_paginate_items",
]


def _resolve_version() -> str:
    """Return the installed distribution version or fall back to the project default."""

    try:
        return metadata.version("labarchives-mcp-pol")
    except metadata.PackageNotFoundError:
        return "0.4.0"


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
        cast(Any, fastmcp.settings).show_cli_banner = False
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised in tests
        raise ImportError(
            "FastMCP is required to run the LabArchives MCP server. Install `fastmcp` to proceed."
        ) from exc

    FastMCP = cast(type[Any], FastMCPClass)
    return FastMCP


async def run_server(settings: Settings | None = None) -> None:
    """Run the MCP server event loop."""

    settings = settings or Settings.from_env()
    credentials = settings.credentials
    fastmcp_class = _import_fastmcp()

    async with httpx.AsyncClient(base_url=str(credentials.region)) as http_client:
        auth_manager = AuthenticationManager(http_client, credentials)
        notebook_client = LabArchivesClient(http_client, auth_manager)
        state_manager = StateManager.from_path(storage_dir=settings.state_dir)

        server = _instantiate_fastmcp(
            fastmcp_class,
            server_id="labarchives-mcp-pol",
            name="LabArchives PoL Server",
            version=__version__,
            description="Proof-of-life MCP server exposing LabArchives notebooks.",
        )

        context = ToolContext(
            credentials=credentials,
            auth_manager=auth_manager,
            notebook_client=notebook_client,
            state_manager=state_manager,
            server_version=__version__,
            settings=settings,
        )
        register_mcp_surface(server, context, upload_enabled=settings.upload_enabled)

        _supervise_background_task(
            validate_graph_task(context),
            name="validate-graph",
        )
        await server.run_async()


def run(main: Callable[[], Coroutine[Any, Any, None]] | None = None) -> None:
    """Synchronous helper for CLI entry points."""
    entry = main or run_server
    try:
        asyncio.run(entry())
    except KeyboardInterrupt:
        logger.warning("MCP server interrupted by user.")
    except (RuntimeError, ValueError, OSError, ImportError, httpx.HTTPError) as exc:
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


def _supervise_background_task(
    coroutine: Coroutine[Any, Any, None],
    *,
    name: str,
) -> asyncio.Task[None]:
    """Schedule a background task while retaining and logging its lifetime."""
    task = asyncio.create_task(coroutine, name=name)
    _background_tasks.add(task)

    def _observe_completion(completed: asyncio.Task[None]) -> None:
        _background_tasks.discard(completed)
        if completed.cancelled():
            return
        if exc := completed.exception():
            logger.opt(exception=exc).error(f"Background task {name!r} failed")

    task.add_done_callback(_observe_completion)
    return task
