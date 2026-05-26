"""Register all LabArchives MCP resources and tools."""

from __future__ import annotations

from typing import Any

from .context import ToolContext
from .discovery import register_discovery_tools
from .onboarding import register_onboarding_tools
from .project import register_project_tools
from .provenance import register_provenance_tools
from .resources import register_resources
from .search import register_search_tools
from .write import register_write_tools


def register_mcp_surface(server: Any, context: ToolContext, *, upload_enabled: bool) -> None:
    """Register every MCP resource and tool for the LabArchives server."""
    register_resources(server, context)
    register_discovery_tools(server, context)
    register_search_tools(server, context)
    register_write_tools(server, context, upload_enabled=upload_enabled)
    register_project_tools(server, context)
    register_provenance_tools(server, context)
    register_onboarding_tools(server, context)
