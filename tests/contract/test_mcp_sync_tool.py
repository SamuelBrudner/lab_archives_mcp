from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from labarchives_mcp import mcp_server


def _setup_fastmcp_capture(mcp_module: Any) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    class DummyFastMCP:
        def __init__(self, *, server_id: str, name: str, version: str, description: str) -> None:
            captured["fastmcp_init"] = {
                "server_id": server_id,
                "name": name,
                "version": version,
                "description": description,
            }
            self._resource_callbacks: dict[str, Callable[..., Any]] = {}
            self._tool_callbacks: dict[str, Callable[..., Any]] = {}
            captured["resource_callbacks"] = self._resource_callbacks
            captured["tool_callbacks"] = self._tool_callbacks

        def resource(self, uri: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                self._resource_callbacks[uri] = func
                return func

            return decorator

        def tool(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                self._tool_callbacks[func.__name__] = func
                return func

            return decorator

        async def serve(self) -> None:
            captured["serve_invoked"] = True

        async def run_async(self) -> None:
            await self.serve()

    mcp_module.FastMCP = DummyFastMCP
    return captured


@pytest.fixture()  # type: ignore[misc]
def mcp_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    mcp_module = cast(Any, mcp_server)
    captured = _setup_fastmcp_capture(mcp_module)

    class DummyCredentials:
        akid = "AKID"
        password = "PW"
        region = "https://example.com"

    monkeypatch.setattr(
        mcp_module.Credentials, "from_file", classmethod(lambda cls: DummyCredentials())
    )

    class DummyAsyncClient:
        async def __aenter__(self) -> DummyAsyncClient:
            return self

        async def __aexit__(self, *exc_info: Any) -> None:  # noqa: ARG002
            return None

    monkeypatch.setattr(mcp_module.httpx, "AsyncClient", lambda **_: DummyAsyncClient())

    # Minimal ELN client to satisfy server wiring; not used in sync tests
    class DummyLabArchivesClient:
        def __init__(self, _client: Any, _auth_manager: Any) -> None:
            pass

    monkeypatch.setattr(mcp_module, "LabArchivesClient", DummyLabArchivesClient)

    class DummyAuthenticationManager:
        async def ensure_uid(self) -> str:
            return "uid-xyz"

    monkeypatch.setattr(
        mcp_module, "AuthenticationManager", lambda *_: DummyAuthenticationManager()
    )

    # Avoid filesystem/config lookups; we will stub plan_sync and record IO
    class DummyConfig:
        class E:
            version = "v1"

        class IU:
            last_indexed_file = "/tmp/.last_indexed"

        embedding = E()
        incremental_updates = IU()

    # Stub openai to avoid heavy import in vector_backend.embedding
    import sys
    import types

    fake_openai = types.ModuleType("openai")

    class _AsyncOpenAI:  # noqa: D401
        """Dummy stub for AsyncOpenAI"""

        pass

    fake_openai.AsyncOpenAI = _AsyncOpenAI  # type: ignore[attr-defined]
    sys.modules["openai"] = fake_openai

    # Wire server
    asyncio.run(mcp_server.run_server())
    captured["module"] = mcp_module
    return captured


def test_sync_tool_registered(mcp_env: dict[str, Any]) -> None:
    tool = mcp_env["tool_callbacks"].get("sync_vector_index")
    assert callable(tool), "sync_vector_index tool must be registered"


def test_sync_skip_path(monkeypatch: pytest.MonkeyPatch, mcp_env: dict[str, Any]) -> None:
    from vector_backend.build_state import compute_config_fingerprint as _fp
    from vector_backend.sync import plan_sync as _plan

    decision = {"action": "skip", "reason": "up_to_date", "built_at": datetime.now(UTC).isoformat()}

    import importlib

    _mod_bs = importlib.import_module(_fp.__module__)
    _mod_sync = importlib.import_module(_plan.__module__)
    monkeypatch.setattr(_mod_bs, "compute_config_fingerprint", lambda cfg: "fp")
    monkeypatch.setattr(_mod_bs, "load_build_record", lambda path: object())
    monkeypatch.setattr(_mod_sync, "plan_sync", lambda rec, fp, ver, **_: decision)

    tool = mcp_env["tool_callbacks"]["sync_vector_index"]
    result = asyncio.run(tool(force=False, dry_run=False, max_age_hours=None))

    assert result["action"] == "skip"
    assert result["reason"] == "up_to_date"


def test_sync_dry_run_rebuild(monkeypatch: pytest.MonkeyPatch, mcp_env: dict[str, Any]) -> None:
    from vector_backend.build_state import compute_config_fingerprint as _fp
    from vector_backend.sync import plan_sync as _plan

    decision = {"action": "rebuild", "reason": "config_changed", "built_at": None}

    import importlib

    _mod_bs = importlib.import_module(_fp.__module__)
    _mod_sync = importlib.import_module(_plan.__module__)
    monkeypatch.setattr(_mod_bs, "compute_config_fingerprint", lambda cfg: "fp")
    monkeypatch.setattr(_mod_bs, "load_build_record", lambda path: None)
    monkeypatch.setattr(_mod_sync, "plan_sync", lambda rec, fp, ver, **_: decision)

    tool = mcp_env["tool_callbacks"]["sync_vector_index"]
    result = asyncio.run(tool(force=False, dry_run=True, max_age_hours=None))

    assert result["action"] == "rebuild"
    assert result["dry_run"] is True


def test_sync_incremental_calls_selector(
    monkeypatch: pytest.MonkeyPatch, mcp_env: dict[str, Any]
) -> None:
    from vector_backend.build_state import compute_config_fingerprint as _fp
    from vector_backend.sync import plan_sync as _plan
    from vector_backend.sync import select_incremental_entries as _sel

    built_at = datetime.now(UTC) - timedelta(hours=25)
    decision = {"action": "incremental", "reason": "stale", "built_at": built_at.isoformat()}
    called: dict[str, Any] = {"selector": 0}

    import importlib

    _mod_bs = importlib.import_module(_fp.__module__)
    _mod_sync = importlib.import_module(_plan.__module__)
    monkeypatch.setattr(_mod_bs, "compute_config_fingerprint", lambda cfg: "fp")
    monkeypatch.setattr(_mod_bs, "load_build_record", lambda path: object())
    monkeypatch.setattr(_mod_sync, "plan_sync", lambda rec, fp, ver, **_: decision)

    def fake_selector(entries: list[dict[str, Any]], dt: datetime) -> list[dict[str, Any]]:
        called["selector"] += 1
        assert dt == built_at
        return []

    _mod_sel = importlib.import_module(_sel.__module__)
    monkeypatch.setattr(_mod_sel, "select_incremental_entries", fake_selector)

    # Minimal notebook client with just enough to be called
    class NB:
        async def get_page_entries(
            self, uid: str, nbid: str, pid: str
        ) -> list[dict[str, Any]]:  # noqa: ARG002
            return []

    mcp_env["module"].LabArchivesClient = lambda *_: NB()

    tool = mcp_env["tool_callbacks"]["sync_vector_index"]
    result = asyncio.run(tool(force=False, dry_run=False, max_age_hours=24, notebook_id=None))

    assert result["action"] == "incremental"
    assert called["selector"] >= 1
