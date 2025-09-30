"""Tests for page-level reading functionality."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from labarchives_mcp.eln_client import LabArchivesClient


@pytest.fixture  # type: ignore[misc]
def mock_client() -> MagicMock:
    """Create a mock httpx client."""
    client = MagicMock()
    client.get = AsyncMock()
    return client


@pytest.fixture  # type: ignore[misc]
def mock_auth_manager() -> MagicMock:
    """Create a mock authentication manager."""
    auth = MagicMock()
    auth._build_auth_params = MagicMock(
        return_value={"akid": "test", "expires": "123", "sig": "abc"}
    )
    return auth


@pytest.fixture  # type: ignore[misc]
def lab_client(mock_client: MagicMock, mock_auth_manager: MagicMock) -> LabArchivesClient:
    """Create a LabArchivesClient with mocked dependencies."""
    return LabArchivesClient(mock_client, mock_auth_manager)


class TestGetNotebookTree:
    """Tests for get_notebook_tree method."""

    def test_returns_pages_and_folders(
        self, lab_client: LabArchivesClient, mock_client: MagicMock
    ) -> None:
        """Given tree XML, when parsing, then returns structured nodes."""
        xml_response = """<?xml version="1.0"?>
        <tree-tools>
            <level-node>
                <tree-id>123</tree-id>
                <display-text>Introduction</display-text>
                <is-page>true</is-page>
            </level-node>
            <level-node>
                <tree-id>456</tree-id>
                <display-text>Methods</display-text>
                <is-page>false</is-page>
            </level-node>
        </tree-tools>
        """

        mock_response = MagicMock()
        mock_response.content = xml_response.encode()
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        result = asyncio.run(lab_client.get_notebook_tree("uid123", "nbid456", 0))

        assert len(result) == 2
        assert result[0]["tree_id"] == "123"
        assert result[0]["display_text"] == "Introduction"
        assert result[0]["is_page"] is True
        assert result[0]["is_folder"] is False

        assert result[1]["tree_id"] == "456"
        assert result[1]["display_text"] == "Methods"
        assert result[1]["is_page"] is False
        assert result[1]["is_folder"] is True

    def test_calls_correct_api_endpoint(
        self, lab_client: LabArchivesClient, mock_client: MagicMock
    ) -> None:
        """Given parameters, when calling API, then uses correct endpoint and params."""
        mock_response = MagicMock()
        mock_response.content = b"<?xml version='1.0'?><tree-tools></tree-tools>"
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        asyncio.run(lab_client.get_notebook_tree("uid123", "nbid456", 5))

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "https://api.labarchives.com/api/tree_tools/get_tree_level"
        assert call_args[1]["params"]["uid"] == "uid123"
        assert call_args[1]["params"]["nbid"] == "nbid456"
        assert call_args[1]["params"]["parent_tree_id"] == "5"

    def test_navigates_into_folders(
        self, lab_client: LabArchivesClient, mock_client: MagicMock
    ) -> None:
        """Given non-zero parent_tree_id, when calling API, then navigates into folder."""
        mock_response = MagicMock()
        mock_response.content = b"""<?xml version='1.0'?>
        <tree-tools>
            <level-node>
                <tree-id>sub123</tree-id>
                <display-text>Sub-page 1</display-text>
                <is-page>true</is-page>
            </level-node>
        </tree-tools>
        """
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        # Simulate navigating into folder with parent_tree_id=100
        result = asyncio.run(lab_client.get_notebook_tree("uid123", "nbid456", 100))

        assert len(result) == 1
        assert result[0]["display_text"] == "Sub-page 1"
        assert result[0]["is_page"] is True

        # Verify API was called with correct parent_tree_id
        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["parent_tree_id"] == "100"


class TestGetPageEntries:
    """Tests for get_page_entries method."""

    def test_returns_entries_with_content(
        self, lab_client: LabArchivesClient, mock_client: MagicMock
    ) -> None:
        """Given page with entries, when reading with data, then returns content."""
        xml_response = """<?xml version="1.0"?>
        <tree-tools>
            <entry>
                <eid>e123</eid>
                <part-type>text_entry</part-type>
                <created-at>2025-01-01T00:00:00Z</created-at>
                <updated-at>2025-01-02T00:00:00Z</updated-at>
                <entry-data>This is the entry content</entry-data>
            </entry>
            <entry>
                <eid>e456</eid>
                <part-type>heading</part-type>
                <created-at>2025-01-01T00:00:00Z</created-at>
                <updated-at>2025-01-01T00:00:00Z</updated-at>
                <entry-data>Section Title</entry-data>
            </entry>
        </tree-tools>
        """

        mock_response = MagicMock()
        mock_response.content = xml_response.encode()
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        result = asyncio.run(
            lab_client.get_page_entries("uid123", "nbid456", 789, include_data=True)
        )

        assert len(result) == 2
        assert result[0]["eid"] == "e123"
        assert result[0]["part_type"] == "text_entry"
        assert result[0]["content"] == "This is the entry content"

        assert result[1]["eid"] == "e456"
        assert result[1]["part_type"] == "heading"
        assert result[1]["content"] == "Section Title"

    def test_excludes_content_when_not_requested(
        self, lab_client: LabArchivesClient, mock_client: MagicMock
    ) -> None:
        """Given include_data=False, when reading page, then omits content."""
        xml_response = """<?xml version="1.0"?>
        <tree-tools>
            <entry>
                <eid>e123</eid>
                <part-type>text_entry</part-type>
                <created-at>2025-01-01T00:00:00Z</created-at>
                <updated-at>2025-01-02T00:00:00Z</updated-at>
            </entry>
        </tree-tools>
        """

        mock_response = MagicMock()
        mock_response.content = xml_response.encode()
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        result = asyncio.run(
            lab_client.get_page_entries("uid123", "nbid456", 789, include_data=False)
        )

        assert len(result) == 1
        assert "content" not in result[0]

    def test_passes_correct_parameters(
        self, lab_client: LabArchivesClient, mock_client: MagicMock
    ) -> None:
        """Given parameters, when calling API, then passes correct values."""
        mock_response = MagicMock()
        mock_response.content = b"<?xml version='1.0'?><tree-tools></tree-tools>"
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        asyncio.run(lab_client.get_page_entries("uid123", "nbid456", 789, include_data=True))

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "https://api.labarchives.com/api/tree_tools/get_entries_for_page"
        assert call_args[1]["params"]["uid"] == "uid123"
        assert call_args[1]["params"]["nbid"] == "nbid456"
        assert call_args[1]["params"]["page_tree_id"] == "789"
        assert call_args[1]["params"]["entry_data"] == "true"
