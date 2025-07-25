"""
LabArchives API High-Level Interface

This module provides a high-level, authenticated interface for interacting with the LabArchives
REST API. It acts as a thin, robust wrapper around the lower-level API client (src/cli/api/client.py),
exposing convenient methods for authentication, notebook/page/entry listing, entry content retrieval,
and user context management.

The module enforces secure credential handling, region-aware endpoint selection, error handling,
and audit logging. It is the canonical entry point for all LabArchives data access in the CLI
and MCP server, abstracting away HTTP, authentication, and response parsing details.

Key Features:
- Region-aware API endpoint selection for US, AU, and UK deployments
- Secure credential handling with comprehensive error management
- Structured error handling with detailed context for debugging and audit
- Comprehensive audit logging for all API operations and security events
- Graceful error handling and user-friendly error messages
- Stateless operation with no persistent storage requirements

This module supports Feature F-002 (LabArchives API Integration), F-003 (Resource Discovery),
F-004 (Content Retrieval), F-005 (Authentication and Security), and F-008 (Audit Logging).
"""

import logging  # builtin - Logs API calls, errors, and audit events
from typing import Optional, Dict, Any, List  # builtin - Type annotations for method signatures and class properties

from src.cli.api.client import LabArchivesAPIClient
from src.cli.api.models import (
    NotebookListResponse,
    PageListResponse,
    EntryListResponse,
    UserContextResponse
)
from src.cli.api.errors import (
    APIError,
    APIAuthenticationError,
    APIRateLimitError,
    APIResponseParseError,
    APIPermissionError
)
from src.cli.constants import (
    DEFAULT_API_BASE_URL,
    AU_API_BASE_URL,
    UK_API_BASE_URL,
    SUPPORTED_REGIONS
)

# Global constants for region handling
DEFAULT_REGION = "US"


def get_api_base_url(region: Optional[str] = None) -> str:
    """
    Returns the appropriate LabArchives API base URL for the specified region.
    
    This function implements region-aware endpoint selection to support LabArchives
    deployments in different geographic regions. It provides automatic fallback to
    the US region (default) if the specified region is not supported or invalid.
    
    The function supports the following regions:
    - US: Primary US deployment (default)
    - AU: Australian deployment
    - UK: United Kingdom deployment
    
    Regional endpoint selection is essential for compliance with data residency
    requirements and optimal performance based on geographic location.
    
    Args:
        region (Optional[str]): The region code ('US', 'AU', 'UK'). If None or
                               invalid, defaults to US region.
    
    Returns:
        str: The API base URL for the specified region. Always returns a valid
             URL, defaulting to US region for invalid inputs.
    
    Examples:
        >>> get_api_base_url("US")
        'https://api.labarchives.com/api'
        >>> get_api_base_url("AU")
        'https://auapi.labarchives.com/api'
        >>> get_api_base_url("UK")
        'https://ukapi.labarchives.com/api'
        >>> get_api_base_url(None)
        'https://api.labarchives.com/api'
        >>> get_api_base_url("INVALID")
        'https://api.labarchives.com/api'
    """
    # Validate region parameter and default to US if invalid
    if region is None or region not in SUPPORTED_REGIONS:
        return DEFAULT_API_BASE_URL
    
    # Return region-specific API base URL
    if region == "AU":
        return AU_API_BASE_URL
    elif region == "UK":
        return UK_API_BASE_URL
    else:
        # Default to US region for all other cases
        return DEFAULT_API_BASE_URL


