"""Project and state-management MCP tools."""

from __future__ import annotations

from typing import Any, cast

from ..schemas.tool_responses import (
    CreateProjectResponse,
    CurrentContextResponse,
    DeleteProjectResponse,
    LogFindingResponse,
    ProjectContextResponse,
    ProjectSummaryResponse,
    ProvenanceJsonLdResponse,
    SwitchProjectResponse,
)
from ..state import ProjectContext
from .context import ToolContext
from .decorators import tool


def _project_context_response(context: ProjectContext) -> ProjectContextResponse:
    return cast(ProjectContextResponse, context.model_dump())


async def create_project(
    context: ToolContext,
    name: str,
    description: str,
    linked_notebook_ids: list[str] | None = None,
    dry_run: bool = False,
) -> CreateProjectResponse:
    """Start a new project context."""
    if dry_run:
        return {
            "status": "dry_run",
            "project": {
                "name": name,
                "description": description,
                "linked_notebook_ids": linked_notebook_ids or [],
            },
        }

    project_context = context.state_manager.create_project(name, description, linked_notebook_ids)
    return {"status": "ok", "project": _project_context_response(project_context)}


async def delete_project(
    context: ToolContext, project_id: str, dry_run: bool = False
) -> DeleteProjectResponse:
    """Delete a project context and its history."""
    exists = project_id in context.state_manager._state.contexts
    if not exists:
        return {"status": "error", "code": "project_not_found", "project_id": project_id}

    if dry_run:
        return {"status": "dry_run", "project_id": project_id}

    success = context.state_manager.delete_project(project_id)
    if success:
        return {"status": "ok", "project_id": project_id}
    return {"status": "error", "code": "delete_failed", "project_id": project_id}


async def switch_project(
    context: ToolContext, project_id: str, dry_run: bool = False
) -> SwitchProjectResponse:
    """Switch the active context to an existing project."""
    if project_id not in context.state_manager._state.contexts:
        return {"status": "error", "code": "project_not_found", "project_id": project_id}

    if dry_run:
        project_context = context.state_manager._state.contexts[project_id]
        return {"status": "dry_run", "project": _project_context_response(project_context)}

    try:
        project_context = context.state_manager.switch_project(project_id)
        return {"status": "ok", "project": _project_context_response(project_context)}
    except ValueError as e:
        return {"status": "error", "code": "switch_failed", "message": str(e)}


async def list_projects(context: ToolContext) -> list[ProjectSummaryResponse]:
    """List all projects and their status."""
    return [
        {
            "id": str(project["id"]),
            "name": str(project["name"]),
            "status": str(project["status"]),
            "active": bool(project["active"]),
        }
        for project in context.state_manager.list_projects()
    ]


async def log_finding(
    context: ToolContext,
    content: str,
    source_url: str | None = None,
    page_id: str | None = None,
    dry_run: bool = False,
) -> LogFindingResponse:
    """Record a key fact or finding in the current project context."""
    try:
        if dry_run:
            return {
                "status": "dry_run",
                "content": content[:50] + "..." if len(content) > 50 else content,
                "page_id": page_id,
            }

        context.state_manager.log_finding(content, source_url=source_url, page_id=page_id)
        active_context = context.state_manager.get_active_context()
        return {
            "status": "ok",
            "content": content[:50] + "..." if len(content) > 50 else content,
            "project": active_context.name if active_context else "Unknown",
            "project_id": active_context.id if active_context else None,
        }
    except RuntimeError as e:
        return {"status": "error", "code": "no_active_context", "message": str(e)}


async def get_current_context(context: ToolContext) -> CurrentContextResponse:
    """Retrieve the full state of the active project."""
    active_context = context.state_manager.get_active_context()
    if not active_context:
        return {
            "status": "no_active_context",
            "message": "No project is currently active.",
        }
    return _project_context_response(active_context)


async def export_provenance_jsonld(
    context: ToolContext, project_id: str
) -> ProvenanceJsonLdResponse:
    """Serialize one project context as JSON-LD aligned to PROV-O + schema.org."""
    from labarchives_mcp.linked_data import export_project_context

    project_context = context.state_manager._state.contexts.get(project_id)
    if project_context is None:
        raise ValueError(f"Unknown project_id: {project_id}")
    return cast(ProvenanceJsonLdResponse, export_project_context(project_context))


_create_project = create_project
_delete_project = delete_project
_switch_project = switch_project
_list_projects = list_projects
_log_finding = log_finding
_get_current_context = get_current_context
_export_provenance_jsonld = export_provenance_jsonld


def register_project_tools(server: Any, context: ToolContext) -> None:
    """Register project and state-management tools."""

    @tool(server)
    async def create_project(
        name: str,
        description: str,
        linked_notebook_ids: list[str] | None = None,
        dry_run: bool = False,
    ) -> CreateProjectResponse:
        """Start a new project context."""
        return await _create_project(
            context,
            name,
            description,
            linked_notebook_ids=linked_notebook_ids,
            dry_run=dry_run,
        )

    @tool(server)
    async def delete_project(project_id: str, dry_run: bool = False) -> DeleteProjectResponse:
        """Delete a project context and its history."""
        return await _delete_project(context, project_id, dry_run=dry_run)

    @tool(server)
    async def switch_project(project_id: str, dry_run: bool = False) -> SwitchProjectResponse:
        """Switch the active context to an existing project."""
        return await _switch_project(context, project_id, dry_run=dry_run)

    @tool(server)
    async def list_projects() -> list[ProjectSummaryResponse]:
        """List all projects and their status."""
        return await _list_projects(context)

    @tool(server)
    async def log_finding(
        content: str,
        source_url: str | None = None,
        page_id: str | None = None,
        dry_run: bool = False,
    ) -> LogFindingResponse:
        """Record a key fact or finding in the current project context."""
        return await _log_finding(
            context,
            content,
            source_url=source_url,
            page_id=page_id,
            dry_run=dry_run,
        )

    @tool(server)
    async def get_current_context() -> CurrentContextResponse:
        """Retrieve the full state of the active project (findings, history)."""
        return await _get_current_context(context)

    @tool(server)
    async def export_provenance_jsonld(project_id: str) -> ProvenanceJsonLdResponse:
        """Serialize one project context as JSON-LD aligned to PROV-O + schema.org."""
        return await _export_provenance_jsonld(context, project_id)
