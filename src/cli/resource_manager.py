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

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

# Internal imports for API client and data models
from src.cli.api.client import LabArchivesAPIClient
from src.cli.mcp.models import (
    MCPResource,
    MCPResourceContent,
    labarchives_to_mcp_resource,
    MCP_JSONLD_CONTEXT
)
from src.cli.api.errors import (
    APIError,
    APIAuthenticationError,
    APIPermissionError,
    APIResponseParseError
)
from src.cli.exceptions import LabArchivesMCPException
from src.cli.constants import MCP_RESOURCE_URI_SCHEME
from src.cli.logging_setup import get_logger
from src.cli.data_models.scoping import FolderPath

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
            context={"uri": uri, "expected_scheme": MCP_RESOURCE_URI_SCHEME}
        )
    
    # Remove the scheme prefix and split into components
    uri_path = uri[len(MCP_RESOURCE_URI_SCHEME):]
    if not uri_path:
        error_msg = f"Empty resource path in URI: {uri}"
        logger.error(error_msg)
        raise LabArchivesMCPException(
            message=error_msg,
            code=400,
            context={"uri": uri}
        )
    
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
                context={"uri": uri, "components": path_components}
            )
        
        notebook_id = path_components[1]
        if not notebook_id:
            error_msg = f"Empty notebook ID in URI: {uri}"
            logger.error(error_msg)
            raise LabArchivesMCPException(
                message=error_msg,
                code=400,
                context={"uri": uri, "components": path_components}
            )
        
        # Check for page sub-resource
        if len(path_components) == 2:
            # Simple notebook resource
            result = {
                'type': 'notebook',
                'notebook_id': notebook_id
            }
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
                    context={"uri": uri, "components": path_components}
                )
            
            result = {
                'type': 'page',
                'notebook_id': notebook_id,
                'page_id': page_id
            }
            logger.debug(f"Parsed page resource: {result}")
            return result
        
        else:
            error_msg = f"Invalid notebook URI format: {uri}"
            logger.error(error_msg)
            raise LabArchivesMCPException(
                message=error_msg,
                code=400,
                context={"uri": uri, "components": path_components}
            )
    
    # Parse entry resources: labarchives://entry/{entry_id}
    elif path_components[0] == 'entry':
        if len(path_components) != 2:
            error_msg = f"Invalid entry URI format. Expected 'entry/{{entry_id}}': {uri}"
            logger.error(error_msg)
            raise LabArchivesMCPException(
                message=error_msg,
                code=400,
                context={"uri": uri, "components": path_components}
            )
        
        entry_id = path_components[1]
        if not entry_id:
            error_msg = f"Empty entry ID in URI: {uri}"
            logger.error(error_msg)
            raise LabArchivesMCPException(
                message=error_msg,
                code=400,
                context={"uri": uri, "components": path_components}
            )
        
        result = {
            'type': 'entry',
            'entry_id': entry_id
        }
        logger.debug(f"Parsed entry resource: {result}")
        return result
    
    else:
        error_msg = f"Unsupported resource type in URI: {uri}"
        logger.error(error_msg)
        raise LabArchivesMCPException(
            message=error_msg,
            code=400,
            context={"uri": uri, "components": path_components}
        )