class LabArchivesAPI:
    """
    High-level wrapper for LabArchivesAPIClient providing convenient, region-aware access to LabArchives data.
    
    This class provides a robust, user-friendly interface for all LabArchives API operations
    while handling authentication, error management, and audit logging. It serves as the main
    interface for all LabArchives data access in the CLI and MCP server applications.
    
    The class abstracts away the complexities of HTTP communication, authentication protocols,
    response parsing, and error handling, providing a clean, consistent interface for consuming
    LabArchives data. All operations are logged for audit purposes and errors are handled
    gracefully with structured exception handling.
    
    Key Features:
    - Automatic region-aware endpoint selection
    - Secure credential handling with comprehensive validation
    - Structured error handling with detailed context preservation
    - Comprehensive audit logging for all operations
    - Graceful error recovery and user-friendly error messages
    - Stateless operation with no persistent storage requirements
    
    The class supports both permanent API key authentication and temporary user token
    authentication, making it suitable for both service account and interactive user scenarios.
    All authentication events and data access operations are logged for security monitoring
    and compliance purposes.
    
    Attributes:
        client (LabArchivesAPIClient): The underlying API client instance
        region (str): The configured LabArchives region
        api_base_url (str): The region-specific API base URL
        logger (logging.Logger): Logger instance for audit and diagnostics
    """
    
    def __init__(self, access_key_id: str, access_password: str, 
                 username: Optional[str] = None, region: Optional[str] = None):
        """
        Initializes the API wrapper with credentials and region configuration.
        
        This constructor sets up the high-level LabArchives API interface with the necessary
        credentials and regional configuration. It initializes the underlying API client,
        configures logging for audit purposes, and validates the regional configuration.
        
        The constructor performs credential validation and region selection but does not
        perform authentication with the LabArchives API. Authentication must be explicitly
        performed by calling the authenticate() method before any data access operations.
        
        The region parameter enables automatic selection of the appropriate LabArchives
        API endpoint based on deployment region, supporting compliance with data residency
        requirements and optimal performance based on geographic location.
        
        Args:
            access_key_id (str): LabArchives API access key ID. This is the public
                                identifier for API authentication, typically obtained
                                from the LabArchives account settings.
            access_password (str): LabArchives API password or user token. For permanent
                                  API keys, this is the secret key. For temporary tokens,
                                  this is the authentication token obtained from LabArchives.
            username (Optional[str]): Username for token authentication. Required for
                                     temporary user tokens (SSO users) but optional for
                                     permanent API keys.
            region (Optional[str]): LabArchives deployment region ('US', 'AU', 'UK').
                                   Defaults to 'US' if not specified or invalid.
        
        Raises:
            APIError: If credential validation fails or client initialization encounters errors.
                     This can occur due to invalid credential format, network configuration
                     issues, or other initialization problems.
        
        Example:
            # Initialize with permanent API key for US region
            api = LabArchivesAPI(
                access_key_id="your_access_key_id",
                access_password="your_secret_key"
            )
            
            # Initialize with temporary token for AU region
            api = LabArchivesAPI(
                access_key_id="your_access_key_id",
                access_password="your_temp_token",
                username="user@university.edu",
                region="AU"
            )
        """
        # Determine the API base URL using region-aware endpoint selection
        self.region = region or DEFAULT_REGION
        self.api_base_url = get_api_base_url(self.region)
        
        # Initialize the logger for audit and diagnostics
        self.logger = logging.getLogger(__name__)
        
        # Log initialization event for audit purposes
        self.logger.info("Initializing LabArchives API wrapper", extra={
            "region": self.region,
            "api_base_url": self.api_base_url,
            "username": username,
            "has_credentials": bool(access_key_id and access_password)
        })
        
        try:
            # Instantiate the underlying LabArchivesAPIClient with credentials and configuration
            self.client = LabArchivesAPIClient(
                access_key_id=access_key_id,
                access_password=access_password,
                username=username,
                api_base_url=self.api_base_url
            )
            
            # Log successful client initialization
            self.logger.info("LabArchives API client initialized successfully", extra={
                "region": self.region,
                "api_base_url": self.api_base_url
            })
            
        except Exception as e:
            # Log initialization failure and re-raise as APIError
            self.logger.error("Failed to initialize LabArchives API client", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "region": self.region,
                "api_base_url": self.api_base_url
            })
            raise APIError(
                message=f"Failed to initialize LabArchives API client: {str(e)}",
                code=500,
                context={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "region": self.region,
                    "api_base_url": self.api_base_url
                }
            )
    
    def authenticate(self) -> UserContextResponse:
        """
        Authenticates with the LabArchives API using the provided credentials.
        
        This method performs authentication with the LabArchives API to validate credentials
        and retrieve user context information. It supports both permanent API key authentication
        and temporary user token authentication, handling the authentication protocol
        automatically based on the provided credentials.
        
        The method fetches and stores the user context (UID, name, email, roles) which is
        required for subsequent API operations. Authentication is a prerequisite for all
        data access operations and must be successfully completed before calling any other
        methods.
        
        All authentication events are logged for security monitoring and audit purposes,
        including both successful authentications and authentication failures. The method
        implements comprehensive error handling to provide clear feedback about authentication
        issues while maintaining security best practices.
        
        Returns:
            UserContextResponse: The authenticated user context containing user profile
                                information, permissions, and roles. This context is used
                                for subsequent API operations and access control validation.
        
        Raises:
            APIAuthenticationError: If authentication fails due to invalid credentials,
                                   expired tokens, network issues, or other authentication
                                   problems. The exception contains detailed context for
                                   debugging and audit logging.
            APIError: If the authentication request fails due to network issues, API
                     unavailability, or other non-authentication related problems.
        
        Example:
            try:
                user_context = api.authenticate()
                print(f"Authenticated as: {user_context.user.name}")
                print(f"User roles: {user_context.user.roles}")
            except APIAuthenticationError as e:
                print(f"Authentication failed: {e}")
            except APIError as e:
                print(f"API error during authentication: {e}")
        """
        self.logger.info("Attempting authentication with LabArchives API", extra={
            "region": self.region,
            "api_base_url": self.api_base_url
        })
        
        try:
            # Perform authentication using the underlying client
            user_context = self.client.authenticate()
            
            # Log successful authentication for audit purposes
            self.logger.info("Authentication successful", extra={
                "user_id": user_context.user.uid,
                "user_name": user_context.user.name,
                "user_email": user_context.user.email,
                "user_roles": user_context.user.roles,
                "region": self.region
            })
            
            return user_context
            
        except APIAuthenticationError as e:
            # Log authentication failure and re-raise
            self.logger.error("Authentication failed", extra={
                "error": str(e),
                "error_code": e.code,
                "region": self.region,
                "api_base_url": self.api_base_url
            })
            raise
            
        except Exception as e:
            # Log unexpected error and re-raise as APIError
            self.logger.error("Unexpected error during authentication", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "region": self.region,
                "api_base_url": self.api_base_url
            })
            raise APIError(
                message=f"Unexpected error during authentication: {str(e)}",
                code=500,
                context={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "region": self.region,
                    "api_base_url": self.api_base_url
                }
            )
    
    def list_notebooks(self) -> NotebookListResponse:
        """
        Retrieves the list of accessible notebooks for the authenticated user.
        
        This method fetches all notebooks that the authenticated user has access to,
        including owned notebooks and notebooks shared with the user. The response
        includes comprehensive metadata such as notebook names, descriptions, creation
        dates, modification timestamps, and content summary statistics.
        
        The method implements comprehensive error handling for authentication failures,
        permission issues, and API errors. All operations are logged for audit purposes
        and monitoring. The method requires prior authentication and will raise an
        APIAuthenticationError if called before successful authentication.
        
        The returned notebook list can be used for resource discovery, navigation,
        and scope validation in MCP resource operations. The metadata provides sufficient
        information for users to identify and select appropriate notebooks for data access.
        
        Returns:
            NotebookListResponse: Validated notebook list response containing notebook
                                 metadata, status information, and optional messages.
                                 The response includes all notebooks accessible to the
                                 authenticated user.
        
        Raises:
            APIAuthenticationError: If the client is not authenticated or authentication
                                   has expired. This indicates that authenticate() must
                                   be called before attempting to list notebooks.
            APIError: If the request fails due to network issues, API unavailability,
                     or other non-authentication related problems. The exception contains
                     detailed context for debugging and error handling.
            APIPermissionError: If the user lacks permission to list notebooks, though
                               this is rare since most users have basic listing permissions.
        
        Example:
            try:
                notebooks = api.list_notebooks()
                print(f"Found {len(notebooks.notebooks)} notebooks:")
                for notebook in notebooks.notebooks:
                    print(f"  - {notebook.name} ({notebook.page_count} pages)")
            except APIAuthenticationError as e:
                print(f"Authentication required: {e}")
            except APIError as e:
                print(f"Error listing notebooks: {e}")
        """
        self.logger.info("Listing notebooks for authenticated user", extra={
            "region": self.region,
            "operation": "list_notebooks"
        })
        
        try:
            # Retrieve notebooks using the underlying client
            notebook_list = self.client.list_notebooks()
            
            # Log successful notebook retrieval for audit purposes
            self.logger.info("Notebooks retrieved successfully", extra={
                "notebook_count": len(notebook_list.notebooks),
                "region": self.region,
                "operation": "list_notebooks"
            })
            
            return notebook_list
            
        except APIAuthenticationError as e:
            # Log authentication error and re-raise
            self.logger.error("Authentication error during notebook listing", extra={
                "error": str(e),
                "error_code": e.code,
                "region": self.region,
                "operation": "list_notebooks"
            })
            raise
            
        except APIError as e:
            # Log API error and re-raise
            self.logger.error("API error during notebook listing", extra={
                "error": str(e),
                "error_code": e.code,
                "region": self.region,
                "operation": "list_notebooks"
            })
            raise
            
        except Exception as e:
            # Log unexpected error and re-raise as APIError
            self.logger.error("Unexpected error during notebook listing", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "region": self.region,
                "operation": "list_notebooks"
            })
            raise APIError(
                message=f"Unexpected error during notebook listing: {str(e)}",
                code=500,
                context={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "region": self.region,
                    "operation": "list_notebooks"
                }
            )
    
    def list_pages(self, notebook_id: str) -> PageListResponse:
        """
        Retrieves the list of pages for a given notebook.
        
        This method fetches all pages within a specified notebook, including comprehensive
        page metadata such as titles, folder organization, creation dates, modification
        timestamps, entry counts, and author information. The user must have read access
        to the notebook to retrieve its pages.
        
        The method implements comprehensive error handling for authentication failures,
        permission issues, and API errors. All operations are logged for audit purposes
        and monitoring. The method validates the notebook_id parameter and provides
        structured error handling for various failure scenarios.
        
        The returned page list can be used for hierarchical navigation, resource discovery,
        and scope validation in MCP resource operations. The metadata provides sufficient
        information for users to identify and select appropriate pages for data access.
        
        Args:
            notebook_id (str): The unique identifier of the notebook for which to retrieve
                              pages. This must be a valid notebook ID that the authenticated
                              user has access to.
        
        Returns:
            PageListResponse: Validated page list response containing page metadata,
                             status information, and optional messages. The response
                             includes all pages accessible within the specified notebook.
        
        Raises:
            APIAuthenticationError: If the client is not authenticated or authentication
                                   has expired. This indicates that authenticate() must
                                   be called before attempting to list pages.
            APIPermissionError: If the user lacks read access to the specified notebook
                               or if the notebook is outside the configured scope limitations.
            APIError: If the request fails due to network issues, API unavailability,
                     invalid notebook ID, or other non-authentication related problems.
        
        Example:
            try:
                pages = api.list_pages("notebook_12345")
                print(f"Found {len(pages.pages)} pages in notebook:")
                for page in pages.pages:
                    print(f"  - {page.title} ({page.entry_count} entries)")
            except APIAuthenticationError as e:
                print(f"Authentication required: {e}")
            except APIPermissionError as e:
                print(f"Permission denied: {e}")
            except APIError as e:
                print(f"Error listing pages: {e}")
        """
        self.logger.info("Listing pages for notebook", extra={
            "notebook_id": notebook_id,
            "region": self.region,
            "operation": "list_pages"
        })
        
        try:
            # Retrieve pages using the underlying client
            page_list = self.client.list_pages(notebook_id)
            
            # Log successful page retrieval for audit purposes
            self.logger.info("Pages retrieved successfully", extra={
                "page_count": len(page_list.pages),
                "notebook_id": notebook_id,
                "region": self.region,
                "operation": "list_pages"
            })
            
            return page_list
            
        except APIAuthenticationError as e:
            # Log authentication error and re-raise
            self.logger.error("Authentication error during page listing", extra={
                "error": str(e),
                "error_code": e.code,
                "notebook_id": notebook_id,
                "region": self.region,
                "operation": "list_pages"
            })
            raise
            
        except APIPermissionError as e:
            # Log permission error and re-raise
            self.logger.error("Permission error during page listing", extra={
                "error": str(e),
                "error_code": e.code,
                "notebook_id": notebook_id,
                "region": self.region,
                "operation": "list_pages"
            })
            raise
            
        except APIError as e:
            # Log API error and re-raise
            self.logger.error("API error during page listing", extra={
                "error": str(e),
                "error_code": e.code,
                "notebook_id": notebook_id,
                "region": self.region,
                "operation": "list_pages"
            })
            raise
            
        except Exception as e:
            # Log unexpected error and re-raise as APIError
            self.logger.error("Unexpected error during page listing", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "notebook_id": notebook_id,
                "region": self.region,
                "operation": "list_pages"
            })
            raise APIError(
                message=f"Unexpected error during page listing: {str(e)}",
                code=500,
                context={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "notebook_id": notebook_id,
                    "region": self.region,
                    "operation": "list_pages"
                }
            )
    
    def list_entries(self, page_id: str) -> EntryListResponse:
        """
        Retrieves the list of entries for a given page.
        
        This method fetches all entries within a specified page, including comprehensive
        entry content, metadata, timestamps, and author information. The user must have
        read access to the page to retrieve its entries. The method returns complete
        entry data including text content, attachments, and associated metadata.
        
        The method implements comprehensive error handling for authentication failures,
        permission issues, and API errors. All operations are logged for audit purposes
        and monitoring. The method validates the page_id parameter and provides
        structured error handling for various failure scenarios.
        
        The returned entry list provides complete data for MCP resource operations,
        including full content and metadata that can be consumed by AI applications.
        The response includes all entry types (text, attachments, tables, etc.) with
        appropriate formatting and context preservation.
        
        Args:
            page_id (str): The unique identifier of the page for which to retrieve
                          entries. This must be a valid page ID that the authenticated
                          user has access to.
        
        Returns:
            EntryListResponse: Validated entry list response containing entry content,
                              metadata, status information, and optional messages. The
                              response includes all entries accessible within the specified page.
        
        Raises:
            APIAuthenticationError: If the client is not authenticated or authentication
                                   has expired. This indicates that authenticate() must
                                   be called before attempting to list entries.
            APIPermissionError: If the user lacks read access to the specified page
                               or if the page is outside the configured scope limitations.
            APIError: If the request fails due to network issues, API unavailability,
                     invalid page ID, or other non-authentication related problems.
        
        Example:
            try:
                entries = api.list_entries("page_67890")
                print(f"Found {len(entries.entries)} entries in page:")
                for entry in entries.entries:
                    print(f"  - {entry.title or 'Untitled'} ({entry.entry_type})")
            except APIAuthenticationError as e:
                print(f"Authentication required: {e}")
            except APIPermissionError as e:
                print(f"Permission denied: {e}")
            except APIError as e:
                print(f"Error listing entries: {e}")
        """
        self.logger.info("Listing entries for page", extra={
            "page_id": page_id,
            "region": self.region,
            "operation": "list_entries"
        })
        
        try:
            # Retrieve entries using the underlying client
            entry_list = self.client.list_entries(page_id)
            
            # Log successful entry retrieval for audit purposes
            self.logger.info("Entries retrieved successfully", extra={
                "entry_count": len(entry_list.entries),
                "page_id": page_id,
                "region": self.region,
                "operation": "list_entries"
            })
            
            return entry_list
            
        except APIAuthenticationError as e:
            # Log authentication error and re-raise
            self.logger.error("Authentication error during entry listing", extra={
                "error": str(e),
                "error_code": e.code,
                "page_id": page_id,
                "region": self.region,
                "operation": "list_entries"
            })
            raise
            
        except APIPermissionError as e:
            # Log permission error and re-raise
            self.logger.error("Permission error during entry listing", extra={
                "error": str(e),
                "error_code": e.code,
                "page_id": page_id,
                "region": self.region,
                "operation": "list_entries"
            })
            raise
            
        except APIError as e:
            # Log API error and re-raise
            self.logger.error("API error during entry listing", extra={
                "error": str(e),
                "error_code": e.code,
                "page_id": page_id,
                "region": self.region,
                "operation": "list_entries"
            })
            raise
            
        except Exception as e:
            # Log unexpected error and re-raise as APIError
            self.logger.error("Unexpected error during entry listing", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "page_id": page_id,
                "region": self.region,
                "operation": "list_entries"
            })
            raise APIError(
                message=f"Unexpected error during entry listing: {str(e)}",
                code=500,
                context={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "page_id": page_id,
                    "region": self.region,
                    "operation": "list_entries"
                }
            )
    
    def get_entry_content(self, entry_id: str) -> EntryListResponse:
        """
        Retrieves the detailed content for a specific entry by entry ID.
        
        This method fetches the complete content and metadata for a single entry,
        including text content, attachments, timestamps, version information, and
        all associated metadata. The user must have read access to the entry to
        retrieve its content. The method returns complete entry data suitable for
        AI consumption and processing.
        
        The method implements comprehensive error handling for authentication failures,
        permission issues, and API errors. All operations are logged for audit purposes
        and monitoring. The method validates the entry_id parameter and provides
        structured error handling for various failure scenarios.
        
        The returned entry content provides complete data for MCP resource operations,
        including full content and metadata that can be consumed by AI applications.
        The response maintains all contextual information and metadata to support
        comprehensive AI analysis and processing.
        
        Args:
            entry_id (str): The unique identifier of the entry for which to retrieve
                           content. This must be a valid entry ID that the authenticated
                           user has access to.
        
        Returns:
            EntryListResponse: Validated entry content response containing a single
                              entry with complete content, metadata, status information,
                              and optional messages. The response includes all available
                              entry data and context.
        
        Raises:
            APIAuthenticationError: If the client is not authenticated or authentication
                                   has expired. This indicates that authenticate() must
                                   be called before attempting to retrieve entry content.
            APIPermissionError: If the user lacks read access to the specified entry
                               or if the entry is outside the configured scope limitations.
            APIError: If the request fails due to network issues, API unavailability,
                     invalid entry ID, or other non-authentication related problems.
        
        Example:
            try:
                entry_content = api.get_entry_content("entry_11111")
                entry = entry_content.entries[0]
                print(f"Entry: {entry.title or 'Untitled'}")
                print(f"Type: {entry.entry_type}")
                print(f"Content: {entry.content[:100]}...")
            except APIAuthenticationError as e:
                print(f"Authentication required: {e}")
            except APIPermissionError as e:
                print(f"Permission denied: {e}")
            except APIError as e:
                print(f"Error retrieving entry content: {e}")
        """
        self.logger.info("Retrieving entry content", extra={
            "entry_id": entry_id,
            "region": self.region,
            "operation": "get_entry_content"
        })
        
        try:
            # Retrieve entry content using the underlying client
            entry_content = self.client.get_entry_content(entry_id)
            
            # Log successful entry content retrieval for audit purposes
            self.logger.info("Entry content retrieved successfully", extra={
                "entry_id": entry_id,
                "region": self.region,
                "operation": "get_entry_content",
                "content_size": len(entry_content.entries[0].content) if entry_content.entries else 0
            })
            
            return entry_content
            
        except APIAuthenticationError as e:
            # Log authentication error and re-raise
            self.logger.error("Authentication error during entry content retrieval", extra={
                "error": str(e),
                "error_code": e.code,
                "entry_id": entry_id,
                "region": self.region,
                "operation": "get_entry_content"
            })
            raise
            
        except APIPermissionError as e:
            # Log permission error and re-raise
            self.logger.error("Permission error during entry content retrieval", extra={
                "error": str(e),
                "error_code": e.code,
                "entry_id": entry_id,
                "region": self.region,
                "operation": "get_entry_content"
            })
            raise
            
        except APIError as e:
            # Log API error and re-raise
            self.logger.error("API error during entry content retrieval", extra={
                "error": str(e),
                "error_code": e.code,
                "entry_id": entry_id,
                "region": self.region,
                "operation": "get_entry_content"
            })
            raise
            
        except Exception as e:
            # Log unexpected error and re-raise as APIError
            self.logger.error("Unexpected error during entry content retrieval", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "entry_id": entry_id,
                "region": self.region,
                "operation": "get_entry_content"
            })
            raise APIError(
                message=f"Unexpected error during entry content retrieval: {str(e)}",
                code=500,
                context={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "entry_id": entry_id,
                    "region": self.region,
                    "operation": "get_entry_content"
                }
            )


