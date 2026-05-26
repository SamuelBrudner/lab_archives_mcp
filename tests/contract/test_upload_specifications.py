"""Specification tests for LabArchives upload functionality.

These tests describe the expected behavior of the upload system from a user perspective,
following behavior-driven development (BDD) principles.
"""

# mypy: disable-error-code="call-arg,union-attr"
# ruff: noqa: E501

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from labarchives_mcp.models.upload import ProvenanceMetadata, UploadRequest


class TestProvenanceMetadataSpecifications:
    """Specifications for code provenance metadata."""

    def test_valid_metadata_is_accepted(self) -> None:
        """Given valid Git and execution metadata, when creating ProvenanceMetadata, then it succeeds."""
        # Arrange
        metadata = ProvenanceMetadata(
            git_commit_sha="a" * 40,
            git_branch="main",
            git_repo_url="https://github.com/user/repo",
            git_is_dirty=False,
            executed_at=datetime.now(UTC),
            python_version="3.11.8",
            dependencies={"numpy": "1.26.0"},
            os_name="Darwin",
            hostname="laptop.local",
        )

        # Assert
        assert metadata.git_commit_sha == "a" * 40
        assert metadata.git_is_dirty is False

    def test_invalid_commit_sha_is_rejected(self) -> None:
        """Given invalid Git SHA, when creating ProvenanceMetadata, then validation fails."""
        with pytest.raises(ValidationError) as exc_info:
            ProvenanceMetadata(
                git_commit_sha="invalid",  # Too short
                git_branch="main",
                git_repo_url="https://github.com/user/repo",
                git_is_dirty=False,
                executed_at=datetime.now(UTC),
                python_version="3.11.8",
                os_name="Darwin",
            )

        assert "git_commit_sha" in str(exc_info.value)

    def test_invalid_python_version_is_rejected(self) -> None:
        """Given invalid Python version, when creating ProvenanceMetadata, then validation fails."""
        with pytest.raises(ValidationError) as exc_info:
            ProvenanceMetadata(
                git_commit_sha="a" * 40,
                git_branch="main",
                git_repo_url="https://github.com/user/repo",
                git_is_dirty=False,
                executed_at=datetime.now(UTC),
                python_version="3.11",  # Missing patch version
                os_name="Darwin",
            )

        assert "python_version" in str(exc_info.value)

    def test_metadata_renders_to_markdown(self) -> None:
        """Given valid metadata, when rendering to markdown, then produces human-readable format."""
        # Arrange
        metadata = ProvenanceMetadata(
            git_commit_sha="a" * 40,
            git_branch="main",
            git_repo_url="https://github.com/user/repo",
            git_is_dirty=False,
            executed_at=datetime(2025, 9, 30, 12, 0, 0, tzinfo=UTC),
            python_version="3.11.8",
            dependencies={"numpy": "1.26.0", "pandas": "2.1.0"},
            os_name="Darwin",
            hostname="laptop.local",
        )

        # Act
        markdown = metadata.to_markdown()

        # Assert
        assert "## Code Provenance" in markdown
        assert "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" in markdown
        assert "main" in markdown
        assert "✅ Clean" in markdown
        assert "numpy==1.26.0" in markdown
        assert "pandas==2.1.0" in markdown

    def test_dirty_git_state_shows_warning(self) -> None:
        """Given dirty Git state, when rendering to markdown, then shows warning."""
        # Arrange
        metadata = ProvenanceMetadata(
            git_commit_sha="a" * 40,
            git_branch="main",
            git_repo_url="https://github.com/user/repo",
            git_is_dirty=True,  # Uncommitted changes
            executed_at=datetime.now(UTC),
            python_version="3.11.8",
            os_name="Darwin",
        )

        # Act
        markdown = metadata.to_markdown()

        # Assert
        assert "⚠️ Dirty" in markdown


