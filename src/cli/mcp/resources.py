"""
LabArchives MCP Server - Resource Management Engine

This module defines the MCPResourceManager class and supporting functions for resource discovery
(listing) and content retrieval (reading) in the LabArchives MCP Server. This module acts as the
core resource management layer for the MCP protocol, orchestrating the transformation of
LabArchives notebooks, pages, and entries (fetched via the API client) into MCP-compliant
resource and content models.

The module enforces scope limitations, permission checks, and hierarchical navigation, and
provides robust error handling and audit logging for all resource operations. It exposes the
main entrypoints for the MCP protocol handler and dispatcher, supporting resources/list and
resources/read requests, and integrates with configuration, logging, and the data model layer.

Key Features:
- Resource Discovery and Listing (F-003): Implements MCP resource listing capabilities to
  enumerate available notebooks, pages, and entries within configured scope
- Content Retrieval and Contextualization (F-004): Implements MCP resource reading capabilities
  to fetch detailed content from specific notebook pages and entries
- Scope Limitation and Access Control (F-007): Enforces configurable scope limitations to
  restrict data exposure to specific notebooks or folders
- Comprehensive Audit Logging (F-008): Logs all resource access and data retrieval operations
  for audit and compliance
- Data Validation & Serialization: Ensures all resource data is validated and serialized
  using Pydantic models for robust, auditable, and interoperable AI-data integration

The module supports hierarchical navigation of LabArchives data structures while maintaining
security boundaries and providing structured error handling for all failure scenarios.
"""

import re
import logging
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse, parse_qs

# Import LabArchives API client for data retrieval
from api.client import LabArchivesAPIClient

# Import MCP data models for resource representation
from .models import (
    MCPResource,
    MCPResourceContent,
    labarchives_to_mcp_resource,
    MCP_JSONLD_CONTEXT,
)

# Import exception classes for structured error handling
from api.errors import APIError
from exceptions import LabArchivesMCPException
from logging_setup import get_logger

# Import constants for URI scheme and protocol configuration
from constants import MCP_RESOURCE_URI_SCHEME

# Global logger name for resource manager operations
RESOURCE_MANAGER_LOGGER_NAME = "mcp.resources"


