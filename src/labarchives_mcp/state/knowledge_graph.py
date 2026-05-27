"""Project knowledge graph mutation service."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable

import networkx as nx
from loguru import logger

from .constants import GRAPH_SCHEMA_VERSION
from .exceptions import GraphUpdateError
from .graph_helpers import (
    GRAPH_UPDATE_ERRORS,
    _touch_graph_node,
    _touch_notebook_node,
    _touch_page_node,
    _upsert_graph_edge,
)
from .models import Finding, ProjectContext, VisitedPage


class KnowledgeGraph:
    """Records visits, content links, and findings in project graphs."""

    def __init__(
        self,
        get_active_context: Callable[[], ProjectContext | None],
        save_state: Callable[[], None],
        max_visits: int,
    ) -> None:
        self._get_active_context = get_active_context
        self._save_state_callback = save_state
        self.MAX_VISITS = max_visits

    def get_active_context(self) -> ProjectContext | None:
        return self._get_active_context()

    def _save_state(self) -> None:
        self._save_state_callback()

    def log_visit(self, notebook_id: str, page_id: str, title: str) -> None:
        """Log a page visit to the active context and update the graph.

        Enriches graph nodes with timestamps and visit counts, and wires
        project→notebook, notebook→page, and project→page edges.
        """
        context = self.get_active_context()
        if not context:
            # If no context is active, we just ignore (or could log a warning)
            return

        original_visited_pages = list(context.visited_pages)

        # 1. Add to visited_pages list
        visit = VisitedPage(page_id=page_id, title=title, notebook_id=notebook_id)
        context.visited_pages.append(visit)
        if len(context.visited_pages) > self.MAX_VISITS:
            removed = len(context.visited_pages) - self.MAX_VISITS
            context.visited_pages = context.visited_pages[-self.MAX_VISITS :]
            logger.warning(f"Pruned visited_pages history by {removed} to cap at {self.MAX_VISITS}")

        # 2. Update Graph
        try:
            graph = nx.node_link_graph(context.graph_data, edges="links")
            graph.graph.setdefault("schema_version", GRAPH_SCHEMA_VERSION)
            now = time.time()

            # Add Project Node (root)
            _touch_graph_node(graph, context.id, now=now, type="project", label=context.name)

            # Add Notebook Node
            if notebook_id:
                notebook_node_id = f"notebook:{notebook_id}"
                _touch_graph_node(
                    graph,
                    notebook_node_id,
                    now=now,
                    type="notebook",
                    label=notebook_id,
                )

            # Add Page Node
            page_node_id = f"page:{page_id}"
            existing_page = graph.nodes[page_node_id] if graph.has_node(page_node_id) else {}
            visit_count = existing_page.get("visit_count", 0) + 1
            _touch_graph_node(
                graph,
                page_node_id,
                now=now,
                type="page",
                label=title,
                notebook_id=notebook_id,
                visit_count=visit_count,
            )

            # Edges
            if notebook_id:
                _upsert_graph_edge(
                    graph,
                    context.id,
                    notebook_node_id,
                    now=now,
                    relation="uses_notebook",
                    created_at=now,
                )
                _upsert_graph_edge(
                    graph,
                    notebook_node_id,
                    page_node_id,
                    now=now,
                    relation="contains",
                    created_at=now,
                )

            _upsert_graph_edge(
                graph, context.id, page_node_id, now=now, relation="visited", created_at=now
            )

            # Serialize back
            context.graph_data = nx.node_link_data(graph, edges="links")
        except GRAPH_UPDATE_ERRORS as exc:
            context.visited_pages = original_visited_pages
            raise GraphUpdateError(f"Failed to update graph for visit to page {page_id}") from exc

        self._save_state()
        logger.debug(f"Logged visit to {title} in context {context.id}")

    def log_page_content_links(
        self,
        source_notebook_id: str,
        source_page_id: str,
        links: list[tuple[str, str]],
    ) -> int:
        """Persist page-to-page links detected in page content.

        Links are represented as directed Page → Page edges with relation
        ``content_link``. The method records only graph structure; it does not
        add target pages to visit history.
        """
        context = self.get_active_context()
        if not context or not source_page_id:
            return 0

        normalized_links: list[tuple[str, str]] = []
        seen_links: set[tuple[str, str]] = set()
        for target_notebook_id, target_page_id in links:
            target_page_id = str(target_page_id or "").strip()
            target_notebook_id = str(target_notebook_id or source_notebook_id or "").strip()
            if not target_page_id or target_page_id == source_page_id:
                continue

            key = (target_notebook_id, target_page_id)
            if key in seen_links:
                continue

            seen_links.add(key)
            normalized_links.append(key)

        if not normalized_links:
            return 0

        try:
            graph = nx.node_link_graph(context.graph_data, edges="links")
            graph.graph.setdefault("schema_version", GRAPH_SCHEMA_VERSION)
            now = time.time()

            source_page_node_id = _touch_page_node(
                graph, source_page_id, source_notebook_id, source_page_id, now=now
            )
            if source_notebook_id:
                source_notebook_node_id = _touch_notebook_node(graph, source_notebook_id, now=now)
                _upsert_graph_edge(
                    graph,
                    source_notebook_node_id,
                    source_page_node_id,
                    now=now,
                    default_created_at=now,
                    setdefault_created_at=True,
                    relation="contains",
                )

            for target_notebook_id, target_page_id in normalized_links:
                target_page_node_id = _touch_page_node(
                    graph, target_page_id, target_notebook_id, "Linked Page", now=now
                )
                if target_notebook_id:
                    target_notebook_node_id = _touch_notebook_node(
                        graph, target_notebook_id, now=now
                    )
                    _upsert_graph_edge(
                        graph,
                        target_notebook_node_id,
                        target_page_node_id,
                        now=now,
                        default_created_at=now,
                        setdefault_created_at=True,
                        relation="contains",
                    )

                _upsert_graph_edge(
                    graph,
                    source_page_node_id,
                    target_page_node_id,
                    now=now,
                    default_created_at=now,
                    setdefault_created_at=True,
                    relation="content_link",
                    source="page_content",
                )

            context.graph_data = nx.node_link_data(graph, edges="links")
            self._save_state()
            return len(normalized_links)
        except GRAPH_UPDATE_ERRORS as exc:
            raise GraphUpdateError(
                f"Failed to update graph content links for page {source_page_id}"
            ) from exc

    def log_finding(
        self, content: str, source_url: str | None = None, page_id: str | None = None
    ) -> None:
        """Record a finding in the active context and update the graph.

        If a page_id is provided, also connect the finding to its source page.
        """
        context = self.get_active_context()
        if not context:
            raise RuntimeError("No active project context. Create or switch to a project first.")

        original_findings = list(context.findings)

        # 1. Add to findings list
        finding = Finding(content=content, source_url=source_url)
        context.findings.append(finding)

        # 2. Update Graph
        try:
            graph = nx.node_link_graph(context.graph_data, edges="links")
            graph.graph.setdefault("schema_version", GRAPH_SCHEMA_VERSION)
            now = time.time()

            # Add Project Node (root)
            if not graph.has_node(context.id):
                _touch_graph_node(graph, context.id, now=now, type="project", label=context.name)
            graph.nodes[context.id]["last_seen"] = now

            # Add Finding Node. Use a hash because content can be long.
            finding_hash = hashlib.md5(content.encode()).hexdigest()[:8]
            finding_node_id = f"finding:{finding_hash}"

            if graph.has_node(finding_node_id):
                node = graph.nodes[finding_node_id]
                node["last_seen"] = now
                node["count"] = node.get("count", 1) + 1
                node["source_url"] = source_url or node.get("source_url")
            else:
                graph.add_node(
                    finding_node_id,
                    type="finding",
                    label=content[:50],
                    full_content=content,
                    source_url=source_url,
                    first_seen=now,
                    last_seen=now,
                    count=1,
                )

            # Edge: Project -> Finding
            if graph.has_edge(context.id, finding_node_id):
                graph.edges[context.id, finding_node_id]["last_seen"] = now
            else:
                _upsert_graph_edge(
                    graph,
                    context.id,
                    finding_node_id,
                    now=now,
                    default_created_at=now,
                    relation="discovered",
                )

            # Edge: Page -> Finding (provenance) if provided
            if page_id:
                page_node_id = f"page:{page_id}"
                if not graph.has_node(page_node_id):
                    _touch_graph_node(graph, page_node_id, now=now, type="page", label=page_id)
                else:
                    graph.nodes[page_node_id]["last_seen"] = now

                if graph.has_edge(page_node_id, finding_node_id):
                    graph.edges[page_node_id, finding_node_id]["last_seen"] = now
                else:
                    _upsert_graph_edge(
                        graph,
                        page_node_id,
                        finding_node_id,
                        now=now,
                        default_created_at=now,
                        relation="evidence_from",
                    )

            # Serialize back
            context.graph_data = nx.node_link_data(graph, edges="links")
        except GRAPH_UPDATE_ERRORS as exc:
            context.findings = original_findings
            raise GraphUpdateError("Failed to update graph for finding") from exc

        self._save_state()
        logger.info(f"Logged finding in context {context.id}")