class TestUploadRequestSpecifications:
    """Specifications for upload request validation."""

    def test_valid_upload_request_is_accepted(self, tmp_path: Path) -> None:
        """Given valid notebook ID and existing file, when creating UploadRequest, then it succeeds."""
        # Arrange
        test_file = tmp_path / "analysis.ipynb"
        test_file.write_text('{"cells": []}')

        metadata = ProvenanceMetadata(
            git_commit_sha="a" * 40,
            git_branch="main",
            git_repo_url="https://github.com/user/repo",
            git_is_dirty=False,
            executed_at=datetime.now(UTC),
            python_version="3.11.8",
            os_name="Darwin",
        )

        # Act
        request = UploadRequest(
            notebook_id="nbid123",
            page_title="Analysis Results",
            file_path=test_file,
            metadata=metadata,
        )

        # Assert
        assert request.notebook_id == "nbid123"
        assert request.file_path == test_file
        assert request.metadata is not None

    def test_missing_file_is_rejected(self) -> None:
        """Given non-existent file path, when creating UploadRequest, then validation fails."""
        # Arrange
        missing_file = Path("/does/not/exist.ipynb")

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            UploadRequest(
                notebook_id="nbid123",
                page_title="Analysis Results",
                file_path=missing_file,
            )

    def test_empty_file_is_rejected(self, tmp_path: Path) -> None:
        """Given empty file, when creating UploadRequest, then validation fails."""
        # Arrange
        empty_file = tmp_path / "empty.txt"
        empty_file.touch()  # Create empty file

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            UploadRequest(
                notebook_id="nbid123",
                page_title="Test",
                file_path=empty_file,
            )

        assert "empty" in str(exc_info.value).lower()

    def test_directory_path_is_rejected(self, tmp_path: Path) -> None:
        """Given directory path instead of file, when creating UploadRequest, then validation fails."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            UploadRequest(
                notebook_id="nbid123",
                page_title="Test",
                file_path=tmp_path,  # Directory, not file
            )

        assert "not a file" in str(exc_info.value).lower()

    def test_title_with_control_characters_is_sanitized(self, tmp_path: Path) -> None:
        """Given title with control characters, when creating UploadRequest, then title is sanitized."""
        # Arrange
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Act
        request = UploadRequest(
            notebook_id="nbid123",
            page_title="Title\x00with\x01control\x02chars",
            file_path=test_file,
        )

        # Assert
        assert "\x00" not in request.page_title
        assert "\x01" not in request.page_title
        assert "Title" in request.page_title

    def test_empty_title_after_sanitization_is_rejected(self, tmp_path: Path) -> None:
        """Given title with only control characters, when sanitizing, then validation fails."""
        # Arrange
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            UploadRequest(
                notebook_id="nbid123",
                page_title="\x00\x01\x02",  # Only control characters
                file_path=test_file,
            )

        assert "empty" in str(exc_info.value).lower()


class TestMetadataRequirementSpecifications:
    """Specifications for mandatory metadata on code/notebook uploads."""

    def test_notebook_upload_without_metadata_should_warn(self, tmp_path: Path) -> None:
        """Given .ipynb file upload without metadata, when validating, then should be flagged.

        Note: This is a specification for future validation logic - currently just documents intent.
        """
        # Arrange
        notebook_file = tmp_path / "analysis.ipynb"
        notebook_file.write_text('{"cells": []}')

        # Act - Currently allows, but should validate in implementation
        request = UploadRequest(
            notebook_id="nbid123",
            page_title="Analysis",
            file_path=notebook_file,
            metadata=None,  # Missing metadata for notebook!
        )

        # Assert - Document expected behavior
        assert request.file_path.suffix == ".ipynb"
        assert request.metadata is None
        # TODO: Implementation should raise ValidationError for .ipynb without metadata

    def test_python_file_upload_without_metadata_should_warn(self, tmp_path: Path) -> None:
        """Given .py file upload without metadata, when validating, then should be flagged."""
        # Arrange
        python_file = tmp_path / "script.py"
        python_file.write_text("print('hello')")

        # Act
        request = UploadRequest(
            notebook_id="nbid123",
            page_title="Script",
            file_path=python_file,
            metadata=None,  # Missing metadata for code!
        )

        # Assert
        assert request.file_path.suffix == ".py"
        assert request.metadata is None
        # TODO: Implementation should raise ValidationError for .py without metadata

    def test_dirty_git_without_allow_flag_should_warn(self, tmp_path: Path) -> None:
        """Given dirty Git state without allow_dirty_git, when validating, then should be flagged."""
        # Arrange
        test_file = tmp_path / "analysis.ipynb"
        test_file.write_text('{"cells": []}')

        metadata = ProvenanceMetadata(
            git_commit_sha="a" * 40,
            git_branch="main",
            git_repo_url="https://github.com/user/repo",
            git_is_dirty=True,  # Dirty!
            executed_at=datetime.now(UTC),
            python_version="3.11.8",
            os_name="Darwin",
        )

        # Act
        request = UploadRequest(
            notebook_id="nbid123",
            page_title="Analysis",
            file_path=test_file,
            metadata=metadata,
            allow_dirty_git=False,  # Not allowed
        )

        # Assert
        assert request.metadata.git_is_dirty is True
        assert request.allow_dirty_git is False
        # TODO: Implementation should raise ValidationError for dirty Git without override

    def test_dirty_git_with_allow_flag_is_accepted(self, tmp_path: Path) -> None:
        """Given dirty Git state WITH allow_dirty_git flag, when validating, then accepts."""
        # Arrange
        test_file = tmp_path / "analysis.ipynb"
        test_file.write_text('{"cells": []}')

        metadata = ProvenanceMetadata(
            git_commit_sha="a" * 40,
            git_branch="main",
            git_repo_url="https://github.com/user/repo",
            git_is_dirty=True,  # Dirty!
            executed_at=datetime.now(UTC),
            python_version="3.11.8",
            os_name="Darwin",
        )

        # Act
        request = UploadRequest(
            notebook_id="nbid123",
            page_title="Analysis",
            file_path=test_file,
            metadata=metadata,
            allow_dirty_git=True,  # Explicit override
        )

        # Assert
        assert request.metadata.git_is_dirty is True
        assert request.allow_dirty_git is True
        # This should be accepted (user explicitly overrode safety check)
