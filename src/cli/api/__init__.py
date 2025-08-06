"""
LabArchives API Package Initializer

This package initializer establishes the public API for the LabArchives API integration
layer, exposing key components for use by CLI commands and the MCP server. It provides
a clean, stable import interface for the API client, error classes, data models, and
response parsing utilities.

The API package supports:
- F-002: LabArchives API Integration through the authenticated APIClient
- F-005: Authentication and Security Management via secure credential handling
- F-007: Scope Limitation and Access Control through permission validation
- F-008: Comprehensive Audit Logging with structured error reporting

This module follows Python package initialization best practices by providing
only the intended public API while maintaining clear separation of concerns
between the API client, error handling, data models, and response parsing.

All components are designed for stateless operation with comprehensive error
handling and audit logging support for enterprise-grade reliability and
security compliance.
"""

# Import API client for LabArchives REST API integration
from src.cli.api.client import LabArchivesAPIClient as APIClient

# Import error classes for structured exception handling
from src.cli.api.errors import APIAuthenticationError as AuthenticationError
from src.cli.api.errors import APIError
from src.cli.api.errors import APIPermissionError
from src.cli.api.errors import APIRateLimitError as RateLimitError
from src.cli.api.errors import APIResponseParseError

# Import data models for LabArchives entities
from src.cli.api.models import EntryContent as LabArchivesEntry
from src.cli.api.models import EntryListResponse
from src.cli.api.models import NotebookListResponse
from src.cli.api.models import NotebookMetadata as LabArchivesNotebook
from src.cli.api.models import PageListResponse
from src.cli.api.models import PageMetadata as LabArchivesPage
from src.cli.api.models import UserContext
from src.cli.api.models import UserContextResponse

# Import response parser for API response processing
from src.cli.api.response_parser import parse_api_response


# Define the public API exports
__all__ = [
    # Primary API client
    "APIClient",
    # Error classes for exception handling
    "APIError",
    "AuthenticationError",
    "RateLimitError",
    "APIResponseParseError",
    "APIPermissionError",
    # Data models for LabArchives entities
    "LabArchivesNotebook",
    "LabArchivesPage",
    "LabArchivesEntry",
    "UserContext",
    "NotebookListResponse",
    "PageListResponse",
    "EntryListResponse",
    "UserContextResponse",
    # Response parsing utilities
    "parse_api_response",
]
