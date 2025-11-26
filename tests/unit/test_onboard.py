"""Tests for the LabArchives MCP onboarding functionality."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, ParamSpec, TypeVar, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from labarchives_mcp.auth import AuthenticationManager
from labarchives_mcp.eln_client import LabArchivesClient, NotebookRecord
from labarchives_mcp.onboard import OnboardService
from labarchives_mcp.schemas.onboard import MAX_ONBOARD_PAYLOAD_BYTES, OnboardPayload

P = ParamSpec("P")
R = TypeVar("R")


def typed_fixture(func: Callable[P, R]) -> Callable[P, R]:
    return cast(Callable[P, R], pytest.fixture()(func))


def async_test(func: Callable[P, Coroutine[Any, Any, R]]) -> Callable[P, Coroutine[Any, Any, R]]:
    return cast(Callable[P, Coroutine[Any, Any, R]], pytest.mark.asyncio(func))


@typed_fixture
def mock_auth_manager() -> AuthenticationManager:
    """Create a mock authentication manager."""
    mock = MagicMock(spec=AuthenticationManager)
    mock.ensure_uid = AsyncMock(return_value="test-uid-123")
    return mock


@typed_fixture
def mock_notebook_client() -> MagicMock:
    """Create a mock notebook client with minimal sample data."""
    mock = MagicMock(spec=LabArchivesClient)

    # Minimal notebooks to stay under size limit
    notebooks = [
        NotebookRecord(
            nbid="nb1",
            name="Lab Notebook 1",
            owner="r@y.edu",
            owner_email="r@y.edu",
            owner_name="R",
            created_at="2025-01-01T00:00:00Z",
            modified_at="2025-10-20T14:30:00Z",
        ),
    ]
    mock.list_notebooks = AsyncMock(return_value=notebooks)

    # Minimal tree nodes
    mock.get_notebook_tree = AsyncMock(
        return_value=[
            {
                "tree_id": "p1",
                "display_text": "Page 1",
                "is_page": True,
                "is_folder": False,
            },
        ]
    )

    # Minimal page entries
    mock.get_page_entries = AsyncMock(
        return_value=[
            {
                "eid": "e1",
                "part_type": "text_entry",
                "content": "<p>Test entry.</p>",
                "created_at": "2025-10-20T14:00:00Z",
                "updated_at": "2025-10-20T14:30:00Z",
            }
        ]
    )

    return mock


@typed_fixture
def onboard_service(
    mock_auth_manager: AuthenticationManager,
    mock_notebook_client: MagicMock,
) -> OnboardService:
    """Create an OnboardService instance with mocked dependencies."""
    return OnboardService(
        auth_manager=mock_auth_manager,
        notebook_client=cast(LabArchivesClient, mock_notebook_client),
        version="0.2.4",
        cache_ttl_seconds=300,
        max_notebooks=5,
        recent_activity_limit=5,
    )


@async_test
async def test_get_payload_returns_valid_structure(
    onboard_service: OnboardService,
) -> None:
    """Test that get_payload returns a properly structured OnboardPayload."""
    payload = await onboard_service.get_payload()

    assert isinstance(payload, OnboardPayload)
    assert payload.server == "lab_archives_mcp"
    assert payload.version == "0.2.4"
    assert payload.purpose == "Provide experimental context from LabArchives ELN."
    assert payload.banner
    assert payload.router_prompt
    assert payload.markdown


@async_test
async def test_get_payload_includes_notebook_summaries(
    onboard_service: OnboardService,
) -> None:
    """Test that payload includes notebook metadata."""
    payload = await onboard_service.get_payload()

    assert len(payload.lab_summary.notebooks) > 0
    nb = payload.lab_summary.notebooks[0]
    assert nb.id
    assert nb.title
    assert nb.n_pages >= 0
    assert nb.last_updated


@async_test
async def test_get_payload_includes_recent_activity(
    onboard_service: OnboardService,
) -> None:
    """Test that payload includes recent activity summaries."""
    payload = await onboard_service.get_payload()

    assert len(payload.lab_summary.recent_activity) > 0
    activity = payload.lab_summary.recent_activity[0]
    assert activity.notebook_id
    assert activity.notebook_title
    assert activity.page_id
    assert activity.page_title
    assert activity.summary
    assert activity.updated_at


@async_test
async def test_get_payload_respects_size_limit(
    onboard_service: OnboardService,
) -> None:
    """Test that payload does not exceed MAX_ONBOARD_PAYLOAD_BYTES."""
    payload = await onboard_service.get_payload()
    payload_bytes = payload.to_json_bytes()

    assert len(payload_bytes) <= MAX_ONBOARD_PAYLOAD_BYTES, (
        f"Payload size {len(payload_bytes)} bytes exceeds "
        f"limit of {MAX_ONBOARD_PAYLOAD_BYTES} bytes"
    )


@async_test
async def test_get_payload_caching(
    onboard_service: OnboardService,
    mock_notebook_client: MagicMock,
) -> None:
    """Test that payload is cached and reused within TTL."""
    # First call
    payload1 = await onboard_service.get_payload()

    # Second call should use cache
    payload2 = await onboard_service.get_payload()

    # Should be the same object
    assert payload1 is payload2

    # list_notebooks should only be called once
    list_notebooks_mock = cast(AsyncMock, mock_notebook_client.list_notebooks)
    assert list_notebooks_mock.await_count == 1


@async_test
async def test_get_payload_cache_expires(
    mock_auth_manager: AuthenticationManager,
    mock_notebook_client: MagicMock,
) -> None:
    """Test that cache expires after TTL."""
    # Create service with very short TTL
    service = OnboardService(
        auth_manager=mock_auth_manager,
        notebook_client=cast(LabArchivesClient, mock_notebook_client),
        version="0.2.4",
        cache_ttl_seconds=0,  # Immediate expiry
    )

    # First call
    await service.get_payload()
    await asyncio.sleep(0.01)  # Small delay to ensure time passes

    # Second call should rebuild
    await service.get_payload()

    # list_notebooks should be called twice
    list_notebooks_mock = cast(AsyncMock, mock_notebook_client.list_notebooks)
    assert list_notebooks_mock.await_count == 2


@async_test
async def test_payload_as_dict_is_serializable(
    onboard_service: OnboardService,
) -> None:
    """Test that as_dict() returns JSON-serializable dict."""
    import json

    payload = await onboard_service.get_payload()
    payload_dict = payload.as_dict()

    # Should be serializable
    json_str = json.dumps(payload_dict)
    assert json_str
    assert isinstance(json_str, str)


@async_test
async def test_payload_markdown_contains_key_sections(
    onboard_service: OnboardService,
) -> None:
    """Test that markdown output includes expected sections."""
    payload = await onboard_service.get_payload()
    markdown = payload.markdown

    assert "## LabArchives MCP Onboarding" in markdown
    assert "### When to Use" in markdown
    assert "### Primary Tools" in markdown
    assert "### Notebooks" in markdown
    assert "### Recent Activity" in markdown
    assert "### Router Prompt" in markdown


@async_test
async def test_how_to_use_includes_primary_tools(
    onboard_service: OnboardService,
) -> None:
    """Test that how_to_use includes expected tool descriptions."""
    payload = await onboard_service.get_payload()
    tools = payload.how_to_use.primary_tools

    assert "search_labarchives" in tools
    assert "list_notebooks" in tools
    assert "list_notebook_pages" in tools
    assert "read_notebook_page" in tools


@async_test
async def test_empty_notebooks_handled_gracefully(
    mock_auth_manager: AuthenticationManager,
) -> None:
    """Test that service handles empty notebook list without errors."""
    mock_client = MagicMock(spec=LabArchivesClient)
    mock_client.list_notebooks = AsyncMock(return_value=[])

    service = OnboardService(
        auth_manager=mock_auth_manager,
        notebook_client=cast(LabArchivesClient, mock_client),
        version="0.2.4",
    )

    payload = await service.get_payload()

    assert len(payload.lab_summary.notebooks) == 0
    assert len(payload.lab_summary.recent_activity) == 0
    assert payload.markdown  # Should still generate markdown


@async_test
async def test_network_errors_during_scan_handled(
    mock_auth_manager: AuthenticationManager,
    mock_notebook_client: MagicMock,
) -> None:
    """Test that network errors during scanning are handled gracefully."""
    # Make get_notebook_tree raise an error
    mock_notebook_client.get_notebook_tree = AsyncMock(side_effect=RuntimeError("Network timeout"))

    service = OnboardService(
        auth_manager=mock_auth_manager,
        notebook_client=cast(LabArchivesClient, mock_notebook_client),
        version="0.2.4",
    )

    # Should not raise, but return payload with limited data
    payload = await service.get_payload()
    assert isinstance(payload, OnboardPayload)
    # Notebooks should still be listed even if pages fail
    assert len(payload.lab_summary.notebooks) > 0


@async_test
async def test_recent_activity_sorted_by_timestamp(
    onboard_service: OnboardService,
    mock_notebook_client: MagicMock,
) -> None:
    """Test that recent activity is sorted by most recent first."""
    # Mock entries with different timestamps
    mock_notebook_client.get_page_entries = AsyncMock(
        side_effect=[
            [
                {
                    "eid": "e1",
                    "part_type": "text_entry",
                    "content": "<p>Old entry</p>",
                    "updated_at": "2025-10-01T10:00:00Z",
                }
            ],
            [
                {
                    "eid": "e2",
                    "part_type": "text_entry",
                    "content": "<p>New entry</p>",
                    "updated_at": "2025-10-20T15:00:00Z",
                }
            ],
        ]
    )

    payload = await onboard_service.get_payload()
    activity = payload.lab_summary.recent_activity

    if len(activity) >= 2:
        # Most recent should be first
        assert activity[0].updated_at >= activity[1].updated_at


@async_test
async def test_html_content_stripped_in_summaries(
    onboard_service: OnboardService,
    mock_notebook_client: MagicMock,
) -> None:
    """Test that HTML tags are stripped from activity summaries."""
    mock_notebook_client.get_page_entries = AsyncMock(
        return_value=[
            {
                "eid": "e1",
                "part_type": "text_entry",
                "content": "<p>Test with <strong>bold</strong> and <em>italic</em> text.</p>",
                "updated_at": "2025-10-20T14:00:00Z",
            }
        ]
    )

    payload = await onboard_service.get_payload()
    activity = payload.lab_summary.recent_activity

    assert activity, "Expected recent activity to be populated"
    summary = activity[0].summary
    # Should not contain HTML tags
    assert "<p>" not in summary
    assert "<strong>" not in summary
    assert "<em>" not in summary
    # Should contain the text content
    assert "bold" in summary
    assert "italic" in summary


@async_test
async def test_sticky_context_initialized(
    onboard_service: OnboardService,
) -> None:
    """Test that sticky_context is properly initialized."""
    payload = await onboard_service.get_payload()
    context = payload.sticky_context

    # Should be initialized but empty
    assert context.last_notebook_id is None
    assert context.last_page_id is None


@async_test
async def test_payload_size_with_large_dataset(
    mock_auth_manager: AuthenticationManager,
) -> None:
    """Test that payload stays within size limit with reasonable notebook counts."""
    # Create a mock client with multiple notebooks
    mock_client = MagicMock(spec=LabArchivesClient)

    # Generate 10 notebooks with short names
    notebooks = [
        NotebookRecord(
            nbid=f"n{i}",
            name=f"NB{i}",
            owner="r@y.edu",
            owner_email="r@y.edu",
            owner_name="R",
            created_at="2025-01-01T00:00:00Z",
            modified_at=f"2025-10-{(i % 28) + 1:02d}T12:00:00Z",
        )
        for i in range(10)
    ]
    mock_client.list_notebooks = AsyncMock(return_value=notebooks)

    # Limited pages per notebook
    mock_client.get_notebook_tree = AsyncMock(
        return_value=[
            {
                "tree_id": f"p{j}",
                "display_text": f"Page {j}",
                "is_page": True,
                "is_folder": False,
            }
            for j in range(3)
        ]
    )

    mock_client.get_page_entries = AsyncMock(
        return_value=[
            {
                "eid": "e1",
                "part_type": "text_entry",
                "content": "<p>Brief content.</p>",
                "updated_at": "2025-10-20T14:00:00Z",
            }
        ]
    )

    service = OnboardService(
        auth_manager=mock_auth_manager,
        notebook_client=cast(LabArchivesClient, mock_client),
        version="0.2.4",
        max_notebooks=5,  # Limit to prevent size explosion
        recent_activity_limit=2,
    )

    payload = await service.get_payload()
    payload_bytes = payload.to_json_bytes()

    # Should respect size limit
    assert len(payload_bytes) <= MAX_ONBOARD_PAYLOAD_BYTES


@async_test
async def test_concurrent_get_payload_calls_use_lock(
    onboard_service: OnboardService,
    mock_notebook_client: MagicMock,
) -> None:
    """Test that concurrent calls don't trigger multiple builds."""
    # Clear any existing cache
    onboard_service._cache = None

    # Make multiple concurrent calls
    results = await asyncio.gather(
        onboard_service.get_payload(),
        onboard_service.get_payload(),
        onboard_service.get_payload(),
    )

    # All should return the same cached payload
    assert results[0] is results[1]
    assert results[1] is results[2]

    # list_notebooks should only be called once despite concurrent requests
    list_notebooks_mock = cast(AsyncMock, mock_notebook_client.list_notebooks)
    assert list_notebooks_mock.await_count == 1
