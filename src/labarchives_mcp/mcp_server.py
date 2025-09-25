"""MCP server entry point for the LabArchives PoL implementation."""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from loguru import logger


async def run_server() -> None:
    """Run the MCP server event loop."""
    raise NotImplementedError("Wire MCP server transport and handlers.")


def run(main: Callable[[], Awaitable[None]] | None = None) -> None:
    """Synchronous helper for CLI entry points."""
    entry = main or run_server
    try:
        asyncio.run(entry())
    except KeyboardInterrupt:
        logger.warning("MCP server interrupted by user.")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled MCP server failure: {}", exc)
        raise
