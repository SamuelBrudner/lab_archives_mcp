"""Data models for LabArchives upload functionality.

These Pydantic models define the semantic contracts for uploading files to LabArchives.
All models enforce validation at construction time to fail fast.
"""

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator


class UploadRequest(BaseModel):
    """Request to upload a file to a LabArchives notebook page.

    Attributes:
        notebook_id: LabArchives notebook ID (nbid)
        parent_folder_id: Optional folder tree_id; None uploads to root
        page_title: Title for the new page to create
        file_path: Path to local file to upload
        caption: Optional caption for the attachment
        change_description: Optional audit log message
    """

    notebook_id: str = Field(..., min_length=1, description="LabArchives notebook ID")
    parent_folder_id: str | None = Field(
        None, description="Parent folder tree_id, or None for root"
    )
    page_title: str = Field(..., min_length=1, max_length=255, description="Page title")
    file_path: Path = Field(..., description="Path to file to upload")
    caption: str | None = Field(None, max_length=500, description="Attachment caption")
    change_description: str | None = Field(None, max_length=1000, description="Audit log message")

    @field_validator("file_path")
    @classmethod
    def validate_file_exists(cls, v: Path) -> Path:
        """Ensure file exists and is readable."""
        if not v.exists():
            raise FileNotFoundError(f"File not found: {v}")
        if not v.is_file():
            raise ValueError(f"Path is not a file: {v}")
        if not v.stat().st_size > 0:
            raise ValueError(f"File is empty: {v}")
        return v

    @field_validator("page_title")
    @classmethod
    def sanitize_title(cls, v: str) -> str:
        """Remove/escape invalid XML characters from title."""
        # Basic sanitization - remove control characters
        sanitized = "".join(char for char in v if ord(char) >= 32 or char in "\n\t")
        if not sanitized.strip():
            raise ValueError("Page title cannot be empty after sanitization")
        return sanitized.strip()


class PageCreationRequest(BaseModel):
    """Request to create a new page or folder in notebook hierarchy.

    Attributes:
        notebook_id: LabArchives notebook ID
        parent_tree_id: Parent folder ID (use "0" for root)
        display_text: Page or folder title
        is_folder: True to create folder, False for page
    """

    notebook_id: str = Field(..., min_length=1)
    parent_tree_id: str | int = Field(..., description="Parent folder tree_id or 0 for root")
    display_text: str = Field(..., min_length=1, max_length=255)
    is_folder: bool = Field(False, description="Create folder vs page")

    @field_validator("parent_tree_id")
    @classmethod
    def normalize_parent_id(cls, v: str | int) -> str:
        """Normalize parent_tree_id to string."""
        return str(v)


class PageCreationResult(BaseModel):
    """Result of creating a new page or folder.

    Attributes:
        tree_id: Base64-encoded tree identifier
        display_text: Page title as stored
        is_page: True if page, False if folder
    """

    tree_id: str = Field(..., description="Base64-encoded tree_id")
    display_text: str
    is_page: bool


class AttachmentUploadRequest(BaseModel):
    """Request to upload file as attachment to a page.

    Attributes:
        notebook_id: LabArchives notebook ID
        page_tree_id: Target page tree_id (from PageCreationResult)
        file_path: Path to file to upload
        filename: Filename to use in LabArchives (defaults to file_path.name)
        caption: Optional attachment caption
        change_description: Optional audit log message
    """

    notebook_id: str = Field(..., min_length=1)
    page_tree_id: str = Field(..., min_length=1, description="Target page tree_id")
    file_path: Path
    filename: str | None = Field(None, min_length=1, max_length=255)
    caption: str | None = Field(None, max_length=500)
    change_description: str | None = Field(None, max_length=1000)

    @field_validator("file_path")
    @classmethod
    def validate_file_exists(cls, v: Path) -> Path:
        """Ensure file exists and is readable."""
        if not v.exists():
            raise FileNotFoundError(f"File not found: {v}")
        if not v.is_file():
            raise ValueError(f"Path is not a file: {v}")
        return v

    @field_validator("filename")
    @classmethod
    def default_filename(cls, v: str | None, info: ValidationInfo) -> str:
        """Default filename to file_path.name if not provided."""
        if v is None:
            file_path = info.data.get("file_path")
            if file_path and isinstance(file_path, Path):
                return str(file_path.name)
            raise ValueError("filename required when file_path not provided")
        return v


class AttachmentUploadResult(BaseModel):
    """Result of uploading an attachment.

    Attributes:
        eid: Entry ID of the attachment
        part_type: Entry type (always 'attachment')
        filename: Stored filename
        caption: Attachment caption
        created_at: Creation timestamp
        file_size_bytes: Size of uploaded file
    """

    eid: str = Field(..., description="Entry ID")
    part_type: Literal["attachment"] = "attachment"
    filename: str
    caption: str | None = None
    created_at: datetime
    file_size_bytes: int = Field(..., ge=0)


class UploadResponse(BaseModel):
    """Complete response for file upload operation.

    Attributes:
        page_tree_id: tree_id of created/target page
        entry_id: eid of uploaded attachment
        page_url: Web URL to view page in LabArchives
        created_at: Timestamp of upload
        file_size_bytes: Size of uploaded file
        filename: Name of uploaded file
    """

    page_tree_id: str = Field(..., description="Created page tree_id")
    entry_id: str = Field(..., description="Attachment entry ID")
    page_url: str = Field(..., description="LabArchives web URL")
    created_at: datetime
    file_size_bytes: int = Field(..., ge=0)
    filename: str


class UploadError(BaseModel):
    """Structured error information for upload failures.

    Attributes:
        error_code: Machine-readable error code
        message: Human-readable error message
        details: Additional context
    """

    error_code: str = Field(..., description="ERROR_FILE_NOT_FOUND, ERROR_PERMISSION, etc")
    message: str
    details: dict[str, str] = Field(default_factory=dict)
