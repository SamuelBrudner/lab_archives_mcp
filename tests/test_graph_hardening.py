"""Tests for graph validation and pruning."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import networkx as nx
import pytest

from labarchives_mcp.state import StateManager


def _build_graph(project_id: str, pages: list[tuple[str, str]]) -> dict[str, Any]:
    """Create a simple graph with given page IDs and notebook IDs."""
    graph = nx.DiGraph()
    graph.add_node(project_id, type="project")
    for page_id, notebook_id in pages:
        node_id = f"page:{page_id}"
        graph.add_node(node_id, type="page", notebook_id=notebook_id)
        graph.add_edge(project_id, node_id, relation="visited")
    return cast(dict[str, Any], nx.node_link_data(graph))


@pytest.mark.asyncio()  # type: ignore[misc]
async def test_validate_graph_respects_max_checks(tmp_path: Path) -> None:
    manager = StateManager(storage_dir=tmp_path)
    context = manager.create_project("Proj", "Desc")

    # Insert pages with a known order: invalid first, then valid
    context.graph_data = _build_graph(context.id, [("invalid", "nb1"), ("valid", "nb1")])
    manager._save_state()

    calls: list[str] = []

    async def check_page(nb: str, page: str) -> bool:
        calls.append(page)
        return page != "invalid"

    stats = await manager.validate_graph(check_page, max_checks=1, include_all_contexts=False)

    assert stats["removed_nodes"] == 1
    assert stats["contexts_checked"] == 1
    assert calls == ["invalid"]  # bounded by max_checks, only first page checked


@pytest.mark.asyncio()  # type: ignore[misc]
async def test_validate_graph_all_contexts(tmp_path: Path) -> None:
    manager = StateManager(storage_dir=tmp_path)
    ctx1 = manager.create_project("Proj1", "Desc1")
    ctx2 = manager.create_project("Proj2", "Desc2")

    ctx1.graph_data = _build_graph(ctx1.id, [("keep", "nb1")])
    ctx2.graph_data = _build_graph(ctx2.id, [("drop", "nb2")])
    manager._save_state()

    async def check_page(nb: str, page: str) -> bool:
        return page != "drop"

    stats = await manager.validate_graph(check_page, max_checks=5, include_all_contexts=True)

    assert stats["contexts_checked"] == 2
    assert stats["removed_nodes"] == 1
    assert stats["removed_edges"] >= 0
