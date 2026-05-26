from __future__ import annotations

from collections.abc import Callable
from inspect import get_annotations

from labarchives_mcp.tools.discovery import (
    list_labarchives_notebooks,
    list_notebook_pages,
    read_notebook_page,
)
from labarchives_mcp.tools.onboarding import get_onboard_payload
from labarchives_mcp.tools.project import (
    create_project,
    delete_project,
    export_provenance_jsonld,
    get_current_context,
    list_projects,
    log_finding,
    switch_project,
)
from labarchives_mcp.tools.provenance import (
    get_related_pages,
    suggest_next_steps,
    trace_provenance,
)
from labarchives_mcp.tools.resources import list_notebooks_resource
from labarchives_mcp.tools.search import search_labarchives, sync_vector_index
from labarchives_mcp.tools.write import upload_to_labarchives, write_notebook_entry

HANDLERS: tuple[Callable[..., object], ...] = (
    list_labarchives_notebooks,
    list_notebook_pages,
    read_notebook_page,
    get_onboard_payload,
    create_project,
    delete_project,
    switch_project,
    list_projects,
    log_finding,
    get_current_context,
    export_provenance_jsonld,
    get_related_pages,
    trace_provenance,
    suggest_next_steps,
    list_notebooks_resource,
    search_labarchives,
    sync_vector_index,
    upload_to_labarchives,
    write_notebook_entry,
)


def test_public_tool_handlers_do_not_return_generic_any_dicts() -> None:
    for handler in HANDLERS:
        return_type = str(get_annotations(handler, eval_str=False)["return"])
        assert "dict[str, Any]" not in return_type, handler.__name__
        assert "list[dict[str, Any]]" not in return_type, handler.__name__
