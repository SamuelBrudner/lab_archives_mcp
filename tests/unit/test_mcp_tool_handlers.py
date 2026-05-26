from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from labarchives_mcp.state import StateManager
from labarchives_mcp.tools import ToolContext
from labarchives_mcp.tools.discovery import list_labarchives_notebooks, read_notebook_page
from labarchives_mcp.tools.project import create_project, list_projects
from labarchives_mcp.tools.provenance import suggest_next_steps, trace_provenance


class _DummyNotebook:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def model_dump(self, *, by_alias: bool = False) -> dict[str, Any]:  # noqa: ARG002
        return self._data


class _DummyAuthManager:
    async def ensure_uid(self) -> str:
        return "uid-1"


class _DummyNotebookClient:
    async def list_notebooks(self, uid: str) -> list[_DummyNotebook]:
        assert uid == "uid-1"
        return [_DummyNotebook({"nbid": "nb1", "name": "Notebook 1"})]

    async def get_page_entries(
        self, uid: str, notebook_id: str, page_id: str, include_data: bool = True
    ) -> list[dict[str, Any]]:  # noqa: ARG002
        assert uid == "uid-1"
        return [{"eid": "entry-1", "part_type": "text_entry", "content": "<p>Body</p>"}]


@pytest.fixture()  # type: ignore[misc]
def tool_context(tmp_path: Path) -> ToolContext:
    return ToolContext(
        credentials=SimpleNamespace(region="https://example.com"),
        auth_manager=_DummyAuthManager(),
        notebook_client=_DummyNotebookClient(),
        state_manager=StateManager.from_path(storage_dir=tmp_path),
        server_version="0.4.0",
        service_module=SimpleNamespace(),
    )


def test_discovery_handler_is_directly_importable(tool_context: ToolContext) -> None:
    notebooks = asyncio.run(list_labarchives_notebooks(tool_context))

    assert notebooks == [{"nbid": "nb1", "name": "Notebook 1"}]


def test_project_handlers_are_directly_importable(tool_context: ToolContext) -> None:
    created = asyncio.run(create_project(tool_context, "Project", "Desc"))
    projects = asyncio.run(list_projects(tool_context))

    assert created["status"] == "ok"
    assert projects == [
        {
            "id": created["project"]["id"],
            "name": "Project",
            "status": "active",
            "active": True,
        }
    ]


def test_read_page_propagates_tracking_failure(tool_context: ToolContext) -> None:
    class FailingStateManager:
        def log_visit(self, notebook_id: str, page_id: str, title: str) -> None:  # noqa: ARG002
            raise RuntimeError("state write failed")

        def get_active_context(self) -> None:
            return None

    failing_context = ToolContext(
        credentials=tool_context.credentials,
        auth_manager=tool_context.auth_manager,
        notebook_client=tool_context.notebook_client,
        state_manager=FailingStateManager(),
        server_version=tool_context.server_version,
        service_module=tool_context.service_module,
    )

    with pytest.raises(RuntimeError, match="state write failed"):
        asyncio.run(read_notebook_page(failing_context, "nb1", "p1", track_visit=True))


def test_trace_provenance_propagates_entry_fetch_failure(tool_context: ToolContext) -> None:
    class FailingNotebookClient(_DummyNotebookClient):
        async def get_page_entries(
            self, uid: str, notebook_id: str, page_id: str, include_data: bool = True
        ) -> list[dict[str, Any]]:  # noqa: ARG002
            raise RuntimeError("entry fetch failed")

    failing_context = ToolContext(
        credentials=tool_context.credentials,
        auth_manager=tool_context.auth_manager,
        notebook_client=FailingNotebookClient(),
        state_manager=tool_context.state_manager,
        server_version=tool_context.server_version,
        service_module=tool_context.service_module,
    )

    with pytest.raises(RuntimeError, match="entry fetch failed"):
        asyncio.run(trace_provenance(failing_context, "nb1", "p1", "entry-1"))


def test_suggest_next_steps_propagates_graph_failure(
    tool_context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tool_context.state_manager.create_project("Project", "Desc")
    project.graph_data = {"not": "node-link-data"}
    monkeypatch.setattr(
        "labarchives_mcp.tools.provenance.nx.node_link_graph",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad graph")),
    )

    with pytest.raises(ValueError, match="bad graph"):
        asyncio.run(suggest_next_steps(tool_context))
