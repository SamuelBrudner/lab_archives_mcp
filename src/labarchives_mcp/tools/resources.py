"""Notebook resource handlers."""

from __future__ import annotations

from typing import Any

from ..transform import LabArchivesAPIError, translate_labarchives_fault
from .context import ToolContext
from .decorators import resource


async def list_notebooks_resource(context: ToolContext) -> dict[str, Any]:
    """Return the LabArchives notebooks resource payload."""
    uid = await context.auth_manager.ensure_uid()
    try:
        notebooks = await context.notebook_client.list_notebooks(uid)
    except LabArchivesAPIError as error:
        translated = translate_labarchives_fault(error)
        return {
            "resource": "labarchives://notebooks",
            "error": translated,
        }

    return {
        "resource": "labarchives://notebooks",
        "list": [notebook.model_dump(by_alias=True) for notebook in notebooks],
    }


def register_resources(server: Any, context: ToolContext) -> None:
    """Register MCP resources."""
    @resource(server, "labarchives://notebooks")
    async def list_notebooks_resource_handler() -> dict[str, Any]:
        return await list_notebooks_resource(context)