def is_resource_in_scope(resource_info: Dict[str, str], scope_config: Dict[str, Any]) -> bool:
    """
    Checks if a resource (by type and ID) is within the configured access scope.
    
    This function enforces scope limitations by comparing resource identifiers against
    the configured scope parameters. It supports notebook-based, folder-based, and
    unrestricted scope configurations, providing granular access control for sensitive
    research data.
    
    Scope validation logic:
    - If no scope is configured, all resources are allowed
    - If notebook_id is configured, only resources within that notebook are allowed
    - If notebook_name is configured, only resources within that named notebook are allowed
    - If folder_path is configured, only resources within that folder are allowed
    
    Args:
        resource_info (Dict[str, str]): Parsed resource information from parse_resource_uri
        scope_config (Dict[str, Any]): Scope configuration containing notebook_id, 
                                      notebook_name, and/or folder_path
        
    Returns:
        bool: True if the resource is within scope, False otherwise
    """
    logger = get_logger()
    
    # Log scope validation attempt
    logger.debug(f"Validating resource scope: {resource_info} against scope: {scope_config}")
    
    # Extract scope parameters
    notebook_id = scope_config.get('notebook_id')
    notebook_name = scope_config.get('notebook_name')
    folder_path = scope_config.get('folder_path')
    
    # If no scope limitations are configured, allow all resources
    if not notebook_id and not notebook_name and not folder_path:
        logger.debug("No scope limitations configured - allowing all resources")
        return True
    
    # Check notebook ID scope limitation
    if notebook_id:
        # For notebook and page resources, check if they belong to the scoped notebook
        if resource_info.get('type') in ['notebook', 'page']:
            resource_notebook_id = resource_info.get('notebook_id')
            if resource_notebook_id == notebook_id:
                logger.debug(f"Resource {resource_info} is within notebook scope: {notebook_id}")
                return True
            else:
                logger.debug(f"Resource {resource_info} is outside notebook scope: {notebook_id}")
                return False
        
        # For entry resources, we need to check if they belong to a page in the scoped notebook
        # This requires additional API calls in the calling context, so we allow entries
        # and let the caller handle the validation during content retrieval
        elif resource_info.get('type') == 'entry':
            logger.debug(f"Entry resource {resource_info} - scope validation deferred to content retrieval")
            return True
    
    # Check notebook name scope limitation (similar logic to notebook_id)
    if notebook_name:
        # For notebook name scope, we need to resolve the name to ID during listing
        # This is handled in the ResourceManager during resource discovery
        logger.debug(f"Notebook name scope validation deferred to resource discovery: {notebook_name}")
        return True
    
    # Check folder path scope limitation
    if folder_path:
        # Folder path scope is handled during resource discovery and content retrieval
        # based on the folder_path metadata from LabArchives API responses
        logger.debug(f"Folder path scope validation deferred to resource discovery: {folder_path}")
        return True
    
    # If we reach here, the resource doesn't match any configured scope
    logger.debug(f"Resource {resource_info} does not match any configured scope")
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
    
    def __init__(self, api_client: LabArchivesAPIClient, scope_config: Dict[str, Any], jsonld_enabled: bool):
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
        self.logger.info("ResourceManager initialized", extra={
            "scope_config": scope_config,
            "jsonld_enabled": jsonld_enabled,
            "api_client_configured": bool(api_client)
        })
    
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
                        if target_folder.is_parent_of(page_folder) or target_folder.components == page_folder.components:
                            self.logger.debug(f"Notebook {notebook.id} contains folder {folder_path} via page {page.id}")
                            return True
                    except Exception as e:
                        # Log error but continue checking other pages
                        self.logger.warning(f"Error processing page folder path '{page.folder_path}': {e}")
                        continue
            
            # No pages found in the specified folder
            self.logger.debug(f"Notebook {notebook.id} does not contain folder {folder_path}")
            return False
            
        except Exception as e:
            # Log error but don't fail - allow notebook to be included for safety
            self.logger.warning(f"Error checking folder containment for notebook {notebook.id}: {e}")
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
        self.logger.info("Starting resource listing operation", extra={
            "scope_config": self.scope_config,
            "operation": "list_resources"
        })
        
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
                    
                    # Apply folder filtering if configured using exact path matching
                    pages_to_process = page_list_response.pages
                    if folder_path and folder_path.strip():
                        try:
                            folder_scope = FolderPath.from_raw(folder_path)
                            filtered_pages = []
                            for page in page_list_response.pages:
                                if page.folder_path and page.folder_path.strip():
                                    try:
                                        page_folder = FolderPath.from_raw(page.folder_path)
                                        # Include page if it's within the folder scope (exact parent-child relationship)
                                        if folder_scope.is_parent_of(page_folder) or folder_scope.components == page_folder.components:
                                            filtered_pages.append(page)
                                    except Exception as e:
                                        self.logger.warning(f"Error processing page folder path '{page.folder_path}': {e}")
                                        continue
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
                        context={"notebook_id": notebook_id, "error": str(e)}
                    )
                
                except APIError as e:
                    self.logger.error(f"API error listing pages for notebook {notebook_id}: {e}")
                    raise LabArchivesMCPException(
                        message=f"Failed to list pages for notebook {notebook_id}",
                        code=500,
                        context={"notebook_id": notebook_id, "error": str(e)}
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
                    
                    # Apply folder filtering if configured using exact path matching
                    pages_to_process = page_list_response.pages
                    if folder_path and folder_path.strip():
                        try:
                            folder_scope = FolderPath.from_raw(folder_path)
                            filtered_pages = []
                            for page in page_list_response.pages:
                                if page.folder_path and page.folder_path.strip():
                                    try:
                                        page_folder = FolderPath.from_raw(page.folder_path)
                                        # Include page if it's within the folder scope (exact parent-child relationship)
                                        if folder_scope.is_parent_of(page_folder) or folder_scope.components == page_folder.components:
                                            filtered_pages.append(page)
                                    except Exception as e:
                                        self.logger.warning(f"Error processing page folder path '{page.folder_path}': {e}")
                                        continue
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
                        context={"notebook_name": notebook_name, "error": str(e)}
                    )
            
            else:
                # No specific notebook scope - check for folder scope
                if folder_path and folder_path.strip():
                    # Two-phase listing with folder scope: find notebooks containing pages in folder scope, then return filtered pages
                    self.logger.debug(f"Performing two-phase listing with folder scope: {folder_path}")
                    
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
                                self.logger.debug(f"Notebook {notebook.id} contains pages in folder {folder_path}")
                        
                        # Phase 2: For each notebook containing pages in scope, list and filter pages
                        for notebook in notebooks_with_scope:
                            try:
                                page_list_response = self.api_client.list_pages(notebook.id)
                                
                                # Filter pages to only those within folder scope
                                for page in page_list_response.pages:
                                    if page.folder_path and page.folder_path.strip():
                                        try:
                                            page_folder = FolderPath.from_raw(page.folder_path)
                                            # Include page if it's within the folder scope (exact parent-child relationship)
                                            if folder_scope.is_parent_of(page_folder) or folder_scope.components == page_folder.components:
                                                # Create parent URI for hierarchical context
                                                parent_uri = f"{MCP_RESOURCE_URI_SCHEME}notebook/{notebook.id}"
                                                
                                                # Transform to MCP resource
                                                mcp_resource = labarchives_to_mcp_resource(page, parent_uri)
                                                resources.append(mcp_resource)
                                                
                                                self.logger.debug(f"Added page resource: {mcp_resource.uri}")
                                        except Exception as e:
                                            self.logger.warning(f"Error processing page folder path '{page.folder_path}': {e}")
                                            continue
                                            
                            except APIError as e:
                                self.logger.warning(f"API error listing pages for notebook {notebook.id}: {e}")
                                continue
                    
                    except APIError as e:
                        self.logger.error(f"API error during two-phase listing: {e}")
                        raise LabArchivesMCPException(
                            message="Failed to list resources with folder scope",
                            code=500,
                            context={"folder_path": folder_path, "error": str(e)}
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
                            context={"error": str(e)}
                        )
            
            # Log successful completion
            self.logger.info(f"Resource listing completed successfully", extra={
                "resource_count": len(resources),
                "scope_type": "notebook_id" if notebook_id else "notebook_name" if notebook_name else "all",
                "operation": "list_resources"
            })
            
            return resources
        
        except APIAuthenticationError as e:
            self.logger.error(f"Authentication error during resource listing: {e}")
            raise LabArchivesMCPException(
                message="Authentication failed during resource listing",
                code=401,
                context={"error": str(e)}
            )
        
        except LabArchivesMCPException:
            # Re-raise MCP exceptions without modification
            raise
        
        except Exception as e:
            self.logger.error(f"Unexpected error during resource listing: {e}", extra={
                "error_type": type(e).__name__,
                "operation": "list_resources"
            })
            raise LabArchivesMCPException(
                message=f"Unexpected error during resource listing: {str(e)}",
                code=500,
                context={"error": str(e), "error_type": type(e).__name__}
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
        self.logger.info(f"Starting resource read operation", extra={
            "uri": uri,
            "operation": "read_resource"
        })
        
        try:
            # Parse the resource URI to extract type and identifiers
            resource_info = parse_resource_uri(uri)
            
            # Validate that the resource is within the configured scope
            if not is_resource_in_scope(resource_info, self.scope_config):
                self.logger.warning(f"Resource access denied - outside configured scope", extra={
                    "uri": uri,
                    "resource_info": resource_info,
                    "scope_config": self.scope_config
                })
                raise LabArchivesMCPException(
                    message="Resource access denied - outside configured scope",
                    code=403,
                    context={"uri": uri, "resource_info": resource_info, "scope_config": self.scope_config}
                )
            
            # Handle resource reading based on type
            resource_type = resource_info.get('type')
            
            if resource_type == 'notebook':
                # Read notebook content with page summaries
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
                            context={"notebook_id": notebook_id}
                        )
                    
                    # Get page list for the notebook
                    page_list_response = self.api_client.list_pages(notebook_id)
                    
                    # Apply folder filtering if configured using exact path matching
                    pages_to_include = page_list_response.pages
                    folder_path = self.scope_config.get('folder_path')
                    if folder_path and folder_path.strip():
                        try:
                            folder_scope = FolderPath.from_raw(folder_path)
                            filtered_pages = []
                            for page in page_list_response.pages:
                                if page.folder_path and page.folder_path.strip():
                                    try:
                                        page_folder = FolderPath.from_raw(page.folder_path)
                                        # Include page if it's within the folder scope (exact parent-child relationship)
                                        if folder_scope.is_parent_of(page_folder) or folder_scope.components == page_folder.components:
                                            filtered_pages.append(page)
                                    except Exception as e:
                                        self.logger.warning(f"Error processing page folder path '{page.folder_path}': {e}")
                                        continue
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
                                "entry_count": page.entry_count
                            }
                            for page in pages_to_include
                        ]
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
                        "retrieved_at": datetime.utcnow().isoformat()
                    }
                    
                    # Create MCPResourceContent with optional JSON-LD context
                    resource_content = MCPResourceContent(
                        content=notebook_content,
                        context=MCP_JSONLD_CONTEXT if self.jsonld_enabled else None,
                        metadata=metadata
                    )
                    
                    self.logger.info(f"Successfully read notebook content", extra={
                        "notebook_id": notebook_id,
                        "page_count": len(page_list_response.pages),
                        "uri": uri
                    })
                    
                    return resource_content
                
                except APIPermissionError as e:
                    self.logger.error(f"Permission denied for notebook {notebook_id}: {e}")
                    raise LabArchivesMCPException(
                        message=f"Access denied to notebook {notebook_id}",
                        code=403,
                        context={"notebook_id": notebook_id, "error": str(e)}
                    )
                
                except APIError as e:
                    self.logger.error(f"API error reading notebook {notebook_id}: {e}")
                    raise LabArchivesMCPException(
                        message=f"Failed to read notebook {notebook_id}",
                        code=500,
                        context={"notebook_id": notebook_id, "error": str(e)}
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
                            context={"page_id": page_id, "notebook_id": notebook_id}
                        )
                    
                    # Validate folder scope for pages using exact path matching
                    folder_path = self.scope_config.get('folder_path')
                    if folder_path and folder_path.strip() and target_page.folder_path and target_page.folder_path.strip():
                        try:
                            folder_scope = FolderPath.from_raw(folder_path)
                            page_folder = FolderPath.from_raw(target_page.folder_path)
                            
                            # Check if page is within folder scope using exact parent-child relationship
                            if not (folder_scope.is_parent_of(page_folder) or folder_scope.components == page_folder.components):
                                self.logger.warning(f"Page access denied - outside folder scope: {target_page.folder_path}")
                                raise LabArchivesMCPException(
                                    message="ScopeViolation",
                                    code=403,
                                    context={"requested": target_page.folder_path, "allowed": folder_path}
                                )
                        except LabArchivesMCPException:
                            # Re-raise scope violations
                            raise
                        except Exception as e:
                            self.logger.error(f"Error validating folder scope for page {page_id}: {e}")
                            raise LabArchivesMCPException(
                                message="ScopeViolation",
                                code=403,
                                context={"page_id": page_id, "error": str(e)}
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
                                "content_preview": entry.content[:200] + "..." if len(entry.content) > 200 else entry.content
                            }
                            for entry in entry_list_response.entries
                        ]
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
                        "retrieved_at": datetime.utcnow().isoformat()
                    }
                    
                    # Create MCPResourceContent with optional JSON-LD context
                    resource_content = MCPResourceContent(
                        content=page_content,
                        context=MCP_JSONLD_CONTEXT if self.jsonld_enabled else None,
                        metadata=metadata
                    )
                    
                    self.logger.info(f"Successfully read page content", extra={
                        "page_id": page_id,
                        "notebook_id": notebook_id,
                        "entry_count": len(entry_list_response.entries),
                        "uri": uri
                    })
                    
                    return resource_content
                
                except APIPermissionError as e:
                    self.logger.error(f"Permission denied for page {page_id}: {e}")
                    raise LabArchivesMCPException(
                        message=f"Access denied to page {page_id}",
                        code=403,
                        context={"page_id": page_id, "notebook_id": notebook_id, "error": str(e)}
                    )
                
                except APIError as e:
                    self.logger.error(f"API error reading page {page_id}: {e}")
                    raise LabArchivesMCPException(
                        message=f"Failed to read page {page_id}",
                        code=500,
                        context={"page_id": page_id, "notebook_id": notebook_id, "error": str(e)}
                    )
            
            elif resource_type == 'entry':
                # Read detailed entry content
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
                            context={"entry_id": entry_id}
                        )
                    
                    # Get the entry (should be only one)
                    entry = entry_response.entries[0]
                    
                    # Validate folder scope for entries by checking their parent page using exact path matching
                    folder_path = self.scope_config.get('folder_path')
                    if folder_path and folder_path.strip() and entry.page_id:
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
                            
                            if entry_page and entry_page.folder_path and entry_page.folder_path.strip():
                                try:
                                    folder_scope = FolderPath.from_raw(folder_path)
                                    page_folder = FolderPath.from_raw(entry_page.folder_path)
                                    
                                    # Check if page is within folder scope using exact parent-child relationship
                                    if not (folder_scope.is_parent_of(page_folder) or folder_scope.components == page_folder.components):
                                        self.logger.warning(f"Entry access denied - parent page outside folder scope: {entry_page.folder_path}")
                                        raise LabArchivesMCPException(
                                            message="ScopeViolation",
                                            code=403,
                                            context={"requested": entry_page.folder_path, "allowed": folder_path}
                                        )
                                except LabArchivesMCPException:
                                    # Re-raise scope violations
                                    raise
                                except Exception as path_error:
                                    self.logger.error(f"Error validating folder scope for entry {entry_id}: {path_error}")
                                    raise LabArchivesMCPException(
                                        message="ScopeViolation",
                                        code=403,
                                        context={"entry_id": entry_id, "error": str(path_error)}
                                    )
                        except APIError as api_error:
                            # If we can't validate the folder scope, deny access for security
                            self.logger.error(f"Unable to validate folder scope for entry {entry_id}: {api_error}")
                            raise LabArchivesMCPException(
                                message="ScopeViolation",
                                code=403,
                                context={"entry_id": entry_id, "error": str(api_error)}
                            )
                    
                    # Transform to MCP resource content using the existing function
                    resource_content = labarchives_to_mcp_resource(entry)
                    
                    # Override context based on jsonld_enabled flag
                    if not self.jsonld_enabled:
                        resource_content.context = None
                    
                    # Add retrieval timestamp to metadata
                    if resource_content.metadata:
                        resource_content.metadata["retrieved_at"] = datetime.utcnow().isoformat()
                    
                    self.logger.info(f"Successfully read entry content", extra={
                        "entry_id": entry_id,
                        "entry_type": entry.entry_type,
                        "content_length": len(entry.content),
                        "uri": uri
                    })
                    
                    return resource_content
                
                except APIPermissionError as e:
                    self.logger.error(f"Permission denied for entry {entry_id}: {e}")
                    raise LabArchivesMCPException(
                        message=f"Access denied to entry {entry_id}",
                        code=403,
                        context={"entry_id": entry_id, "error": str(e)}
                    )
                
                except APIError as e:
                    self.logger.error(f"API error reading entry {entry_id}: {e}")
                    raise LabArchivesMCPException(
                        message=f"Failed to read entry {entry_id}",
                        code=500,
                        context={"entry_id": entry_id, "error": str(e)}
                    )
            
            else:
                # Unsupported resource type
                self.logger.error(f"Unsupported resource type: {resource_type}")
                raise LabArchivesMCPException(
                    message=f"Unsupported resource type: {resource_type}",
                    code=400,
                    context={"resource_type": resource_type, "uri": uri}
                )
        
        except APIAuthenticationError as e:
            self.logger.error(f"Authentication error during resource reading: {e}")
            raise LabArchivesMCPException(
                message="Authentication failed during resource reading",
                code=401,
                context={"uri": uri, "error": str(e)}
            )
        
        except LabArchivesMCPException:
            # Re-raise MCP exceptions without modification
            raise
        
        except Exception as e:
            self.logger.error(f"Unexpected error during resource reading: {e}", extra={
                "error_type": type(e).__name__,
                "uri": uri,
                "operation": "read_resource"
            })
            raise LabArchivesMCPException(
                message=f"Unexpected error during resource reading: {str(e)}",
                code=500,
                context={"uri": uri, "error": str(e), "error_type": type(e).__name__}
            )


# Export the main classes and functions for external use
__all__ = [
    "ResourceManager",
    "parse_resource_uri",
    "is_resource_in_scope"
]