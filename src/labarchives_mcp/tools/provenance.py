"""Graph provenance and suggestion tools."""

from __future__ import annotations

import re
from typing import Any

import networkx as nx

from ..schemas.tool_responses import (
    JsonObject,
    ProvenanceSourceResponse,
    RelatedPageResponse,
    RelatedPagesResponse,
    SuggestNextStepsResponse,
    TraceProvenanceResponse,
)
from .context import ToolContext
from .decorators import register_context_tool
from .utils import _extract_labarchives_page_links, _paginate_items


async def get_related_pages(
    context: ToolContext, notebook_id: str, page_id: str, limit: int | None = 20, offset: int = 0
) -> RelatedPagesResponse:
    """Find pages related to the given page using the project graph and content links."""
    active_context = context.state_manager.get_active_context()
    if not active_context:
        return {
            "items": [],
            "meta": {
                "total": 0,
                "offset": offset,
                "limit": limit,
                "truncated": False,
            },
        }

    related_pages: list[RelatedPageResponse] = []
    seen_ids: set[str] = set()

    def _add_related_page(related_page_id: str, title: str, source: str) -> None:
        if related_page_id == page_id or related_page_id in seen_ids:
            return

        related_pages.append(
            {
                "page_id": related_page_id,
                "title": title,
                "source": source,
            }
        )
        seen_ids.add(related_page_id)

    content_links: list[tuple[str, str]] = []
    uid = await context.auth_manager.ensure_uid()
    entries = await context.notebook_client.get_page_entries(
        uid, notebook_id, page_id, include_data=True
    )
    content_links = _extract_labarchives_page_links(entries)
    context.state_manager.log_page_content_links(notebook_id, page_id, content_links)
    active_context = context.state_manager.get_active_context() or active_context

    graph = nx.node_link_graph(active_context.graph_data, edges="links")
    page_node_id = f"page:{page_id}"

    if graph.has_node(page_node_id):

        def _page_title(node_id: str) -> str:
            node_data = graph.nodes[node_id]
            return str(node_data.get("label") or node_id.replace("page:", ""))

        for _, target, edge_data in graph.out_edges(page_node_id, data=True):
            target_data = graph.nodes[target]
            if target_data.get("type") == "page" and edge_data.get("relation") == "content_link":
                _add_related_page(
                    target.replace("page:", ""),
                    _page_title(target),
                    "content_link",
                )

        graph_undir = graph.to_undirected()
        for neighbor in graph_undir.neighbors(page_node_id):
            node_data = graph.nodes[neighbor]
            if node_data.get("type") != "page":
                continue

            edge_data = graph.get_edge_data(page_node_id, neighbor) or graph.get_edge_data(
                neighbor, page_node_id, default={}
            )
            if edge_data.get("relation") == "content_link":
                continue

            _add_related_page(
                neighbor.replace("page:", ""),
                _page_title(neighbor),
                "graph_neighbor",
            )

        for neighbor in graph_undir.neighbors(page_node_id):
            node_data = graph.nodes[neighbor]
            if node_data.get("type") == "project":
                for sibling in graph_undir.neighbors(neighbor):
                    sibling_data = graph.nodes[sibling]
                    if sibling_data.get("type") == "page":
                        _add_related_page(
                            sibling.replace("page:", ""),
                            str(sibling_data.get("label", "Unknown")),
                            "project_sibling",
                        )

    for _target_notebook_id, target_page_id in content_links:
        _add_related_page(target_page_id, "Linked Page", "content_link")

    items, meta = _paginate_items(related_pages, limit=limit, offset=offset)
    return {"items": items, "meta": meta}


async def trace_provenance(
    context: ToolContext, notebook_id: str, page_id: str, entry_id: str
) -> TraceProvenanceResponse:
    """Trace the provenance of a specific entry."""
    sources: list[ProvenanceSourceResponse] = []
    metadata: JsonObject = {}

    uid = await context.auth_manager.ensure_uid()
    entries = await context.notebook_client.get_page_entries(
        uid, notebook_id, page_id, include_data=True
    )

    target_entry = next((entry for entry in entries if entry.get("eid") == entry_id), None)
    if not target_entry:
        return {"error": f"Entry {entry_id} not found on page {page_id}"}

    content = target_entry.get("content") or ""
    source_pattern = re.compile(r"(?:Derived From|Source):\s*([a-zA-Z0-9_\-]+)")

    matches = source_pattern.findall(content)
    for match in matches:
        sources.append(
            {
                "id": match,
                "type": "derived_from_text",
                "description": "Found explicit citation in entry content",
            }
        )

    for entry in entries:
        caption = entry.get("caption", "") or ""
        e_content = entry.get("content") or ""

        if "Code Provenance Metadata" in caption or "Git Commit SHA" in e_content:
            metadata["code_provenance"] = {
                "eid": entry.get("eid"),
                "content_snippet": e_content[:200] + "...",
            }

    active_context = context.state_manager.get_active_context()
    if active_context:
        graph = nx.node_link_graph(active_context.graph_data, edges="links")
        page_node_id = f"page:{page_id}"

        if graph.has_node(page_node_id):
            for successor in graph.successors(page_node_id):
                node_data = graph.nodes[successor]
                if node_data.get("type") == "finding":
                    edge_data = graph.get_edge_data(page_node_id, successor)
                    if edge_data.get("relation") == "evidence_from":
                        sources.append(
                            {
                                "id": successor.replace("finding:", ""),
                                "type": "agent_finding",
                                "description": str(node_data.get("label", "Agent finding")),
                            }
                        )

    return {"sources": sources, "metadata": metadata}


async def suggest_next_steps(context: ToolContext) -> SuggestNextStepsResponse:
    """Provide lightweight heuristics on next actions based on current project state."""
    active_context = context.state_manager.get_active_context()
    if not active_context:
        return {
            "phase": "no_context",
            "suggestions": [
                "Create a project with create_project() to start tracking your work.",
            ],
        }

    graph = nx.node_link_graph(active_context.graph_data, edges="links")

    pages = [node for node, data in graph.nodes(data=True) if data.get("type") == "page"]
    findings = [node for node, data in graph.nodes(data=True) if data.get("type") == "finding"]

    if len(pages) == 0 and len(findings) == 0:
        return {
            "phase": "cold_start",
            "suggestions": [
                "Use search_labarchives to find relevant pages.",
                "Use list_notebooks to explore what's available.",
                "Read pages with read_notebook_page to start building context.",
            ],
        }

    return {
        "phase": "active",
        "stats": {
            "pages_visited": len(pages),
            "findings_logged": len(findings),
            "project_name": active_context.name,
        },
        "suggestions": [
            "Continue exploring with search_labarchives or read_notebook_page.",
            "Log key observations with log_finding.",
            "Review your progress with get_current_context.",
            "Find related content with get_related_pages.",
        ],
    }


def register_provenance_tools(server: Any, context: ToolContext) -> None:
    """Register graph provenance tools."""
    for handler in (get_related_pages, trace_provenance, suggest_next_steps):
        register_context_tool(server, context, handler)
