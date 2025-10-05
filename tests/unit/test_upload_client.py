"""Unit tests for LabArchives upload client methods.

Tests the insert_node, add_attachment, and upload_to_labarchives methods
of LabArchivesClient using mocked HTTP responses.
"""

# mypy: disable-error-code="misc"
# ruff: noqa: F841

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from labarchives_mcp.auth import AuthenticationManager
from labarchives_mcp.eln_client import LabArchivesClient
from labarchives_mcp.models.upload import (
    AttachmentUploadRequest,
    AttachmentUploadResult,
    PageCreationRequest,
    PageCreationResult,
    ProvenanceMetadata,
    UploadRequest,
    UploadResponse,
)


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock HTTP client."""
    return MagicMock()


@pytest.fixture
def mock_auth_manager(mock_client: MagicMock) -> MagicMock:
    """Create a mock authentication manager."""
    auth = MagicMock(spec=AuthenticationManager)
    auth._build_auth_params.return_value = {
        "akid": "test_key",
        "expires": "1234567890",
        "sig": "test_signature",
    }
    return auth


@pytest.fixture
def lab_client(mock_client: MagicMock, mock_auth_manager: MagicMock) -> LabArchivesClient:
    """Create a LabArchivesClient with mocked dependencies."""
    return LabArchivesClient(mock_client, mock_auth_manager)


class TestInsertNode:
    """Tests for insert_node method (creating pages/folders)."""

    def test_creates_page_with_correct_parameters(
        self, lab_client: LabArchivesClient, mock_client: MagicMock
    ) -> None:
        """Given page creation request, when calling insert_node, then sends correct API params."""
        # Arrange
        mock_response = MagicMock()
        mock_response.content = b"""<?xml version="1.0"?>
        <tree-tools>
            <node>
                <tree-id>BASE64_TREE_ID</tree-id>
                <display-text>New Analysis Page</display-text>
                <is-page type="boolean">true</is-page>
            </node>
        </tree-tools>
        """
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        request = PageCreationRequest(
            notebook_id="nbid123",
            parent_tree_id=0,
            display_text="New Analysis Page",
            is_folder=False,
        )

        # Act
        result = asyncio.run(lab_client.insert_node("uid123", request))

        # Assert
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://api.labarchives.com/api/tree_tools/insert_node"
        assert call_args[1]["params"]["uid"] == "uid123"
        assert call_args[1]["params"]["nbid"] == "nbid123"
        assert call_args[1]["params"]["parent_tree_id"] == "0"
        assert call_args[1]["params"]["display_text"] == "New Analysis Page"
        assert call_args[1]["params"]["is_folder"] == "false"

        assert isinstance(result, PageCreationResult)
        assert result.tree_id == "BASE64_TREE_ID"
        assert result.display_text == "New Analysis Page"
        assert result.is_page is True

    def test_creates_folder_with_is_folder_true(
        self, lab_client: LabArchivesClient, mock_client: MagicMock
    ) -> None:
        """Given folder creation request, when calling insert_node, then sets is_folder=true."""
        # Arrange
        mock_response = MagicMock()
        mock_response.content = b"""<?xml version="1.0"?>
        <tree-tools>
            <node>
                <tree-id>FOLDER_ID</tree-id>
                <display-text>New Folder</display-text>
                <is-page type="boolean">false</is-page>
            </node>
        </tree-tools>
        """
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        request = PageCreationRequest(
            notebook_id="nbid123",
            parent_tree_id=0,
            display_text="New Folder",
            is_folder=True,
        )

        # Act
        result = asyncio.run(lab_client.insert_node("uid123", request))

        # Assert
        call_args = mock_client.post.call_args
        assert call_args[1]["params"]["is_folder"] == "true"
        assert result.is_page is False

    def test_creates_page_under_parent_folder(
        self, lab_client: LabArchivesClient, mock_client: MagicMock
    ) -> None:
        """Given parent folder ID, when creating page, then uses correct parent_tree_id."""
        # Arrange
        mock_response = MagicMock()
        mock_response.content = b"""<?xml version="1.0"?>
        <tree-tools>
            <node>
                <tree-id>CHILD_PAGE_ID</tree-id>
                <display-text>Child Page</display-text>
                <is-page type="boolean">true</is-page>
            </node>
        </tree-tools>
        """
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        request = PageCreationRequest(
            notebook_id="nbid123",
            parent_tree_id="PARENT_FOLDER_ID",
            display_text="Child Page",
            is_folder=False,
        )

        # Act
        result = asyncio.run(lab_client.insert_node("uid123", request))

        # Assert
        call_args = mock_client.post.call_args
        assert call_args[1]["params"]["parent_tree_id"] == "PARENT_FOLDER_ID"


class TestAddAttachment:
    """Tests for add_attachment method (uploading files)."""

    def test_uploads_file_with_correct_parameters(
        self, lab_client: LabArchivesClient, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Given file upload request, when calling add_attachment, then sends file correctly."""
        # Arrange
        test_file = tmp_path / "test.ipynb"
        test_file.write_text('{"cells": []}')

        mock_response = MagicMock()
        mock_response.content = b"""<?xml version="1.0"?>
        <entries>
            <entry>
                <eid>ENTRY123</eid>
                <part-type>attachment</part-type>
                <filename>test.ipynb</filename>
                <caption>Test notebook</caption>
                <created-at>2025-09-30T12:00:00Z</created-at>
            </entry>
        </entries>
        """
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        request = AttachmentUploadRequest(
            notebook_id="nbid123",
            page_tree_id="PAGE_ID",
            file_path=test_file,
            filename=None,
            caption="Test notebook",
            change_description=None,
        )

        # Act
        result = asyncio.run(lab_client.add_attachment("uid123", request))

        # Assert
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://api.labarchives.com/api/entries/add_attachment"
        assert call_args[1]["params"]["uid"] == "uid123"
        assert call_args[1]["params"]["nbid"] == "nbid123"
        assert call_args[1]["params"]["pid"] == "PAGE_ID"
        assert call_args[1]["params"]["filename"] == "test.ipynb"
        assert call_args[1]["params"]["caption"] == "Test notebook"
        assert call_args[1]["headers"]["Content-Type"] == "application/octet-stream"

        assert isinstance(result, AttachmentUploadResult)
        assert result.eid == "ENTRY123"
        assert result.filename == "test.ipynb"

    def test_reads_file_content_correctly(
        self, lab_client: LabArchivesClient, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Given file with content, when uploading, then reads and sends file data."""
        # Arrange
        test_file = tmp_path / "data.txt"
        test_content = "test data content"
        test_file.write_text(test_content)

        mock_response = MagicMock()
        mock_response.content = b"""<?xml version="1.0"?>
        <entries>
            <entry>
                <eid>ENTRY456</eid>
                <part-type>attachment</part-type>
                <filename>data.txt</filename>
                <created-at>2025-09-30T12:00:00Z</created-at>
            </entry>
        </entries>
        """
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        request = AttachmentUploadRequest(
            notebook_id="nbid123",
            page_tree_id="PAGE_ID",
            file_path=test_file,
            filename=None,
            caption=None,
            change_description=None,
        )

        # Act
        result = asyncio.run(lab_client.add_attachment("uid123", request))

        # Assert
        call_args = mock_client.post.call_args
        assert call_args[1]["content"] == test_content.encode()


class TestAddEntry:
    """Tests for add_entry method (adding text/metadata entries)."""

    def test_adds_text_entry_with_html_content(
        self, lab_client: LabArchivesClient, mock_client: MagicMock
    ) -> None:
        """Given HTML content, when adding text entry, then sends correct parameters."""
        # Arrange
        mock_response = MagicMock()
        mock_response.content = b"""<?xml version="1.0"?>
        <entries>
            <entry>
                <eid>TEXT_ENTRY_123</eid>
                <part-type>text entry</part-type>
                <created-at>2025-09-30T12:00:00Z</created-at>
            </entry>
        </entries>
        """
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        html_content = "<p>Analysis results</p>"

        # Act
        result = asyncio.run(
            lab_client.add_entry(
                uid="uid123",
                notebook_id="nbid123",
                page_tree_id="PAGE_ID",
                part_type="text entry",
                entry_data=html_content,
            )
        )

        # Assert
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://api.labarchives.com/api/entries/add_entry"
        assert call_args[1]["params"]["part_type"] == "text entry"
        assert call_args[1]["params"]["entry_data"] == html_content

    def test_adds_plain_text_entry(
        self, lab_client: LabArchivesClient, mock_client: MagicMock
    ) -> None:
        """Given plain text, when adding plain text entry, then uses correct part_type."""
        # Arrange
        mock_response = MagicMock()
        mock_response.content = b"""<?xml version="1.0"?>
        <entries>
            <entry>
                <eid>PLAIN_TEXT_123</eid>
                <part-type>plain text entry</part-type>
                <created-at>2025-09-30T12:00:00Z</created-at>
            </entry>
        </entries>
        """
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        plain_text = "Code Provenance\n\nCommit: abc123"

        # Act
        result = asyncio.run(
            lab_client.add_entry(
                uid="uid123",
                notebook_id="nbid123",
                page_tree_id="PAGE_ID",
                part_type="plain text entry",
                entry_data=plain_text,
            )
        )

        # Assert
        call_args = mock_client.post.call_args
        assert call_args[1]["params"]["part_type"] == "plain text entry"


class TestUploadToLabArchives:
    """Tests for upload_to_labarchives orchestration method."""

    def test_orchestrates_complete_upload_workflow(
        self, lab_client: LabArchivesClient, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Given upload request, when uploading, then creates page, uploads file, adds metadata."""
        # Arrange
        test_file = tmp_path / "analysis.ipynb"
        test_file.write_text('{"cells": []}')

        metadata = ProvenanceMetadata(
            git_commit_sha="a" * 40,
            git_branch="main",
            git_repo_url="https://github.com/user/repo",
            git_is_dirty=False,
            code_version=None,
            executed_at=datetime(2025, 9, 30, 12, 0, 0, tzinfo=UTC),
            python_version="3.11.8",
            os_name="Darwin",
            hostname=None,
        )

        request = UploadRequest(
            notebook_id="nbid123",
            parent_folder_id=None,
            page_title="Analysis Results",
            file_path=test_file,
            caption=None,
            change_description=None,
            metadata=metadata,
            allow_dirty_git=False,
            create_as_text=False,
        )

        # Mock responses
        page_response = MagicMock()
        page_response.content = b"""<?xml version="1.0"?>
        <tree-tools>
            <node>
                <tree-id>NEW_PAGE_ID</tree-id>
                <display-text>Analysis Results</display-text>
                <is-page type="boolean">true</is-page>
            </node>
        </tree-tools>
        """
        page_response.raise_for_status = MagicMock()

        attachment_response = MagicMock()
        attachment_response.content = b"""<?xml version="1.0"?>
        <entries>
            <entry>
                <eid>ATTACH_123</eid>
                <part-type>attachment</part-type>
                <filename>analysis.ipynb</filename>
                <created-at>2025-09-30T12:00:00Z</created-at>
            </entry>
        </entries>
        """
        attachment_response.raise_for_status = MagicMock()

        metadata_response = MagicMock()
        metadata_response.content = b"""<?xml version="1.0"?>
        <entries>
            <entry>
                <eid>META_123</eid>
                <part-type>plain text entry</part-type>
                <created-at>2025-09-30T12:00:00Z</created-at>
            </entry>
        </entries>
        """
        metadata_response.raise_for_status = MagicMock()

        mock_client.post = AsyncMock(
            side_effect=[page_response, attachment_response, metadata_response]
        )

        # Act
        result = asyncio.run(lab_client.upload_to_labarchives("uid123", request))

        # Assert
        assert mock_client.post.call_count == 3  # page, attachment, metadata
        assert isinstance(result, UploadResponse)
        assert result.page_tree_id == "NEW_PAGE_ID"
        assert result.entry_id == "ATTACH_123"
        assert result.filename == "analysis.ipynb"

    def test_refuses_dirty_git_without_override(
        self, lab_client: LabArchivesClient, tmp_path: Path
    ) -> None:
        """Given dirty Git without allow flag, when uploading, then raises ValidationError."""
        # Arrange
        test_file = tmp_path / "analysis.ipynb"
        test_file.write_text('{"cells": []}')

        metadata = ProvenanceMetadata(
            git_commit_sha="a" * 40,
            git_branch="main",
            git_repo_url="https://github.com/user/repo",
            git_is_dirty=True,  # Dirty!
            code_version=None,
            executed_at=datetime.now(UTC),
            python_version="3.11.8",
            os_name="Darwin",
            hostname=None,
        )

        request = UploadRequest(
            notebook_id="nbid123",
            parent_folder_id=None,
            page_title="Analysis",
            file_path=test_file,
            caption=None,
            change_description=None,
            metadata=metadata,
            allow_dirty_git=False,
            create_as_text=False,
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            asyncio.run(lab_client.upload_to_labarchives("uid123", request))

        assert "dirty" in str(exc_info.value).lower()
        assert "uncommitted" in str(exc_info.value).lower()

    def test_requires_metadata_for_notebook_files(
        self, lab_client: LabArchivesClient, tmp_path: Path
    ) -> None:
        """Given .ipynb file without metadata, when uploading, then raises ValidationError."""
        # Arrange
        test_file = tmp_path / "analysis.ipynb"
        test_file.write_text('{"cells": []}')

        request = UploadRequest(
            notebook_id="nbid123",
            parent_folder_id=None,
            page_title="Analysis",
            file_path=test_file,
            caption=None,
            change_description=None,
            metadata=None,  # Missing!
            allow_dirty_git=False,
            create_as_text=False,
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            asyncio.run(lab_client.upload_to_labarchives("uid123", request))

        assert "metadata" in str(exc_info.value).lower()
        assert "required" in str(exc_info.value).lower()

    def test_requires_metadata_for_python_files(
        self, lab_client: LabArchivesClient, tmp_path: Path
    ) -> None:
        """Given .py file without metadata, when uploading, then raises ValidationError."""
        # Arrange
        test_file = tmp_path / "script.py"
        test_file.write_text("print('hello')")

        request = UploadRequest(
            notebook_id="nbid123",
            parent_folder_id=None,
            page_title="Script",
            file_path=test_file,
            caption=None,
            change_description=None,
            metadata=None,  # Missing!
            allow_dirty_git=False,
            create_as_text=False,
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            asyncio.run(lab_client.upload_to_labarchives("uid123", request))

        assert "metadata" in str(exc_info.value).lower()
