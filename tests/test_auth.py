"""Tests for LabArchives MCP authentication flows."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import time
from collections.abc import Callable
from typing import Any, cast
from urllib.parse import quote

import httpx
import pytest
from pydantic import HttpUrl

from labarchives_mcp.auth import AuthenticationManager, Credentials


class StubAsyncClient:
    """Minimal async client surface used by `AuthenticationManager`."""

    def __init__(
        self,
        handler: Callable[[str, dict[str, Any] | None, dict[str, Any] | None], httpx.Response],
    ) -> None:
        self._handler = handler
        self.calls: list[dict[str, Any]] = []

    async def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        call = {"method": "GET", "url": url, "params": params, "json": json}
        self.calls.append(call)
        return self._handler(url, params, json)


def test_ensure_uid_returns_cached_credentials_uid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given credentials with a pre-set uid, when `ensure_uid()` runs, then it returns the cached
    value without HTTP requests."""

    credentials = Credentials(
        akid="AK123",
        password="super-secret",
        region=cast(HttpUrl, "https://api.labarchives.com"),
        uid="uid-123",
    )

    def handler(
        url: str,
        params: dict[str, Any] | None,
        json: dict[str, Any] | None,
    ) -> httpx.Response:
        raise AssertionError("HTTP should not be called when uid is pre-configured")

    client = StubAsyncClient(handler)
    manager = AuthenticationManager(cast(httpx.AsyncClient, client), credentials)

    uid_first = asyncio.run(manager.ensure_uid())
    assert uid_first == "uid-123"
    assert not client.calls

    manager.clear_uid()
    with pytest.raises(RuntimeError, match="require either"):
        asyncio.run(manager.ensure_uid())


def test_ensure_uid_raises_on_failed_login(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given a 4xx response from `user_access_info`, when resolving the uid, then a runtime error
    is raised and the attempt is recorded."""

    credentials = Credentials(
        akid="AK999",
        password="bad-secret",
        region=cast(HttpUrl, "https://api.labarchives.com"),
        auth_email="user@example.com",
        auth_code="temp-token",
    )

    def handler(
        url: str,
        params: dict[str, Any] | None,
        json: dict[str, Any] | None,
    ) -> httpx.Response:
        request = httpx.Request("GET", url, params=params)
        return httpx.Response(403, json={"status": "error"}, request=request)

    client = StubAsyncClient(handler)
    manager = AuthenticationManager(cast(httpx.AsyncClient, client), credentials)

    with pytest.raises(RuntimeError, match="user_access_info failed"):
        asyncio.run(manager.ensure_uid())

    assert client.calls, "user_access_info should have been attempted"


def test_ensure_uid_fetches_via_user_access_info(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given temporary credentials, when `ensure_uid()` runs, then it calls `user_access_info`
    with correct signature."""

    credentials = Credentials(
        akid="AK123",
        password="super-secret",
        region=cast(HttpUrl, "https://api.labarchives.com"),
        auth_email="user@example.com",
        auth_code="temp-token",
    )
    fixed_time = 1_700_000_000.0
    monkeypatch.setattr(time, "time", lambda: fixed_time)

    def handler(
        url: str,
        params: dict[str, Any] | None,
        json: dict[str, Any] | None,
    ) -> httpx.Response:
        request = httpx.Request("GET", url, params=params)
        return httpx.Response(200, json={"uid": "uid-123"}, request=request)

    client = StubAsyncClient(handler)
    manager = AuthenticationManager(cast(httpx.AsyncClient, client), credentials)

    uid = asyncio.run(manager.ensure_uid())
    assert uid == "uid-123"

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["url"] == "https://api.labarchives.com/apiv1/users/user_access_info"

    expected_expires = str(int(fixed_time * 1000) + 120_000)
    message = (
        f"{credentials.akid}{AuthenticationManager.USER_ACCESS_METHOD}{expected_expires}".encode()
    )
    expected_sig = quote(
        base64.b64encode(
            hmac.new(credentials.password.encode("utf-8"), message, hashlib.sha512).digest()
        ).decode("ascii"),
        safe="",
    )

    assert call["params"] == {
        "akid": credentials.akid,
        "expires": expected_expires,
        "sig": expected_sig,
        "email": "user@example.com",
        "password": "temp-token",
    }
