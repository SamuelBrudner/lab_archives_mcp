"""Validation and pruning for serialized project graphs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import networkx as nx
from loguru import logger

from .models import ProjectContext, SessionState


class GraphValidationService:
    """Validates serialized project graph data."""

    def __init__(
        self,
        state: SessionState,
        save_state: Callable[[], None],
        get_active_context: Callable[[], ProjectContext | None],
    ) -> None:
        self._state = state
        self._save_state_callback = save_state
        self._get_active_context = get_active_context

    def _save_state(self) -> None:
        self._save_state_callback()

    def get_active_context(self) -> ProjectContext | None:
        return self._get_active_context()

    async def _prune_context_graph(
        self, context: ProjectContext, check_page_exists: Any, max_checks: int
    ) -> dict[str, int]:
        """Prune invalid page nodes from a single context graph."""
        graph = nx.node_link_graph(context.graph_data, edges="links")
        page_nodes = [
            (node, data) for node, data in graph.nodes(data=True) if data.get("type") == "page"
        ]

        if max_checks > 0 and len(page_nodes) > max_checks:
            page_nodes = page_nodes[:max_checks]

        removed_nodes = 0
        removed_edges = 0
        initial_edge_count = graph.number_of_edges()

        for node, data in page_nodes:
            page_id = node.replace("page:", "")
            notebook_id = data.get("notebook_id")

            if notebook_id and page_id:
                exists = await check_page_exists(notebook_id, page_id)
                if not exists:
                    graph.remove_node(node)
                    removed_nodes += 1
                    logger.warning(f"Pruning invalid page node: {node}")

        if removed_nodes > 0:
            removed_edges = max(0, initial_edge_count - graph.number_of_edges())
            context.graph_data = nx.node_link_data(graph, edges="links")
            self._save_state()

        return {"removed_nodes": removed_nodes, "removed_edges": removed_edges}

    async def validate_graph(
        self, check_page_exists: Any, max_checks: int = 10, include_all_contexts: bool = False
    ) -> dict[str, int]:
        """Prune invalid nodes from project graphs.

        Args:
            check_page_exists: Async callable(notebook_id, page_id) -> bool
            max_checks: Maximum page nodes to validate per context (limits API load)
            include_all_contexts: Validate every context when True; otherwise only active.

        Returns:
            Dict with counts of removed nodes/edges across checked contexts.
        """
        contexts: list[ProjectContext] = []
        if include_all_contexts:
            contexts = list(self._state.contexts.values())
        else:
            active = self.get_active_context()
            if active:
                contexts = [active]

        if not contexts:
            return {"removed_nodes": 0, "removed_edges": 0, "contexts_checked": 0}

        total_removed_nodes = 0
        total_removed_edges = 0

        for context in contexts:
            stats = await self._prune_context_graph(context, check_page_exists, max_checks)
            total_removed_nodes += stats.get("removed_nodes", 0)
            total_removed_edges += stats.get("removed_edges", 0)

        return {
            "removed_nodes": total_removed_nodes,
            "removed_edges": total_removed_edges,
            "contexts_checked": len(contexts),
        }
