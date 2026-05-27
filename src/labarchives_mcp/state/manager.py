"""Compatibility facade over state services."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

from .knowledge_graph import KnowledgeGraph
from .models import ProjectContext, SessionState
from .project import ProjectService
from .provenance import ProvenanceService
from .repository import StateRepository
from .validation import GraphValidationService

if TYPE_CHECKING:
    from ..models.upload import ProvenanceMetadata


class StateManager:
    """Facade over persistent state, project lifecycle, and graph services.

    The constructor accepts already-loaded state and performs no disk I/O. Use
    :meth:`from_path` when state should be loaded from persistent storage.
    """

    # Bound each project history to recent context while keeping state files small.
    MAX_VISITS = 1000

    def __init__(
        self, state: SessionState | None = None, storage_dir: Path | str | None = None
    ) -> None:
        self._repository = StateRepository(storage_dir)
        self.storage_dir = self._repository.storage_dir
        self.state_file = self._repository.state_file
        self._state: SessionState = (
            state if state is not None else SessionState(active_context_id=None, contexts={})
        )
        self._wire_services()

    @classmethod
    def from_path(cls, storage_dir: Path | str | None = None) -> Self:
        """Create a manager by loading state from disk."""
        repository = StateRepository(storage_dir)
        return cls(state=repository.load(), storage_dir=repository.storage_dir)

    def _wire_services(self) -> None:
        self._project_service = ProjectService(self._state, self._save_state)
        self._graph_validation = GraphValidationService(
            self._state,
            self._save_state,
            self.get_active_context,
        )
        self._provenance_service = ProvenanceService(
            self.get_active_context,
            self._save_state,
        )
        self._knowledge_graph = KnowledgeGraph(
            self.get_active_context,
            self._save_state,
            self.MAX_VISITS,
        )

    def _load_state(self) -> SessionState:
        return self._repository.load()

    def _save_state(self) -> None:
        self._repository.save(self._state)

    def _migrate_state_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        return self._repository.migrate_state_dict(data)

    def _migrate_graph_data(
        self, graph_data: dict[str, Any], default_ts: float | None = None
    ) -> dict[str, Any]:
        return self._repository.migrate_graph_data(graph_data, default_ts)

    async def _prune_context_graph(
        self, context: ProjectContext, check_page_exists: Any, max_checks: int
    ) -> dict[str, int]:
        return await self._graph_validation._prune_context_graph(
            context,
            check_page_exists,
            max_checks,
        )

    async def validate_graph(
        self, check_page_exists: Any, max_checks: int = 10, include_all_contexts: bool = False
    ) -> dict[str, int]:
        return await self._graph_validation.validate_graph(
            check_page_exists,
            max_checks=max_checks,
            include_all_contexts=include_all_contexts,
        )

    @staticmethod
    def _coerce_timestamp(value: Any) -> float | None:
        return ProvenanceService._coerce_timestamp(value)

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
        self._provenance_service.record_upload_provenance(
            uid=uid,
            notebook_id=notebook_id,
            page_title=page_title,
            file_path=file_path,
            page_tree_id=page_tree_id,
            entry_id=entry_id,
            page_url=page_url,
            created_at=created_at,
            file_size_bytes=file_size_bytes,
            filename=filename,
            metadata=metadata,
            server_version=server_version,
            as_page_text=as_page_text,
        )

    def create_project(
        self, name: str, description: str, linked_notebook_ids: list[str] | None = None
    ) -> ProjectContext:
        return self._project_service.create_project(name, description, linked_notebook_ids)

    def delete_project(self, project_id: str) -> bool:
        return self._project_service.delete_project(project_id)

    def switch_project(self, project_id: str) -> ProjectContext:
        return self._project_service.switch_project(project_id)

    def get_active_context(self) -> ProjectContext | None:
        return self._project_service.get_active_context()

    def list_projects(self) -> list[dict[str, Any]]:
        return self._project_service.list_projects()

    def _ensure_default_context(self) -> ProjectContext:
        return self._project_service._ensure_default_context()

    def log_visit(self, notebook_id: str, page_id: str, title: str) -> None:
        self._knowledge_graph.log_visit(notebook_id, page_id, title)

    def log_page_content_links(
        self,
        source_notebook_id: str,
        source_page_id: str,
        links: list[tuple[str, str]],
    ) -> int:
        return self._knowledge_graph.log_page_content_links(
            source_notebook_id,
            source_page_id,
            links,
        )

    def log_finding(
        self, content: str, source_url: str | None = None, page_id: str | None = None
    ) -> None:
        self._knowledge_graph.log_finding(content, source_url=source_url, page_id=page_id)
