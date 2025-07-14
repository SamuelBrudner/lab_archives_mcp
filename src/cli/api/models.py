"""
LabArchives API Data Models

This module defines Pydantic data models and type definitions for LabArchives API entities
including notebooks, pages, entries, and user context. These models provide structured,
validated representations for secure API integration and downstream processing.

The models support:
- Strict type validation and serialization
- JSON/XML response parsing from LabArchives API
- MCP resource construction and metadata preservation
- Comprehensive field documentation for API integration

All models are designed for stateless operation with no persistent storage requirements.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field, EmailStr, constr, conint  # pydantic>=2.11.7


class NotebookMetadata(BaseModel):
    """
    Represents a LabArchives notebook with metadata and summary information.
    
    This model provides a structured representation of notebook data retrieved from
    the LabArchives API, including ownership, timestamps, and content summary metrics.
    Used for resource discovery and listing operations in the MCP server.
    
    Attributes:
        id: Unique notebook identifier from LabArchives
        name: Human-readable notebook display name
        description: Optional notebook description or summary
        owner: Username of the notebook owner
        created_date: Timestamp when notebook was created
        last_modified: Timestamp of last modification
        folder_count: Number of folders within the notebook
        page_count: Number of pages within the notebook
    """
    
    id: constr(min_length=1, max_length=255) = Field(
        description="Unique notebook identifier from LabArchives API",
        example="nb_123456"
    )
    
    name: constr(min_length=1, max_length=500) = Field(
        description="Human-readable notebook display name",
        example="Protein Analysis Lab Notebook"
    )
    
    description: Optional[constr(max_length=2000)] = Field(
        default=None,
        description="Optional notebook description or summary",
        example="Research notebook for protein structure analysis experiments"
    )
    
    owner: constr(min_length=1, max_length=255) = Field(
        description="Username of the notebook owner",
        example="researcher@university.edu"
    )
    
    created_date: datetime = Field(
        description="Timestamp when notebook was created",
        example="2024-01-15T10:30:00Z"
    )
    
    last_modified: datetime = Field(
        description="Timestamp of last modification to notebook",
        example="2024-11-20T14:22:35Z"
    )
    
    folder_count: conint(ge=0) = Field(
        description="Number of folders within the notebook",
        example=5
    )
    
    page_count: conint(ge=0) = Field(
        description="Number of pages within the notebook",
        example=24
    )

    class Config:
        """Pydantic configuration for NotebookMetadata model."""
        json_schema_extra = {
            "example": {
                "id": "nb_123456",
                "name": "Protein Analysis Lab Notebook",
                "description": "Research notebook for protein structure analysis experiments",
                "owner": "researcher@university.edu",
                "created_date": "2024-01-15T10:30:00Z",
                "last_modified": "2024-11-20T14:22:35Z",
                "folder_count": 5,
                "page_count": 24
            }
        }


class PageMetadata(BaseModel):
    """
    Represents a LabArchives page with metadata and hierarchical context.
    
    This model captures page-level information including its parent notebook,
    folder organization, and content summary. Used for resource discovery
    and hierarchical navigation within the MCP server.
    
    Attributes:
        id: Unique page identifier from LabArchives
        notebook_id: Parent notebook identifier
        title: Page title or heading
        folder_path: Optional folder hierarchy path
        created_date: Timestamp when page was created
        last_modified: Timestamp of last modification
        entry_count: Number of entries on the page
        author: Username of the page author
    """
    
    id: constr(min_length=1, max_length=255) = Field(
        description="Unique page identifier from LabArchives API",
        example="page_789012"
    )
    
    notebook_id: constr(min_length=1, max_length=255) = Field(
        description="Parent notebook identifier",
        example="nb_123456"
    )
    
    title: constr(min_length=1, max_length=500) = Field(
        description="Page title or heading",
        example="Experiment 1: Protein Purification Protocol"
    )
    
    folder_path: Optional[constr(max_length=1000)] = Field(
        default=None,
        description="Optional folder hierarchy path within notebook",
        example="/Experiments/Protein Analysis/Purification"
    )
    
    created_date: datetime = Field(
        description="Timestamp when page was created",
        example="2024-01-16T09:15:00Z"
    )
    
    last_modified: datetime = Field(
        description="Timestamp of last modification to page",
        example="2024-11-20T16:45:12Z"
    )
    
    entry_count: conint(ge=0) = Field(
        description="Number of entries on this page",
        example=8
    )
    
    author: constr(min_length=1, max_length=255) = Field(
        description="Username of the page author",
        example="researcher@university.edu"
    )

    class Config:
        """Pydantic configuration for PageMetadata model."""
        json_schema_extra = {
            "example": {
                "id": "page_789012",
                "notebook_id": "nb_123456",
                "title": "Experiment 1: Protein Purification Protocol",
                "folder_path": "/Experiments/Protein Analysis/Purification",
                "created_date": "2024-01-16T09:15:00Z",
                "last_modified": "2024-11-20T16:45:12Z",
                "entry_count": 8,
                "author": "researcher@university.edu"
            }
        }


class EntryContent(BaseModel):
    """
    Represents a LabArchives entry with content, metadata, and versioning.
    
    This model captures individual entry data including text content, attachments,
    and associated metadata. Supports various entry types (text, attachment, table)
    and maintains version history for content tracking.
    
    Attributes:
        id: Unique entry identifier from LabArchives
        page_id: Parent page identifier
        entry_type: Type of entry (text, attachment, table, etc.)
        title: Optional entry title or caption
        content: Entry content or description
        created_date: Timestamp when entry was created
        last_modified: Timestamp of last modification
        author: Username of the entry author
        version: Entry version number for tracking changes
        metadata: Additional entry metadata and attributes
    """
    
    id: constr(min_length=1, max_length=255) = Field(
        description="Unique entry identifier from LabArchives API",
        example="entry_345678"
    )
    
    page_id: constr(min_length=1, max_length=255) = Field(
        description="Parent page identifier",
        example="page_789012"
    )
    
    entry_type: constr(min_length=1, max_length=50) = Field(
        description="Type of entry (text, attachment, table, image, etc.)",
        example="text"
    )
    
    title: Optional[constr(max_length=500)] = Field(
        default=None,
        description="Optional entry title or caption",
        example="Experimental Procedure"
    )
    
    content: str = Field(
        description="Entry content, description, or file information",
        example="1. Prepare protein sample in buffer solution...",
        max_length=100000  # Support large text content
    )
    
    created_date: datetime = Field(
        description="Timestamp when entry was created",
        example="2024-01-16T10:30:00Z"
    )
    
    last_modified: datetime = Field(
        description="Timestamp of last modification to entry",
        example="2024-11-20T17:12:48Z"
    )
    
    author: constr(min_length=1, max_length=255) = Field(
        description="Username of the entry author",
        example="researcher@university.edu"
    )
    
    version: conint(ge=1) = Field(
        description="Entry version number for tracking changes",
        example=3
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional entry metadata and attributes",
        example={
            "file_size": 2048,
            "mime_type": "text/plain",
            "attachment_count": 2,
            "tags": ["protein", "purification", "experiment"]
        }
    )

    class Config:
        """Pydantic configuration for EntryContent model."""
        json_schema_extra = {
            "example": {
                "id": "entry_345678",
                "page_id": "page_789012",
                "entry_type": "text",
                "title": "Experimental Procedure",
                "content": "1. Prepare protein sample in buffer solution...",
                "created_date": "2024-01-16T10:30:00Z",
                "last_modified": "2024-11-20T17:12:48Z",
                "author": "researcher@university.edu",
                "version": 3,
                "metadata": {
                    "file_size": 2048,
                    "mime_type": "text/plain",
                    "attachment_count": 2,
                    "tags": ["protein", "purification", "experiment"]
                }
            }
        }


class UserContext(BaseModel):
    """
    Represents authenticated LabArchives user context and permissions.
    
    This model captures user identity information obtained from LabArchives
    authentication, including user ID, profile information, and assigned roles.
    Used for session management and access control validation.
    
    Attributes:
        uid: Unique user identifier from LabArchives
        name: User's full name
        email: User's email address
        roles: List of assigned user roles and permissions
    """
    
    uid: constr(min_length=1, max_length=255) = Field(
        description="Unique user identifier from LabArchives",
        example="user_987654"
    )
    
    name: constr(min_length=1, max_length=255) = Field(
        description="User's full name",
        example="Dr. Sarah Johnson"
    )
    
    email: EmailStr = Field(
        description="User's email address",
        example="sarah.johnson@university.edu"
    )
    
    roles: List[constr(min_length=1, max_length=100)] = Field(
        description="List of assigned user roles and permissions",
        example=["researcher", "notebook_owner", "collaborator"]
    )

    class Config:
        """Pydantic configuration for UserContext model."""
        json_schema_extra = {
            "example": {
                "uid": "user_987654",
                "name": "Dr. Sarah Johnson",
                "email": "sarah.johnson@university.edu",
                "roles": ["researcher", "notebook_owner", "collaborator"]
            }
        }


class NotebookListResponse(BaseModel):
    """
    Represents the API response for a notebook listing request.
    
    This model wraps the notebook metadata list returned by the LabArchives API,
    including status information and optional response messages. Used for
    parsing and validating notebook discovery responses.
    
    Attributes:
        notebooks: List of notebook metadata objects
        status: Optional response status indicator
        message: Optional response message or error description
    """
    
    notebooks: List[NotebookMetadata] = Field(
        description="List of notebook metadata objects",
        example=[
            {
                "id": "nb_123456",
                "name": "Protein Analysis Lab Notebook",
                "description": "Research notebook for protein structure analysis",
                "owner": "researcher@university.edu",
                "created_date": "2024-01-15T10:30:00Z",
                "last_modified": "2024-11-20T14:22:35Z",
                "folder_count": 5,
                "page_count": 24
            }
        ]
    )
    
    status: Optional[constr(max_length=50)] = Field(
        default=None,
        description="Optional response status indicator",
        example="success"
    )
    
    message: Optional[constr(max_length=500)] = Field(
        default=None,
        description="Optional response message or error description",
        example="Successfully retrieved 3 notebooks"
    )

    class Config:
        """Pydantic configuration for NotebookListResponse model."""
        json_schema_extra = {
            "example": {
                "notebooks": [
                    {
                        "id": "nb_123456",
                        "name": "Protein Analysis Lab Notebook",
                        "description": "Research notebook for protein structure analysis",
                        "owner": "researcher@university.edu",
                        "created_date": "2024-01-15T10:30:00Z",
                        "last_modified": "2024-11-20T14:22:35Z",
                        "folder_count": 5,
                        "page_count": 24
                    }
                ],
                "status": "success",
                "message": "Successfully retrieved 3 notebooks"
            }
        }


class PageListResponse(BaseModel):
    """
    Represents the API response for a page listing request.
    
    This model wraps the page metadata list returned by the LabArchives API,
    including status information and optional response messages. Used for
    parsing and validating page discovery responses within notebooks.
    
    Attributes:
        pages: List of page metadata objects
        status: Optional response status indicator
        message: Optional response message or error description
    """
    
    pages: List[PageMetadata] = Field(
        description="List of page metadata objects",
        example=[
            {
                "id": "page_789012",
                "notebook_id": "nb_123456",
                "title": "Experiment 1: Protein Purification Protocol",
                "folder_path": "/Experiments/Protein Analysis/Purification",
                "created_date": "2024-01-16T09:15:00Z",
                "last_modified": "2024-11-20T16:45:12Z",
                "entry_count": 8,
                "author": "researcher@university.edu"
            }
        ]
    )
    
    status: Optional[constr(max_length=50)] = Field(
        default=None,
        description="Optional response status indicator",
        example="success"
    )
    
    message: Optional[constr(max_length=500)] = Field(
        default=None,
        description="Optional response message or error description",
        example="Successfully retrieved 12 pages from notebook"
    )

    class Config:
        """Pydantic configuration for PageListResponse model."""
        json_schema_extra = {
            "example": {
                "pages": [
                    {
                        "id": "page_789012",
                        "notebook_id": "nb_123456",
                        "title": "Experiment 1: Protein Purification Protocol",
                        "folder_path": "/Experiments/Protein Analysis/Purification",
                        "created_date": "2024-01-16T09:15:00Z",
                        "last_modified": "2024-11-20T16:45:12Z",
                        "entry_count": 8,
                        "author": "researcher@university.edu"
                    }
                ],
                "status": "success",
                "message": "Successfully retrieved 12 pages from notebook"
            }
        }


class EntryListResponse(BaseModel):
    """
    Represents the API response for entry listing or content retrieval.
    
    This model wraps the entry content list returned by the LabArchives API,
    including status information and optional response messages. Used for
    parsing and validating entry content responses from pages.
    
    Attributes:
        entries: List of entry content objects
        status: Optional response status indicator
        message: Optional response message or error description
    """
    
    entries: List[EntryContent] = Field(
        description="List of entry content objects",
        example=[
            {
                "id": "entry_345678",
                "page_id": "page_789012",
                "entry_type": "text",
                "title": "Experimental Procedure",
                "content": "1. Prepare protein sample in buffer solution...",
                "created_date": "2024-01-16T10:30:00Z",
                "last_modified": "2024-11-20T17:12:48Z",
                "author": "researcher@university.edu",
                "version": 3,
                "metadata": {
                    "file_size": 2048,
                    "mime_type": "text/plain",
                    "attachment_count": 2,
                    "tags": ["protein", "purification", "experiment"]
                }
            }
        ]
    )
    
    status: Optional[constr(max_length=50)] = Field(
        default=None,
        description="Optional response status indicator",
        example="success"
    )
    
    message: Optional[constr(max_length=500)] = Field(
        default=None,
        description="Optional response message or error description",
        example="Successfully retrieved 8 entries from page"
    )

    class Config:
        """Pydantic configuration for EntryListResponse model."""
        json_schema_extra = {
            "example": {
                "entries": [
                    {
                        "id": "entry_345678",
                        "page_id": "page_789012",
                        "entry_type": "text",
                        "title": "Experimental Procedure",
                        "content": "1. Prepare protein sample in buffer solution...",
                        "created_date": "2024-01-16T10:30:00Z",
                        "last_modified": "2024-11-20T17:12:48Z",
                        "author": "researcher@university.edu",
                        "version": 3,
                        "metadata": {
                            "file_size": 2048,
                            "mime_type": "text/plain",
                            "attachment_count": 2,
                            "tags": ["protein", "purification", "experiment"]
                        }
                    }
                ],
                "status": "success",
                "message": "Successfully retrieved 8 entries from page"
            }
        }


class UserContextResponse(BaseModel):
    """
    Represents the API response for user context retrieval.
    
    This model wraps the user context information returned by the LabArchives API,
    including status information and optional response messages. Used for
    parsing and validating user authentication and profile responses.
    
    Attributes:
        user: User context object with profile and permissions
        status: Optional response status indicator
        message: Optional response message or error description
    """
    
    user: UserContext = Field(
        description="User context object with profile and permissions",
        example={
            "uid": "user_987654",
            "name": "Dr. Sarah Johnson",
            "email": "sarah.johnson@university.edu",
            "roles": ["researcher", "notebook_owner", "collaborator"]
        }
    )
    
    status: Optional[constr(max_length=50)] = Field(
        default=None,
        description="Optional response status indicator",
        example="success"
    )
    
    message: Optional[constr(max_length=500)] = Field(
        default=None,
        description="Optional response message or error description",
        example="User context retrieved successfully"
    )

    class Config:
        """Pydantic configuration for UserContextResponse model."""
        json_schema_extra = {
            "example": {
                "user": {
                    "uid": "user_987654",
                    "name": "Dr. Sarah Johnson",
                    "email": "sarah.johnson@university.edu",
                    "roles": ["researcher", "notebook_owner", "collaborator"]
                },
                "status": "success",
                "message": "User context retrieved successfully"
            }
        }


# Export all models for external use
__all__ = [
    "NotebookMetadata",
    "PageMetadata", 
    "EntryContent",
    "UserContext",
    "NotebookListResponse",
    "PageListResponse",
    "EntryListResponse",
    "UserContextResponse"
]