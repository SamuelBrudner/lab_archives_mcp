"""Persistent state management for LabArchives MCP agent context."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import networkx as nx
from loguru import logger
from pydantic import BaseModel, Field


class Finding(BaseModel):
    """A key fact or data point extracted during an experiment."""

    content: str = Field(..., description="The fact or finding text")
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp of discovery")
    source_url: str | None = Field(None, description="URL or ID of the source page")


class VisitedPage(BaseModel):
    """Record of a page visit within an experiment context."""

    page_id: str = Field(..., description="Page tree ID")
    title: str = Field(..., description="Page title")
    notebook_id: str | None = Field(None, description="Notebook ID")
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp of visit")


class ProjectContext(BaseModel):
    """A scoped unit of work representing a research project."""

    id: str = Field(..., description="Unique identifier for the project")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="High-level goal or description")
    linked_notebook_ids: list[str] = Field(
        default_factory=list, description="List of relevant LabArchives Notebook IDs"
    )
    status: str = Field("active", description="active, paused, completed")
    created_at: float = Field(default_factory=time.time)
    visited_pages: list[VisitedPage] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    graph_data: dict[str, Any] = Field(
        default_factory=lambda: {
            "nodes": [],
            "links": [],
            "directed": True,
            "multigraph": False,
            "graph": {},
        },
        description="Serialized NetworkX graph",
    )


class SessionState(BaseModel):
    """Global state container for the agent's memory."""

    active_context_id: str | None = Field(None, description="ID of the currently active project")
    contexts: dict[str, ProjectContext] = Field(default_factory=dict)


class StateManager:
    """Manages persistence and modification of agent state."""

    def __init__(self, storage_dir: Path | str | None = None) -> None:
        if storage_dir is None:
            # Default to home directory for cross-repository access
            storage_dir = Path.home() / ".labarchives_state"
        self.storage_dir = Path(storage_dir)
        self.state_file = self.storage_dir / "session_state.json"
        self._state: SessionState = self._load_state()

    def _load_state(self) -> SessionState:
        """Load state from disk or create fresh."""
        if not self.state_file.exists():
            return SessionState(active_context_id=None, contexts={})

        try:
            with open(self.state_file, encoding="utf-8") as f:
                data = json.load(f)
                return SessionState.model_validate(data)
        except Exception as e:
            logger.error(f"Failed to load state: {e}. Starting fresh.")
            return SessionState(active_context_id=None, contexts={})

    def _save_state(self) -> None:
        """Persist current state to disk."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            f.write(self._state.model_dump_json(indent=2))

    def create_project(
        self, name: str, description: str, linked_notebook_ids: list[str] | None = None
    ) -> ProjectContext:
        """Start a new project context and make it active."""
        import uuid

        proj_id = f"proj-{uuid.uuid4().hex[:8]}"
        context = ProjectContext(
            id=proj_id,
            name=name,
            description=description,
            linked_notebook_ids=linked_notebook_ids or [],
            status="active",
        )

        self._state.contexts[proj_id] = context
        self._state.active_context_id = proj_id
        self._save_state()

        logger.info(f"Created project {name} ({proj_id}) linked to notebooks {linked_notebook_ids}")
        return context

    def delete_project(self, project_id: str) -> bool:
        """Delete a project context. Returns True if found and deleted."""
        if project_id not in self._state.contexts:
            return False

        del self._state.contexts[project_id]

        # If we deleted the active context, clear the pointer
        if self._state.active_context_id == project_id:
            self._state.active_context_id = None

        self._save_state()
        logger.info(f"Deleted project context: {project_id}")
        return True

    def switch_project(self, project_id: str) -> ProjectContext:
        """Switch the active context to an existing project."""
        if project_id not in self._state.contexts:
            raise ValueError(f"Project ID {project_id} not found")

        self._state.active_context_id = project_id
        self._save_state()
        logger.info(f"Switched to project context: {project_id}")
        return self._state.contexts[project_id]

    def get_active_context(self) -> ProjectContext | None:
        """Return the currently active project context, if any."""
        if not self._state.active_context_id:
            return None
        return self._state.contexts.get(self._state.active_context_id)

    def list_projects(self) -> list[dict[str, Any]]:
        """Return a summary of all projects."""
        return [
            {
                "id": ctx.id,
                "name": ctx.name,
                "status": ctx.status,
                "active": ctx.id == self._state.active_context_id,
            }
            for ctx in self._state.contexts.values()
        ]

    def log_visit(self, notebook_id: str, page_id: str, title: str) -> None:
        """Log a page visit to the active context and update the graph."""
        context = self.get_active_context()
        if not context:
            # If no context is active, we just ignore (or could log a warning)
            return

        # 1. Add to visited_pages list
        visit = VisitedPage(page_id=page_id, title=title, notebook_id=notebook_id)
        context.visited_pages.append(visit)

        # 2. Update Graph
        try:
            graph = nx.node_link_graph(context.graph_data)

            # Add Project Node (root)
            if not graph.has_node(context.id):
                graph.add_node(context.id, type="project", label=context.name)

            # Add Page Node
            page_node_id = f"page:{page_id}"
            if not graph.has_node(page_node_id):
                graph.add_node(page_node_id, type="page", label=title, notebook_id=notebook_id)

            # Edge: Project -> Page (indicates "visited during project")
            graph.add_edge(context.id, page_node_id, relation="visited")

            # Serialize back
            context.graph_data = nx.node_link_data(graph)
        except Exception as e:
            logger.error(f"Failed to update graph for visit: {e}")

        self._save_state()
        logger.debug(f"Logged visit to {title} in context {context.id}")

    def log_finding(self, content: str, source_url: str | None = None) -> None:
        """Record a finding in the active context and update the graph."""
        context = self.get_active_context()
        if not context:
            raise RuntimeError("No active project context. Create or switch to a project first.")

        # 1. Add to findings list
        finding = Finding(content=content, source_url=source_url)
        context.findings.append(finding)

        # 2. Update Graph
        try:
            graph = nx.node_link_graph(context.graph_data)

            # Add Project Node (root)
            if not graph.has_node(context.id):
                graph.add_node(context.id, type="project", label=context.name)

            # Add Finding Node
            # Use a hash or timestamp for ID since content can be long
            import hashlib

            finding_hash = hashlib.md5(content.encode()).hexdigest()[:8]
            finding_node_id = f"finding:{finding_hash}"

            if not graph.has_node(finding_node_id):
                graph.add_node(
                    finding_node_id, type="finding", label=content[:50], full_content=content
                )

            # Edge: Project -> Finding
            graph.add_edge(context.id, finding_node_id, relation="discovered")

            # Serialize back
            context.graph_data = nx.node_link_data(graph)
        except Exception as e:
            logger.error(f"Failed to update graph for finding: {e}")

        self._save_state()
        logger.info(f"Logged finding in context {context.id}")
