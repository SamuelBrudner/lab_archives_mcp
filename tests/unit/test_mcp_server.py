from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import networkx as nx
import pytest

from labarchives_mcp.linked_data import export_project_jsonld
from labarchives_mcp.models.upload import ProvenanceMetadata
from labarchives_mcp import mcp_server
from labarchives_mcp.state import StateManager


class DummyCredentials:
    akid = "AKID"
    password = "secret"
    region = "https://example.com"


class DummyAsyncClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.kwargs = kwargs

    async def __aenter__(self) -> DummyAsyncClient:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


class DummyFastMCP:
    def __init__(self, *, server_id: str, name: str, version: str, description: str) -> None:
        self._metadata: dict[str, str] = {
            "server_id": server_id,
            "name": name,
            "version": version,
            "description": description,
        }
        self.resource_callbacks: dict[str, Callable[..., Any]] = {}
        self.tool_callbacks: dict[str, Callable[..., Any]] = {}

    def resource(self, uri: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.resource_callbacks[uri] = func
            return func

        return decorator

    def tool(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.tool_callbacks[func.__name__] = func
            return func

        return decorator

    async def serve(self) -> None:
        return None

    async def run_async(self) -> None:
        await self.serve()


def _run_server_with_test_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    entries_by_page: dict[tuple[str, str], list[dict[str, Any]]] | None = None,
) -> tuple[DummyFastMCP, StateManager]:
    mcp_module = cast(Any, mcp_server)
    state_manager = StateManager(storage_dir=tmp_path)
    page_entries = entries_by_page or {}

    monkeypatch.setattr(
        mcp_module.Credentials,
        "from_file",
        classmethod(lambda cls: DummyCredentials()),
    )
    monkeypatch.setattr(mcp_module.httpx, "AsyncClient", DummyAsyncClient)
    monkeypatch.setattr(mcp_module, "StateManager", lambda: state_manager)

    class DummyAuthenticationManager:
        def __init__(self, client: DummyAsyncClient, credentials: DummyCredentials) -> None:
            self._client = client
            self._credentials = credentials

        async def ensure_uid(self) -> str:
            return "uid-1"

    class DummyLabArchivesClient:
        def __init__(self, client: DummyAsyncClient, auth_manager: Any) -> None:
            self._client = client
            self._auth_manager = auth_manager

        async def list_notebooks(self, _uid: str) -> list[Any]:
            return []

        async def get_page_entries(
            self,
            _uid: str,
            notebook_id: str,
            page_id: str,
            include_data: bool = False,
        ) -> list[dict[str, Any]]:
            return page_entries.get((notebook_id, page_id), [])

    monkeypatch.setattr(mcp_module, "AuthenticationManager", DummyAuthenticationManager)
    monkeypatch.setattr(mcp_module, "LabArchivesClient", DummyLabArchivesClient)

    fastmcp_instance = DummyFastMCP(
        server_id="labarchives-mcp-pol",
        name="",
        version="",
        description="",
    )
    monkeypatch.setattr(mcp_module, "FastMCP", lambda **kwargs: fastmcp_instance)

    asyncio.run(mcp_server.run_server())
    return fastmcp_instance, state_manager


def test_notebooks_handler_propagates_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given a failing LabArchives client, when the notebooks resource
    executes, then the original error propagates to the caller."""

    mcp_module = cast(Any, mcp_server)
    monkeypatch.setattr(
        mcp_module.Credentials,
        "from_file",
        classmethod(lambda cls: DummyCredentials()),
    )
    monkeypatch.setattr(mcp_module.httpx, "AsyncClient", DummyAsyncClient)

    class ExplodingClient:
        async def list_notebooks(self, _uid: str) -> list[Any]:
            raise RuntimeError("boom")

    class DummyAuthenticationManager:
        def __init__(self, client: DummyAsyncClient, credentials: DummyCredentials) -> None:
            self._client = client
            self._credentials = credentials

        async def ensure_uid(self) -> str:
            return "uid-1"

    monkeypatch.setattr(mcp_module, "AuthenticationManager", DummyAuthenticationManager)
    monkeypatch.setattr(
        mcp_module, "LabArchivesClient", lambda client, auth_manager: ExplodingClient()
    )

    fastmcp_instance = DummyFastMCP(
        server_id="labarchives-mcp-pol",
        name="",
        version="",
        description="",
    )
    monkeypatch.setattr(mcp_module, "FastMCP", lambda **kwargs: fastmcp_instance)

    asyncio.run(mcp_server.run_server())

    handler = fastmcp_instance.resource_callbacks.get("labarchives://notebooks")
    assert handler is not None, "Resource should be registered"

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(handler())


def test_run_server_uses_region_as_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given configured credentials, when `run_server()` builds the HTTP
    client, then the client's base URL matches the credential region."""

    mcp_module = cast(Any, mcp_server)
    created_clients: list[DummyAsyncClient] = []

    monkeypatch.setattr(
        mcp_module.Credentials,
        "from_file",
        classmethod(lambda cls: DummyCredentials()),
    )

    def record_client(*args: Any, **kwargs: Any) -> DummyAsyncClient:
        client = DummyAsyncClient(*args, **kwargs)
        created_clients.append(client)
        return client

    monkeypatch.setattr(mcp_module.httpx, "AsyncClient", record_client)

    class DummyAuthenticationManager:
        def __init__(self, client: DummyAsyncClient, credentials: DummyCredentials) -> None:
            self._client = client
            self._credentials = credentials

        async def ensure_uid(self) -> str:
            return "uid-1"

    class DummyLabArchivesClient:
        def __init__(self, client: DummyAsyncClient, auth_manager: Any) -> None:
            self._client = client
            self._auth_manager = auth_manager

        async def list_notebooks(self, _uid: str) -> list[Any]:
            return []

    monkeypatch.setattr(mcp_module, "AuthenticationManager", DummyAuthenticationManager)
    monkeypatch.setattr(mcp_module, "LabArchivesClient", DummyLabArchivesClient)

    fastmcp_instance = DummyFastMCP(
        server_id="labarchives-mcp-pol",
        name="",
        version="",
        description="",
    )
    monkeypatch.setattr(mcp_module, "FastMCP", lambda **kwargs: fastmcp_instance)

    asyncio.run(mcp_server.run_server())

    assert created_clients, "AsyncClient should be constructed"
    client = created_clients[0]
    assert client.kwargs.get("base_url") == DummyCredentials.region


def test_upload_tool_not_registered_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given LABARCHIVES_ENABLE_UPLOAD=false, when the server initializes,
    then the upload_to_labarchives tool should not be registered."""

    mcp_module = cast(Any, mcp_server)
    monkeypatch.setenv("LABARCHIVES_ENABLE_UPLOAD", "false")
    monkeypatch.setattr(
        mcp_module.Credentials,
        "from_file",
        classmethod(lambda cls: DummyCredentials()),
    )
    monkeypatch.setattr(mcp_module.httpx, "AsyncClient", DummyAsyncClient)

    class DummyAuthenticationManager:
        def __init__(self, client: DummyAsyncClient, credentials: DummyCredentials) -> None:
            self._client = client
            self._credentials = credentials

        async def ensure_uid(self) -> str:
            return "uid-1"

    class DummyLabArchivesClient:
        def __init__(self, client: DummyAsyncClient, auth_manager: Any) -> None:
            self._client = client
            self._auth_manager = auth_manager

        async def list_notebooks(self, _uid: str) -> list[Any]:
            return []

    monkeypatch.setattr(mcp_module, "AuthenticationManager", DummyAuthenticationManager)
    monkeypatch.setattr(mcp_module, "LabArchivesClient", DummyLabArchivesClient)

    fastmcp_instance = DummyFastMCP(
        server_id="labarchives-mcp-pol",
        name="",
        version="",
        description="",
    )
    monkeypatch.setattr(mcp_module, "FastMCP", lambda **kwargs: fastmcp_instance)

    asyncio.run(mcp_server.run_server())

    assert (
        "upload_to_labarchives" not in fastmcp_instance.tool_callbacks
    ), "upload_to_labarchives should not be registered when LABARCHIVES_ENABLE_UPLOAD=false"


def test_upload_tool_registered_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given LABARCHIVES_ENABLE_UPLOAD=true, when the server initializes,
    then the upload_to_labarchives tool should be registered."""

    mcp_module = cast(Any, mcp_server)
    monkeypatch.setenv("LABARCHIVES_ENABLE_UPLOAD", "true")
    monkeypatch.setattr(
        mcp_module.Credentials,
        "from_file",
        classmethod(lambda cls: DummyCredentials()),
    )
    monkeypatch.setattr(mcp_module.httpx, "AsyncClient", DummyAsyncClient)

    class DummyAuthenticationManager:
        def __init__(self, client: DummyAsyncClient, credentials: DummyCredentials) -> None:
            self._client = client
            self._credentials = credentials

        async def ensure_uid(self) -> str:
            return "uid-1"

    class DummyLabArchivesClient:
        def __init__(self, client: DummyAsyncClient, auth_manager: Any) -> None:
            self._client = client
            self._auth_manager = auth_manager

        async def list_notebooks(self, _uid: str) -> list[Any]:
            return []

    monkeypatch.setattr(mcp_module, "AuthenticationManager", DummyAuthenticationManager)
    monkeypatch.setattr(mcp_module, "LabArchivesClient", DummyLabArchivesClient)

    fastmcp_instance = DummyFastMCP(
        server_id="labarchives-mcp-pol",
        name="",
        version="",
        description="",
    )
    monkeypatch.setattr(mcp_module, "FastMCP", lambda **kwargs: fastmcp_instance)

    asyncio.run(mcp_server.run_server())

    assert (
        "upload_to_labarchives" in fastmcp_instance.tool_callbacks
    ), "upload_to_labarchives should be registered when LABARCHIVES_ENABLE_UPLOAD=true"


def test_upload_tool_registered_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given no LABARCHIVES_ENABLE_UPLOAD env var, when the server initializes,
    then the upload_to_labarchives tool should be registered (enabled by default)."""

    mcp_module = cast(Any, mcp_server)
    # Ensure env var is not set
    monkeypatch.delenv("LABARCHIVES_ENABLE_UPLOAD", raising=False)
    monkeypatch.setattr(
        mcp_module.Credentials,
        "from_file",
        classmethod(lambda cls: DummyCredentials()),
    )
    monkeypatch.setattr(mcp_module.httpx, "AsyncClient", DummyAsyncClient)

    class DummyAuthenticationManager:
        def __init__(self, client: DummyAsyncClient, credentials: DummyCredentials) -> None:
            self._client = client
            self._credentials = credentials

        async def ensure_uid(self) -> str:
            return "uid-1"

    class DummyLabArchivesClient:
        def __init__(self, client: DummyAsyncClient, auth_manager: Any) -> None:
            self._client = client
            self._auth_manager = auth_manager

        async def list_notebooks(self, _uid: str) -> list[Any]:
            return []

    monkeypatch.setattr(mcp_module, "AuthenticationManager", DummyAuthenticationManager)
    monkeypatch.setattr(mcp_module, "LabArchivesClient", DummyLabArchivesClient)

    fastmcp_instance = DummyFastMCP(
        server_id="labarchives-mcp-pol",
        name="",
        version="",
        description="",
    )
    monkeypatch.setattr(mcp_module, "FastMCP", lambda **kwargs: fastmcp_instance)

    asyncio.run(mcp_server.run_server())

    assert (
        "upload_to_labarchives" in fastmcp_instance.tool_callbacks
    ), "upload_to_labarchives should be registered by default when env var is not set"


def test_export_tool_registered_and_matches_state_wrapper(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The JSON-LD export tool should be registered and match the state wrapper output."""

    mcp_module = cast(Any, mcp_server)
    monkeypatch.delenv("LABARCHIVES_ENABLE_UPLOAD", raising=False)
    monkeypatch.setattr(
        mcp_module.Credentials,
        "from_file",
        classmethod(lambda cls: DummyCredentials()),
    )
    monkeypatch.setattr(mcp_module.httpx, "AsyncClient", DummyAsyncClient)

    class DummyAuthenticationManager:
        def __init__(self, client: DummyAsyncClient, credentials: DummyCredentials) -> None:
            self._client = client
            self._credentials = credentials

        async def ensure_uid(self) -> str:
            return "uid123"

    class DummyLabArchivesClient:
        def __init__(self, client: DummyAsyncClient, auth_manager: Any) -> None:
            self._client = client
            self._auth_manager = auth_manager

        async def list_notebooks(self, _uid: str) -> list[Any]:
            return []

    state_manager = StateManager(storage_dir=tmp_path)
    context = state_manager.create_project("Proj 1", "Desc")
    metadata = ProvenanceMetadata(
        git_commit_sha="f" * 40,
        git_branch="main",
        git_repo_url="https://github.com/SamuelBrudner/lab_archives_mcp",
        git_is_dirty=False,
        code_version="0.4.0",
        executed_at=datetime(2026, 4, 20, 14, 1, 58, tzinfo=UTC),
        python_version="3.11.8",
        dependencies={"networkx": "3.4"},
        os_name="Darwin",
        hostname="host.local",
    )
    state_manager.record_upload_provenance(
        uid="uid123",
        notebook_id="nb1",
        page_title="Analysis Results",
        file_path=tmp_path / "analysis.ipynb",
        page_tree_id="page-123",
        entry_id="ATTACH_123",
        page_url="https://example.org/page-123",
        created_at="2026-04-20T14:02:11Z",
        file_size_bytes=1234,
        filename="analysis.ipynb",
        metadata=metadata,
        server_version="0.4.0",
        as_page_text=False,
    )

    monkeypatch.setattr(mcp_module, "AuthenticationManager", DummyAuthenticationManager)
    monkeypatch.setattr(mcp_module, "LabArchivesClient", DummyLabArchivesClient)
    monkeypatch.setattr(mcp_module, "StateManager", lambda: state_manager)

    fastmcp_instance = DummyFastMCP(
        server_id="labarchives-mcp-pol",
        name="",
        version="",
        description="",
    )
    monkeypatch.setattr(mcp_module, "FastMCP", lambda **kwargs: fastmcp_instance)

    asyncio.run(mcp_server.run_server())

    assert "export_provenance_jsonld" in fastmcp_instance.tool_callbacks
    tool = fastmcp_instance.tool_callbacks["export_provenance_jsonld"]
    result = asyncio.run(tool(context.id))

    assert result == export_project_jsonld(context.id, state_dir=tmp_path)


def test_get_related_pages_returns_actionable_cross_notebook_links(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Content links should preserve notebook identity in related-page results."""
    fastmcp_instance, state_manager = _run_server_with_test_state(
        monkeypatch,
        tmp_path,
        entries_by_page={
            ("nb1", "page-a"): [
                {
                    "eid": "entry-1",
                    "content": "See https://labarchives.com/share/nb2/page-c for details.",
                }
            ]
        },
    )
    state_manager.create_project("Proj", "Desc")
    state_manager.log_visit("nb1", "page-a", "Page A")

    tool = fastmcp_instance.tool_callbacks["get_related_pages"]
    result = asyncio.run(tool("nb1", "page-a"))

    assert result["items"] == [
        {
            "notebook_id": "nb2",
            "page_id": "page-c",
            "title": "Linked Page",
            "source": "content_link",
        }
    ]

    context = state_manager.get_active_context()
    assert context is not None
    graph = nx.node_link_graph(context.graph_data, edges="links")
    assert graph.has_edge("page:nb1:page-a", "page:nb2:page-c")
    assert graph.edges["page:nb1:page-a", "page:nb2:page-c"]["relation"] == "content_link"


def test_get_related_pages_keeps_same_page_id_from_multiple_notebooks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Distinct notebook targets with the same page_id should both survive dedupe."""
    fastmcp_instance, state_manager = _run_server_with_test_state(
        monkeypatch,
        tmp_path,
        entries_by_page={
            ("nb1", "page-a"): [
                {
                    "eid": "entry-1",
                    "content": (
                        "A https://labarchives.com/share/nb2/shared "
                        "B https://labarchives.com/share/nb3/shared"
                    ),
                }
            ]
        },
    )
    state_manager.create_project("Proj", "Desc")
    state_manager.log_visit("nb1", "page-a", "Page A")

    tool = fastmcp_instance.tool_callbacks["get_related_pages"]
    result = asyncio.run(tool("nb1", "page-a"))

    assert result["items"] == [
        {
            "notebook_id": "nb2",
            "page_id": "shared",
            "title": "Linked Page",
            "source": "content_link",
        },
        {
            "notebook_id": "nb3",
            "page_id": "shared",
            "title": "Linked Page",
            "source": "content_link",
        },
    ]


def test_log_finding_tool_reports_ambiguous_page_ids(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ambiguous bare page references should return a structured tool error."""
    fastmcp_instance, state_manager = _run_server_with_test_state(monkeypatch, tmp_path)
    state_manager.create_project("Proj", "Desc")
    state_manager.log_visit("nb1", "shared", "Shared A")
    state_manager.log_visit("nb2", "shared", "Shared B")

    tool = fastmcp_instance.tool_callbacks["log_finding"]
    result = asyncio.run(tool("A key fact", page_id="shared"))

    assert result == {
        "status": "error",
        "code": "ambiguous_page_reference",
        "message": "Page 'shared' matches multiple notebooks; provide notebook_id.",
        "page_id": "shared",
        "notebook_id": None,
    }


def test_log_finding_tool_links_page_with_notebook_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Explicit notebook_id should make provenance links actionable."""
    fastmcp_instance, state_manager = _run_server_with_test_state(monkeypatch, tmp_path)
    state_manager.create_project("Proj", "Desc")
    state_manager.log_visit("nb1", "page-a", "Page A")

    tool = fastmcp_instance.tool_callbacks["log_finding"]
    result = asyncio.run(tool("A key fact", page_id="page-a", notebook_id="nb1"))

    assert result["status"] == "ok"
    context = state_manager.get_active_context()
    assert context is not None
    graph = nx.node_link_graph(context.graph_data, edges="links")
    finding_nodes = [n for n, d in graph.nodes(data=True) if d.get("type") == "finding"]
    assert finding_nodes
    assert graph.has_edge("page:nb1:page-a", finding_nodes[0])
