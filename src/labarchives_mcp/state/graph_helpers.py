"""Small helpers for project graph mutation."""

from __future__ import annotations

from typing import Any

import networkx as nx

GRAPH_UPDATE_ERRORS = (nx.NetworkXException, TypeError, ValueError, KeyError, AttributeError)


def _graph_attrs(attrs: dict[str, Any], *, drop_none: bool) -> dict[str, Any]:
    if drop_none:
        return {key: value for key, value in attrs.items() if value is not None}
    return attrs


def _touch_graph_node(
    graph: nx.Graph,
    node_id: str,
    *,
    now: float,
    first_seen: float | None = None,
    drop_none: bool = False,
    **attrs: Any,
) -> None:
    seen_at = now if first_seen is None else first_seen
    update_attrs = _graph_attrs(attrs, drop_none=drop_none)
    if graph.has_node(node_id):
        node = graph.nodes[node_id]
        node.setdefault("first_seen", seen_at)
        node["last_seen"] = now
        node.update(update_attrs)
        return

    graph.add_node(node_id, first_seen=seen_at, last_seen=now, **update_attrs)


def _upsert_graph_edge(
    graph: nx.Graph,
    src: str,
    dst: str,
    *,
    now: float,
    default_created_at: float | None = None,
    setdefault_created_at: bool = False,
    drop_none: bool = False,
    **attrs: Any,
) -> None:
    update_attrs = _graph_attrs(attrs, drop_none=drop_none)
    if graph.has_edge(src, dst):
        edge = graph.edges[src, dst]
        if setdefault_created_at and default_created_at is not None:
            edge.setdefault("created_at", default_created_at)
        edge["last_seen"] = now
        edge.update(update_attrs)
        return

    edge_attrs = dict(update_attrs)
    if default_created_at is not None and "created_at" not in edge_attrs:
        edge_attrs["created_at"] = default_created_at
    graph.add_edge(src, dst, last_seen=now, **edge_attrs)


def _touch_notebook_node(graph: nx.Graph, notebook_id: str, *, now: float) -> str:
    notebook_node_id = f"notebook:{notebook_id}"
    if graph.has_node(notebook_node_id):
        node = graph.nodes[notebook_node_id]
        node.setdefault("first_seen", now)
        node["last_seen"] = now
        node["type"] = "notebook"
        node.setdefault("label", notebook_id)
        return notebook_node_id

    graph.add_node(
        notebook_node_id,
        type="notebook",
        label=notebook_id,
        first_seen=now,
        last_seen=now,
    )
    return notebook_node_id


def _touch_page_node(
    graph: nx.Graph, page_id: str, notebook_id: str, label: str, *, now: float
) -> str:
    page_node_id = f"page:{page_id}"
    if graph.has_node(page_node_id):
        node = graph.nodes[page_node_id]
        node.setdefault("first_seen", now)
        node["last_seen"] = now
        node["type"] = "page"
        if notebook_id and not node.get("notebook_id"):
            node["notebook_id"] = notebook_id
        node.setdefault("label", label)
        return page_node_id

    graph.add_node(
        page_node_id,
        type="page",
        label=label,
        notebook_id=notebook_id or None,
        first_seen=now,
        last_seen=now,
    )
    return page_node_id
