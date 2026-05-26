"""Background graph validation for the MCP server."""

from __future__ import annotations

import asyncio

from loguru import logger

from .context import ToolContext


async def validate_graph_task(context: ToolContext) -> None:
    """Run bounded background graph validation after server startup."""
    await asyncio.sleep(5)
    logger.info("Starting background graph validation (bounded sample)...")

    async def _check_page(nb_id: str, p_id: str) -> bool:
        try:
            uid = await context.auth_manager.ensure_uid()
            await context.notebook_client.get_page_entries(uid, nb_id, p_id)
            await asyncio.sleep(0)
            return True
        except Exception:
            return False

    stats = await context.state_manager.validate_graph(
        _check_page, max_checks=10, include_all_contexts=True
    )
    if stats.get("removed_nodes", 0) > 0:
        logger.warning(f"Graph validation pruned invalid elements: {stats}")
    else:
        logger.info("Graph validation passed (no invalid nodes found).")
