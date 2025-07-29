"""
LabArchives MCP Server Resource Manager

This module implements the ResourceManager class and supporting functions for orchestrating
resource discovery (listing) and content retrieval (reading) for the LabArchives MCP Server.
This module acts as the core business logic layer between the LabArchives API client and the
MCP protocol handler, transforming LabArchives notebooks, pages, and entries into MCP-compliant
resource and content models.

The ResourceManager enforces scope limitations, permission checks, and hierarchical navigation,
and provides robust error handling and audit logging for all resource operations. It exposes
the main entrypoints for the MCP protocol handler and dispatcher, supporting resources/list
and resources/read requests, and integrates with configuration, logging, and the data model layer.

Key Features:
- Resource Discovery and Listing (F-003): Enumerates available notebooks, pages, and entries
  within configured scope with hierarchical navigation and MCP-compliant resource URIs
- Content Retrieval and Contextualization (F-004): Fetches detailed content from specific
  resources, preserving metadata and hierarchical context for AI consumption
- Scope Limitation and Access Control (F-007): Enforces configurable scope limitations to
  restrict data exposure to specific notebooks or folders with granular access control
- Data Validation & Serialization: Ensures all resource data is validated and serialized
  using Pydantic models for robust, auditable, and interoperable AI-data integration
- Comprehensive Audit Logging (F-008): Logs all resource access and data retrieval operations
  for audit and compliance, including scope violations and permission errors

This module serves as the canonical interface for all MCP resource operations, providing
secure, authenticated access to LabArchives electronic lab notebook data through the
standardized Model Context Protocol.
"""

from datetime import datetime
import logging
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

# Internal imports for API client and data models
from api.client import LabArchivesAPIClient
from api.errors import APIAuthenticationError
from api.errors import APIError
from api.errors import APIPermissionError
from api.errors import APIResponseParseError
from constants import MCP_RESOURCE_URI_SCHEME
from data_models.scoping import FolderPath
from exceptions import LabArchivesMCPException
from logging_setup import get_logger
from mcp.models import MCPResource
from mcp.models import MCPResourceContent
from mcp.models import MCP_JSONLD_CONTEXT
from mcp.models import labarchives_to_mcp_resource

# Security utilities for fail-secure validation
from security.validators import validate_folder_scope_access


# Logger name for resource management operations
RESOURCE_MANAGER_LOGGER_NAME = "mcp.resources"


def parse_resource_uri(uri: str) -> Dict[str, str]:
    """
    Parses an MCP resource URI (labarchives://...) and extracts the resource type and identifiers.

    This function validates and parses LabArchives MCP resource URIs following the standard
    labarchives:// scheme, extracting resource type and relevant identifiers for routing
    and scope enforcement. The function supports hierarchical resource addressing with
    proper validation and error handling.

    Supported URI formats:
    - labarchives://notebook/{notebook_id}
    - labarchives://notebook/{notebook_id}/page/{page_id}
    - labarchives://entry/{entry_id}

    Args:
        uri (str): The MCP resource URI to parse

    Returns:
        Dict[str, str]: Dictionary containing resource type and relevant identifiers
                       Examples:
                       {'type': 'notebook', 'notebook_id': '123'}
                       {'type': 'page', 'notebook_id': '123', 'page_id': '456'}
                       {'type': 'entry', 'entry_id': '789'}

    Raises:
        LabArchivesMCPException: If the URI is invalid or doesn't follow the expected format
    """
    logger = get_logger()

    # Log the parsing operation for audit trail
    logger.debug(f"Parsing resource URI: {uri}")

    # Validate URI starts with the correct scheme
    if not uri.startswith(MCP_RESOURCE_URI_SCHEME):
        error_msg = f"Invalid resource URI scheme. Expected '{MCP_RESOURCE_URI_SCHEME}', got: {uri}"
        logger.error(error_msg)
        raise LabArchivesMCPException(
            message=error_msg,
            code=400,
            context={"uri": uri, "expected_scheme": MCP_RESOURCE_URI_SCHEME},
        )

    # Remove the scheme prefix and split into components
    uri_path = uri[len(MCP_RESOURCE_URI_SCHEME) :]
    if not uri_path:
        error_msg = f"Empty resource path in URI: {uri}"
        logger.error(error_msg)
        raise LabArchivesMCPException(message=error_msg, code=400, context={"uri": uri})

    # Split path into components
    path_components = uri_path.split('/')

    # Parse notebook resources: labarchives://notebook/{notebook_id}[/page/{page_id}]
    if path_components[0] == 'notebook':
        if len(path_components) < 2:
            error_msg = f"Invalid notebook URI format. Missing notebook ID: {uri}"
            logger.error(error_msg)
            raise LabArchivesMCPException(
                message=error_msg,
                code=400,
                context={"uri": uri, "components": path_components},
            )

        notebook_id = path_components[1]
        if not notebook_id:
            error_msg = f"Empty notebook ID in URI: {uri}"
            logger.error(error_msg)
            raise LabArchivesMCPException(
                message=error_msg,
                code=400,
                context={"uri": uri, "components": path_components},
            )

        # Check for page sub-resource
        if len(path_components) == 2:
            # Simple notebook resource
            result = {'type': 'notebook', 'notebook_id': notebook_id}
            logger.debug(f"Parsed notebook resource: {result}")
            return result

        elif len(path_components) == 4 and path_components[2] == 'page':
            # Page within notebook resource
            page_id = path_components[3]
            if not page_id:
                error_msg = f"Empty page ID in URI: {uri}"
                logger.error(error_msg)
                raise LabArchivesMCPException(
                    message=error_msg,
                    code=400,
                    context={"uri": uri, "components": path_components},
                )

            result = {'type': 'page', 'notebook_id': notebook_id, 'page_id': page_id}
            logger.debug(f"Parsed page resource: {result}")
            return result

        else:
            error_msg = f"Invalid notebook URI format: {uri}"
            logger.error(error_msg)
            raise LabArchivesMCPException(
                message=error_msg,
                code=400,
                context={"uri": uri, "components": path_components},
            )

    # Parse entry resources: labarchives://entry/{entry_id}
    elif path_components[0] == 'entry':
        if len(path_components) != 2:
            error_msg = f"Invalid entry URI format. Expected 'entry/{{entry_id}}': {uri}"
            logger.error(error_msg)
            raise LabArchivesMCPException(
                message=error_msg,
                code=400,
                context={"uri": uri, "components": path_components},
            )

        entry_id = path_components[1]
        if not entry_id:
            error_msg = f"Empty entry ID in URI: {uri}"
            logger.error(error_msg)
            raise LabArchivesMCPException(
                message=error_msg,
                code=400,
                context={"uri": uri, "components": path_components},
            )

        result = {'type': 'entry', 'entry_id': entry_id}
        logger.debug(f"Parsed entry resource: {result}")
        return result

    else:
        error_msg = f"Unsupported resource type in URI: {uri}"
        logger.error(error_msg)
        raise LabArchivesMCPException(
            message=error_msg,
            code=400,
            context={"uri": uri, "components": path_components},
        )


