"""Upload provenance graph recording."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import networkx as nx

from .constants import GRAPH_SCHEMA_VERSION
from .exceptions import GraphUpdateError
from .graph_helpers import GRAPH_UPDATE_ERRORS, _touch_graph_node, _upsert_graph_edge
from .models import ProjectContext

if TYPE_CHECKING:
    from ..models.upload import ProvenanceMetadata


class ProvenanceService:
    """Records upload provenance subgraphs."""

    def __init__(
        self,
        get_active_context: Callable[[], ProjectContext | None],
        save_state: Callable[[], None],
    ) -> None:
        self._get_active_context = get_active_context
        self._save_state_callback = save_state

    def get_active_context(self) -> ProjectContext | None:
        return self._get_active_context()

    def _save_state(self) -> None:
        self._save_state_callback()

    @staticmethod
    def _coerce_timestamp(value: Any) -> float | None:
        """Normalize timestamps from floats, datetimes, or ISO strings."""
        if value is None:
            return None
        if isinstance(value, int | float):
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
        metadata: ProvenanceMetadata,
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
                self._coerce_timestamp(created_at) or metadata.executed_at.timestamp() or now
            )
            file_path_obj = Path(file_path)

            artifact_suffix = entry_id or file_path_obj.stem or "upload"
            page_node_id = f"page:{page_tree_id}"
            notebook_node_id = f"notebook:{notebook_id}"
            artifact_node_id = f"artifact:{page_tree_id}:{artifact_suffix}"
            activity_node_id = f"activity:upload:{page_tree_id}:{artifact_suffix}"
            user_node_id = f"user:{uid}"
            software_node_id = "software_agent:labarchives-mcp-pol"

            _touch_graph_node(
                graph,
                context.id,
                now=now,
                first_seen=created_ts,
                drop_none=True,
                type="project",
                label=context.name,
                description=context.description,
                created_at=context.created_at,
            )
            _touch_graph_node(
                graph,
                notebook_node_id,
                now=now,
                first_seen=created_ts,
                drop_none=True,
                type="notebook",
                label=notebook_id,
                notebook_id=notebook_id,
            )
            _touch_graph_node(
                graph,
                page_node_id,
                now=now,
                first_seen=created_ts,
                drop_none=True,
                type="page",
                label=page_title,
                page_id=page_tree_id,
                notebook_id=notebook_id,
                page_url=page_url,
                created_at=created_ts,
                upload_count=(
                    (graph.nodes[page_node_id].get("upload_count", 0) + 1)
                    if graph.has_node(page_node_id)
                    else 1
                ),
            )
            _touch_graph_node(
                graph,
                artifact_node_id,
                now=now,
                first_seen=created_ts,
                drop_none=True,
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
            _touch_graph_node(
                graph,
                activity_node_id,
                now=now,
                first_seen=created_ts,
                drop_none=True,
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
            _touch_graph_node(
                graph,
                user_node_id,
                now=now,
                first_seen=created_ts,
                drop_none=True,
                type="user",
                label=uid,
                uid=uid,
            )
            _touch_graph_node(
                graph,
                software_node_id,
                now=now,
                first_seen=created_ts,
                drop_none=True,
                type="software_agent",
                label="LabArchives MCP Server",
                identifier="labarchives-mcp-pol",
                server_version=server_version,
                created_at=datetime.now(UTC).timestamp(),
            )

            _upsert_graph_edge(
                graph,
                context.id,
                notebook_node_id,
                now=now,
                default_created_at=created_ts,
                relation="uses_notebook",
            )
            _upsert_graph_edge(
                graph,
                notebook_node_id,
                page_node_id,
                now=now,
                default_created_at=created_ts,
                relation="contains",
            )
            _upsert_graph_edge(
                graph,
                context.id,
                page_node_id,
                now=now,
                default_created_at=created_ts,
                relation="tracked",
            )
            _upsert_graph_edge(
                graph,
                context.id,
                artifact_node_id,
                now=now,
                default_created_at=created_ts,
                relation="tracked",
            )
            _upsert_graph_edge(
                graph,
                context.id,
                activity_node_id,
                now=now,
                default_created_at=created_ts,
                relation="tracked",
            )
            _upsert_graph_edge(
                graph,
                page_node_id,
                artifact_node_id,
                now=now,
                default_created_at=created_ts,
                relation="contains_artifact",
            )
            _upsert_graph_edge(
                graph,
                page_node_id,
                activity_node_id,
                now=now,
                default_created_at=created_ts,
                relation="was_generated_by",
            )
            _upsert_graph_edge(
                graph,
                artifact_node_id,
                activity_node_id,
                now=now,
                default_created_at=created_ts,
                relation="was_generated_by",
            )
            _upsert_graph_edge(
                graph,
                page_node_id,
                user_node_id,
                now=now,
                default_created_at=created_ts,
                relation="was_attributed_to",
            )
            _upsert_graph_edge(
                graph,
                artifact_node_id,
                user_node_id,
                now=now,
                default_created_at=created_ts,
                relation="was_attributed_to",
            )
            _upsert_graph_edge(
                graph,
                activity_node_id,
                user_node_id,
                now=now,
                default_created_at=created_ts,
                relation="was_associated_with",
            )
            _upsert_graph_edge(
                graph,
                activity_node_id,
                software_node_id,
                now=now,
                default_created_at=created_ts,
                relation="was_associated_with",
            )

            context.graph_data = nx.node_link_data(graph, edges="links")
            self._save_state()
        except GRAPH_UPDATE_ERRORS as exc:
            raise GraphUpdateError(
                f"Failed to record upload provenance in project graph for page {page_tree_id}"
            ) from exc
