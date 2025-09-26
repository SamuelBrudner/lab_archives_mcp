"""MCP server entry point for the LabArchives PoL implementation."""

from __future__ import annotations

import asyncio
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
        from fastmcp import FastMCP as FastMCPClass
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
        notebook_client = LabArchivesClient(http_client)

        server = fastmcp_class(
            server_id="labarchives-mcp-pol",
            name="LabArchives PoL Server",
            version=__version__,
            description="Proof-of-life MCP server exposing LabArchives notebooks.",
        )

        resource_decorator = cast(ResourceDecorator, server.resource("labarchives:notebooks"))

        @resource_decorator
        async def list_notebooks_resource() -> dict[str, Any]:
            uid = await auth_manager.ensure_uid()
            try:
                notebooks = await notebook_client.list_notebooks(uid)
            except LabArchivesAPIError as error:
                translated = translate_labarchives_fault(error)
                return {
                    "resource": "labarchives:notebooks",
                    "error": translated,
                }

            return {
                "resource": "labarchives:notebooks",
                "list": [notebook.model_dump(by_alias=True) for notebook in notebooks],
            }

        await server.serve()


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