def is_resource_in_scope(resource_info: Dict[str, str], scope_config: Dict[str, Any]) -> bool:
    """
    Immediate, fail-secure scope validation replacing deferred validation approach.

    This function enforces scope limitations by performing immediate, synchronous validation
    against configured scope parameters. Unlike the previous implementation that deferred
    validation for entries and folder paths, this function validates all resource types
    immediately and denies access by default when scope boundaries are unclear.

    Key Security Improvements:
    - Immediate validation: No deferred checks that could be bypassed
    - Fail-secure behavior: Any uncertainty results in access denial
    - Entry-to-notebook validation: Prevents cross-notebook data access
    - Folder scope enforcement: Blocks unauthorized folder boundary violations
    - Comprehensive audit logging: All decisions are logged for compliance

    Scope validation logic:
    - If no scope is configured, all resources are allowed
    - If notebook_id is configured, validates notebook ownership immediately
    - If notebook_name is configured, validates against resolved notebook names
    - If folder_path is configured, validates folder boundaries with root-level support

    Args:
        resource_info (Dict[str, str]): Parsed resource information from parse_resource_uri
        scope_config (Dict[str, Any]): Scope configuration containing notebook_id,
                                      notebook_name, and/or folder_path

    Returns:
        bool: True if the resource is definitively within scope, False otherwise.
              Always returns False for uncertain or ambiguous cases (fail-secure)

    Raises:
        LabArchivesMCPException: For validation errors or scope violations with specific error messages
    """
    logger = get_logger()

    # Validate input parameters - fail secure on invalid input
    if not isinstance(resource_info, dict) or 'type' not in resource_info:
        logger.error(
            "Invalid resource_info provided - failing secure",
            extra={
                "resource_info_type": type(resource_info).__name__,
                "validation_event": "invalid_input_fail_secure",
            },
        )
        return False

    if not isinstance(scope_config, dict):
        logger.error(
            "Invalid scope_config provided - failing secure",
            extra={
                "scope_config_type": type(scope_config).__name__,
                "validation_event": "invalid_scope_config_fail_secure",
            },
        )
        return False

    # Enhanced audit logging for security compliance (after validation to avoid null pointer errors)
    logger.debug(
        f"Performing immediate scope validation (fail-secure): {resource_info} against scope: {scope_config}",
        extra={
            "resource_type": resource_info.get('type'),
            "validation_approach": "immediate_fail_secure",
            "validation_event": "scope_check_start",
        },
    )

    # Extract scope parameters
    notebook_id = scope_config.get('notebook_id')
    notebook_name = scope_config.get('notebook_name')
    folder_path = scope_config.get('folder_path')
    resource_type = resource_info.get('type')

    # If no scope limitations are configured, allow all resources
    if not notebook_id and not notebook_name and not folder_path:
        logger.debug(
            "No scope limitations configured - allowing all resources",
            extra={"validation_event": "no_scope_allow_all"},
        )
        return True

    # Immediate notebook ID scope validation
    if notebook_id:
        if resource_type in ['notebook', 'page']:
            resource_notebook_id = resource_info.get('notebook_id')
            if resource_notebook_id == notebook_id:
                logger.debug(
                    f"Resource {resource_info} validated within notebook scope: {notebook_id}",
                    extra={
                        "resource_notebook_id": resource_notebook_id,
                        "scope_notebook_id": notebook_id,
                        "validation_event": "notebook_scope_match",
                    },
                )
                return True
            else:
                logger.warning(
                    f"Resource {resource_info} denied - outside notebook scope: {notebook_id}",
                    extra={
                        "resource_notebook_id": resource_notebook_id,
                        "scope_notebook_id": notebook_id,
                        "validation_event": "notebook_scope_violation",
                    },
                )
                return False

        # For entry resources, perform immediate notebook ownership validation
        elif resource_type == 'entry':
            entry_id = resource_info.get('entry_id')
            # Entry validation requires notebook_id to be provided in resource_info for immediate validation
            entry_notebook_id = resource_info.get('notebook_id')
            if entry_notebook_id:
                if entry_notebook_id == notebook_id:
                    logger.debug(
                        f"Entry {entry_id} validated within notebook scope: {notebook_id}",
                        extra={
                            "entry_id": entry_id,
                            "entry_notebook_id": entry_notebook_id,
                            "scope_notebook_id": notebook_id,
                            "validation_event": "entry_notebook_scope_match",
                        },
                    )
                    return True
                else:
                    logger.warning(
                        f"Entry {entry_id} denied - belongs to notebook {entry_notebook_id} outside scope: {notebook_id}",
                        extra={
                            "entry_id": entry_id,
                            "entry_notebook_id": entry_notebook_id,
                            "scope_notebook_id": notebook_id,
                            "validation_event": "entry_notebook_scope_violation",
                        },
                    )
                    return False
            else:
                # Without notebook_id in resource_info, we cannot validate immediately - fail secure
                logger.warning(
                    f"Entry {entry_id} denied - insufficient information for immediate notebook validation",
                    extra={
                        "entry_id": entry_id,
                        "validation_event": "entry_insufficient_info_fail_secure",
                    },
                )
                return False

    # Immediate notebook name scope validation
    if notebook_name:
        # For notebook name validation, we need the actual notebook name in resource_info
        resource_notebook_name = resource_info.get('notebook_name')
        if resource_notebook_name:
            if resource_notebook_name == notebook_name:
                logger.debug(
                    f"Resource validated within notebook name scope: {notebook_name}",
                    extra={
                        "resource_notebook_name": resource_notebook_name,
                        "scope_notebook_name": notebook_name,
                        "validation_event": "notebook_name_scope_match",
                    },
                )
                return True
            else:
                logger.warning(
                    f"Resource denied - notebook name '{resource_notebook_name}' outside scope: '{notebook_name}'",
                    extra={
                        "resource_notebook_name": resource_notebook_name,
                        "scope_notebook_name": notebook_name,
                        "validation_event": "notebook_name_scope_violation",
                    },
                )
                return False
        else:
            # Without notebook name in resource_info, fail secure
            logger.warning(
                f"Resource denied - insufficient information for immediate notebook name validation",
                extra={
                    "resource_type": resource_type,
                    "scope_notebook_name": notebook_name,
                    "validation_event": "notebook_name_insufficient_info_fail_secure",
                },
            )
            return False

    # Immediate folder path scope validation with root-level page support
    if folder_path:
        resource_folder_path = resource_info.get('folder_path')

        # Special handling for root-level access
        if not folder_path or folder_path in ['', '/']:
            # Root scope allows all resources including those with empty/null folder paths
            logger.debug(
                f"Resource validated within root folder scope - all resources allowed",
                extra={
                    "resource_folder_path": resource_folder_path,
                    "scope_folder_path": folder_path,
                    "validation_event": "root_folder_scope_allow_all",
                },
            )
            return True

        # For non-root folder scope, validate against specific folder path
        if resource_folder_path is not None:
            try:
                # Use FolderPath for proper hierarchical validation
                if resource_folder_path in ['', None]:
                    # Root-level resource doesn't match non-root folder scope
                    logger.debug(
                        f"Root-level resource denied by non-root folder scope: {folder_path}",
                        extra={
                            "resource_folder_path": resource_folder_path,
                            "scope_folder_path": folder_path,
                            "validation_event": "root_resource_non_root_scope_denied",
                        },
                    )
                    return False

                # Parse folder paths for hierarchical comparison
                scope_folder = FolderPath.from_raw(folder_path)
                resource_folder = FolderPath.from_raw(resource_folder_path)

                # Check if resource folder is within scope using hierarchical validation
                if (
                    scope_folder.is_parent_of(resource_folder)
                    or scope_folder.components == resource_folder.components
                ):
                    logger.debug(
                        f"Resource validated within folder scope: {folder_path}",
                        extra={
                            "resource_folder_path": resource_folder_path,
                            "scope_folder_path": folder_path,
                            "validation_event": "folder_scope_hierarchical_match",
                        },
                    )
                    return True
                else:
                    logger.warning(
                        f"Resource denied - folder '{resource_folder_path}' outside scope: '{folder_path}'",
                        extra={
                            "resource_folder_path": resource_folder_path,
                            "scope_folder_path": folder_path,
                            "validation_event": "folder_scope_hierarchical_violation",
                        },
                    )
                    return False

            except Exception as e:
                # Fail secure on folder path parsing errors
                logger.error(
                    f"Folder path validation error - failing secure: {e}",
                    extra={
                        "resource_folder_path": resource_folder_path,
                        "scope_folder_path": folder_path,
                        "error_type": type(e).__name__,
                        "validation_event": "folder_path_parse_error_fail_secure",
                    },
                )
                return False
        else:
            # Without folder path information, fail secure for non-root scopes
            logger.warning(
                f"Resource denied - insufficient folder information for scope validation",
                extra={
                    "resource_type": resource_type,
                    "scope_folder_path": folder_path,
                    "validation_event": "folder_insufficient_info_fail_secure",
                },
            )
            return False

    # If we reach here, the resource doesn't match any configured scope - fail secure
    logger.warning(
        f"Resource {resource_info} denied - does not match any configured scope",
        extra={
            "resource_type": resource_type,
            "validation_event": "no_scope_match_fail_secure",
        },
    )
    return False


