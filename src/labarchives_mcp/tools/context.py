"""Shared dependencies for MCP tool handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..state import StateManager

if TYPE_CHECKING:
    from ..settings import Settings


@dataclass(slots=True)
class ToolContext:
    """Runtime dependencies passed into importable MCP handlers."""

    credentials: Any
    auth_manager: Any
    notebook_client: Any
    state_manager: StateManager
    server_version: str
    service_module: Any
    settings: Settings | None = None
