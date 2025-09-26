from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, cast

import pytest

from labarchives_mcp import mcp_server


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

    def resource(self, uri: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.resource_callbacks[uri] = func
            return func

        return decorator

    async def serve(self) -> None:
        return None


def test_notebooks_handler_propagates_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """The resource handler should surface underlying client failures."""

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
    monkeypatch.setattr(mcp_module, "LabArchivesClient", lambda client: ExplodingClient())

    fastmcp_instance = DummyFastMCP(
        server_id="labarchives-mcp-pol",
        name="",
        version="",
        description="",
    )
    monkeypatch.setattr(mcp_module, "FastMCP", lambda **kwargs: fastmcp_instance)

    asyncio.run(mcp_server.run_server())

    handler = fastmcp_instance.resource_callbacks.get("labarchives:notebooks")
    assert handler is not None, "Resource should be registered"

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(handler())


def test_run_server_uses_region_as_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """`httpx.AsyncClient` should be initialised against the region endpoint."""

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
        def __init__(self, client: DummyAsyncClient) -> None:
            self._client = client

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