class ResourceManager:
    """
    Main resource manager for MCP resource discovery and content retrieval.

    This class orchestrates resource listing and reading by interacting with the LabArchives
    API client, enforcing scope limitations, transforming data to MCP models, and logging
    all operations. It provides the core interface for the MCP protocol handler and dispatcher,
    supporting both resources/list and resources/read MCP requests.

    The ResourceManager implements the business logic layer between the LabArchives API and
    the MCP protocol, ensuring that all resource operations are secure, scoped, validated,
    and properly audited for compliance and debugging purposes.

    Key responsibilities:
    - Resource discovery with hierarchical navigation
    - Content retrieval with metadata preservation
    - Scope enforcement and access control
    - Data transformation and serialization
    - Comprehensive audit logging
    - Error handling and graceful degradation

    Attributes:
        api_client (LabArchivesAPIClient): Authenticated client for LabArchives API operations
        scope_config (Dict[str, Any]): Configuration for scope-based access control
        jsonld_enabled (bool): Flag to enable JSON-LD context in resource content
        logger (logging.Logger): Logger instance for audit and diagnostic logging
    """

    def __init__(
        self,
        api_client: LabArchivesAPIClient,
        scope_config: Dict[str, Any],
        jsonld_enabled: bool,
    ):
        """
        Initializes the ResourceManager with the LabArchives API client, scope configuration, and JSON-LD flag.

        Sets up the resource manager with all necessary dependencies for secure, scoped resource
        operations. Initializes logging and validates the configuration parameters to ensure
        proper operation.

        Args:
            api_client (LabArchivesAPIClient): Authenticated LabArchives API client instance
            scope_config (Dict[str, Any]): Dictionary containing scope configuration parameters
                                          (notebook_id, notebook_name, folder_path)
            jsonld_enabled (bool): Flag to enable JSON-LD context in resource content responses

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        # Validate required parameters
        if not api_client:
            raise ValueError("API client is required for ResourceManager initialization")

        if scope_config is None:
            raise ValueError("Scope configuration is required for ResourceManager initialization")

        # Store dependencies as instance properties
        self.api_client = api_client
        self.scope_config = scope_config
        self.jsonld_enabled = jsonld_enabled

        # Initialize logger for resource management operations
        self.logger = get_logger()

        # Log successful initialization
        self.logger.info(
            "ResourceManager initialized",
            extra={
                "scope_config": scope_config,
                "jsonld_enabled": jsonld_enabled,
                "api_client_configured": bool(api_client),
            },
        )

    def _notebook_contains_folder(self, notebook, folder_path: str) -> bool:
        """
        Check if a notebook contains pages in the specified folder path.

        This method enforces folder-scoped access control by checking if any pages
        within the notebook reside in the specified folder path. It makes an API call
        to list pages for the notebook and examines their folder_path metadata using
        exact hierarchical path comparison via FolderPath.

        Args:
            notebook: The notebook object to check
            folder_path (str): The folder path to check for

        Returns:
            bool: True if the notebook contains pages in the folder path, False otherwise
        """
        try:
            # Get page list for the notebook to check folder containment
            page_list_response = self.api_client.list_pages(notebook.id)

            # Create FolderPath instance for the target folder for exact comparison
            if not folder_path or not folder_path.strip():
                # Empty folder path means root scope - all pages match
                return True

            try:
                target_folder = FolderPath.from_raw(folder_path)
            except Exception as e:
                self.logger.warning(f"Invalid folder path '{folder_path}': {e}")
                return False

            # Check if any page is in the specified folder path using exact hierarchical validation
            for page in page_list_response.pages:
                if page.folder_path and page.folder_path.strip():
                    try:
                        page_folder = FolderPath.from_raw(page.folder_path)

                        # Check if page is within folder using exact parent-child relationship
                        if (
                            target_folder.is_parent_of(page_folder)
                            or target_folder.components == page_folder.components
                        ):
                            self.logger.debug(
                                f"Notebook {notebook.id} contains folder {folder_path} via page {page.id}"
                            )
                            return True
                    except Exception as e:
                        # Log error but continue checking other pages
                        self.logger.warning(
                            f"Error processing page folder path '{page.folder_path}': {e}"
                        )
                        continue

            # No pages found in the specified folder
            self.logger.debug(f"Notebook {notebook.id} does not contain folder {folder_path}")
            return False

        except Exception as e:
            # Log error but don't fail - allow notebook to be included for safety
            self.logger.warning(
                f"Error checking folder containment for notebook {notebook.id}: {e}"
            )
            return True

    def list_resources(self) -> List[MCPResource]:
        """
        Enumerates available MCP resources (notebooks, pages, entries) within the configured scope.

        This method performs resource discovery by querying the LabArchives API for accessible
        resources and transforming them into MCP-compliant resource objects. It handles scope
        enforcement, error handling, and comprehensive logging for all resource listing operations.

        The method supports different scoping modes:
        - No scope: Lists all accessible notebooks
        - Notebook scope: Lists pages within a specific notebook
        - Folder scope: Lists pages within a specific folder

        Returns:
            List[MCPResource]: List of MCP resources available within the configured scope

        Raises:
            LabArchivesMCPException: If resource listing fails due to API errors or scope violations
            APIAuthenticationError: If authentication with LabArchives API fails
            APIPermissionError: If the user lacks permission to access requested resources
        """
        # Log the start of resource listing operation
        self.logger.info(
            "Starting resource listing operation",
            extra={"scope_config": self.scope_config, "operation": "list_resources"},
        )

        try:
            resources = []

            # Extract scope parameters for routing
            notebook_id = self.scope_config.get('notebook_id')
            notebook_name = self.scope_config.get('notebook_name')
            folder_path = self.scope_config.get('folder_path')

            # Determine scope type and handle accordingly
            if notebook_id:
                # List pages within a specific notebook
                self.logger.debug(f"Listing pages for notebook ID: {notebook_id}")

                try:
                    # Get page list for the specified notebook
                    page_list_response = self.api_client.list_pages(notebook_id)

                    # Apply folder filtering if configured using exact path matching with root-level page support
                    pages_to_process = page_list_response.pages
                    if folder_path is not None:
                        if folder_path.strip() in ['', '/']:
                            # Root folder scope - include ALL pages including root-level ones
                            self.logger.debug(
                                f"Root folder scope configured - including all pages including root-level pages"
                            )
                            pages_to_process = page_list_response.pages
                        else:
                            # Non-root folder scope - filter pages by folder hierarchy
                            try:
                                folder_scope = FolderPath.from_raw(folder_path)
                                filtered_pages = []
                                for page in page_list_response.pages:
                                    # Include page if it's within the folder scope OR if it's root-level and scope allows
                                    if page.folder_path and page.folder_path.strip():
                                        try:
                                            page_folder = FolderPath.from_raw(page.folder_path)
                                            # Include page if it's within the folder scope (exact parent-child relationship)
                                            if (
                                                folder_scope.is_parent_of(page_folder)
                                                or folder_scope.components == page_folder.components
                                            ):
                                                filtered_pages.append(page)
                                        except Exception as e:
                                            self.logger.warning(
                                                f"Error processing page folder path '{page.folder_path}': {e}"
                                            )
                                            continue
                                    # Note: Root-level pages (empty folder_path) are NOT included in non-root folder scopes
                                pages_to_process = filtered_pages
                            except Exception as e:
                                self.logger.warning(f"Invalid folder path '{folder_path}': {e}")
                                pages_to_process = []

                    # Transform each page to MCP resource
                    for page in pages_to_process:
                        # Create parent URI for hierarchical context
                        parent_uri = f"{MCP_RESOURCE_URI_SCHEME}notebook/{notebook_id}"

                        # Transform to MCP resource
                        mcp_resource = labarchives_to_mcp_resource(page, parent_uri)
                        resources.append(mcp_resource)

                        self.logger.debug(f"Added page resource: {mcp_resource.uri}")

                except APIPermissionError as e:
                    self.logger.error(f"Permission denied for notebook {notebook_id}: {e}")
                    raise LabArchivesMCPException(
                        message=f"Access denied to notebook {notebook_id}",
                        code=403,
                        context={"notebook_id": notebook_id, "error": str(e)},
                    )

                except APIError as e:
                    self.logger.error(f"API error listing pages for notebook {notebook_id}: {e}")
                    raise LabArchivesMCPException(
                        message=f"Failed to list pages for notebook {notebook_id}",
                        code=500,
                        context={"notebook_id": notebook_id, "error": str(e)},
                    )

            elif notebook_name:
                # First, find the notebook by name, then list its pages
                self.logger.debug(f"Listing pages for notebook name: {notebook_name}")

                try:
                    # Get all accessible notebooks to find the one with matching name
                    notebook_list_response = self.api_client.list_notebooks()

                    # Find notebook with matching name
                    target_notebook = None
                    for notebook in notebook_list_response.notebooks:
                        if notebook.name == notebook_name:
                            target_notebook = notebook
                            break

                    if not target_notebook:
                        self.logger.warning(f"Notebook not found with name: {notebook_name}")
                        # Return empty list rather than error for better UX
                        return []

                    # List pages for the found notebook
                    page_list_response = self.api_client.list_pages(target_notebook.id)

                    # Apply folder filtering if configured using exact path matching with root-level page support
                    pages_to_process = page_list_response.pages
                    if folder_path is not None:
                        if folder_path.strip() in ['', '/']:
                            # Root folder scope - include ALL pages including root-level ones
                            self.logger.debug(
                                f"Root folder scope configured - including all pages including root-level pages"
                            )
                            pages_to_process = page_list_response.pages
                        else:
                            # Non-root folder scope - filter pages by folder hierarchy
                            try:
                                folder_scope = FolderPath.from_raw(folder_path)
                                filtered_pages = []
                                for page in page_list_response.pages:
                                    # Include page if it's within the folder scope OR if it's root-level and scope allows
                                    if page.folder_path and page.folder_path.strip():
                                        try:
                                            page_folder = FolderPath.from_raw(page.folder_path)
                                            # Include page if it's within the folder scope (exact parent-child relationship)
                                            if (
                                                folder_scope.is_parent_of(page_folder)
                                                or folder_scope.components == page_folder.components
                                            ):
                                                filtered_pages.append(page)
                                        except Exception as e:
                                            self.logger.warning(
                                                f"Error processing page folder path '{page.folder_path}': {e}"
                                            )
                                            continue
                                    # Note: Root-level pages (empty folder_path) are NOT included in non-root folder scopes
                                pages_to_process = filtered_pages
                            except Exception as e:
                                self.logger.warning(f"Invalid folder path '{folder_path}': {e}")
                                pages_to_process = []

                    # Transform each page to MCP resource
                    for page in pages_to_process:
                        # Create parent URI for hierarchical context
                        parent_uri = f"{MCP_RESOURCE_URI_SCHEME}notebook/{target_notebook.id}"

                        # Transform to MCP resource
                        mcp_resource = labarchives_to_mcp_resource(page, parent_uri)
                        resources.append(mcp_resource)

                        self.logger.debug(f"Added page resource: {mcp_resource.uri}")

                except APIError as e:
                    self.logger.error(f"API error finding notebook by name '{notebook_name}': {e}")
                    raise LabArchivesMCPException(
                        message=f"Failed to find notebook '{notebook_name}'",
                        code=500,
                        context={"notebook_name": notebook_name, "error": str(e)},
                    )

            else:
                # No specific notebook scope - check for folder scope
                if folder_path and folder_path.strip():
                    # Two-phase listing with folder scope: find notebooks containing pages in folder scope, then return filtered pages
                    self.logger.debug(
                        f"Performing two-phase listing with folder scope: {folder_path}"
                    )

                    try:
                        # Phase 1: Get all accessible notebooks and filter to those containing pages in folder scope
                        notebook_list_response = self.api_client.list_notebooks()

                        try:
                            folder_scope = FolderPath.from_raw(folder_path)
                        except Exception as e:
                            self.logger.warning(f"Invalid folder path '{folder_path}': {e}")
                            return []

                        notebooks_with_scope = []
                        for notebook in notebook_list_response.notebooks:
                            if self._notebook_contains_folder(notebook, folder_path):
                                notebooks_with_scope.append(notebook)
                                self.logger.debug(
                                    f"Notebook {notebook.id} contains pages in folder {folder_path}"
                                )

                        # Phase 2: For each notebook containing pages in scope, list and filter pages
                        for notebook in notebooks_with_scope:
                            try:
                                page_list_response = self.api_client.list_pages(notebook.id)

                                # Filter pages to only those within folder scope with root-level page support
                                for page in page_list_response.pages:
                                    include_page = False

                                    # Special handling for root folder scope - include ALL pages including root-level
                                    if folder_scope.is_root or folder_path.strip() in [
                                        '',
                                        '/',
                                    ]:
                                        include_page = True
                                        self.logger.debug(
                                            f"Including page {page.id} - root scope includes all pages"
                                        )
                                    elif page.folder_path and page.folder_path.strip():
                                        # Non-root scope with non-empty page folder path
                                        try:
                                            page_folder = FolderPath.from_raw(page.folder_path)
                                            # Include page if it's within the folder scope (exact parent-child relationship)
                                            if (
                                                folder_scope.is_parent_of(page_folder)
                                                or folder_scope.components == page_folder.components
                                            ):
                                                include_page = True
                                                self.logger.debug(
                                                    f"Including page {page.id} - within folder scope '{folder_scope}'"
                                                )
                                        except Exception as e:
                                            self.logger.warning(
                                                f"Error processing page folder path '{page.folder_path}': {e}"
                                            )
                                            continue
                                    elif not page.folder_path or page.folder_path.strip() == '':
                                        # Root-level page (empty folder_path) - only include if folder scope is root
                                        if folder_scope.is_root or folder_path.strip() in ['', '/']:
                                            include_page = True
                                            self.logger.debug(
                                                f"Including root-level page {page.id} - root scope allows root pages"
                                            )
                                        else:
                                            self.logger.debug(
                                                f"Excluding root-level page {page.id} - non-root scope excludes root pages"
                                            )

                                    # Add page if it should be included
                                    if include_page:
                                        # Create parent URI for hierarchical context
                                        parent_uri = (
                                            f"{MCP_RESOURCE_URI_SCHEME}notebook/{notebook.id}"
                                        )

                                        # Transform to MCP resource
                                        mcp_resource = labarchives_to_mcp_resource(page, parent_uri)
                                        resources.append(mcp_resource)

                                        self.logger.debug(
                                            f"Added page resource: {mcp_resource.uri}"
                                        )

                            except APIError as e:
                                self.logger.warning(
                                    f"API error listing pages for notebook {notebook.id}: {e}"
                                )
                                continue

                    except APIError as e:
                        self.logger.error(f"API error during two-phase listing: {e}")
                        raise LabArchivesMCPException(
                            message="Failed to list resources with folder scope",
                            code=500,
                            context={"folder_path": folder_path, "error": str(e)},
                        )

                else:
                    # No scope limitation - list all accessible notebooks
                    self.logger.debug("Listing all accessible notebooks (no scope)")

                    try:
                        # Get all accessible notebooks
                        notebook_list_response = self.api_client.list_notebooks()

                        # Transform each notebook to MCP resource
                        for notebook in notebook_list_response.notebooks:
                            # Transform to MCP resource
                            mcp_resource = labarchives_to_mcp_resource(notebook)
                            resources.append(mcp_resource)
                            self.logger.debug(f"Added notebook resource: {mcp_resource.uri}")

                    except APIError as e:
                        self.logger.error(f"API error listing notebooks: {e}")
                        raise LabArchivesMCPException(
                            message="Failed to list notebooks",
                            code=500,
                            context={"error": str(e)},
                        )

            # Log successful completion
            self.logger.info(
                f"Resource listing completed successfully",
                extra={
                    "resource_count": len(resources),
                    "scope_type": (
                        "notebook_id"
                        if notebook_id
                        else "notebook_name" if notebook_name else "all"
                    ),
                    "operation": "list_resources",
                },
            )

            return resources

        except APIAuthenticationError as e:
            self.logger.error(f"Authentication error during resource listing: {e}")
            raise LabArchivesMCPException(
                message="Authentication failed during resource listing",
                code=401,
                context={"error": str(e)},
            )

        except LabArchivesMCPException:
            # Re-raise MCP exceptions without modification
            raise

        except Exception as e:
            self.logger.error(
                f"Unexpected error during resource listing: {e}",
                extra={"error_type": type(e).__name__, "operation": "list_resources"},
            )
            raise LabArchivesMCPException(
                message=f"Unexpected error during resource listing: {str(e)}",
                code=500,
                context={"error": str(e), "error_type": type(e).__name__},
            )

    def read_resource(self, uri: str) -> MCPResourceContent:
        """
        Fetches detailed content for a specific MCP resource URI (notebook, page, or entry).

        This method retrieves comprehensive content for a specified resource, enforcing scope
        limitations and permissions. It handles URI parsing, scope validation, API interaction,
        data transformation, and comprehensive logging for all resource reading operations.

        Supported resource types:
        - Notebook: Returns notebook metadata and page summaries
        - Page: Returns page metadata and entry summaries
        - Entry: Returns detailed entry content and metadata

        Args:
            uri (str): MCP resource URI to read (e.g., "labarchives://notebook/123")

        Returns:
            MCPResourceContent: Structured content for the requested resource with metadata
                               and optional JSON-LD context

        Raises:
            LabArchivesMCPException: If the resource URI is invalid or resource reading fails
            APIAuthenticationError: If authentication with LabArchives API fails
            APIPermissionError: If the user lacks permission to access the requested resource
        """
        # Log the start of resource read operation
        self.logger.info(
            f"Starting resource read operation",
            extra={"uri": uri, "operation": "read_resource"},
        )

        try:
            # Parse the resource URI to extract type and identifiers
            resource_info = parse_resource_uri(uri)

            # Validate that the resource is within the configured scope
            if not is_resource_in_scope(resource_info, self.scope_config):
                self.logger.warning(
                    f"Resource access denied - outside configured scope",
                    extra={
                        "uri": uri,
                        "resource_info": resource_info,
                        "scope_config": self.scope_config,
                    },
                )
                raise LabArchivesMCPException(
                    message="Resource access denied - outside configured scope",
                    code=403,
                    context={
                        "uri": uri,
                        "resource_info": resource_info,
                        "scope_config": self.scope_config,
                    },
                )

            # Handle resource reading based on type
            resource_type = resource_info.get('type')

            if resource_type == 'notebook':
                # Read notebook content with page summaries and folder scope validation
                notebook_id = resource_info.get('notebook_id')
                self.logger.debug(f"Reading notebook content: {notebook_id}")

                try:
                    # Get notebook metadata by listing all notebooks and finding the match
                    notebook_list_response = self.api_client.list_notebooks()

                    # Find the target notebook
                    target_notebook = None
                    for notebook in notebook_list_response.notebooks:
                        if notebook.id == notebook_id:
                            target_notebook = notebook
                            break

                    if not target_notebook:
                        self.logger.error(f"Notebook not found: {notebook_id}")
                        raise LabArchivesMCPException(
                            message=f"Notebook not found: {notebook_id}",
                            code=404,
                            context={"notebook_id": notebook_id},
                        )

                    # Critical Security Fix: Prevent information leakage when only folder scope is configured
                    # Direct notebook reads must be blocked if notebook has no pages in the configured folder scope
                    folder_path = self.scope_config.get('folder_path')
                    if (
                        folder_path is not None
                        and not self.scope_config.get('notebook_id')
                        and not self.scope_config.get('notebook_name')
                    ):
                        # Only folder scope is configured - validate notebook contains pages in folder scope
                        self.logger.debug(
                            f"Validating notebook {notebook_id} contains pages in folder scope: {folder_path}",
                            extra={
                                "notebook_id": notebook_id,
                                "folder_scope": folder_path,
                                "validation_type": "notebook_folder_scope_containment",
                            },
                        )

                        # Use the integrated folder scope validation
                        try:
                            notebook_contains_folder_pages = validate_folder_scope_access(
                                resource_info={
                                    'type': 'notebook',
                                    'notebook_id': notebook_id,
                                },
                                folder_scope=folder_path,
                                resource_metadata={
                                    'notebook_folders': [],  # Will be populated below
                                    'has_root_pages': False,  # Will be populated below
                                },
                            )

                            # Get page list to check for folder containment
                            page_list_response = self.api_client.list_pages(notebook_id)

                            # Build folder metadata for validation
                            notebook_folders = set()
                            has_root_pages = False
                            for page in page_list_response.pages:
                                if page.folder_path and page.folder_path.strip():
                                    notebook_folders.add(page.folder_path)
                                else:
                                    has_root_pages = True

                            # Update metadata and re-validate
                            updated_metadata = {
                                'notebook_folders': list(notebook_folders),
                                'has_root_pages': has_root_pages,
                            }

                            # Check if notebook contains pages within folder scope
                            if folder_path.strip() in ['', '/']:
                                # Root scope allows access if notebook has any pages
                                folder_scope_allows_access = len(page_list_response.pages) > 0
                            else:
                                # Non-root scope requires pages within specific folder
                                folder_scope_allows_access = False
                                try:
                                    scope_folder = FolderPath.from_raw(folder_path)
                                    for page in page_list_response.pages:
                                        if page.folder_path and page.folder_path.strip():
                                            try:
                                                page_folder = FolderPath.from_raw(page.folder_path)
                                                if (
                                                    scope_folder.is_parent_of(page_folder)
                                                    or scope_folder.components
                                                    == page_folder.components
                                                ):
                                                    folder_scope_allows_access = True
                                                    break
                                            except Exception as e:
                                                self.logger.warning(
                                                    f"Error processing page folder path '{page.folder_path}': {e}"
                                                )
                                                continue
                                except Exception as e:
                                    self.logger.error(
                                        f"Error parsing folder scope '{folder_path}': {e}"
                                    )
                                    folder_scope_allows_access = False

                            if not folder_scope_allows_access:
                                self.logger.warning(
                                    f"Direct notebook {notebook_id} read denied - no pages in configured folder scope '{folder_path}'",
                                    extra={
                                        "notebook_id": notebook_id,
                                        "folder_scope": folder_path,
                                        "notebook_folders": list(notebook_folders),
                                        "has_root_pages": has_root_pages,
                                        "security_violation": "notebook_metadata_leakage_prevention",
                                    },
                                )
                                raise LabArchivesMCPException(
                                    message=f"Direct notebook {notebook_id} read denied: no pages in configured folder scope '{folder_path}'",
                                    code=403,
                                    context={
                                        "notebook_id": notebook_id,
                                        "configured_folder_scope": folder_path,
                                        "notebook_folders": list(notebook_folders),
                                        "violation_type": "notebook_folder_scope_metadata_leakage",
                                    },
                                )
                            else:
                                self.logger.debug(
                                    f"Notebook {notebook_id} contains pages in folder scope '{folder_path}' - access allowed",
                                    extra={
                                        "notebook_id": notebook_id,
                                        "folder_scope": folder_path,
                                        "validation_result": "notebook_folder_scope_validated",
                                    },
                                )

                        except LabArchivesMCPException:
                            # Re-raise security violations
                            raise
                        except Exception as e:
                            # Fail secure on validation errors
                            self.logger.error(
                                f"Error validating notebook {notebook_id} folder scope - denying access: {e}",
                                extra={
                                    "notebook_id": notebook_id,
                                    "folder_scope": folder_path,
                                    "error_type": type(e).__name__,
                                    "security_decision": "fail_secure_validation_error",
                                },
                            )
                            raise LabArchivesMCPException(
                                message=f"Cannot validate notebook {notebook_id} folder scope - access denied for security",
                                code=403,
                                context={
                                    "notebook_id": notebook_id,
                                    "configured_folder_scope": folder_path,
                                    "error": str(e),
                                    "violation_type": "notebook_folder_validation_failure",
                                },
                            )

                    # Get page list for the notebook
                    page_list_response = self.api_client.list_pages(notebook_id)

                    # Apply folder filtering if configured using exact path matching with root-level page support
                    pages_to_include = page_list_response.pages
                    folder_path = self.scope_config.get('folder_path')
                    if folder_path is not None:
                        if folder_path.strip() in ['', '/']:
                            # Root folder scope - include ALL pages including root-level ones
                            self.logger.debug(
                                f"Root folder scope configured - including all pages including root-level pages"
                            )
                            pages_to_include = page_list_response.pages
                        else:
                            # Non-root folder scope - filter pages by folder hierarchy
                            try:
                                folder_scope = FolderPath.from_raw(folder_path)
                                filtered_pages = []
                                for page in page_list_response.pages:
                                    # Include page if it's within the folder scope OR if it's root-level and scope allows
                                    if page.folder_path and page.folder_path.strip():
                                        try:
                                            page_folder = FolderPath.from_raw(page.folder_path)
                                            # Include page if it's within the folder scope (exact parent-child relationship)
                                            if (
                                                folder_scope.is_parent_of(page_folder)
                                                or folder_scope.components == page_folder.components
                                            ):
                                                filtered_pages.append(page)
                                        except Exception as e:
                                            self.logger.warning(
                                                f"Error processing page folder path '{page.folder_path}': {e}"
                                            )
                                            continue
                                    # Note: Root-level pages (empty folder_path) are NOT included in non-root folder scopes
                                pages_to_include = filtered_pages
                            except Exception as e:
                                self.logger.warning(f"Invalid folder path '{folder_path}': {e}")
                                pages_to_include = []

                    # Create comprehensive notebook content
                    notebook_content = {
                        "id": target_notebook.id,
                        "name": target_notebook.name,
                        "description": target_notebook.description,
                        "owner": target_notebook.owner,
                        "created": target_notebook.created_date.isoformat(),
                        "modified": target_notebook.last_modified.isoformat(),
                        "folder_count": target_notebook.folder_count,
                        "page_count": target_notebook.page_count,
                        "pages": [
                            {
                                "id": page.id,
                                "title": page.title,
                                "folder_path": page.folder_path,
                                "author": page.author,
                                "created": page.created_date.isoformat(),
                                "modified": page.last_modified.isoformat(),
                                "entry_count": page.entry_count,
                            }
                            for page in pages_to_include
                        ],
                    }

                    # Create metadata for the resource
                    metadata = {
                        "resource_type": "notebook",
                        "uri": uri,
                        "notebook_id": notebook_id,
                        "created": target_notebook.created_date.isoformat(),
                        "modified": target_notebook.last_modified.isoformat(),
                        "owner": target_notebook.owner,
                        "total_pages": len(page_list_response.pages),
                        "retrieved_at": datetime.utcnow().isoformat(),
                    }

                    # Create MCPResourceContent with optional JSON-LD context
                    resource_content = MCPResourceContent(
                        content=notebook_content,
                        context=MCP_JSONLD_CONTEXT if self.jsonld_enabled else None,
                        metadata=metadata,
                    )

                    self.logger.info(
                        f"Successfully read notebook content",
                        extra={
                            "notebook_id": notebook_id,
                            "page_count": len(page_list_response.pages),
                            "uri": uri,
                        },
                    )

                    return resource_content

                except APIPermissionError as e:
                    self.logger.error(f"Permission denied for notebook {notebook_id}: {e}")
                    raise LabArchivesMCPException(
                        message=f"Access denied to notebook {notebook_id}",
                        code=403,
                        context={"notebook_id": notebook_id, "error": str(e)},
                    )

                except APIError as e:
                    self.logger.error(f"API error reading notebook {notebook_id}: {e}")
                    raise LabArchivesMCPException(
                        message=f"Failed to read notebook {notebook_id}",
                        code=500,
                        context={"notebook_id": notebook_id, "error": str(e)},
                    )

            elif resource_type == 'page':
                # Read page content with entry summaries
                notebook_id = resource_info.get('notebook_id')
                page_id = resource_info.get('page_id')
                self.logger.debug(f"Reading page content: {page_id} in notebook {notebook_id}")

                try:
                    # Get page metadata by listing pages in the notebook
                    page_list_response = self.api_client.list_pages(notebook_id)

                    # Find the target page
                    target_page = None
                    for page in page_list_response.pages:
                        if page.id == page_id:
                            target_page = page
                            break

                    if not target_page:
                        self.logger.error(f"Page not found: {page_id} in notebook {notebook_id}")
                        raise LabArchivesMCPException(
                            message=f"Page not found: {page_id}",
                            code=404,
                            context={"page_id": page_id, "notebook_id": notebook_id},
                        )

                    # Validate folder scope for pages using exact path matching with root-level page support
                    folder_path = self.scope_config.get('folder_path')
                    if folder_path is not None:
                        if folder_path.strip() in ['', '/']:
                            # Root folder scope - allow all pages including root-level ones
                            self.logger.debug(
                                f"Page {page_id} allowed - root folder scope includes all pages"
                            )
                        else:
                            # Non-root folder scope - validate page folder against scope
                            if target_page.folder_path and target_page.folder_path.strip():
                                try:
                                    folder_scope = FolderPath.from_raw(folder_path)
                                    page_folder = FolderPath.from_raw(target_page.folder_path)

                                    # Check if page is within folder scope using exact parent-child relationship
                                    if not (
                                        folder_scope.is_parent_of(page_folder)
                                        or folder_scope.components == page_folder.components
                                    ):
                                        self.logger.warning(
                                            f"Page {page_id} access denied - folder '{target_page.folder_path}' outside scope '{folder_path}'",
                                            extra={
                                                "page_id": page_id,
                                                "page_folder_path": target_page.folder_path,
                                                "configured_folder_scope": folder_path,
                                                "security_violation": "page_folder_scope_violation",
                                            },
                                        )
                                        raise LabArchivesMCPException(
                                            message=f"Page {page_id} access denied: folder '{target_page.folder_path}' is outside configured scope '{folder_path}'",
                                            code=403,
                                            context={
                                                "page_id": page_id,
                                                "page_folder_path": target_page.folder_path,
                                                "configured_folder_scope": folder_path,
                                                "violation_type": "page_folder_scope_violation",
                                            },
                                        )
                                    else:
                                        self.logger.debug(
                                            f"Page {page_id} validated - folder '{target_page.folder_path}' within scope '{folder_path}'"
                                        )
                                except LabArchivesMCPException:
                                    # Re-raise scope violations
                                    raise
                                except Exception as e:
                                    self.logger.error(
                                        f"Error validating folder scope for page {page_id}: {e}"
                                    )
                                    raise LabArchivesMCPException(
                                        message=f"Cannot validate folder scope for page {page_id} - access denied for security",
                                        code=403,
                                        context={
                                            "page_id": page_id,
                                            "configured_folder_scope": folder_path,
                                            "error": str(e),
                                            "violation_type": "page_folder_validation_failure",
                                        },
                                    )
                            elif (
                                not target_page.folder_path or target_page.folder_path.strip() == ''
                            ):
                                # Root-level page with non-root folder scope - deny access
                                self.logger.warning(
                                    f"Root-level page {page_id} access denied - non-root folder scope '{folder_path}' excludes root pages",
                                    extra={
                                        "page_id": page_id,
                                        "page_folder_path": target_page.folder_path,
                                        "configured_folder_scope": folder_path,
                                        "security_violation": "root_page_non_root_scope_violation",
                                    },
                                )
                                raise LabArchivesMCPException(
                                    message=f"Root-level page {page_id} access denied: non-root folder scope '{folder_path}' excludes root-level pages",
                                    code=403,
                                    context={
                                        "page_id": page_id,
                                        "page_folder_path": target_page.folder_path,
                                        "configured_folder_scope": folder_path,
                                        "violation_type": "root_page_non_root_scope_violation",
                                    },
                                )

                    # Get entry list for the page
                    entry_list_response = self.api_client.list_entries(page_id)

                    # Create comprehensive page content
                    page_content = {
                        "id": target_page.id,
                        "notebook_id": target_page.notebook_id,
                        "title": target_page.title,
                        "folder_path": target_page.folder_path,
                        "author": target_page.author,
                        "created": target_page.created_date.isoformat(),
                        "modified": target_page.last_modified.isoformat(),
                        "entry_count": target_page.entry_count,
                        "entries": [
                            {
                                "id": entry.id,
                                "entry_type": entry.entry_type,
                                "title": entry.title,
                                "author": entry.author,
                                "created": entry.created_date.isoformat(),
                                "modified": entry.last_modified.isoformat(),
                                "version": entry.version,
                                "content_preview": (
                                    entry.content[:200] + "..."
                                    if len(entry.content) > 200
                                    else entry.content
                                ),
                            }
                            for entry in entry_list_response.entries
                        ],
                    }

                    # Create metadata for the resource
                    metadata = {
                        "resource_type": "page",
                        "uri": uri,
                        "page_id": page_id,
                        "notebook_id": notebook_id,
                        "folder_path": target_page.folder_path,
                        "created": target_page.created_date.isoformat(),
                        "modified": target_page.last_modified.isoformat(),
                        "author": target_page.author,
                        "total_entries": len(entry_list_response.entries),
                        "retrieved_at": datetime.utcnow().isoformat(),
                    }

                    # Create MCPResourceContent with optional JSON-LD context
                    resource_content = MCPResourceContent(
                        content=page_content,
                        context=MCP_JSONLD_CONTEXT if self.jsonld_enabled else None,
                        metadata=metadata,
                    )

                    self.logger.info(
                        f"Successfully read page content",
                        extra={
                            "page_id": page_id,
                            "notebook_id": notebook_id,
                            "entry_count": len(entry_list_response.entries),
                            "uri": uri,
                        },
                    )

                    return resource_content

                except APIPermissionError as e:
                    self.logger.error(f"Permission denied for page {page_id}: {e}")
                    raise LabArchivesMCPException(
                        message=f"Access denied to page {page_id}",
                        code=403,
                        context={
                            "page_id": page_id,
                            "notebook_id": notebook_id,
                            "error": str(e),
                        },
                    )

                except APIError as e:
                    self.logger.error(f"API error reading page {page_id}: {e}")
                    raise LabArchivesMCPException(
                        message=f"Failed to read page {page_id}",
                        code=500,
                        context={
                            "page_id": page_id,
                            "notebook_id": notebook_id,
                            "error": str(e),
                        },
                    )

            elif resource_type == 'entry':
                # Read detailed entry content with entry-to-notebook validation
                entry_id = resource_info.get('entry_id')
                self.logger.debug(f"Reading entry content: {entry_id}")

                try:
                    # Get entry content
                    entry_response = self.api_client.get_entry_content(entry_id)

                    if not entry_response.entries:
                        self.logger.error(f"Entry not found: {entry_id}")
                        raise LabArchivesMCPException(
                            message=f"Entry not found: {entry_id}",
                            code=404,
                            context={"entry_id": entry_id},
                        )

                    # Get the entry (should be only one)
                    entry = entry_response.entries[0]

                    # Critical Security Fix: Validate entry-to-notebook ownership before content access
                    # This prevents unauthorized cross-notebook data access by ensuring entries
                    # can only be accessed if their parent notebook is within configured scope
                    notebook_id_scope = self.scope_config.get('notebook_id')
                    if notebook_id_scope:
                        # Find the notebook containing this entry through its parent page
                        entry_notebook_id = None
                        if entry.page_id:
                            try:
                                # Search through notebooks to find the one containing the entry's page
                                notebook_list_response = self.api_client.list_notebooks()
                                for notebook in notebook_list_response.notebooks:
                                    try:
                                        page_list_response = self.api_client.list_pages(notebook.id)
                                        for page in page_list_response.pages:
                                            if page.id == entry.page_id:
                                                entry_notebook_id = notebook.id
                                                break
                                        if entry_notebook_id:
                                            break
                                    except APIError:
                                        # Continue searching in other notebooks if one fails
                                        continue

                                # Validate entry belongs to notebook within scope
                                if entry_notebook_id != notebook_id_scope:
                                    self.logger.warning(
                                        f"Entry {entry_id} access denied - belongs to notebook {entry_notebook_id} outside configured scope [{notebook_id_scope}]",
                                        extra={
                                            "entry_id": entry_id,
                                            "entry_notebook_id": entry_notebook_id,
                                            "configured_notebook_scope": notebook_id_scope,
                                            "security_violation": "cross_notebook_entry_access",
                                        },
                                    )
                                    raise LabArchivesMCPException(
                                        message=f"Entry {entry_id} belongs to notebook {entry_notebook_id} which is outside configured scope [{notebook_id_scope}]",
                                        code=403,
                                        context={
                                            "entry_id": entry_id,
                                            "entry_notebook_id": entry_notebook_id,
                                            "configured_scope": notebook_id_scope,
                                            "violation_type": "cross_notebook_entry_access",
                                        },
                                    )
                                else:
                                    self.logger.debug(
                                        f"Entry {entry_id} validated - belongs to notebook {entry_notebook_id} within scope",
                                        extra={
                                            "entry_id": entry_id,
                                            "entry_notebook_id": entry_notebook_id,
                                            "configured_notebook_scope": notebook_id_scope,
                                            "validation_result": "entry_notebook_ownership_validated",
                                        },
                                    )
                            except APIError as api_error:
                                # If we cannot validate ownership, deny access for security
                                self.logger.error(
                                    f"Unable to validate entry {entry_id} notebook ownership - denying access: {api_error}",
                                    extra={
                                        "entry_id": entry_id,
                                        "configured_notebook_scope": notebook_id_scope,
                                        "security_decision": "fail_secure_entry_validation",
                                    },
                                )
                                raise LabArchivesMCPException(
                                    message=f"Cannot validate entry {entry_id} notebook ownership - access denied for security",
                                    code=403,
                                    context={
                                        "entry_id": entry_id,
                                        "configured_scope": notebook_id_scope,
                                        "error": str(api_error),
                                        "violation_type": "entry_validation_failure",
                                    },
                                )
                        else:
                            # Entry without page_id cannot be validated - deny access
                            self.logger.warning(
                                f"Entry {entry_id} has no page_id - cannot validate notebook ownership",
                                extra={
                                    "entry_id": entry_id,
                                    "configured_notebook_scope": notebook_id_scope,
                                    "security_decision": "fail_secure_no_page_id",
                                },
                            )
                            raise LabArchivesMCPException(
                                message=f"Entry {entry_id} cannot be validated for notebook ownership - access denied",
                                code=403,
                                context={
                                    "entry_id": entry_id,
                                    "configured_scope": notebook_id_scope,
                                    "violation_type": "entry_missing_page_id",
                                },
                            )

                    # Validate folder scope for entries by checking their parent page with root-level page support
                    folder_path = self.scope_config.get('folder_path')
                    if folder_path is not None and entry.page_id:
                        if folder_path.strip() in ['', '/']:
                            # Root folder scope - allow all entries including those on root-level pages
                            self.logger.debug(
                                f"Entry {entry_id} allowed - root folder scope includes all entries"
                            )
                        else:
                            # Non-root folder scope - validate parent page folder against scope
                            try:
                                # Find the parent page by searching through all notebooks
                                # This is necessary because EntryContent doesn't contain notebook_id
                                entry_page = None
                                notebook_list_response = self.api_client.list_notebooks()

                                for notebook in notebook_list_response.notebooks:
                                    try:
                                        page_list_response = self.api_client.list_pages(notebook.id)
                                        for page in page_list_response.pages:
                                            if page.id == entry.page_id:
                                                entry_page = page
                                                break
                                        if entry_page:
                                            break
                                    except APIError:
                                        # Continue searching in other notebooks if one fails
                                        continue

                                if entry_page:
                                    if entry_page.folder_path and entry_page.folder_path.strip():
                                        try:
                                            folder_scope = FolderPath.from_raw(folder_path)
                                            page_folder = FolderPath.from_raw(
                                                entry_page.folder_path
                                            )

                                            # Check if page is within folder scope using exact parent-child relationship
                                            if not (
                                                folder_scope.is_parent_of(page_folder)
                                                or folder_scope.components == page_folder.components
                                            ):
                                                self.logger.warning(
                                                    f"Entry {entry_id} access denied - parent page folder '{entry_page.folder_path}' outside scope '{folder_path}'",
                                                    extra={
                                                        "entry_id": entry_id,
                                                        "parent_page_id": entry_page.id,
                                                        "parent_page_folder_path": entry_page.folder_path,
                                                        "configured_folder_scope": folder_path,
                                                        "security_violation": "entry_parent_page_folder_scope_violation",
                                                    },
                                                )
                                                raise LabArchivesMCPException(
                                                    message=f"Entry {entry_id} access denied: parent page folder '{entry_page.folder_path}' is outside configured scope '{folder_path}'",
                                                    code=403,
                                                    context={
                                                        "entry_id": entry_id,
                                                        "parent_page_id": entry_page.id,
                                                        "parent_page_folder_path": entry_page.folder_path,
                                                        "configured_folder_scope": folder_path,
                                                        "violation_type": "entry_parent_page_folder_scope_violation",
                                                    },
                                                )
                                            else:
                                                self.logger.debug(
                                                    f"Entry {entry_id} validated - parent page folder '{entry_page.folder_path}' within scope '{folder_path}'"
                                                )
                                        except LabArchivesMCPException:
                                            # Re-raise scope violations
                                            raise
                                        except Exception as path_error:
                                            self.logger.error(
                                                f"Error validating folder scope for entry {entry_id}: {path_error}"
                                            )
                                            raise LabArchivesMCPException(
                                                message=f"Cannot validate folder scope for entry {entry_id} - access denied for security",
                                                code=403,
                                                context={
                                                    "entry_id": entry_id,
                                                    "configured_folder_scope": folder_path,
                                                    "error": str(path_error),
                                                    "violation_type": "entry_folder_validation_failure",
                                                },
                                            )
                                    elif (
                                        not entry_page.folder_path
                                        or entry_page.folder_path.strip() == ''
                                    ):
                                        # Entry on root-level page with non-root folder scope - deny access
                                        self.logger.warning(
                                            f"Entry {entry_id} access denied - on root-level page but non-root folder scope '{folder_path}' excludes root pages",
                                            extra={
                                                "entry_id": entry_id,
                                                "parent_page_id": entry_page.id,
                                                "parent_page_folder_path": entry_page.folder_path,
                                                "configured_folder_scope": folder_path,
                                                "security_violation": "entry_root_page_non_root_scope_violation",
                                            },
                                        )
                                        raise LabArchivesMCPException(
                                            message=f"Entry {entry_id} access denied: on root-level page but non-root folder scope '{folder_path}' excludes root-level pages",
                                            code=403,
                                            context={
                                                "entry_id": entry_id,
                                                "parent_page_id": entry_page.id,
                                                "parent_page_folder_path": entry_page.folder_path,
                                                "configured_folder_scope": folder_path,
                                                "violation_type": "entry_root_page_non_root_scope_violation",
                                            },
                                        )
                                else:
                                    # Cannot find parent page - deny access for security
                                    self.logger.error(
                                        f"Cannot find parent page for entry {entry_id} - denying access",
                                        extra={
                                            "entry_id": entry_id,
                                            "parent_page_id": entry.page_id,
                                            "configured_folder_scope": folder_path,
                                            "security_decision": "fail_secure_parent_page_not_found",
                                        },
                                    )
                                    raise LabArchivesMCPException(
                                        message=f"Cannot find parent page for entry {entry_id} - access denied for security",
                                        code=403,
                                        context={
                                            "entry_id": entry_id,
                                            "parent_page_id": entry.page_id,
                                            "configured_folder_scope": folder_path,
                                            "violation_type": "entry_parent_page_not_found",
                                        },
                                    )
                            except APIError as api_error:
                                # If we can't validate the folder scope, deny access for security
                                self.logger.error(
                                    f"Unable to validate folder scope for entry {entry_id}: {api_error}",
                                    extra={
                                        "entry_id": entry_id,
                                        "configured_folder_scope": folder_path,
                                        "error_type": type(api_error).__name__,
                                        "security_decision": "fail_secure_api_error",
                                    },
                                )
                                raise LabArchivesMCPException(
                                    message=f"Cannot validate folder scope for entry {entry_id} - access denied for security",
                                    code=403,
                                    context={
                                        "entry_id": entry_id,
                                        "configured_folder_scope": folder_path,
                                        "error": str(api_error),
                                        "violation_type": "entry_folder_validation_api_failure",
                                    },
                                )

                    # Transform to MCP resource content using the existing function
                    resource_content = labarchives_to_mcp_resource(entry)

                    # Override context based on jsonld_enabled flag
                    if not self.jsonld_enabled:
                        resource_content.context = None

                    # Add retrieval timestamp to metadata
                    if resource_content.metadata:
                        resource_content.metadata["retrieved_at"] = datetime.utcnow().isoformat()

                    self.logger.info(
                        f"Successfully read entry content",
                        extra={
                            "entry_id": entry_id,
                            "entry_type": entry.entry_type,
                            "content_length": len(entry.content),
                            "uri": uri,
                        },
                    )

                    return resource_content

                except APIPermissionError as e:
                    self.logger.error(f"Permission denied for entry {entry_id}: {e}")
                    raise LabArchivesMCPException(
                        message=f"Access denied to entry {entry_id}",
                        code=403,
                        context={"entry_id": entry_id, "error": str(e)},
                    )

                except APIError as e:
                    self.logger.error(f"API error reading entry {entry_id}: {e}")
                    raise LabArchivesMCPException(
                        message=f"Failed to read entry {entry_id}",
                        code=500,
                        context={"entry_id": entry_id, "error": str(e)},
                    )

            else:
                # Unsupported resource type
                self.logger.error(f"Unsupported resource type: {resource_type}")
                raise LabArchivesMCPException(
                    message=f"Unsupported resource type: {resource_type}",
                    code=400,
                    context={"resource_type": resource_type, "uri": uri},
                )

        except APIAuthenticationError as e:
            self.logger.error(f"Authentication error during resource reading: {e}")
            raise LabArchivesMCPException(
                message="Authentication failed during resource reading",
                code=401,
                context={"uri": uri, "error": str(e)},
            )

        except LabArchivesMCPException:
            # Re-raise MCP exceptions without modification
            raise

        except Exception as e:
            self.logger.error(
                f"Unexpected error during resource reading: {e}",
                extra={
                    "error_type": type(e).__name__,
                    "uri": uri,
                    "operation": "read_resource",
                },
            )
            raise LabArchivesMCPException(
                message=f"Unexpected error during resource reading: {str(e)}",
                code=500,
                context={"uri": uri, "error": str(e), "error_type": type(e).__name__},
            )


# Export the main classes and functions for external use
__all__ = ["ResourceManager", "parse_resource_uri", "is_resource_in_scope"]
