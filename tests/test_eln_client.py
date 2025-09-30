"""Tests for the LabArchives ELN client behaviour."""

from __future__ import annotations

import asyncio
from typing import cast

import httpx
import pytest
from pydantic import HttpUrl

from labarchives_mcp.auth import AuthenticationManager, Credentials
from labarchives_mcp.eln_client import LabArchivesClient, NotebookRecord


def test_list_notebooks_handles_http_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given a non-200 LabArchives response, when `list_notebooks()` is
    called, then an `HTTPStatusError` is raised."""

    async def scenario() -> None:
        credentials = Credentials(
            akid="test",
            password="test",
            region=cast(HttpUrl, "https://example.com"),
        )
        async with httpx.AsyncClient(base_url="https://example.com") as async_client:
            auth_manager = AuthenticationManager(async_client, credentials)
            client = LabArchivesClient(async_client, auth_manager)

            async def fake_get(url: str, params: dict[str, str]) -> httpx.Response:
                return httpx.Response(404, request=httpx.Request("GET", url, params=params))

            monkeypatch.setattr(async_client, "get", fake_get)

            with pytest.raises(httpx.HTTPStatusError):
                await client.list_notebooks("example-uid")

    asyncio.run(scenario())


def test_notebook_record_model() -> None:
    """Given LabArchives notebook metadata, when `NotebookRecord` validates
    it, then alias fields normalize correctly."""
    record = NotebookRecord.model_validate(
        {
            "nbid": "12345",
            "name": "Fly Behavior Study",
            "owner": "samuel.brudner@yale.edu",
            "owner_email": "samuel.brudner@yale.edu",
            "owner_name": "Samuel Brudner",
            "created_at": "2025-01-01T12:00:00Z",
            "modified_at": "2025-01-02T08:30:00Z",
        }
    )

    assert record.nbid == "12345"
    assert record.name == "Fly Behavior Study"
    assert record.owner == "samuel.brudner@yale.edu"
    assert record.created_at == "2025-01-01T12:00:00Z"
    assert record.modified_at == "2025-01-02T08:30:00Z"


def test_parse_xml_hydrates_records() -> None:
    """Given LabArchives notebook XML from user_info_via_id, when `parse_xml()` runs,
    then it yields normalized dictionaries."""
    xml_payload = (
        "<users>"
        "  <email>samuel.brudner@yale.edu</email>"
        "  <fullname>Samuel Brudner</fullname>"
        "  <notebooks>"
        "    <notebook>"
        "      <id>123</id>"
        "      <name>Fly Behavior Study</name>"
        "      <owner-email>samuel.brudner@yale.edu</owner-email>"
        "      <owner-name>Samuel Brudner</owner-name>"
        "      <created-at>2025-01-01T12:00:00Z</created-at>"
        "      <modified-at>2025-01-02T08:30:00Z</modified-at>"
        "    </notebook>"
        "    <notebook>"
        "      <id>456</id>"
        "      <name>Optogenetics</name>"
        "      <owner-email>pi@example.edu</owner-email>"
        "      <owner-name>Principal Investigator</owner-name>"
        "      <created-at>2025-02-02T08:30:00Z</created-at>"
        "      <modified-at>2025-02-02T10:45:00Z</modified-at>"
        "    </notebook>"
        "  </notebooks>"
        "</users>"
    )

    records = LabArchivesClient.parse_xml(xml_payload)

    assert records == [
        {
            "nbid": "123",
            "name": "Fly Behavior Study",
            "owner": "samuel.brudner@yale.edu",
            "owner_email": "samuel.brudner@yale.edu",
            "owner_name": "Samuel Brudner",
            "created_at": "2025-01-01T12:00:00Z",
            "modified_at": "2025-01-02T08:30:00Z",
        },
        {
            "nbid": "456",
            "name": "Optogenetics",
            "owner": "samuel.brudner@yale.edu",  # Falls back to root user email
            "owner_email": "pi@example.edu",
            "owner_name": "Principal Investigator",
            "created_at": "2025-02-02T08:30:00Z",
            "modified_at": "2025-02-02T10:45:00Z",
        },
    ]


def test_list_notebooks_returns_notebook_records(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given a well-formed API response, when `list_notebooks()` executes,
    then it returns validated notebook records."""

    async def scenario() -> None:
        credentials = Credentials(
            akid="test",
            password="test",
            region=cast(HttpUrl, "https://example.com"),
        )
        async with httpx.AsyncClient(base_url="https://example.com") as async_client:
            auth_manager = AuthenticationManager(async_client, credentials)
            client = LabArchivesClient(async_client, auth_manager)

            async def fake_get(url: str, params: dict[str, str]) -> httpx.Response:
                assert url.endswith("/api/users/user_info_via_id")
                assert params["uid"] == "example-uid"
                payload = (
                    "<users>"
                    "  <email>samuel.brudner@yale.edu</email>"
                    "  <fullname>Samuel Brudner</fullname>"
                    "  <notebooks>"
                    "    <notebook>"
                    "      <id>123</id>"
                    "      <name>Fly Behavior Study</name>"
                    "    </notebook>"
                    "  </notebooks>"
                    "</users>"
                )
                request = httpx.Request("GET", url, params=params)
                return httpx.Response(
                    200,
                    text=payload,
                    headers={"content-type": "application/xml"},
                    request=request,
                )

            monkeypatch.setattr(async_client, "get", fake_get)

            notebooks = await client.list_notebooks("example-uid")

            assert notebooks == [
                NotebookRecord(
                    nbid="123",
                    name="Fly Behavior Study",
                    owner="samuel.brudner@yale.edu",
                    owner_email="samuel.brudner@yale.edu",
                    owner_name="Samuel Brudner",
                    created_at="2025-01-01T12:00:00Z",
                    modified_at="2025-01-02T08:30:00Z",
                )
            ]
