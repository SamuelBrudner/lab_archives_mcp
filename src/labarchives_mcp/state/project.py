"""Project lifecycle and active-context selection."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from loguru import logger

from .models import ProjectContext, SessionState


class ProjectService:
    """Handles project lifecycle and active-context selection."""

    def __init__(self, state: SessionState, save_state: Callable[[], None]) -> None:
        self._state = state
        self._save_state_callback = save_state

    def _save_state(self) -> None:
        self._save_state_callback()

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
