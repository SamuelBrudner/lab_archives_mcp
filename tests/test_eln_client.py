"""Tests for the LabArchives ELN client behaviour."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from labarchives_mcp.eln_client import LabArchivesClient, NotebookRecord


def test_list_notebooks_handles_http_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given a non-200 LabArchives response, when `list_notebooks()` is
    called, then an `HTTPStatusError` is raised."""

    async def scenario() -> None:
        async with httpx.AsyncClient(base_url="https://example.com") as async_client:
            client = LabArchivesClient(async_client)

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
    """Given LabArchives notebook XML, when `parse_xml()` runs, then it
    yields normalized dictionaries."""
    xml_payload = (
        "<notebooks>"
        "  <notebook>"
        "    <nbid>123</nbid>"
        "    <name>Fly Behavior Study</name>"
        "    <owner>samuel.brudner@yale.edu</owner>"
        "    <owner-email>samuel.brudner@yale.edu</owner-email>"
        "    <owner-name>Samuel Brudner</owner-name>"
        "    <created-at>2025-01-01T12:00:00Z</created-at>"
        "    <modified-at>2025-01-02T08:30:00Z</modified-at>"
        "  </notebook>"
        "  <notebook>"
        "    <nbid>456</nbid>"
        "    <name>Optogenetics</name>"
        "    <owner>pi@example.edu</owner>"
        "    <owner-email>pi@example.edu</owner-email>"
        "    <owner-name>Principal Investigator</owner-name>"
        "    <created-at>2025-02-02T08:30:00Z</created-at>"
        "    <modified-at>2025-02-02T10:45:00Z</modified-at>"
        "  </notebook>"
        "</notebooks>"
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
            "owner": "pi@example.edu",
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
        async with httpx.AsyncClient(base_url="https://example.com") as async_client:
            client = LabArchivesClient(async_client)

            async def fake_get(url: str, params: dict[str, str]) -> httpx.Response:
                assert url.endswith("/apiv1/notebooks/list")
                assert params["uid"] == "example-uid"
                payload = (
                    "<notebooks>"
                    "  <notebook>"
                    "    <nbid>123</nbid>"
                    "    <name>Fly Behavior Study</name>"
                    "    <owner>samuel.brudner@yale.edu</owner>"
                    "    <created-at>2025-01-01T12:00:00Z</created-at>"
                    "  </notebook>"
                    "</notebooks>"
                )
                request = httpx.Request("GET", url, params=params)
                return httpx.Response(
                    200,
                    text=payload,
                    headers={"content-type": "application/xml"},
                    request=request,
                )

            def fake_parse_xml(payload: str) -> list[dict[str, Any]]:
                return [
                    {
                        "nbid": "123",
                        "name": "Fly Behavior Study",
                        "owner": "samuel.brudner@yale.edu",
                        "owner_email": "samuel.brudner@yale.edu",
                        "owner_name": "Samuel Brudner",
                        "created_at": "2025-01-01T12:00:00Z",
                        "modified_at": "2025-01-02T08:30:00Z",
                    }
                ]

            monkeypatch.setattr(LabArchivesClient, "parse_xml", staticmethod(fake_parse_xml))

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
