from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, cast

import pytest

from labarchives_mcp import mcp_server
from labarchives_mcp.transform import LabArchivesAPIError


def test_run_server_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """`run_server` should wire FastMCP with auth + notebook handlers."""

    mcp_module = cast(Any, mcp_server)
    captured: dict[str, Any] = {}

    class DummyCredentials:
        akid = "AKID"
        password = "secret"
        region = "https://example.com"

    monkeypatch.setattr(
        mcp_module.Credentials,
        "from_file",
        classmethod(lambda cls: DummyCredentials()),
    )

    class DummyAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            captured["httpx_kwargs"] = kwargs

        async def __aenter__(self) -> DummyAsyncClient:
            captured["httpx_enter"] = True
            return self

        async def __aexit__(self, *exc_info: Any) -> None:
            captured["httpx_exit"] = True

    monkeypatch.setattr(mcp_module.httpx, "AsyncClient", DummyAsyncClient)

    class DummyNotebook:
        def __init__(self, data: dict[str, Any]) -> None:
            self._data = data

        def model_dump(self, *, by_alias: bool = False) -> dict[str, Any]:  # noqa: ARG002
            return self._data

    class DummyLabArchivesClient:
        def __init__(self, http_client: DummyAsyncClient, auth_manager: Any) -> None:
            captured["eln_client_init"] = http_client
            captured["eln_auth_manager"] = auth_manager

        async def list_notebooks(self, uid: str) -> list[DummyNotebook]:
            captured["list_notebooks_uid"] = uid
            return [
                DummyNotebook(
                    {
                        "nbid": "123",
                        "name": "Example",
                        "owner": "user@example.com",
                        "created_at": "2025-01-01T00:00:00Z",
                        "owner_email": "user@example.com",
                        "owner_name": "Example User",
                        "modified_at": "2025-01-05T13:45:09Z",
                    }
                )
            ]

    monkeypatch.setattr(mcp_module, "LabArchivesClient", DummyLabArchivesClient)

    class DummyAuthenticationManager:
        def __init__(self, http_client: DummyAsyncClient, credentials: DummyCredentials) -> None:
            captured["auth_init"] = {
                "client": http_client,
                "credentials": credentials,
            }
            self._uid_calls = 0

        async def ensure_uid(self) -> str:
            self._uid_calls += 1
            captured["ensure_uid_calls"] = self._uid_calls
            return "uid-456"

    monkeypatch.setattr(mcp_module, "AuthenticationManager", DummyAuthenticationManager)

    class DummyFastMCP:
        def __init__(self, *, server_id: str, name: str, version: str, description: str) -> None:
            captured["fastmcp_init"] = {
                "server_id": server_id,
                "name": name,
                "version": version,
                "description": description,
            }
            self._resource_callbacks: dict[str, Callable[..., Any]] = {}
            captured["resource_callbacks"] = self._resource_callbacks

        def resource(self, uri: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                self._resource_callbacks[uri] = func
                return func

            return decorator

        async def serve(self) -> None:
            captured["serve_invoked"] = True

    monkeypatch.setattr(mcp_module, "FastMCP", DummyFastMCP)

    asyncio.run(mcp_server.run_server())

    assert captured["fastmcp_init"] == {
        "server_id": "labarchives-mcp-pol",
        "name": "LabArchives PoL Server",
        "version": mcp_server.__version__,
        "description": "Proof-of-life MCP server exposing LabArchives notebooks.",
    }

    assert captured.get("serve_invoked"), "run_server should await FastMCP.serve()"

    notebooks_handler = captured["resource_callbacks"].get("labarchives:notebooks")
    assert notebooks_handler is not None, "Notebooks resource must be registered"

    result = asyncio.run(notebooks_handler())

    assert captured.get("ensure_uid_calls") == 1
    assert captured.get("list_notebooks_uid") == "uid-456"

    assert result == {
        "resource": "labarchives:notebooks",
        "list": [
            {
                "nbid": "123",
                "name": "Example",
                "owner": "user@example.com",
                "created_at": "2025-01-01T00:00:00Z",
                "owner_email": "user@example.com",
                "owner_name": "Example User",
                "modified_at": "2025-01-05T13:45:09Z",
            }
        ],
    }


def test_run_server_maps_labarchives_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resource handlers should expose LabArchives faults as structured MCP errors."""

    mcp_module = cast(Any, mcp_server)
    captured: dict[str, Any] = {}

    class DummyCredentials:
        akid = "AKID"
        password = "secret"
        region = "https://example.com"

    monkeypatch.setattr(
        mcp_module.Credentials,
        "from_file",
        classmethod(lambda cls: DummyCredentials()),
    )

    class DummyAsyncClient:
        async def __aenter__(self) -> DummyAsyncClient:
            return self

        async def __aexit__(self, *exc_info: Any) -> None:
            return None

    monkeypatch.setattr(mcp_module.httpx, "AsyncClient", lambda **_: DummyAsyncClient())

    class DummyLabArchivesClient:
        def __init__(self, _client: DummyAsyncClient, _auth_manager: Any) -> None:
            captured["eln_client_init"] = True

        async def list_notebooks(self, _uid: str) -> list[Any]:
            raise LabArchivesAPIError(code=4501, message="Invalid UID")

    monkeypatch.setattr(mcp_module, "LabArchivesClient", DummyLabArchivesClient)

    class DummyAuthenticationManager:
        async def ensure_uid(self) -> str:
            return "uid-789"

    monkeypatch.setattr(
        mcp_module, "AuthenticationManager", lambda *_: DummyAuthenticationManager()
    )

    class DummyFastMCP:
        def __init__(self, *, server_id: str, name: str, version: str, description: str) -> None:
            captured["fastmcp_init"] = {
                "server_id": server_id,
                "name": name,
                "version": version,
                "description": description,
            }
            self._resource_callbacks: dict[str, Callable[..., Any]] = {}
            captured["resource_callbacks"] = self._resource_callbacks

        def resource(self, uri: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                self._resource_callbacks[uri] = func
                return func

            return decorator

        async def serve(self) -> None:
            captured["serve_invoked"] = True

    monkeypatch.setattr(mcp_module, "FastMCP", DummyFastMCP)

    asyncio.run(mcp_server.run_server())

    handler = captured["resource_callbacks"]["labarchives:notebooks"]
    outcome = asyncio.run(handler())

    assert outcome == {
        "resource": "labarchives:notebooks",
        "error": {
            "code": "labarchives:4501",
            "message": "Invalid UID",
            "retryable": False,
            "domain": "labarchives",
        },
    }