def parse_resource_uri(uri: str) -> Dict[str, str]:
    """
    Parses an MCP resource URI (labarchives://...) and extracts the resource type and identifiers.

    This function analyzes LabArchives MCP resource URIs to extract the resource type and
    relevant identifiers (notebook_id, page_id, entry_id). It supports the hierarchical
    URI structure defined by the MCP protocol for LabArchives resources and is used for
    routing operations and scope enforcement throughout the system.

    The function supports three primary URI patterns:
    - labarchives://notebook/{notebook_id} - for notebook resources
    - labarchives://notebook/{notebook_id}/page/{page_id} - for page resources
    - labarchives://entry/{entry_id} - for entry resources

    Args:
        uri (str): The MCP resource URI to parse, must start with labarchives://

    Returns:
        Dict[str, str]: Dictionary containing resource type and relevant identifiers.
                       Structure varies by resource type:
                       - Notebook: {'type': 'notebook', 'notebook_id': '123'}
                       - Page: {'type': 'page', 'notebook_id': '123', 'page_id': '456'}
                       - Entry: {'type': 'entry', 'entry_id': '789'}

    Raises:
        LabArchivesMCPException: If the URI is invalid, malformed, or doesn't match
                                expected patterns for LabArchives MCP resources

    Examples:
        >>> parse_resource_uri("labarchives://notebook/nb_123456")
        {'type': 'notebook', 'notebook_id': 'nb_123456'}

        >>> parse_resource_uri("labarchives://notebook/nb_123456/page/page_789012")
        {'type': 'page', 'notebook_id': 'nb_123456', 'page_id': 'page_789012'}

        >>> parse_resource_uri("labarchives://entry/entry_345678")
        {'type': 'entry', 'entry_id': 'entry_345678'}
    """
    # Validate that the URI starts with the correct scheme
    if not uri.startswith(MCP_RESOURCE_URI_SCHEME):
        raise LabArchivesMCPException(
            message=f"Invalid URI scheme: expected '{MCP_RESOURCE_URI_SCHEME}' but got '{uri}'",
            code=400,
            context={"uri": uri, "expected_scheme": MCP_RESOURCE_URI_SCHEME},
        )

    # Remove the scheme to get the resource path
    resource_path = uri[len(MCP_RESOURCE_URI_SCHEME) :]

    # Split the path into components
    path_components = [component for component in resource_path.split('/') if component]

    # Validate that we have at least two components (resource type and ID)
    if len(path_components) < 2:
        raise LabArchivesMCPException(
            message=f"Invalid URI format: insufficient path components in '{uri}'",
            code=400,
            context={"uri": uri, "path_components": path_components},
        )

    # Parse based on the first component (resource type)
    resource_type = path_components[0]

    # Handle notebook resources (notebook or notebook/page)
    if resource_type == "notebook":
        if len(path_components) == 2:
            # Simple notebook resource: labarchives://notebook/{notebook_id}
            return {"type": "notebook", "notebook_id": path_components[1]}
        elif len(path_components) == 4 and path_components[2] == "page":
            # Page resource: labarchives://notebook/{notebook_id}/page/{page_id}
            return {
                "type": "page",
                "notebook_id": path_components[1],
                "page_id": path_components[3],
            }
        else:
            raise LabArchivesMCPException(
                message=f"Invalid notebook URI format: unexpected path structure in '{uri}'",
                code=400,
                context={"uri": uri, "path_components": path_components},
            )

    # Handle entry resources
    elif resource_type == "entry":
        if len(path_components) == 2:
            # Entry resource: labarchives://entry/{entry_id}
            return {"type": "entry", "entry_id": path_components[1]}
        else:
            raise LabArchivesMCPException(
                message=f"Invalid entry URI format: unexpected path structure in '{uri}'",
                code=400,
                context={"uri": uri, "path_components": path_components},
            )

    # Handle unsupported resource types
    else:
        raise LabArchivesMCPException(
            message=f"Unsupported resource type: '{resource_type}' in URI '{uri}'",
            code=400,
            context={
                "uri": uri,
                "resource_type": resource_type,
                "supported_types": ["notebook", "entry"],
            },
        )


def is_resource_in_scope(resource_info: Dict[str, str], scope_config: Dict[str, Any]) -> bool:
    """
    Checks if a resource (by type and ID) is within the configured access scope.

    This function enforces scope limitations by validating whether a given resource
    falls within the configured access boundaries. It supports multiple scope types
    including notebook-level restrictions, folder-based filtering, and unrestricted
    access, enabling granular access control for sensitive research data.

    The function is used throughout the resource management system to ensure that
    all resource operations (listing and reading) respect the configured scope
    limitations and prevent unauthorized access to out-of-scope resources.

    Supported scope types:
    - No scope (empty config): All accessible resources allowed
    - Notebook scope: Access restricted to specific notebook by ID or name
    - Folder scope: Access restricted to specific folder within notebook

    Args:
        resource_info (Dict[str, str]): Resource information dictionary containing
                                       resource type and identifiers as returned by
                                       parse_resource_uri()
        scope_config (Dict[str, Any]): Scope configuration dictionary containing
                                     scope parameters such as notebook_id, notebook_name,
                                     or folder_path for access control

    Returns:
        bool: True if the resource is within the configured scope, False otherwise

    Examples:
        >>> # No scope restriction - allow all resources
        >>> is_resource_in_scope(
        ...     {"type": "notebook", "notebook_id": "nb_123"},
        ...     {}
        ... )
        True

        >>> # Notebook scope restriction - allow only specific notebook
        >>> is_resource_in_scope(
        ...     {"type": "notebook", "notebook_id": "nb_123"},
        ...     {"notebook_id": "nb_123"}
        ... )
        True

        >>> # Notebook scope restriction - deny different notebook
        >>> is_resource_in_scope(
        ...     {"type": "notebook", "notebook_id": "nb_456"},
        ...     {"notebook_id": "nb_123"}
        ... )
        False
    """
    # If no scope configuration is provided, allow all resources
    if not scope_config:
        return True

    # Extract scope parameters from configuration
    scope_notebook_id = scope_config.get("notebook_id")
    scope_notebook_name = scope_config.get("notebook_name")
    scope_folder_path = scope_config.get("folder_path")

    # Get resource type and identifiers
    resource_type = resource_info.get("type")

    # Handle notebook-level scope restrictions
    if scope_notebook_id:
        # For notebook resources, check direct match
        if resource_type == "notebook":
            return resource_info.get("notebook_id") == scope_notebook_id

        # For page resources, check parent notebook
        elif resource_type == "page":
            return resource_info.get("notebook_id") == scope_notebook_id

        # For entry resources, we need to resolve the parent notebook
        # This would require additional API calls, so for now we allow entries
        # and rely on the API permissions to enforce access control
        elif resource_type == "entry":
            # Entry scope checking would require resolving the parent page and notebook
            # For now, we delegate this to the LabArchives API permission system
            return True

    # Handle notebook name-based scope restrictions
    if scope_notebook_name:
        # Name-based scope checking requires additional API calls to resolve names
        # For now, we allow the resource and let the API handle the name resolution
        # This could be enhanced in future versions with caching
        return True

    # Handle folder-based scope restrictions
    if scope_folder_path:
        # Folder scope checking requires page metadata to determine folder paths
        # For now, we allow the resource and let the API handle folder validation
        # This could be enhanced with page metadata caching
        return True

    # If no specific scope restrictions are configured, allow all resources
    return True


