"""
LabArchives API Client for MCP Server

This module implements the LabArchives API client for the CLI, providing a high-level,
authenticated interface for interacting with the LabArchives REST API. Handles all HTTP
communication, authentication, request construction, error handling, and response parsing
for notebook, page, entry, and user context operations.

The client integrates with the response parser for robust data validation and with the
custom error hierarchy for structured exception handling. Supports rate limiting, retry
logic, and audit logging for all API operations.

This client is the canonical interface for all LabArchives data access in the CLI and
MCP server, providing secure, authenticated access to electronic lab notebook data
through the LabArchives REST API.
"""

import time  # builtin - Implements retry and backoff logic for rate limiting and transient errors
import logging  # builtin - Logs API calls, errors, and audit events
import hashlib  # builtin - For generating API signatures
import hmac  # builtin - For HMAC-SHA256 signature generation
from datetime import datetime  # builtin - For timestamp generation
from typing import (
    Optional,
    Dict,
    Any,
    List,
)  # builtin - Type annotations for method signatures and class properties
from urllib.parse import urlencode  # builtin - URL encoding for query parameters

import requests  # requests>=2.31.0 - HTTP client for making LabArchives API requests
from requests.adapters import (
    HTTPAdapter,
)  # requests>=2.31.0 - For connection pooling and retries
from requests.packages.urllib3.util.retry import (
    Retry,
)  # requests>=2.31.0 - For retry strategy

from api.models import (
    NotebookListResponse,
    PageListResponse,
    EntryListResponse,
    UserContextResponse,
)
from api.response_parser import (
    parse_notebook_list_response,
    parse_page_list_response,
    parse_entry_list_response,
    parse_user_context_response,
)
from api.errors import (
    APIError,
    APIAuthenticationError,
    APIRateLimitError,
    APIResponseParseError,
    APIPermissionError,
)
from constants import (
    DEFAULT_API_BASE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_BACKOFF,
)
from utils import safe_serialize
from security.sanitizers import sanitize_url_params

# Global constants for retry behavior
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2

# LabArchives API endpoint mapping
LABARCHIVES_API_ENDPOINTS = {
    "user_info": "/users/user_info",
    "notebooks_list": "/notebooks/list",
    "pages_list": "/pages/list",
    "entries_get": "/entries/get",
}


def mask_sensitive_query_params(url: str) -> str:
    """
    Helper function for secure debug logging that automatically redacts sensitive query parameters.

    This function serves as a dedicated interface for masking sensitive query parameters
    (tokens, passwords, secrets) in URLs before they are logged. It integrates with the
    centralized Security Utilities sanitizers module to ensure consistent parameter
    masking policies across all API client debug output.

    This implementation addresses Section 0.3.2 security sanitization pattern requirements
    and Section 6.4.7.4.1 audit event processing requirements to prevent credentials
    from appearing in logs, debug outputs, or audit trails.

    Args:
        url (str): The URL string containing query parameters to sanitize

    Returns:
        str: Sanitized URL with sensitive parameter values replaced by [REDACTED]

    Examples:
        >>> mask_sensitive_query_params("https://api.labarchives.com/users?akid=123&token=secret")
        'https://api.labarchives.com/users?akid=[REDACTED]&token=[REDACTED]'
    """
    return sanitize_url_params(url)


def build_api_url(
    endpoint: str, params: Dict[str, Any], base_url: str = DEFAULT_API_BASE_URL
) -> str:
    """
    Constructs the full API URL for a given endpoint, including the base URL and query parameters.

    This function creates properly formatted LabArchives API URLs by combining the base URL,
    endpoint path, and query parameters. It handles URL encoding of parameters and ensures
    the resulting URL is properly formatted for HTTP requests.

    The function supports regional API endpoints by allowing different base URLs while
    maintaining consistent endpoint paths and parameter handling.

    Args:
        endpoint (str): The API endpoint path (e.g., "/users/user_info")
        params (Dict[str, Any]): Dictionary of query parameters to include in the URL
        base_url (str): The base API URL, defaults to DEFAULT_API_BASE_URL

    Returns:
        str: The full API URL with query parameters properly encoded

    Example:
        >>> build_api_url("/users/user_info", {"akid": "12345", "uid": "67890"})
        'https://api.labarchives.com/api/users/user_info?akid=12345&uid=67890'
    """
    # Ensure the base URL ends with "/api" for LabArchives API compatibility
    if not base_url.endswith("/api"):
        base_url = base_url.rstrip("/") + "/api"

    # Combine base URL and endpoint path
    full_url = base_url + endpoint

    # Add query parameters if provided
    if params:
        query_string = urlencode(params)
        full_url = f"{full_url}?{query_string}"

    return full_url


