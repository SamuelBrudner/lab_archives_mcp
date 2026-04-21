"""Persistent state management for LabArchives MCP agent context."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import networkx as nx
from loguru import logger
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .models.upload import ProvenanceMetadata


GRAPH_SCHEMA_VERSION = 2


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
            "graph": {"schema_version": GRAPH_SCHEMA_VERSION},
        },
        description="Serialized NetworkX graph",
    )


class SessionState(BaseModel):
    """Global state container for the agent's memory."""

    active_context_id: str | None = Field(None, description="ID of the currently active project")
    contexts: dict[str, ProjectContext] = Field(default_factory=dict)


class StateManager:
    """Manages persistence and modification of agent state."""

    MAX_VISITS = 1000

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
                migrated = self._migrate_state_dict(data)
                return SessionState.model_validate(migrated)
        except Exception as e:
            logger.error(f"Failed to load state: {e}. Backing up and starting fresh.")
            # Backup corrupted state
            backup_path = self.state_file.with_suffix(".json.bak")
            try:
                import shutil

                shutil.copy(self.state_file, backup_path)
                logger.warning(f"Corrupted state backed up to {backup_path}")
            except Exception as backup_err:
                logger.error(f"Failed to backup corrupted state: {backup_err}")

            return SessionState(active_context_id=None, contexts={})

    def _save_state(self) -> None:
        """Persist current state to disk using atomic write pattern."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Write to temp file first
        temp_file = self.state_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(self._state.model_dump_json(indent=2))
                f.flush()
                import os

                os.fsync(f.fileno())

            # Atomic rename
            temp_file.replace(self.state_file)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            if temp_file.exists():
                temp_file.unlink()

    def _migrate_state_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Ensure graph data carries schema version and baseline metadata."""
        contexts = data.get("contexts") or {}
        now = time.time()

        if not isinstance(contexts, dict):
            return data

        for ctx in contexts.values():
            if not isinstance(ctx, dict):
                continue
            graph_data = ctx.get("graph_data") or {}
            ctx["graph_data"] = self._migrate_graph_data(graph_data, now)

        data["contexts"] = contexts
        return data

    def _migrate_graph_data(
        self, graph_data: dict[str, Any], default_ts: float | None = None
    ) -> dict[str, Any]:
        """Backfill schema_version and timing metadata for nodes/edges."""
        ts = default_ts or time.time()
        graph_data = graph_data or {}

        nodes = graph_data.get("nodes") or []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node.setdefault("first_seen", ts)
            node.setdefault("last_seen", ts)

        links = graph_data.get("links") or []
        for edge in links:
            if not isinstance(edge, dict):
                continue
            edge.setdefault("created_at", ts)
            edge.setdefault("last_seen", ts)

        meta = graph_data.get("graph")
        if not isinstance(meta, dict):
            meta = {}
        meta.setdefault("schema_version", GRAPH_SCHEMA_VERSION)

        graph_data["nodes"] = nodes
        graph_data["links"] = links
        graph_data["graph"] = meta
        graph_data.setdefault("directed", True)
        graph_data.setdefault("multigraph", False)
        return graph_data

    async def _prune_context_graph(
        self, context: ProjectContext, check_page_exists: Any, max_checks: int
    ) -> dict[str, int]:
        """Prune invalid page nodes from a single context graph."""
        try:
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
        except Exception as e:
            logger.error(f"Graph validation failed for context {context.id}: {e}")
            return {"removed_nodes": 0, "removed_edges": 0}

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

    @staticmethod
    def _coerce_timestamp(value: Any) -> float | None:
        """Normalize timestamps from floats, datetimes, or ISO strings."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, datetime):
            return value.timestamp()
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
            except ValueError:
                return None
        return None

    def record_upload_provenance(
        self,
        *,
        uid: str,
        notebook_id: str,
        page_title: str,
        file_path: Path | str,
        page_tree_id: str,
        entry_id: str | None,
        page_url: str,
        created_at: str | float | datetime | None,
        file_size_bytes: int | None,
        filename: str,
        metadata: "ProvenanceMetadata",
        server_version: str,
        as_page_text: bool,
    ) -> None:
        """Record a successful upload as a provenance subgraph on the active project."""
        context = self.get_active_context()
        if not context:
            return

        try:
            graph = nx.node_link_graph(context.graph_data, edges="links")
            graph.graph.setdefault("schema_version", GRAPH_SCHEMA_VERSION)
            now = time.time()
            created_ts = (
                self._coerce_timestamp(created_at)
                or metadata.executed_at.timestamp()
                or now
            )
            file_path_obj = Path(file_path)

            def _touch_node(node_id: str, **attrs: Any) -> None:
                default_attrs = {"first_seen": created_ts, "last_seen": now}
                if graph.has_node(node_id):
                    existing = graph.nodes[node_id]
                    existing.setdefault("first_seen", created_ts)
                    existing["last_seen"] = now
                    existing.update({k: v for k, v in attrs.items() if v is not None})
                else:
                    default_attrs.update({k: v for k, v in attrs.items() if v is not None})
                    graph.add_node(node_id, **default_attrs)

            def _add_edge(src: str, dst: str, **attrs: Any) -> None:
                if graph.has_edge(src, dst):
                    edge = graph.edges[src, dst]
                    edge["last_seen"] = now
                    edge.update({k: v for k, v in attrs.items() if v is not None})
                else:
                    graph.add_edge(
                        src,
                        dst,
                        created_at=created_ts,
                        last_seen=now,
                        **{k: v for k, v in attrs.items() if v is not None},
                    )

            artifact_suffix = entry_id or file_path_obj.stem or "upload"
            page_node_id = f"page:{page_tree_id}"
            notebook_node_id = f"notebook:{notebook_id}"
            artifact_node_id = f"artifact:{page_tree_id}:{artifact_suffix}"
            activity_node_id = f"activity:upload:{page_tree_id}:{artifact_suffix}"
            user_node_id = f"user:{uid}"
            software_node_id = "software_agent:labarchives-mcp-pol"

            _touch_node(
                context.id,
                type="project",
                label=context.name,
                description=context.description,
                created_at=context.created_at,
            )
            _touch_node(
                notebook_node_id,
                type="notebook",
                label=notebook_id,
                notebook_id=notebook_id,
            )
            _touch_node(
                page_node_id,
                type="page",
                label=page_title,
                page_id=page_tree_id,
                notebook_id=notebook_id,
                page_url=page_url,
                created_at=created_ts,
                upload_count=(graph.nodes[page_node_id].get("upload_count", 0) + 1)
                if graph.has_node(page_node_id)
                else 1,
            )
            _touch_node(
                artifact_node_id,
                type="artifact",
                label=filename,
                filename=filename,
                entry_id=entry_id,
                page_id=page_tree_id,
                notebook_id=notebook_id,
                page_url=page_url,
                file_size_bytes=file_size_bytes,
                created_at=created_ts,
                encoding_format=file_path_obj.suffix.lower() or None,
                entry_kind="page_text" if as_page_text else "attachment",
            )
            _touch_node(
                activity_node_id,
                type="activity",
                label=f"Upload {filename}",
                activity_type="upload_to_labarchives",
                notebook_id=notebook_id,
                page_id=page_tree_id,
                entry_id=entry_id,
                executed_at=metadata.executed_at.timestamp(),
                completed_at=created_ts,
                git_commit_sha=metadata.git_commit_sha,
                git_branch=metadata.git_branch,
                git_repo_url=metadata.git_repo_url,
                git_is_dirty=metadata.git_is_dirty,
                code_version=metadata.code_version or server_version,
                python_version=metadata.python_version,
                dependencies=metadata.dependencies,
                os_name=metadata.os_name,
                hostname=metadata.hostname,
                server_version=server_version,
            )
            _touch_node(
                user_node_id,
                type="user",
                label=uid,
                uid=uid,
            )
            _touch_node(
                software_node_id,
                type="software_agent",
                label="LabArchives MCP Server",
                identifier="labarchives-mcp-pol",
                server_version=server_version,
                created_at=datetime.now(UTC).timestamp(),
            )

            _add_edge(context.id, notebook_node_id, relation="uses_notebook")
            _add_edge(notebook_node_id, page_node_id, relation="contains")
            _add_edge(context.id, page_node_id, relation="tracked")
            _add_edge(context.id, artifact_node_id, relation="tracked")
            _add_edge(context.id, activity_node_id, relation="tracked")
            _add_edge(page_node_id, artifact_node_id, relation="contains_artifact")
            _add_edge(page_node_id, activity_node_id, relation="was_generated_by")
            _add_edge(artifact_node_id, activity_node_id, relation="was_generated_by")
            _add_edge(page_node_id, user_node_id, relation="was_attributed_to")
            _add_edge(artifact_node_id, user_node_id, relation="was_attributed_to")
            _add_edge(activity_node_id, user_node_id, relation="was_associated_with")
            _add_edge(activity_node_id, software_node_id, relation="was_associated_with")

            context.graph_data = nx.node_link_data(graph, edges="links")
            self._save_state()
        except Exception as e:
            logger.warning(f"Failed to record upload provenance in project graph: {e}")

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

    def _ensure_default_context(self) -> ProjectContext:
        """Get or create the singleton default project context.

        Returns the same default context every time, preventing proliferation.
        """
        # Check if default already exists
        default_id = "default-research-context"
        if default_id in self._state.contexts:
            context = self._state.contexts[default_id]
            # Ensure it's active
            if self._state.active_context_id != default_id:
                self._state.active_context_id = default_id
                self._save_state()
            return context

        # Create it for the first time with a fixed ID
        context = ProjectContext(
            id=default_id,
            name="Default Research Context",
            description="Auto-created context for tracking work",
            status="active",
        )
        self._state.contexts[default_id] = context
        self._state.active_context_id = default_id
        self._save_state()
        logger.info("Created singleton default project context")
        return context

    def log_visit(self, notebook_id: str, page_id: str, title: str) -> None:
        """Log a page visit to the active context and update the graph.

        Enriches graph nodes with timestamps and visit counts, and wires
        project→notebook, notebook→page, and project→page edges.
        """
        context = self.get_active_context()
        if not context:
            # If no context is active, we just ignore (or could log a warning)
            return

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

            def _touch_node(node_id: str, **attrs: Any) -> None:
                """Create or update a node while preserving first_seen/last_seen."""
                default_attrs = {
                    "first_seen": now,
                    "last_seen": now,
                }
                if graph.has_node(node_id):
                    existing = graph.nodes[node_id]
                    existing.setdefault("first_seen", now)
                    existing["last_seen"] = now
                    existing.update(attrs)
                else:
                    default_attrs.update(attrs)
                    graph.add_node(node_id, **default_attrs)

            # Add Project Node (root)
            _touch_node(context.id, type="project", label=context.name)

            # Add Notebook Node
            if notebook_id:
                notebook_node_id = f"notebook:{notebook_id}"
                _touch_node(
                    notebook_node_id,
                    type="notebook",
                    label=notebook_id,
                )

            # Add Page Node
            page_node_id = f"page:{page_id}"
            existing_page = graph.nodes[page_node_id] if graph.has_node(page_node_id) else {}
            visit_count = existing_page.get("visit_count", 0) + 1
            _touch_node(
                page_node_id,
                type="page",
                label=title,
                notebook_id=notebook_id,
                visit_count=visit_count,
            )

            def _add_edge(src: str, dst: str, **attrs: Any) -> None:
                if graph.has_edge(src, dst):
                    edge = graph.edges[src, dst]
                    edge["last_seen"] = now
                    edge.update(attrs)
                else:
                    graph.add_edge(src, dst, last_seen=now, **attrs)

            # Edges
            if notebook_id:
                _add_edge(context.id, notebook_node_id, relation="uses_notebook", created_at=now)
                _add_edge(notebook_node_id, page_node_id, relation="contains", created_at=now)

            _add_edge(context.id, page_node_id, relation="visited", created_at=now)

            # Serialize back
            context.graph_data = nx.node_link_data(graph, edges="links")
        except Exception as e:
            logger.error(f"Failed to update graph for visit: {e}")

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

            def _touch_notebook(notebook_id: str) -> str:
                notebook_node_id = f"notebook:{notebook_id}"
                if graph.has_node(notebook_node_id):
                    node = graph.nodes[notebook_node_id]
                    node.setdefault("first_seen", now)
                    node["last_seen"] = now
                    node["type"] = "notebook"
                    node.setdefault("label", notebook_id)
                else:
                    graph.add_node(
                        notebook_node_id,
                        type="notebook",
                        label=notebook_id,
                        first_seen=now,
                        last_seen=now,
                    )
                return notebook_node_id

            def _touch_page(page_id: str, notebook_id: str, label: str) -> str:
                page_node_id = f"page:{page_id}"
                if graph.has_node(page_node_id):
                    node = graph.nodes[page_node_id]
                    node.setdefault("first_seen", now)
                    node["last_seen"] = now
                    node["type"] = "page"
                    if notebook_id and not node.get("notebook_id"):
                        node["notebook_id"] = notebook_id
                    node.setdefault("label", label)
                else:
                    graph.add_node(
                        page_node_id,
                        type="page",
                        label=label,
                        notebook_id=notebook_id or None,
                        first_seen=now,
                        last_seen=now,
                    )
                return page_node_id

            def _add_edge(src: str, dst: str, **attrs: Any) -> None:
                if graph.has_edge(src, dst):
                    edge = graph.edges[src, dst]
                    edge.setdefault("created_at", now)
                    edge["last_seen"] = now
                    edge.update(attrs)
                else:
                    graph.add_edge(src, dst, created_at=now, last_seen=now, **attrs)

            source_page_node_id = _touch_page(
                source_page_id, source_notebook_id, source_page_id
            )
            if source_notebook_id:
                source_notebook_node_id = _touch_notebook(source_notebook_id)
                _add_edge(
                    source_notebook_node_id,
                    source_page_node_id,
                    relation="contains",
                )

            for target_notebook_id, target_page_id in normalized_links:
                target_page_node_id = _touch_page(
                    target_page_id, target_notebook_id, "Linked Page"
                )
                if target_notebook_id:
                    target_notebook_node_id = _touch_notebook(target_notebook_id)
                    _add_edge(
                        target_notebook_node_id,
                        target_page_node_id,
                        relation="contains",
                    )

                _add_edge(
                    source_page_node_id,
                    target_page_node_id,
                    relation="content_link",
                    source="page_content",
                )

            context.graph_data = nx.node_link_data(graph, edges="links")
            self._save_state()
            return len(normalized_links)
        except Exception as e:
            logger.error(f"Failed to update graph for content links: {e}")
            return 0

    def log_finding(
        self, content: str, source_url: str | None = None, page_id: str | None = None
    ) -> None:
        """Record a finding in the active context and update the graph.

        If a page_id is provided, also connect the finding to its source page.
        """
        context = self.get_active_context()
        if not context:
            raise RuntimeError("No active project context. Create or switch to a project first.")

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
                graph.add_node(context.id, type="project", label=context.name, first_seen=now)
            graph.nodes[context.id]["last_seen"] = now

            # Add Finding Node
            # Use a hash or timestamp for ID since content can be long
            import hashlib

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
                graph.add_edge(
                    context.id,
                    finding_node_id,
                    relation="discovered",
                    created_at=now,
                    last_seen=now,
                )

            # Edge: Page -> Finding (provenance) if provided
            if page_id:
                page_node_id = f"page:{page_id}"
                if not graph.has_node(page_node_id):
                    graph.add_node(
                        page_node_id,
                        type="page",
                        label=page_id,
                        first_seen=now,
                        last_seen=now,
                    )
                else:
                    graph.nodes[page_node_id]["last_seen"] = now

                if graph.has_edge(page_node_id, finding_node_id):
                    graph.edges[page_node_id, finding_node_id]["last_seen"] = now
                else:
                    graph.add_edge(
                        page_node_id,
                        finding_node_id,
                        relation="evidence_from",
                        created_at=now,
                        last_seen=now,
                    )

            # Serialize back
            context.graph_data = nx.node_link_data(graph, edges="links")
        except Exception as e:
            logger.error(f"Failed to update graph for finding: {e}")

        self._save_state()
        logger.info(f"Logged finding in context {context.id}")
