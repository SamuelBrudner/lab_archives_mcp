"""Shared dependencies for MCP tool handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..auth import AuthenticationManager, Credentials
from ..eln_client import LabArchivesClient
from ..state import StateManager
from .vector_runtime import VectorRuntime

if TYPE_CHECKING:
    from ..settings import Settings


@dataclass(slots=True)
class ToolContext:
    """Runtime dependencies passed into importable MCP handlers."""

    credentials: Credentials
    auth_manager: AuthenticationManager
    notebook_client: LabArchivesClient
    state_manager: StateManager
    server_version: str
    settings: Settings | None = None
    vector_runtime: VectorRuntime | None = None

    def get_vector_runtime(self) -> VectorRuntime:
        """Return the lazy vector runtime, requiring startup settings."""
        if self.vector_runtime is None:
            if self.settings is None:
                raise RuntimeError("ToolContext.settings is required for vector search tools.")
            self.vector_runtime = VectorRuntime(self.settings)
        return self.vector_runtime