class LabArchivesAPIClient:
    """
    High-level, authenticated client for interacting with the LabArchives REST API.

    This client handles all HTTP requests, authentication, error handling, and response
    parsing for notebooks, pages, entries, and user context. It integrates with the
    response parser and error modules for robust validation and diagnostics.

    The client supports both permanent API key authentication and temporary user token
    authentication, with comprehensive security controls, rate limiting, and audit logging.
    It implements retry logic with exponential backoff for transient failures and provides
    structured error handling for all API operations.

    Key features:
    - Secure credential handling with environment variable storage
    - Automatic retry logic with exponential backoff
    - Comprehensive error handling and logging
    - Rate limiting compliance
    - Response parsing and validation
    - Audit trail generation

    Attributes:
        access_key_id (str): LabArchives API access key ID
        access_password (str): LabArchives API password or user token
        username (Optional[str]): Username for token authentication
        api_base_url (str): Base URL for LabArchives API (regional)
        uid (Optional[str]): User ID obtained from authentication
        user_context (Optional[UserContextResponse]): Full user context from API
        logger (logging.Logger): Logger instance for audit and diagnostics
    """

    def __init__(
        self,
        access_key_id: str,
        access_password: str,
        username: Optional[str] = None,
        api_base_url: str = DEFAULT_API_BASE_URL,
    ):
        """
        Initializes the API client with credentials, base URL, and logger.

        Sets up the HTTP session with retry logic, configures authentication parameters,
        and initializes the audit logger. The client is ready for API operations after
        initialization but requires explicit authentication to access user data.

        Args:
            access_key_id (str): LabArchives API access key ID
            access_password (str): LabArchives API password or user token
            username (Optional[str]): Username for token authentication (SSO users)
            api_base_url (str): Base URL for LabArchives API (defaults to US region)

        Raises:
            APIError: If credential validation fails or initialization encounters errors
        """
        # Store authentication credentials
        self.access_key_id = access_key_id
        self.access_password = access_password
        self.username = username
        self.api_base_url = api_base_url

        # Initialize session state
        self.uid: Optional[str] = None
        self.user_context: Optional[UserContextResponse] = None

        # Set up logger for audit and diagnostics
        self.logger = logging.getLogger(__name__)

        # Configure HTTP session with retry logic
        self.session = requests.Session()

        # Set up retry strategy for transient failures
        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=RETRY_BACKOFF_SECONDS,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )

        # Mount HTTP adapter with retry strategy
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set default timeout and headers
        self.session.timeout = DEFAULT_TIMEOUT_SECONDS
        self.session.headers.update(
            {
                "User-Agent": "LabArchives-MCP-Client/1.0",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

        self.logger.info(
            "LabArchives API client initialized",
            extra={
                "api_base_url": api_base_url,
                "access_key_id": (
                    access_key_id[:8] + "..." if len(access_key_id) > 8 else "[short]"
                ),
                "username": username,
                "has_credentials": bool(access_key_id and access_password),
            },
        )

    def _generate_signature(self, method: str, endpoint: str, params: Dict[str, Any]) -> str:
        """
        Generates HMAC-SHA256 signature for LabArchives API authentication.

        Creates the required signature for LabArchives API requests using the access key
        and secret. The signature is generated from the HTTP method, endpoint path, and
        query parameters according to LabArchives API specifications.

        Args:
            method (str): HTTP method (GET, POST, etc.)
            endpoint (str): API endpoint path
            params (Dict[str, Any]): Query parameters for the request

        Returns:
            str: HMAC-SHA256 signature for the request
        """
        # Create canonical string for signature generation
        canonical_string = f"{method.upper()}{endpoint}"

        # Add sorted parameters to canonical string
        sorted_params = sorted(params.items())
        for key, value in sorted_params:
            canonical_string += f"{key}{value}"

        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            self.access_password.encode('utf-8'),
            canonical_string.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

        return signature

    def _build_authenticated_params(
        self, additional_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Builds authentication parameters for LabArchives API requests.

        Creates the required authentication parameters including access key ID, user ID,
        timestamp, and signature. Optionally includes additional parameters for specific
        API endpoints.

        Args:
            additional_params (Optional[Dict[str, Any]]): Additional parameters for the request

        Returns:
            Dict[str, Any]: Complete parameter dictionary with authentication

        Raises:
            APIAuthenticationError: If authentication parameters cannot be generated
        """
        if not self.uid:
            raise APIAuthenticationError(
                message="User ID not available - authentication required",
                context={"operation": "build_authenticated_params"},
            )

        # Generate timestamp
        timestamp = str(int(time.time()))

        # Build base parameters
        params = {"akid": self.access_key_id, "uid": self.uid, "ts": timestamp}

        # Add additional parameters if provided
        if additional_params:
            params.update(additional_params)

        return params

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 0,
    ) -> requests.Response:
        """
        Makes an authenticated HTTP request to the LabArchives API.

        Handles request construction, authentication, error handling, and retry logic.
        Includes comprehensive logging and error context for debugging and audit purposes.

        Args:
            method (str): HTTP method (GET, POST, etc.)
            endpoint (str): API endpoint path
            params (Optional[Dict[str, Any]]): Query parameters for the request
            retry_count (int): Current retry attempt number

        Returns:
            requests.Response: HTTP response object

        Raises:
            APIError: For HTTP errors and request failures
            APIRateLimitError: For rate limiting responses
            APIAuthenticationError: For authentication failures
        """
        if params is None:
            params = {}

        try:
            # Build complete URL
            url = build_api_url(endpoint, params, self.api_base_url)

            # Log request details (without sensitive data)
            self.logger.debug(
                f"Making {method} request to {endpoint}",
                extra={
                    "method": method,
                    "endpoint": endpoint,
                    "url": mask_sensitive_query_params(url),
                    "retry_count": retry_count,
                },
            )

            # Make HTTP request
            response = self.session.request(method, url, timeout=DEFAULT_TIMEOUT_SECONDS)

            # Handle rate limiting
            if response.status_code == 429:
                self.handle_rate_limit(retry_count)
                return self._make_request(method, endpoint, params, retry_count + 1)

            # Handle authentication errors
            if response.status_code == 401:
                self.logger.error(
                    "Authentication failed",
                    extra={
                        "status_code": response.status_code,
                        "endpoint": endpoint,
                        "method": method,
                    },
                )
                raise APIAuthenticationError(
                    message="Authentication failed - invalid credentials",
                    context={
                        "endpoint": endpoint,
                        "method": method,
                        "response_headers": dict(response.headers),
                        "status_code": response.status_code,
                    },
                )

            # Handle permission errors
            if response.status_code == 403:
                self.logger.error(
                    "Permission denied",
                    extra={
                        "status_code": response.status_code,
                        "endpoint": endpoint,
                        "method": method,
                    },
                )
                raise APIPermissionError(
                    message="Permission denied - insufficient access rights",
                    code=response.status_code,
                    context={
                        "endpoint": endpoint,
                        "method": method,
                        "response_headers": dict(response.headers),
                    },
                )

            # Handle other HTTP errors
            if not response.ok:
                error_message = f"HTTP {response.status_code}: {response.reason}"
                self.logger.error(
                    f"API request failed: {error_message}",
                    extra={
                        "status_code": response.status_code,
                        "endpoint": endpoint,
                        "method": method,
                        "response_text": response.text[:500],
                    },
                )
                raise APIError(
                    message=error_message,
                    code=response.status_code,
                    context={
                        "endpoint": endpoint,
                        "method": method,
                        "response_text": response.text,
                        "response_headers": dict(response.headers),
                    },
                )

            # Log successful request
            self.logger.info(
                f"API request successful: {method} {endpoint}",
                extra={
                    "status_code": response.status_code,
                    "endpoint": endpoint,
                    "method": method,
                    "response_size": len(response.content),
                },
            )

            return response

        except requests.exceptions.Timeout:
            self.logger.error(
                f"Request timeout: {method} {endpoint}",
                extra={
                    "endpoint": endpoint,
                    "method": method,
                    "timeout": DEFAULT_TIMEOUT_SECONDS,
                },
            )
            raise APIError(
                message=f"Request timeout after {DEFAULT_TIMEOUT_SECONDS} seconds",
                code=408,
                context={"endpoint": endpoint, "method": method},
            )

        except requests.exceptions.ConnectionError as e:
            self.logger.error(
                f"Connection error: {method} {endpoint}",
                extra={"endpoint": endpoint, "method": method, "error": str(e)},
            )
            raise APIError(
                message=f"Connection error: {str(e)}",
                code=503,
                context={"endpoint": endpoint, "method": method, "error": str(e)},
            )

        except Exception as e:
            self.logger.error(
                f"Unexpected error: {method} {endpoint}",
                extra={
                    "endpoint": endpoint,
                    "method": method,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            raise APIError(
                message=f"Unexpected error: {str(e)}",
                code=500,
                context={
                    "endpoint": endpoint,
                    "method": method,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

    def handle_rate_limit(self, retry_count: int) -> None:
        """
        Handles API rate limiting by implementing exponential backoff for retries.

        When rate limiting is encountered, this method implements exponential backoff
        to avoid overwhelming the API. If the maximum retry count is reached, it raises
        an APIRateLimitError to indicate the operation cannot be completed.

        Args:
            retry_count (int): Current retry attempt number

        Raises:
            APIRateLimitError: If retry count exceeds MAX_RETRIES
        """
        if retry_count >= MAX_RETRIES:
            self.logger.error(
                "Rate limit exceeded - max retries reached",
                extra={"retry_count": retry_count, "max_retries": MAX_RETRIES},
            )
            raise APIRateLimitError(
                message=f"Rate limit exceeded - max retries ({MAX_RETRIES}) reached",
                code=429,
                context={"retry_count": retry_count, "max_retries": MAX_RETRIES},
            )

        # Calculate exponential backoff delay
        delay = RETRY_BACKOFF_SECONDS * (2**retry_count)

        self.logger.warning(
            f"Rate limit encountered - retrying in {delay} seconds",
            extra={"retry_count": retry_count, "delay_seconds": delay},
        )

        # Sleep before retry
        time.sleep(delay)

    def authenticate(self) -> UserContextResponse:
        """
        Authenticates with the LabArchives API using the provided credentials.

        This method performs the initial authentication with LabArchives API to validate
        credentials and obtain user context information. It supports both permanent API
        key authentication and temporary user token authentication.

        The method fetches user information including UID, name, email, and roles,
        which are stored for subsequent API calls. The authentication is required
        before any other API operations can be performed.

        Returns:
            UserContextResponse: The authenticated user context with profile information

        Raises:
            APIAuthenticationError: If authentication fails due to invalid credentials
            APIError: If the authentication request fails for other reasons
        """
        self.logger.info(
            "Attempting authentication with LabArchives API",
            extra={"username": self.username, "api_base_url": self.api_base_url},
        )

        try:
            # Prepare authentication parameters
            auth_params = {"akid": self.access_key_id}

            # Add username and token for SSO authentication
            if self.username:
                auth_params["email"] = self.username
                auth_params["token"] = self.access_password
            else:
                # For direct API key authentication, use HMAC signature
                auth_params["ts"] = str(int(time.time()))
                auth_params["sig"] = self._generate_signature(
                    "GET", LABARCHIVES_API_ENDPOINTS["user_info"], auth_params
                )

            # Make authentication request
            response = self._make_request(
                method="GET",
                endpoint=LABARCHIVES_API_ENDPOINTS["user_info"],
                params=auth_params,
            )

            # Parse response to get user context
            user_context = parse_user_context_response(
                raw_response=response.text,
                format="json",  # LabArchives API returns JSON by default
            )

            # Store user context and UID for subsequent requests
            self.user_context = user_context
            self.uid = user_context.user.uid

            self.logger.info(
                "Authentication successful",
                extra={
                    "user_id": self.uid,
                    "user_name": user_context.user.name,
                    "user_email": user_context.user.email,
                },
            )

            return user_context

        except APIAuthenticationError:
            # Re-raise authentication errors without modification
            raise
        except Exception as e:
            self.logger.error(
                "Authentication failed with unexpected error",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            raise APIAuthenticationError(
                message=f"Authentication failed: {str(e)}",
                context={"error": str(e), "error_type": type(e).__name__},
            )

    def list_notebooks(self) -> NotebookListResponse:
        """
        Retrieves the list of accessible notebooks for the authenticated user.

        This method fetches all notebooks that the authenticated user has access to,
        including owned notebooks and notebooks shared with the user. The response
        includes metadata such as notebook names, descriptions, creation dates, and
        page counts.

        Returns:
            NotebookListResponse: Validated notebook list response with metadata

        Raises:
            APIAuthenticationError: If the client is not authenticated
            APIError: If the request fails or response parsing fails
        """
        # Ensure authentication
        if not self.uid:
            self.logger.error("List notebooks called without authentication")
            raise APIAuthenticationError(
                message="Authentication required - call authenticate() first",
                context={"operation": "list_notebooks"},
            )

        self.logger.info(
            "Listing notebooks for user",
            extra={"user_id": self.uid, "operation": "list_notebooks"},
        )

        try:
            # Build authenticated parameters
            params = self._build_authenticated_params()

            # Make API request
            response = self._make_request(
                method="GET",
                endpoint=LABARCHIVES_API_ENDPOINTS["notebooks_list"],
                params=params,
            )

            # Parse and validate response
            notebook_list = parse_notebook_list_response(raw_response=response.text, format="json")

            self.logger.info(
                "Notebooks retrieved successfully",
                extra={
                    "notebook_count": len(notebook_list.notebooks),
                    "user_id": self.uid,
                },
            )

            return notebook_list

        except (APIAuthenticationError, APIError, APIResponseParseError):
            # Re-raise known API errors
            raise
        except Exception as e:
            self.logger.error(
                "Unexpected error listing notebooks",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "user_id": self.uid,
                },
            )
            raise APIError(
                message=f"Failed to list notebooks: {str(e)}",
                code=500,
                context={
                    "operation": "list_notebooks",
                    "user_id": self.uid,
                    "error": str(e),
                },
            )

    def list_pages(self, notebook_id: str) -> PageListResponse:
        """
        Retrieves the list of pages for a given notebook.

        This method fetches all pages within a specified notebook, including page
        metadata such as titles, creation dates, entry counts, and folder organization.
        The user must have read access to the notebook to retrieve its pages.

        Args:
            notebook_id (str): The unique identifier of the notebook

        Returns:
            PageListResponse: Validated page list response with metadata

        Raises:
            APIAuthenticationError: If the client is not authenticated
            APIPermissionError: If the user lacks access to the notebook
            APIError: If the request fails or response parsing fails
        """
        # Ensure authentication
        if not self.uid:
            self.logger.error("List pages called without authentication")
            raise APIAuthenticationError(
                message="Authentication required - call authenticate() first",
                context={"operation": "list_pages", "notebook_id": notebook_id},
            )

        self.logger.info(
            "Listing pages for notebook",
            extra={
                "notebook_id": notebook_id,
                "user_id": self.uid,
                "operation": "list_pages",
            },
        )

        try:
            # Build authenticated parameters with notebook ID
            params = self._build_authenticated_params({"notebook_id": notebook_id})

            # Make API request
            response = self._make_request(
                method="GET",
                endpoint=LABARCHIVES_API_ENDPOINTS["pages_list"],
                params=params,
            )

            # Parse and validate response
            page_list = parse_page_list_response(raw_response=response.text, format="json")

            self.logger.info(
                "Pages retrieved successfully",
                extra={
                    "page_count": len(page_list.pages),
                    "notebook_id": notebook_id,
                    "user_id": self.uid,
                },
            )

            return page_list

        except (
            APIAuthenticationError,
            APIPermissionError,
            APIError,
            APIResponseParseError,
        ):
            # Re-raise known API errors
            raise
        except Exception as e:
            self.logger.error(
                "Unexpected error listing pages",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "notebook_id": notebook_id,
                    "user_id": self.uid,
                },
            )
            raise APIError(
                message=f"Failed to list pages: {str(e)}",
                code=500,
                context={
                    "operation": "list_pages",
                    "notebook_id": notebook_id,
                    "user_id": self.uid,
                    "error": str(e),
                },
            )

    def list_entries(self, page_id: str) -> EntryListResponse:
        """
        Retrieves the list of entries for a given page.

        This method fetches all entries within a specified page, including entry
        content, metadata, timestamps, and author information. The user must have
        read access to the page to retrieve its entries.

        Args:
            page_id (str): The unique identifier of the page

        Returns:
            EntryListResponse: Validated entry list response with content and metadata

        Raises:
            APIAuthenticationError: If the client is not authenticated
            APIPermissionError: If the user lacks access to the page
            APIError: If the request fails or response parsing fails
        """
        # Ensure authentication
        if not self.uid:
            self.logger.error("List entries called without authentication")
            raise APIAuthenticationError(
                message="Authentication required - call authenticate() first",
                context={"operation": "list_entries", "page_id": page_id},
            )

        self.logger.info(
            "Listing entries for page",
            extra={
                "page_id": page_id,
                "user_id": self.uid,
                "operation": "list_entries",
            },
        )

        try:
            # Build authenticated parameters with page ID
            params = self._build_authenticated_params({"page_id": page_id})

            # Make API request
            response = self._make_request(
                method="GET",
                endpoint=LABARCHIVES_API_ENDPOINTS["entries_get"],
                params=params,
            )

            # Parse and validate response
            entry_list = parse_entry_list_response(raw_response=response.text, format="json")

            self.logger.info(
                "Entries retrieved successfully",
                extra={
                    "entry_count": len(entry_list.entries),
                    "page_id": page_id,
                    "user_id": self.uid,
                },
            )

            return entry_list

        except (
            APIAuthenticationError,
            APIPermissionError,
            APIError,
            APIResponseParseError,
        ):
            # Re-raise known API errors
            raise
        except Exception as e:
            self.logger.error(
                "Unexpected error listing entries",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "page_id": page_id,
                    "user_id": self.uid,
                },
            )
            raise APIError(
                message=f"Failed to list entries: {str(e)}",
                code=500,
                context={
                    "operation": "list_entries",
                    "page_id": page_id,
                    "user_id": self.uid,
                    "error": str(e),
                },
            )

    def get_entry_content(self, entry_id: str) -> EntryListResponse:
        """
        Retrieves the detailed content for a specific entry by entry ID.

        This method fetches the complete content and metadata for a single entry,
        including text content, attachments, timestamps, and version information.
        The user must have read access to the entry to retrieve its content.

        Args:
            entry_id (str): The unique identifier of the entry

        Returns:
            EntryListResponse: Validated entry content response (single entry)

        Raises:
            APIAuthenticationError: If the client is not authenticated
            APIPermissionError: If the user lacks access to the entry
            APIError: If the request fails or response parsing fails
        """
        # Ensure authentication
        if not self.uid:
            self.logger.error("Get entry content called without authentication")
            raise APIAuthenticationError(
                message="Authentication required - call authenticate() first",
                context={"operation": "get_entry_content", "entry_id": entry_id},
            )

        self.logger.info(
            "Getting entry content",
            extra={
                "entry_id": entry_id,
                "user_id": self.uid,
                "operation": "get_entry_content",
            },
        )

        try:
            # Build authenticated parameters with entry ID
            params = self._build_authenticated_params({"entry_id": entry_id})

            # Make API request
            response = self._make_request(
                method="GET",
                endpoint=LABARCHIVES_API_ENDPOINTS["entries_get"],
                params=params,
            )

            # Parse and validate response
            entry_content = parse_entry_list_response(raw_response=response.text, format="json")

            self.logger.info(
                "Entry content retrieved successfully",
                extra={
                    "entry_id": entry_id,
                    "user_id": self.uid,
                    "content_size": (
                        len(entry_content.entries[0].content) if entry_content.entries else 0
                    ),
                },
            )

            return entry_content

        except (
            APIAuthenticationError,
            APIPermissionError,
            APIError,
            APIResponseParseError,
        ):
            # Re-raise known API errors
            raise
        except Exception as e:
            self.logger.error(
                "Unexpected error getting entry content",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "entry_id": entry_id,
                    "user_id": self.uid,
                },
            )
            raise APIError(
                message=f"Failed to get entry content: {str(e)}",
                code=500,
                context={
                    "operation": "get_entry_content",
                    "entry_id": entry_id,
                    "user_id": self.uid,
                    "error": str(e),
                },
            )

    def __enter__(self):
        """Context manager entry - returns self for use in with statements."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - closes the HTTP session."""
        if hasattr(self, 'session'):
            self.session.close()
            self.logger.info("HTTP session closed")

    def close(self):
        """Explicitly close the HTTP session and clean up resources."""
        if hasattr(self, 'session'):
            self.session.close()
            self.logger.info("LabArchives API client closed")


# Export the main client class
__all__ = ["LabArchivesAPIClient", "build_api_url"]
