from __future__ import annotations

import asyncio
from collections.abc import Callable
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

    # Minimal ELN client to satisfy server wiring
    class DummyLabArchivesClient:
        def __init__(self, _client: Any, _auth_manager: Any) -> None:
            pass

        async def get_page_entries(
            self, uid: str, nbid: str, pid: str
        ) -> list[dict[str, Any]]:  # noqa: ARG002
            return []

    monkeypatch.setattr(mcp_module, "LabArchivesClient", DummyLabArchivesClient)

    class DummyAuthenticationManager:
        async def ensure_uid(self) -> str:
            return "uid-xyz"

    monkeypatch.setattr(
        mcp_module, "AuthenticationManager", lambda *_: DummyAuthenticationManager()
    )

    # Stub out embedding and index to avoid network
    class DummyEmbed:
        async def embed_single(self, text: str) -> list[float]:  # noqa: ARG002
            return [0.1] * 1536

    def fake_create_embedding_client(_cfg: Any) -> DummyEmbed:  # noqa: ARG001
        return DummyEmbed()

    from vector_backend import models as vm

    class DummyIndex:
        def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401, ARG002
            pass

        async def health_check(self) -> bool:
            return True

        async def stats(self) -> Any:  # noqa: ANN401
            class S:
                total_chunks = 0

            return S()

        async def search(
            self, request: Any, query_vector: list[float]
        ) -> list[vm.SearchResult]:  # noqa: ANN401, ARG002
            # Two results on p1, then p2, p3 — to test deduplication
            def make_result(pid: str, score: float) -> vm.SearchResult:
                meta = vm.ChunkMetadata(
                    notebook_id="nb1",
                    notebook_name="Example",
                    page_id=pid,
                    page_title=f"Page {pid}",
                    entry_id="e1",
                    entry_type="text_entry",
                    author="test@example.com",
                    date=__import__("datetime").datetime.now(),
                    labarchives_url="https://example.com",
                    embedding_version="v1",
                )
                chunk = vm.EmbeddedChunk(
                    id=f"nb1_{pid}_e1_0",
                    text="t",
                    vector=[0.0] * 1536,
                    metadata=meta,
                )
                return vm.SearchResult(chunk=chunk, score=score, rank=1)

            return [
                make_result("p1", 0.99),
                make_result("p1", 0.98),
                make_result("p2", 0.97),
                make_result("p3", 0.96),
            ]

    import sys
    import types

    fake_openai = types.ModuleType("openai")

    class _AsyncOpenAI:  # noqa: D401
        """Dummy stub for AsyncOpenAI"""

        pass

    fake_openai.AsyncOpenAI = _AsyncOpenAI  # type: ignore[attr-defined]
    sys.modules["openai"] = fake_openai

    import yaml  # type: ignore[import-untyped]

    import vector_backend.embedding as vbe
    import vector_backend.index as vbi

    # Stub imports used inside search tool
    fake_aiofiles = types.ModuleType("aiofiles")

    def _fake_open(_path: str) -> Any:  # noqa: ANN001
        class _C:
            async def __aenter__(self) -> Any:  # noqa: D401
                class _F:
                    async def read(self) -> str:
                        return "{}"

                return _F()

            async def __aexit__(self, *exc_info: Any) -> None:  # noqa: ANN002
                return None

        return _C()

    fake_aiofiles.open = _fake_open  # type: ignore[attr-defined]
    sys.modules["aiofiles"] = fake_aiofiles

    monkeypatch.setattr(vbe, "create_embedding_client", fake_create_embedding_client)
    monkeypatch.setattr(vbi, "PineconeIndex", DummyIndex)
    monkeypatch.setattr(
        yaml,
        "safe_load",
        lambda _: {
            "OPENAI_API_KEY": "x",
            "PINECONE_API_KEY": "y",
        },
    )

    # Wire server
    asyncio.run(mcp_server.run_server())
    captured["module"] = mcp_module
    return captured


def test_search_page_limit_dedup(monkeypatch: pytest.MonkeyPatch, mcp_env: dict[str, Any]) -> None:
    tool = mcp_env["tool_callbacks"]["search_labarchives"]
    # Ask for 2 pages, with duplicates in top candidates
    result = asyncio.run(tool(query="q", limit=2))
    assert isinstance(result, list)
    assert len(result) == 2
    # Ensure we got unique pages
    page_ids = [r["page_id"] for r in result]
    assert len(set(page_ids)) == len(page_ids)