# =============================================================================
# High-Level API Functions
# =============================================================================
# These functions provide a simplified interface to the LabArchivesAPI class
# for common operations. They are used by the CLI and MCP server components.


def get_authenticated_client(access_key_id: str, access_secret: str, 
                           region: Optional[str] = None, 
                           username: Optional[str] = None) -> LabArchivesAPI:
    """
    Create and return an authenticated LabArchives API client.
    
    Args:
        access_key_id: API access key ID or permanent API key
        access_secret: API access secret or temporary token
        region: LabArchives region (US, AU, UK)
        username: Username (required for token-based auth)
    
    Returns:
        LabArchivesAPI: Authenticated API client instance
    """
    # Placeholder implementation - needs to be fully implemented
    api_client = LabArchivesAPI(
        access_key_id=access_key_id,
        access_secret=access_secret,
        region=region or "US"
    )
    return api_client


def list_user_notebooks(api_client: LabArchivesAPI) -> List[Dict[str, Any]]:
    """
    List all notebooks accessible to the authenticated user.
    
    Args:
        api_client: Authenticated LabArchives API client
    
    Returns:
        List[Dict[str, Any]]: List of notebook metadata dictionaries
    """
    # Placeholder implementation - needs to be fully implemented
    try:
        response = api_client.list_user_notebooks()
        return response.notebooks if hasattr(response, 'notebooks') else []
    except Exception:
        return []


