"""Tests for LabArchives MCP authentication flows."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
from collections.abc import Callable
from typing import Any, cast

import httpx
import pytest
from pydantic import HttpUrl

from labarchives_mcp.auth import AuthenticationManager, Credentials


class StubAsyncClient:
    """Minimal async client surface used by `AuthenticationManager`."""

    def __init__(
        self,
        handler: Callable[
            [str, dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None],
            httpx.Response,
        ],
    ) -> None:
        self._handler = handler
        self.calls: list[dict[str, Any]] = []

    async def post(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> httpx.Response:
        call = {"url": url, "params": params, "json": json, "data": data}
        self.calls.append(call)
        return self._handler(url, params, json, data)


def test_ensure_uid_caches_uid_and_applies_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given valid credentials, when `ensure_uid()` is invoked repeatedly,
    then the first call signs the request and later calls reuse the cached uid
    until cleared."""

    credentials = Credentials(
        akid="AK123",
        password="super-secret",
        region=cast(HttpUrl, "https://api.labarchives.com"),
    )
    fixed_time = 1_700_000_000
    monkeypatch.setattr(time, "time", lambda: fixed_time)

    responses = iter(
        [
            httpx.Response(
                200,
                json={"status": "success", "uid": "uid-123"},
                request=httpx.Request("POST", "https://api.labarchives.com/api/v1/login"),
            ),
            httpx.Response(
                200,
                json={"status": "success", "uid": "uid-999"},
                request=httpx.Request("POST", "https://api.labarchives.com/api/v1/login"),
            ),
        ]
    )

    def handler(
        url: str,
        params: dict[str, Any] | None,
        json: dict[str, Any] | None,
        data: dict[str, Any] | None,
    ) -> httpx.Response:
        return next(responses)

    client = StubAsyncClient(handler)
    manager = AuthenticationManager(cast(httpx.AsyncClient, client), credentials)

    uid_first = asyncio.run(manager.ensure_uid())
    assert uid_first == "uid-123"
    assert len(client.calls) == 1

    login_call = client.calls[0]
    assert login_call["url"] == "https://api.labarchives.com/api/v1/login"
    expected_expires = str(fixed_time + 300)
    expected_sig = hmac.new(
        credentials.password.encode("utf-8"),
        f"{credentials.akid}{expected_expires}".encode(),
        hashlib.sha256,
    ).hexdigest()
    assert login_call["params"] == {
        "akid": credentials.akid,
        "expires": expected_expires,
        "sig": expected_sig,
    }

    uid_cached = asyncio.run(manager.ensure_uid())
    assert uid_cached == "uid-123"
    assert len(client.calls) == 1, "Cached uid should not trigger another HTTP request"

    manager.clear_uid()
    uid_after_clear = asyncio.run(manager.ensure_uid())
    assert uid_after_clear == "uid-999"
    assert len(client.calls) == 2, "Clearing the uid should force a new login"


def test_ensure_uid_raises_on_failed_login(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given an HTTP 403 response, when `ensure_uid()` attempts login,
    then a runtime error is raised and the attempt is recorded."""

    credentials = Credentials(
        akid="AK999",
        password="bad-secret",
        region=cast(HttpUrl, "https://api.labarchives.com"),
    )

    def handler(
        url: str,
        params: dict[str, Any] | None,
        json: dict[str, Any] | None,
        data: dict[str, Any] | None,
    ) -> httpx.Response:
        request = httpx.Request("POST", url, params=params)
        return httpx.Response(
            403, json={"status": "error", "message": "Forbidden"}, request=request
        )

    client = StubAsyncClient(handler)
    manager = AuthenticationManager(cast(httpx.AsyncClient, client), credentials)

    with pytest.raises(RuntimeError, match="LabArchives login failed"):
        asyncio.run(manager.ensure_uid())

    assert client.calls, "Login should have been attempted"