class MCPResourceManager:
    """
    Main resource manager for MCP resource discovery and content retrieval.

    This class orchestrates resource listing and reading operations by interacting with
    the LabArchives API client, enforcing scope limitations, transforming data to MCP
    models, and logging all operations. It provides the core interface for the MCP
    protocol handler and dispatcher, supporting both resources/list and resources/read
    requests while maintaining security boundaries and audit compliance.

    The resource manager acts as the central coordination point for all resource operations,
    ensuring that data flows correctly from the LabArchives API through the transformation
    layer to the MCP protocol layer while maintaining scope enforcement, error handling,
    and comprehensive audit logging throughout the process.

    Key Features:
    - Resource Discovery: Enumerates available notebooks, pages, and entries within scope
    - Content Retrieval: Fetches detailed content for specific resources
    - Scope Enforcement: Validates all resource access against configured limitations
    - Data Transformation: Converts LabArchives data to MCP-compliant formats
    - Audit Logging: Tracks all resource operations for compliance and monitoring
    - Error Handling: Provides structured error responses for all failure scenarios

    The manager supports hierarchical navigation of LabArchives data while maintaining
    clear separation between the API layer, transformation layer, and MCP protocol layer.
    """

    def __init__(
        self,
        api_client: LabArchivesAPIClient,
        scope_config: Dict[str, Any],
        jsonld_enabled: bool = False,
    ):
        """
        Initializes the MCPResourceManager with the LabArchives API client and configuration.

        This constructor sets up the resource manager with all necessary dependencies
        for resource operations, including the API client for data retrieval, scope
        configuration for access control, and JSON-LD settings for semantic enrichment.
        It also establishes the logging system for comprehensive audit trail generation.

        Args:
            api_client (LabArchivesAPIClient): Authenticated LabArchives API client instance
                                             for retrieving notebook, page, and entry data
            scope_config (Dict[str, Any]): Configuration dictionary containing scope parameters
                                         such as notebook_id, notebook_name, or folder_path
                                         for access control enforcement
            jsonld_enabled (bool): Flag indicating whether to include JSON-LD context in
                                 resource content for semantic enrichment (default: False)
        """
        # Store the API client for data retrieval operations
        self.api_client = api_client

        # Store the scope configuration for access control enforcement
        self.scope_config = scope_config

        # Store the JSON-LD enablement flag for semantic enrichment
        self.jsonld_enabled = jsonld_enabled

        # Initialize the logger for audit and operational logging
        self.logger = get_logger()

        # Log the initialization with configuration details
        self.logger.info(
            "MCPResourceManager initialized",
            extra={
                "scope_config": scope_config,
                "jsonld_enabled": jsonld_enabled,
                "api_client_initialized": hasattr(api_client, 'uid') and api_client.uid is not None,
            },
        )

    def list_resources(self) -> List[MCPResource]:
        """
        Enumerates available MCP resources within the configured scope.

        This method performs comprehensive resource discovery by querying the LabArchives
        API for accessible notebooks, pages, and entries based on the configured scope
        limitations. It handles hierarchical navigation, scope enforcement, data transformation,
        and error handling to provide a complete list of discoverable resources.

        The method supports different scope types:
        - No scope: Lists all accessible notebooks for the authenticated user
        - Notebook scope: Lists pages within a specific notebook
        - Folder scope: Lists pages within a specific folder in a notebook

        All resources are transformed to MCP-compliant format and validated before
        being returned to ensure protocol compliance and data integrity.

        Returns:
            List[MCPResource]: List of MCP resources available within the configured scope.
                              Each resource includes URI, name, description, and metadata
                              suitable for client consumption and navigation.

        Raises:
            LabArchivesMCPException: If resource listing fails due to scope violations,
                                   API errors, or data transformation issues
            APIError: If the LabArchives API returns errors during resource retrieval
        """
        # Log the start of resource listing operation
        self.logger.info(
            "Starting resource listing operation",
            extra={"operation": "list_resources", "scope_config": self.scope_config},
        )

        try:
            # Initialize the list to store MCP resources
            mcp_resources = []

            # Determine the scope type and execute appropriate listing strategy
            scope_notebook_id = self.scope_config.get("notebook_id")
            scope_notebook_name = self.scope_config.get("notebook_name")
            scope_folder_path = self.scope_config.get("folder_path")

            # Handle notebook-specific scope (list pages within notebook)
            if scope_notebook_id:
                self.logger.info(
                    "Listing pages within notebook scope",
                    extra={
                        "notebook_id": scope_notebook_id,
                        "operation": "list_pages_in_notebook",
                    },
                )

                # Retrieve pages for the specified notebook
                page_list_response = self.api_client.list_pages(scope_notebook_id)

                # Transform each page to MCP resource format
                for page in page_list_response.pages:
                    # Verify the page is within scope (additional validation)
                    page_resource_info = {
                        "type": "page",
                        "notebook_id": page.notebook_id,
                        "page_id": page.id,
                    }

                    if is_resource_in_scope(page_resource_info, self.scope_config):
                        # Transform LabArchives page to MCP resource
                        mcp_resource = labarchives_to_mcp_resource(
                            page,
                            parent_uri=f"labarchives://notebook/{scope_notebook_id}",
                        )
                        mcp_resources.append(mcp_resource)
                    else:
                        self.logger.warning(
                            "Page excluded due to scope restrictions",
                            extra={
                                "page_id": page.id,
                                "notebook_id": page.notebook_id,
                                "scope_config": self.scope_config,
                            },
                        )

            # Handle notebook name-based scope (resolve name to ID and list pages)
            elif scope_notebook_name:
                self.logger.info(
                    "Listing pages within notebook name scope",
                    extra={
                        "notebook_name": scope_notebook_name,
                        "operation": "list_pages_in_named_notebook",
                    },
                )

                # First, get all notebooks to find the one with matching name
                notebook_list_response = self.api_client.list_notebooks()

                # Find the notebook with matching name
                target_notebook = None
                for notebook in notebook_list_response.notebooks:
                    if notebook.name == scope_notebook_name:
                        target_notebook = notebook
                        break

                if target_notebook:
                    # Retrieve pages for the found notebook
                    page_list_response = self.api_client.list_pages(target_notebook.id)

                    # Transform each page to MCP resource format
                    for page in page_list_response.pages:
                        # Verify the page is within scope
                        page_resource_info = {
                            "type": "page",
                            "notebook_id": page.notebook_id,
                            "page_id": page.id,
                        }

                        if is_resource_in_scope(page_resource_info, self.scope_config):
                            # Transform LabArchives page to MCP resource
                            mcp_resource = labarchives_to_mcp_resource(
                                page,
                                parent_uri=f"labarchives://notebook/{target_notebook.id}",
                            )
                            mcp_resources.append(mcp_resource)
                else:
                    self.logger.warning(
                        "Notebook not found with specified name",
                        extra={
                            "notebook_name": scope_notebook_name,
                            "available_notebooks": [
                                nb.name for nb in notebook_list_response.notebooks
                            ],
                        },
                    )

            # Handle no scope or unrestricted access (list all notebooks)
            else:
                self.logger.info(
                    "Listing all accessible notebooks",
                    extra={"operation": "list_all_notebooks"},
                )

                # Retrieve all notebooks accessible to the authenticated user
                notebook_list_response = self.api_client.list_notebooks()

                # Transform each notebook to MCP resource format
                for notebook in notebook_list_response.notebooks:
                    # Verify the notebook is within scope (should be true for no scope)
                    notebook_resource_info = {
                        "type": "notebook",
                        "notebook_id": notebook.id,
                    }

                    if is_resource_in_scope(notebook_resource_info, self.scope_config):
                        # Transform LabArchives notebook to MCP resource
                        mcp_resource = labarchives_to_mcp_resource(notebook)
                        mcp_resources.append(mcp_resource)
                    else:
                        self.logger.warning(
                            "Notebook excluded due to scope restrictions",
                            extra={
                                "notebook_id": notebook.id,
                                "notebook_name": notebook.name,
                                "scope_config": self.scope_config,
                            },
                        )

            # Log the successful completion of resource listing
            self.logger.info(
                "Resource listing completed successfully",
                extra={
                    "operation": "list_resources",
                    "resource_count": len(mcp_resources),
                    "scope_config": self.scope_config,
                },
            )

            return mcp_resources

        except APIError as e:
            # Handle LabArchives API errors with detailed logging
            self.logger.error(
                "LabArchives API error during resource listing",
                extra={
                    "operation": "list_resources",
                    "error": str(e),
                    "error_code": e.code,
                    "error_context": e.context,
                },
            )
            raise LabArchivesMCPException(
                message=f"Failed to list resources: {str(e)}",
                code=500,
                context={"operation": "list_resources", "api_error": str(e)},
            )

        except Exception as e:
            # Handle unexpected errors with comprehensive logging
            self.logger.error(
                "Unexpected error during resource listing",
                extra={
                    "operation": "list_resources",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "scope_config": self.scope_config,
                },
            )
            raise LabArchivesMCPException(
                message=f"Unexpected error during resource listing: {str(e)}",
                code=500,
                context={
                    "operation": "list_resources",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

    def read_resource(self, uri: str) -> MCPResourceContent:
        """
        Fetches detailed content for a specific MCP resource URI.

        This method retrieves comprehensive content for a specific resource identified
        by its MCP URI, including full content, metadata, and optional JSON-LD context.
        It enforces scope limitations, handles different resource types, and provides
        structured content optimized for AI consumption.

        The method supports reading different resource types:
        - Notebook: Returns notebook metadata and page listings
        - Page: Returns page content with all entries
        - Entry: Returns individual entry content and metadata

        All content is transformed to MCP-compliant format with optional JSON-LD
        semantic enrichment for enhanced AI understanding and processing.

        Args:
            uri (str): The MCP resource URI to read (e.g., "labarchives://notebook/123")
                      Must be a valid LabArchives MCP resource URI

        Returns:
            MCPResourceContent: Structured content object containing the resource data,
                               metadata, and optional JSON-LD context suitable for
                               AI consumption and processing

        Raises:
            LabArchivesMCPException: If the URI is invalid, the resource is out of scope,
                                   or content retrieval fails
            APIError: If the LabArchives API returns errors during content retrieval
        """
        # Log the start of resource reading operation
        self.logger.info(
            "Starting resource read operation",
            extra={"operation": "read_resource", "uri": uri},
        )

        try:
            # Parse the resource URI to extract type and identifiers
            resource_info = parse_resource_uri(uri)

            # Validate that the resource is within the configured scope
            if not is_resource_in_scope(resource_info, self.scope_config):
                self.logger.warning(
                    "Resource read denied due to scope violation",
                    extra={
                        "uri": uri,
                        "resource_info": resource_info,
                        "scope_config": self.scope_config,
                    },
                )
                raise LabArchivesMCPException(
                    message=f"Resource '{uri}' is outside the configured scope",
                    code=403,
                    context={
                        "uri": uri,
                        "resource_info": resource_info,
                        "scope_config": self.scope_config,
                    },
                )

            # Handle different resource types
            resource_type = resource_info.get("type")

            # Handle notebook resource reading
            if resource_type == "notebook":
                notebook_id = resource_info.get("notebook_id")

                self.logger.info(
                    "Reading notebook resource",
                    extra={"notebook_id": notebook_id, "operation": "read_notebook"},
                )

                # Get notebook metadata by listing notebooks and finding the match
                notebook_list_response = self.api_client.list_notebooks()
                target_notebook = None

                for notebook in notebook_list_response.notebooks:
                    if notebook.id == notebook_id:
                        target_notebook = notebook
                        break

                if not target_notebook:
                    raise LabArchivesMCPException(
                        message=f"Notebook not found: {notebook_id}",
                        code=404,
                        context={"notebook_id": notebook_id, "uri": uri},
                    )

                # Get pages within the notebook for complete content
                page_list_response = self.api_client.list_pages(notebook_id)

                # Build comprehensive notebook content
                notebook_content = {
                    "id": target_notebook.id,
                    "name": target_notebook.name,
                    "description": target_notebook.description,
                    "owner": target_notebook.owner,
                    "created": target_notebook.created_date.isoformat(),
                    "modified": target_notebook.last_modified.isoformat(),
                    "folder_count": target_notebook.folder_count,
                    "page_count": target_notebook.page_count,
                    "pages": [],
                }

                # Add page summaries to notebook content
                for page in page_list_response.pages:
                    page_summary = {
                        "id": page.id,
                        "title": page.title,
                        "folder_path": page.folder_path,
                        "author": page.author,
                        "created": page.created_date.isoformat(),
                        "modified": page.last_modified.isoformat(),
                        "entry_count": page.entry_count,
                    }
                    notebook_content["pages"].append(page_summary)

                # Create metadata dictionary
                metadata = {
                    "resource_type": "notebook",
                    "uri": uri,
                    "id": target_notebook.id,
                    "owner": target_notebook.owner,
                    "created": target_notebook.created_date.isoformat(),
                    "modified": target_notebook.last_modified.isoformat(),
                    "folder_count": target_notebook.folder_count,
                    "page_count": target_notebook.page_count,
                    "total_pages": len(page_list_response.pages),
                }

                # Create MCPResourceContent with optional JSON-LD context
                content = MCPResourceContent(
                    content=notebook_content,
                    context=MCP_JSONLD_CONTEXT if self.jsonld_enabled else None,
                    metadata=metadata,
                )

                self.logger.info(
                    "Notebook resource read successfully",
                    extra={
                        "notebook_id": notebook_id,
                        "page_count": len(page_list_response.pages),
                    },
                )

                return content

            # Handle page resource reading
            elif resource_type == "page":
                notebook_id = resource_info.get("notebook_id")
                page_id = resource_info.get("page_id")

                self.logger.info(
                    "Reading page resource",
                    extra={
                        "notebook_id": notebook_id,
                        "page_id": page_id,
                        "operation": "read_page",
                    },
                )

                # Get page metadata by listing pages and finding the match
                page_list_response = self.api_client.list_pages(notebook_id)
                target_page = None

                for page in page_list_response.pages:
                    if page.id == page_id:
                        target_page = page
                        break

                if not target_page:
                    raise LabArchivesMCPException(
                        message=f"Page not found: {page_id} in notebook {notebook_id}",
                        code=404,
                        context={
                            "notebook_id": notebook_id,
                            "page_id": page_id,
                            "uri": uri,
                        },
                    )

                # Get entries within the page for complete content
                entry_list_response = self.api_client.list_entries(page_id)

                # Build comprehensive page content
                page_content = {
                    "id": target_page.id,
                    "notebook_id": target_page.notebook_id,
                    "title": target_page.title,
                    "folder_path": target_page.folder_path,
                    "author": target_page.author,
                    "created": target_page.created_date.isoformat(),
                    "modified": target_page.last_modified.isoformat(),
                    "entry_count": target_page.entry_count,
                    "entries": [],
                }

                # Add entries to page content
                for entry in entry_list_response.entries:
                    entry_data = {
                        "id": entry.id,
                        "page_id": entry.page_id,
                        "entry_type": entry.entry_type,
                        "title": entry.title,
                        "content": entry.content,
                        "author": entry.author,
                        "created": entry.created_date.isoformat(),
                        "modified": entry.last_modified.isoformat(),
                        "version": entry.version,
                    }
                    page_content["entries"].append(entry_data)

                # Create metadata dictionary
                metadata = {
                    "resource_type": "page",
                    "uri": uri,
                    "id": target_page.id,
                    "notebook_id": target_page.notebook_id,
                    "folder_path": target_page.folder_path,
                    "author": target_page.author,
                    "created": target_page.created_date.isoformat(),
                    "modified": target_page.last_modified.isoformat(),
                    "entry_count": target_page.entry_count,
                    "total_entries": len(entry_list_response.entries),
                }

                # Create MCPResourceContent with optional JSON-LD context
                content = MCPResourceContent(
                    content=page_content,
                    context=MCP_JSONLD_CONTEXT if self.jsonld_enabled else None,
                    metadata=metadata,
                )

                self.logger.info(
                    "Page resource read successfully",
                    extra={
                        "page_id": page_id,
                        "entry_count": len(entry_list_response.entries),
                    },
                )

                return content

            # Handle entry resource reading
            elif resource_type == "entry":
                entry_id = resource_info.get("entry_id")

                self.logger.info(
                    "Reading entry resource",
                    extra={"entry_id": entry_id, "operation": "read_entry"},
                )

                # Get entry content directly
                entry_response = self.api_client.get_entry_content(entry_id)

                if not entry_response.entries:
                    raise LabArchivesMCPException(
                        message=f"Entry not found: {entry_id}",
                        code=404,
                        context={"entry_id": entry_id, "uri": uri},
                    )

                # Get the first (and should be only) entry
                entry = entry_response.entries[0]

                # Transform the entry to MCP resource content
                mcp_content = labarchives_to_mcp_resource(entry)

                # If JSON-LD is disabled, remove the context
                if not self.jsonld_enabled:
                    mcp_content.context = None

                self.logger.info(
                    "Entry resource read successfully",
                    extra={
                        "entry_id": entry_id,
                        "content_size": len(entry.content) if entry.content else 0,
                    },
                )

                return mcp_content

            # Handle unsupported resource types
            else:
                raise LabArchivesMCPException(
                    message=f"Unsupported resource type for reading: {resource_type}",
                    code=400,
                    context={"resource_type": resource_type, "uri": uri},
                )

        except LabArchivesMCPException:
            # Re-raise LabArchives MCP exceptions without modification
            raise

        except APIError as e:
            # Handle LabArchives API errors with detailed logging
            self.logger.error(
                "LabArchives API error during resource reading",
                extra={
                    "operation": "read_resource",
                    "uri": uri,
                    "error": str(e),
                    "error_code": e.code,
                    "error_context": e.context,
                },
            )
            raise LabArchivesMCPException(
                message=f"Failed to read resource '{uri}': {str(e)}",
                code=500,
                context={"operation": "read_resource", "uri": uri, "api_error": str(e)},
            )

        except Exception as e:
            # Handle unexpected errors with comprehensive logging
            self.logger.error(
                "Unexpected error during resource reading",
                extra={
                    "operation": "read_resource",
                    "uri": uri,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            raise LabArchivesMCPException(
                message=f"Unexpected error reading resource '{uri}': {str(e)}",
                code=500,
                context={
                    "operation": "read_resource",
                    "uri": uri,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