def list_notebook_pages(api_client: LabArchivesAPI, notebook_id: str) -> List[Dict[str, Any]]:
    """
    List all pages in the specified notebook.
    
    Args:
        api_client: Authenticated LabArchives API client
        notebook_id: Target notebook identifier
    
    Returns:
        List[Dict[str, Any]]: List of page metadata dictionaries
    """
    # Placeholder implementation - needs to be fully implemented
    try:
        response = api_client.list_notebook_pages(notebook_id)
        return response.pages if hasattr(response, 'pages') else []
    except Exception:
        return []


def list_page_entries(api_client: LabArchivesAPI, page_id: str) -> List[Dict[str, Any]]:
    """
    List all entries in the specified page.
    
    Args:
        api_client: Authenticated LabArchives API client
        page_id: Target page identifier
    
    Returns:
        List[Dict[str, Any]]: List of entry metadata dictionaries
    """
    # Placeholder implementation - needs to be fully implemented
    try:
        response = api_client.list_page_entries(page_id)
        return response.entries if hasattr(response, 'entries') else []
    except Exception:
        return []


def get_notebook_metadata(api_client: LabArchivesAPI, notebook_id: str) -> Dict[str, Any]:
    """
    Get metadata for the specified notebook.
    
    Args:
        api_client: Authenticated LabArchives API client
        notebook_id: Target notebook identifier
    
    Returns:
        Dict[str, Any]: Notebook metadata dictionary
    """
    # Placeholder implementation - needs to be fully implemented
    try:
        response = api_client.get_notebook_metadata(notebook_id)
        return response.dict() if hasattr(response, 'dict') else {}
    except Exception:
        return {}


def get_page_metadata(api_client: LabArchivesAPI, page_id: str) -> Dict[str, Any]:
    """
    Get metadata for the specified page.
    
    Args:
        api_client: Authenticated LabArchives API client
        page_id: Target page identifier
    
    Returns:
        Dict[str, Any]: Page metadata dictionary
    """
    # Placeholder implementation - needs to be fully implemented
    try:
        response = api_client.get_page_metadata(page_id)
        return response.dict() if hasattr(response, 'dict') else {}
    except Exception:
        return {}


def get_entry_content(api_client: LabArchivesAPI, entry_id: str) -> Dict[str, Any]:
    """
    Get content for the specified entry.
    
    Args:
        api_client: Authenticated LabArchives API client
        entry_id: Target entry identifier
    
    Returns:
        Dict[str, Any]: Entry content dictionary
    """
    # Placeholder implementation - needs to be fully implemented
    try:
        response = api_client.get_entry_content(entry_id)
        return response.dict() if hasattr(response, 'dict') else {}
    except Exception:
        return {}