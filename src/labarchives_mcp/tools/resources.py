"""Notebook resource handlers."""

from __future__ import annotations

from typing import Any, cast

from ..eln_client import NotebookRecord
from ..schemas.tool_responses import NotebookResponse, NotebooksResourceResponse
from ..transform import LabArchivesAPIError, translate_labarchives_fault
from .context import ToolContext
from .decorators import resource


def _notebook_response(notebook: NotebookRecord) -> NotebookResponse:
    return cast(NotebookResponse, notebook.model_dump(by_alias=True))


async def list_notebooks_resource(context: ToolContext) -> NotebooksResourceResponse:
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
        "list": [_notebook_response(notebook) for notebook in notebooks],
    }


def register_resources(server: Any, context: ToolContext) -> None:
    """Register MCP resources."""
    @resource(server, "labarchives://notebooks")
    async def list_notebooks_resource_handler() -> NotebooksResourceResponse:
        return await list_notebooks_resource(context)
