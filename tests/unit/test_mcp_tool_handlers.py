from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from labarchives_mcp.state import StateManager
from labarchives_mcp.tools import ToolContext
from labarchives_mcp.tools.discovery import list_labarchives_notebooks
from labarchives_mcp.tools.project import create_project, list_projects


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
