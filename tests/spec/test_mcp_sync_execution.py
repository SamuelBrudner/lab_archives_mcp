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
            self._resource_callbacks: dict[str, Any] = {}
            self._tool_callbacks: dict[str, Any] = {}
            captured["tool_callbacks"] = self._tool_callbacks

        def resource(self, uri: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
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
def mcp_env_exec(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> dict[str, Any]:
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

    class DummyAuth:
        async def ensure_uid(self) -> str:
            return "uid-xyz"

    monkeypatch.setattr(mcp_module, "AuthenticationManager", lambda *_: DummyAuth())

    # Stub openai module to avoid heavy import paths in embedding factory in case it is reached
    import sys
    import types

    fake_openai = types.ModuleType("openai")
    sys.modules["openai"] = fake_openai

    # Wire server (captures tools)
    asyncio.run(mcp_server.run_server())
    captured["module"] = mcp_module

    def _cleanup() -> None:
        for name in ("openai",):
            sys.modules.pop(name, None)

    request.addfinalizer(_cleanup)
    return captured


def test_sync_incremental_exec_indexes_changed(
    monkeypatch: pytest.MonkeyPatch, mcp_env_exec: dict[str, Any]
) -> None:
    # Plan: incremental with built_at 24h ago
    import importlib

    from vector_backend.sync import plan_sync as _plan

    built_at = datetime.now(UTC) - timedelta(hours=24)
    _mod_sync = importlib.import_module(_plan.__module__)
    monkeypatch.setattr(
        _mod_sync,
        "plan_sync",
        lambda *_, **__: {
            "action": "incremental",
            "reason": "stale",
            "built_at": built_at.isoformat(),
        },
    )

    # Dummy notebook with two pages; only page p2 has changed entries
    class NB:
        async def get_notebook_tree(
            self, uid: str, nbid: str, parent_tree_id: int | str = 0
        ) -> list[dict[str, Any]]:  # noqa: ARG002
            if parent_tree_id == 0:
                return [
                    {
                        "tree_id": "p1",
                        "display_text": "Page 1",
                        "is_page": True,
                        "is_folder": False,
                    },
                    {
                        "tree_id": "p2",
                        "display_text": "Page 2",
                        "is_page": True,
                        "is_folder": False,
                    },
                ]
            return []

        async def get_page_entries(
            self, uid: str, nbid: str, pid: str
        ) -> list[dict[str, Any]]:  # noqa: ARG002
            old_ts = (built_at - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
            new_ts = (built_at + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
            if pid == "p1":
                # All older than built_at
                return [
                    {
                        "eid": "e1",
                        "part_type": "text_entry",
                        "content": "old",
                        "created_at": old_ts,
                        "updated_at": old_ts,
                    }
                ]
            return [
                {
                    "eid": "e2",
                    "part_type": "text_entry",
                    "content": "new content",
                    "created_at": new_ts,
                    "updated_at": new_ts,
                }
            ]

    mcp_env_exec["module"].LabArchivesClient = lambda *_: NB()

    # Stub embedding + index
    import vector_backend.embedding as vbe
    import vector_backend.index as vbi

    class DummyEmbed:
        async def embed_batch(self, texts: list[str]) -> list[list[float]]:  # noqa: D401
            return [[0.0] * 1536 for _ in texts]

    class DummyIndex:
        def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401, ARG002
            self.upserts: list[Any] = []

        async def upsert(self, chunks: list[Any]) -> None:  # noqa: D401, ANN401
            self.upserts.extend(chunks)

        async def delete(self, chunk_ids: list[str]) -> None:  # noqa: D401
            return None

        async def search(self, request: Any) -> list[Any]:  # noqa: D401, ANN401
            return []

        async def stats(self) -> Any:  # noqa: D401, ANN401
            class S:
                total_chunks = 0

            return S()

        async def health_check(self) -> bool:  # noqa: D401
            return True

    monkeypatch.setattr(vbe, "create_embedding_client", lambda cfg: DummyEmbed())
    monkeypatch.setattr(vbi, "PineconeIndex", DummyIndex)

    tool = mcp_env_exec["tool_callbacks"]["sync_vector_index"]
    result = asyncio.run(tool(force=False, dry_run=False, max_age_hours=24, notebook_id="nb1"))

    assert result["action"] == "incremental"
    assert result["processed_pages"] == 1
    assert result["indexed_chunks"] >= 1


def test_sync_rebuild_exec_indexes_all_and_saves_record(
    monkeypatch: pytest.MonkeyPatch, mcp_env_exec: dict[str, Any]
) -> None:
    # Plan: rebuild
    import importlib

    from vector_backend.sync import plan_sync as _plan

    _mod_sync = importlib.import_module(_plan.__module__)
    monkeypatch.setattr(
        _mod_sync,
        "plan_sync",
        lambda *_, **__: {"action": "rebuild", "reason": "no_record", "built_at": None},
    )

    # Dummy notebook: two pages, both indexable
    class NB:
        async def get_notebook_tree(
            self, uid: str, nbid: str, parent_tree_id: int | str = 0
        ) -> list[dict[str, Any]]:  # noqa: ARG002
            if parent_tree_id == 0:
                return [
                    {
                        "tree_id": "p1",
                        "display_text": "Page 1",
                        "is_page": True,
                        "is_folder": False,
                    },
                    {
                        "tree_id": "p2",
                        "display_text": "Page 2",
                        "is_page": True,
                        "is_folder": False,
                    },
                ]
            return []

        async def get_page_entries(
            self, uid: str, nbid: str, pid: str
        ) -> list[dict[str, Any]]:  # noqa: ARG002
            ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            return [
                {
                    "eid": f"{pid}-1",
                    "part_type": "text_entry",
                    "content": "content",
                    "created_at": ts,
                    "updated_at": ts,
                }
            ]

    mcp_env_exec["module"].LabArchivesClient = lambda *_: NB()

    # Stub embedding + index
    import vector_backend.build_state as vbs
    import vector_backend.embedding as vbe
    import vector_backend.index as vbi

    class DummyEmbed:
        async def embed_batch(self, texts: list[str]) -> list[list[float]]:  # noqa: D401
            return [[0.0] * 1536 for _ in texts]

    class DummyIndex:
        def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401, ARG002
            self.upserts: list[Any] = []

        async def upsert(self, chunks: list[Any]) -> None:  # noqa: D401, ANN401
            self.upserts.extend(chunks)

        async def delete(self, chunk_ids: list[str]) -> None:  # noqa: D401
            return None

        async def search(self, request: Any) -> list[Any]:  # noqa: D401, ANN401
            return []

        async def stats(self) -> Any:  # noqa: D401, ANN401
            class S:
                total_chunks = 0

            return S()

        async def health_check(self) -> bool:  # noqa: D401
            return True

    saved = {"calls": 0}

    def fake_save(path: Any, record: Any) -> None:  # noqa: ANN001
        saved["calls"] += 1

    monkeypatch.setattr(vbe, "create_embedding_client", lambda cfg: DummyEmbed())
    monkeypatch.setattr(vbi, "PineconeIndex", DummyIndex)
    monkeypatch.setattr(vbs, "save_build_record", fake_save)

    tool = mcp_env_exec["tool_callbacks"]["sync_vector_index"]
    result = asyncio.run(tool(force=False, dry_run=False, max_age_hours=None, notebook_id="nb1"))

    assert result["action"] == "rebuild"
    assert result["processed_pages"] == 2
    assert result["indexed_chunks"] >= 2
    assert saved["calls"] >= 1
