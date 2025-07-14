"""
LabArchives MCP Server - Authentication Manager

This module implements the AuthenticationManager class and related functions for secure 
authentication and credential management with the LabArchives API. It handles both 
permanent API key authentication and temporary user token authentication, manages 
session context, validates credentials, and integrates with logging and error handling 
for audit and compliance.

Key Features:
- Dual authentication support for permanent API keys and temporary user tokens
- Secure credential handling with environment variable support and in-memory storage only
- Token validation and session management with automatic expiration handling
- Comprehensive security controls including error sanitization and audit logging
- Integration with LabArchives API client for seamless authentication workflows
- Stateless operation with no persistent credential storage for enhanced security

This module supports the following technical specification features:
- F-005: Authentication and Security Management - Secure authentication mechanisms
- F-005-RQ-001: Credential Management - Secure handling of API credentials
- F-005-RQ-002: Token Validation and Session Management - Token validation and session handling
- F-005-RQ-003: Session Management - Authentication session lifecycle management
- F-005-RQ-004: Security Controls and Audit Logging - Comprehensive security practices

All authentication operations are designed to be secure, auditable, and production-ready
with comprehensive error handling and detailed logging for troubleshooting and compliance.
"""

import logging  # builtin - Python 3.11+ logging framework for audit and security event logging
from datetime import datetime, timedelta  # builtin - Python 3.11+ datetime handling for session timestamps and expiration
from typing import Optional  # builtin - Python 3.11+ type annotations for optional fields in session and config

# Internal imports - LabArchives API client for direct communication with LabArchives REST API
from src.cli.labarchives_api import LabArchivesAPI

# Internal imports - Authentication configuration schema from configuration management
from src.cli.config import AuthenticationConfig

# Internal imports - Custom exception for authentication failures and structured error handling
from src.cli.exceptions import LabArchivesAPIException

# Internal imports - Configured logger for audit and security event logging
from src.cli.logging_setup import get_logger

# =============================================================================
# Global Constants
# =============================================================================

# Authentication session lifetime in seconds (1 hour)
# This constant defines the default session lifetime for authentication sessions
# and is used for token expiration calculations and session validation
AUTH_SESSION_LIFETIME_SECONDS = 3600

# =============================================================================
# Utility Functions for Security and Validation
# =============================================================================

def sanitize_credentials(credentials: dict) -> dict:
    """
    Removes sensitive credential information from a dictionary for secure logging and error reporting.
    
    This function implements security best practices by redacting sensitive credential
    fields from dictionaries before they are logged or included in error messages.
    This prevents accidental exposure of sensitive information in log files, error
    outputs, and audit trails while maintaining the structure for debugging purposes.
    
    The function identifies common credential field names and replaces their values
    with '[REDACTED]' to maintain the dictionary structure while protecting sensitive
    data. This is essential for compliance with security standards and regulatory
    requirements that mandate protection of authentication credentials.
    
    Security Features:
    - Comprehensive redaction of common credential field names
    - Preserves dictionary structure for debugging while protecting sensitive data
    - Case-insensitive matching to catch various naming conventions
    - Returns a new dictionary to avoid modifying the original
    
    Args:
        credentials (dict): The credentials dictionary to sanitize. Can contain any
                           combination of credential fields including API keys, tokens,
                           passwords, and other sensitive authentication information.
    
    Returns:
        dict: A new dictionary with the same structure as the input but with sensitive
              field values replaced with '[REDACTED]'. Non-sensitive fields are
              preserved unchanged.
    
    Example:
        >>> creds = {
        ...     'access_key_id': 'AKID123456',
        ...     'access_secret': 'secret123',
        ...     'username': 'user@example.com',
        ...     'api_base_url': 'https://api.labarchives.com/api'
        ... }
        >>> sanitized = sanitize_credentials(creds)
        >>> print(sanitized)
        {
            'access_key_id': '[REDACTED]',
            'access_secret': '[REDACTED]',
            'username': 'user@example.com',
            'api_base_url': 'https://api.labarchives.com/api'
        }
    """
    # Create a copy of the credentials dictionary to avoid modifying the original
    sanitized = credentials.copy()
    
    # Define sensitive field names that should be redacted
    # This list includes common credential field names and variations
    sensitive_fields = {
        'access_key_id',
        'access_secret', 
        'token',
        'password',
        'secret',
        'api_key',
        'auth_token',
        'session_token',
        'access_token',
        'refresh_token',
        'private_key',
        'client_secret'
    }
    
    # Iterate over the credentials dictionary and redact sensitive fields
    for key, value in sanitized.items():
        # Check if the field name (case-insensitive) matches any sensitive field
        if key.lower() in sensitive_fields:
            sanitized[key] = '[REDACTED]'
        # Also check if the field name contains sensitive keywords
        elif any(sensitive in key.lower() for sensitive in ['secret', 'token', 'password', 'key']):
            sanitized[key] = '[REDACTED]'
    
    return sanitized


def is_token_expired(expires_at: datetime) -> bool:
    """
    Checks if a given token expiration timestamp is in the past.
    
    This function provides a simple and reliable way to determine if an authentication
    token has expired by comparing the expiration timestamp with the current UTC time.
    It is used throughout the authentication system to validate session validity and
    trigger token renewal processes when necessary.
    
    The function uses UTC time for all comparisons to ensure consistent behavior
    across different time zones and avoid issues with daylight saving time transitions.
    This is essential for distributed systems and ensures reliable token expiration
    checking regardless of the server's local time zone.
    
    Args:
        expires_at (datetime): The expiration timestamp to check against current time.
                              Should be a timezone-aware datetime object in UTC for
                              accurate comparison.
    
    Returns:
        bool: True if the token is expired (current time is after expires_at),
              False if the token is still valid (current time is before expires_at).
    
    Example:
        >>> from datetime import datetime, timedelta
        >>> # Token that expires in 1 hour
        >>> future_time = datetime.utcnow() + timedelta(hours=1)
        >>> is_token_expired(future_time)
        False
        >>> 
        >>> # Token that expired 1 hour ago
        >>> past_time = datetime.utcnow() - timedelta(hours=1)
        >>> is_token_expired(past_time)
        True
    """
    # Compare the expiration timestamp with the current UTC time
    # Return True if the current time is after the expiration time
    return datetime.utcnow() > expires_at


# =============================================================================
# Authentication Session Management
# =============================================================================

class AuthenticationSession:
    """
    Represents an in-memory authentication session for LabArchives API access.
    
    This class encapsulates all information related to an authenticated session,
    including user context, session tokens, and expiration timestamps. It provides
    a structured way to manage authentication state and validate session validity
    throughout the application lifecycle.
    
    The session is designed to be stateless and ephemeral, existing only in memory
    for the duration of the application process. This approach enhances security
    by ensuring that sensitive authentication information is not persisted to disk
    and is automatically cleaned up when the process terminates.
    
    Key Features:
    - Immutable session data for security and consistency
    - Built-in validation for session integrity and expiration
    - User context preservation for audit logging and access control
    - Session token management with automatic expiration handling
    - Secure credential handling with no persistent storage
    
    The session object is used throughout the authentication system to maintain
    authentication state and provide context for API operations and audit logging.
    
    Attributes:
        user_id (str): The unique user identifier from LabArchives
        access_key_id (str): The API access key identifier used for authentication
        session_token (str): The session token for API authentication
        authenticated_at (datetime): Timestamp when the session was created
        expires_at (Optional[datetime]): Optional expiration timestamp for the session
    """
    
    def __init__(self, user_id: str, access_key_id: str, session_token: str, 
                 authenticated_at: datetime, expires_at: Optional[datetime] = None):
        """
        Initializes the authentication session with user context and session information.
        
        This constructor creates a new authentication session with all required
        information for maintaining authenticated state throughout the application.
        It performs basic validation of the input parameters and establishes the
        session context for subsequent API operations.
        
        The session is created with the current authentication timestamp and an
        optional expiration timestamp. If no expiration is provided, the session
        will be considered valid indefinitely (until process termination).
        
        Args:
            user_id (str): The unique user identifier from LabArchives API. This is
                          typically the UID returned by the authentication endpoint.
            access_key_id (str): The API access key identifier used for authentication.
                                This is stored for audit logging and session context.
            session_token (str): The session token for API authentication. This could
                               be an API password or a temporary authentication token.
            authenticated_at (datetime): The timestamp when the session was created.
                                        Should be the current UTC time at session creation.
            expires_at (Optional[datetime]): Optional expiration timestamp for the session.
                                            If provided, the session will be considered
                                            invalid after this time.
        
        Raises:
            ValueError: If any required parameter is None or empty, or if the
                       expiration time is in the past.
        
        Example:
            >>> from datetime import datetime, timedelta
            >>> 
            >>> # Create a session that expires in 1 hour
            >>> now = datetime.utcnow()
            >>> expires = now + timedelta(hours=1)
            >>> session = AuthenticationSession(
            ...     user_id='12345',
            ...     access_key_id='AKID123456',
            ...     session_token='token123',
            ...     authenticated_at=now,
            ...     expires_at=expires
            ... )
        """
        # Validate required parameters
        if not user_id or not isinstance(user_id, str):
            raise ValueError("user_id must be a non-empty string")
        
        if not access_key_id or not isinstance(access_key_id, str):
            raise ValueError("access_key_id must be a non-empty string")
        
        if not session_token or not isinstance(session_token, str):
            raise ValueError("session_token must be a non-empty string")
        
        if not authenticated_at or not isinstance(authenticated_at, datetime):
            raise ValueError("authenticated_at must be a datetime object")
        
        # Validate expiration time if provided
        if expires_at is not None:
            if not isinstance(expires_at, datetime):
                raise ValueError("expires_at must be a datetime object if provided")
            if expires_at <= authenticated_at:
                raise ValueError("expires_at must be after authenticated_at")
        
        # Assign all parameters to instance properties
        self.user_id = user_id
        self.access_key_id = access_key_id
        self.session_token = session_token
        self.authenticated_at = authenticated_at
        self.expires_at = expires_at
    
    def is_valid(self) -> bool:
        """
        Checks if the session is still valid (not expired and has required data).
        
        This method performs comprehensive validation of the session state to determine
        if it can be used for API operations. It checks for token expiration, required
        user context, and overall session integrity.
        
        The validation process includes:
        1. Checking if the session has expired (if expiration is set)
        2. Validating that essential user context is present
        3. Ensuring the session is in a consistent state
        
        This method is used throughout the authentication system to validate session
        state before performing API operations or granting access to resources.
        
        Returns:
            bool: True if the session is valid and can be used for API operations,
                  False if the session is expired, invalid, or missing required data.
        
        Example:
            >>> # Check if session is valid before using it
            >>> if session.is_valid():
            ...     # Proceed with API operations
            ...     result = api_client.list_notebooks()
            ... else:
            ...     # Re-authenticate or handle expired session
            ...     logger.warning("Session expired, re-authentication required")
        """
        # Check if the session has expired
        if self.expires_at is not None and is_token_expired(self.expires_at):
            return False
        
        # Check if the user_id is present and valid
        if not self.user_id or not isinstance(self.user_id, str):
            return False
        
        # Check if required session data is present
        if not self.access_key_id or not self.session_token:
            return False
        
        # Session is valid if all checks pass
        return True
    
    def __str__(self) -> str:
        """
        Returns a string representation of the session with sanitized information.
        
        This method provides a human-readable representation of the session that
        includes essential information while protecting sensitive data. It's used
        for logging and debugging purposes.
        
        Returns:
            str: A sanitized string representation of the session.
        """
        expires_str = self.expires_at.isoformat() if self.expires_at else "No expiration"
        return (f"AuthenticationSession(user_id={self.user_id}, "
                f"access_key_id=[REDACTED], authenticated_at={self.authenticated_at.isoformat()}, "
                f"expires_at={expires_str})")
    
    def __repr__(self) -> str:
        """
        Returns a detailed string representation of the session for debugging.
        
        This method provides a detailed representation that includes all session
        attributes while protecting sensitive information.
        
        Returns:
            str: A detailed string representation of the session.
        """
        return self.__str__()


# =============================================================================
# Authentication Manager
# =============================================================================

class AuthenticationManager:
    """
    Handles all authentication logic for the LabArchives MCP Server.
    
    This class provides a comprehensive authentication management system that handles
    credential loading, validation, session management, and integration with the
    LabArchives API client. It supports both permanent API key authentication and
    temporary user token authentication, implementing security best practices and
    comprehensive audit logging.
    
    The manager serves as the central authentication authority for the entire
    application, coordinating between configuration management, the LabArchives API
    client, and the session management system. It ensures that all authentication
    operations are secure, auditable, and compliant with security requirements.
    
    Key Features:
    - Dual authentication support for permanent API keys and temporary user tokens
    - Secure credential handling with comprehensive validation and sanitization
    - Session lifecycle management with automatic expiration handling
    - Integration with LabArchives API client for seamless authentication workflows
    - Comprehensive audit logging for all authentication events and security operations
    - Stateless operation with no persistent credential storage for enhanced security
    
    The manager implements the complete authentication workflow from credential
    validation through session establishment and maintenance, providing a secure
    and reliable foundation for all LabArchives API operations.
    
    Attributes:
        config (AuthenticationConfig): The authentication configuration containing
                                      credentials and connection settings
        api_client (LabArchivesAPI): The LabArchives API client for authentication
        session (Optional[AuthenticationSession]): Current authentication session
        logger (logging.Logger): Logger instance for audit and security events
    """
    
    def __init__(self, config: AuthenticationConfig):
        """
        Initializes the AuthenticationManager with configuration and prepares the API client.
        
        This constructor sets up the authentication manager with the provided configuration
        and initializes the LabArchives API client. It performs initial validation of
        the configuration and prepares the system for authentication operations.
        
        The initialization process includes:
        1. Storing the authentication configuration
        2. Setting up the logger for audit and security events
        3. Initializing the LabArchives API client with configuration
        4. Preparing the session management system
        
        Args:
            config (AuthenticationConfig): The authentication configuration containing
                                         access credentials, API base URL, and other
                                         authentication parameters.
        
        Raises:
            ValueError: If the configuration is invalid or missing required parameters.
            LabArchivesAPIException: If the API client initialization fails.
        
        Example:
            >>> from src.cli.config import AuthenticationConfig
            >>> 
            >>> # Create authentication configuration
            >>> auth_config = AuthenticationConfig(
            ...     access_key_id='AKID123456',
            ...     access_secret='secret123',
            ...     api_base_url='https://api.labarchives.com/api'
            ... )
            >>> 
            >>> # Initialize authentication manager
            >>> auth_manager = AuthenticationManager(auth_config)
        """
        # Validate the configuration parameter
        if not config or not isinstance(config, AuthenticationConfig):
            raise ValueError("config must be a valid AuthenticationConfig instance")
        
        # Store the configuration for use throughout the authentication process
        self.config = config
        
        # Initialize the logger for audit and security event logging
        self.logger = get_logger()
        
        # Initialize the session to None - will be set during authentication
        self.session: Optional[AuthenticationSession] = None
        
        # Log the initialization event for audit purposes
        self.logger.info("Initializing AuthenticationManager", extra={
            'component': 'AuthenticationManager',
            'operation': 'init',
            'api_base_url': config.api_base_url,
            'has_username': bool(config.username),
            'config_valid': True
        })
        
        try:
            # Instantiate the LabArchives API client with the provided configuration
            self.api_client = LabArchivesAPI(
                access_key_id=config.access_key_id,
                access_secret=config.access_secret,
                username=config.username,
                region=self._determine_region_from_url(config.api_base_url)
            )
            
            # Log successful API client initialization
            self.logger.info("LabArchives API client initialized successfully", extra={
                'component': 'AuthenticationManager',
                'operation': 'init',
                'api_base_url': config.api_base_url,
                'client_initialized': True
            })
            
        except Exception as e:
            # Log the initialization failure with sanitized context
            self.logger.error("Failed to initialize LabArchives API client", extra={
                'component': 'AuthenticationManager',
                'operation': 'init',
                'error': str(e),
                'error_type': type(e).__name__,
                'config': sanitize_credentials(config.__dict__)
            })
            
            # Re-raise as LabArchivesAPIException with context
            raise LabArchivesAPIException(
                message=f"Failed to initialize LabArchives API client: {str(e)}",
                code=500,
                context={
                    'operation': 'init',
                    'config': sanitize_credentials(config.__dict__),
                    'error': str(e),
                    'error_type': type(e).__name__
                }
            )
    
    def authenticate(self) -> 'AuthenticationSession':
        """
        Performs authentication with LabArchives API and manages session context.
        
        This method performs the complete authentication workflow with the LabArchives
        API, including credential validation, authentication method determination,
        session establishment, and comprehensive audit logging. It supports both
        permanent API key authentication and temporary user token authentication.
        
        The authentication process includes:
        1. Determining the appropriate authentication method based on configuration
        2. Performing authentication with the LabArchives API
        3. Creating and validating the authentication session
        4. Storing the session context for subsequent API operations
        5. Comprehensive audit logging of all authentication events
        
        Authentication Methods:
        - API Key Authentication: Uses access_key_id and access_secret as password
        - User Token Authentication: Uses access_key_id, access_secret as token, and username
        
        Returns:
            AuthenticationSession: The authenticated session object containing user
                                  context, session tokens, and expiration information.
                                  This session is used for all subsequent API operations.
        
        Raises:
            LabArchivesAPIException: If authentication fails due to invalid credentials,
                                    network issues, API errors, or other authentication
                                    problems. The exception contains detailed context
                                    for debugging and audit logging.
        
        Example:
            >>> try:
            ...     session = auth_manager.authenticate()
            ...     logger.info(f"Authenticated as user: {session.user_id}")
            ... except LabArchivesAPIException as e:
            ...     logger.error(f"Authentication failed: {e}")
            ...     # Handle authentication failure
        """
        # Log the authentication attempt for audit purposes
        self.logger.info("Attempting authentication with LabArchives API", extra={
            'component': 'AuthenticationManager',
            'operation': 'authenticate',
            'api_base_url': self.config.api_base_url,
            'has_username': bool(self.config.username),
            'auth_method': 'user_token' if self.config.username else 'api_key'
        })
        
        try:
            # Determine authentication method based on configuration
            if self.config.username:
                # User token authentication for SSO users
                self.logger.info("Using user token authentication method", extra={
                    'component': 'AuthenticationManager',
                    'operation': 'authenticate',
                    'auth_method': 'user_token',
                    'username': self.config.username
                })
                
                # Perform authentication using user token method
                user_context = self.api_client.authenticate()
                
            else:
                # API key authentication for permanent credentials
                self.logger.info("Using API key authentication method", extra={
                    'component': 'AuthenticationManager',
                    'operation': 'authenticate',
                    'auth_method': 'api_key'
                })
                
                # Perform authentication using API key method
                user_context = self.api_client.authenticate()
            
            # Extract user information from the authentication response
            user_id = user_context.user.uid
            user_name = user_context.user.name
            user_email = user_context.user.email
            
            # Create authentication session with user context
            current_time = datetime.utcnow()
            expires_at = current_time + timedelta(seconds=AUTH_SESSION_LIFETIME_SECONDS)
            
            # Create the authentication session object
            self.session = AuthenticationSession(
                user_id=user_id,
                access_key_id=self.config.access_key_id,
                session_token=self.config.access_secret,
                authenticated_at=current_time,
                expires_at=expires_at
            )
            
            # Log successful authentication for audit purposes
            self.logger.info("Authentication successful", extra={
                'component': 'AuthenticationManager',
                'operation': 'authenticate',
                'user_id': user_id,
                'user_name': user_name,
                'user_email': user_email,
                'authenticated_at': current_time.isoformat(),
                'expires_at': expires_at.isoformat(),
                'auth_method': 'user_token' if self.config.username else 'api_key',
                'session_valid': self.session.is_valid()
            })
            
            return self.session
            
        except LabArchivesAPIException as e:
            # Log authentication failure with detailed context
            self.logger.error("Authentication failed", extra={
                'component': 'AuthenticationManager',
                'operation': 'authenticate',
                'error': str(e),
                'error_code': e.code,
                'error_context': e.context,
                'auth_method': 'user_token' if self.config.username else 'api_key',
                'api_base_url': self.config.api_base_url
            })
            
            # Re-raise the exception with additional context
            raise LabArchivesAPIException(
                message=f"Authentication failed: {str(e)}",
                code=e.code or 401,
                context={
                    'operation': 'authenticate',
                    'auth_method': 'user_token' if self.config.username else 'api_key',
                    'api_base_url': self.config.api_base_url,
                    'original_error': str(e),
                    'original_context': e.context
                }
            )
            
        except Exception as e:
            # Log unexpected error during authentication
            self.logger.error("Unexpected error during authentication", extra={
                'component': 'AuthenticationManager',
                'operation': 'authenticate',
                'error': str(e),
                'error_type': type(e).__name__,
                'auth_method': 'user_token' if self.config.username else 'api_key',
                'api_base_url': self.config.api_base_url
            })
            
            # Re-raise as LabArchivesAPIException with context
            raise LabArchivesAPIException(
                message=f"Unexpected error during authentication: {str(e)}",
                code=500,
                context={
                    'operation': 'authenticate',
                    'auth_method': 'user_token' if self.config.username else 'api_key',
                    'api_base_url': self.config.api_base_url,
                    'error': str(e),
                    'error_type': type(e).__name__
                }
            )
    
    def get_session(self) -> 'AuthenticationSession':
        """
        Returns the current authentication session if valid, otherwise triggers re-authentication.
        
        This method provides access to the current authentication session, automatically
        handling session validation and re-authentication when necessary. It ensures
        that the returned session is always valid and can be used for API operations.
        
        The method performs the following operations:
        1. Checks if a session exists and is valid
        2. If no session exists or the session is invalid, triggers re-authentication
        3. Returns the valid session for use in API operations
        4. Logs session access events for audit purposes
        
        This method is the primary way to access authentication state throughout
        the application, providing a reliable and secure way to ensure valid
        authentication context for all API operations.
        
        Returns:
            AuthenticationSession: A valid authentication session that can be used
                                  for API operations. The session is guaranteed to
                                  be valid and not expired.
        
        Raises:
            LabArchivesAPIException: If re-authentication fails or if the session
                                    cannot be established or validated. The exception
                                    contains detailed context for debugging and audit logging.
        
        Example:
            >>> try:
            ...     session = auth_manager.get_session()
            ...     # Use the session for API operations
            ...     notebooks = api_client.list_notebooks()
            ... except LabArchivesAPIException as e:
            ...     logger.error(f"Failed to get valid session: {e}")
        """
        # Log session access attempt for audit purposes
        self.logger.debug("Accessing authentication session", extra={
            'component': 'AuthenticationManager',
            'operation': 'get_session',
            'has_session': self.session is not None,
            'session_valid': self.session.is_valid() if self.session else False
        })
        
        # Check if session exists and is valid
        if self.session is None or not self.session.is_valid():
            # Log session validation failure
            if self.session is None:
                self.logger.info("No authentication session found, triggering authentication", extra={
                    'component': 'AuthenticationManager',
                    'operation': 'get_session',
                    'reason': 'no_session'
                })
            else:
                self.logger.info("Current session is invalid, triggering re-authentication", extra={
                    'component': 'AuthenticationManager',
                    'operation': 'get_session',
                    'reason': 'session_invalid',
                    'session_expired': self.session.expires_at is not None and is_token_expired(self.session.expires_at)
                })
            
            # Trigger re-authentication to establish a valid session
            self.session = self.authenticate()
        
        # Log successful session access
        self.logger.debug("Valid authentication session accessed", extra={
            'component': 'AuthenticationManager',
            'operation': 'get_session',
            'user_id': self.session.user_id,
            'session_valid': self.session.is_valid(),
            'expires_at': self.session.expires_at.isoformat() if self.session.expires_at else None
        })
        
        return self.session
    
    def is_authenticated(self) -> bool:
        """
        Checks if the current session is valid and authenticated.
        
        This method provides a simple way to check authentication status without
        triggering re-authentication. It's useful for conditional logic that needs
        to determine authentication state without side effects.
        
        The method performs a quick validation of the current session state and
        returns a boolean indicating whether the session is valid and can be used
        for API operations.
        
        Returns:
            bool: True if the current session is valid and authenticated,
                  False if no session exists or the session is invalid/expired.
        
        Example:
            >>> if auth_manager.is_authenticated():
            ...     # Proceed with authenticated operations
            ...     notebooks = api_client.list_notebooks()
            ... else:
            ...     # Handle unauthenticated state
            ...     logger.warning("Authentication required before API access")
        """
        # Check if session exists and is valid
        is_auth = self.session is not None and self.session.is_valid()
        
        # Log authentication status check for audit purposes
        self.logger.debug("Authentication status checked", extra={
            'component': 'AuthenticationManager',
            'operation': 'is_authenticated',
            'is_authenticated': is_auth,
            'has_session': self.session is not None,
            'session_valid': self.session.is_valid() if self.session else False
        })
        
        return is_auth
    
    def invalidate_session(self) -> None:
        """
        Invalidates the current authentication session (e.g., on logout or token expiration).
        
        This method provides a secure way to invalidate the current authentication
        session, clearing all session state and ensuring that subsequent API operations
        will require re-authentication. It's typically used during logout operations,
        error handling, or when token expiration is detected.
        
        The invalidation process includes:
        1. Clearing the current session from memory
        2. Logging the invalidation event for audit purposes
        3. Ensuring that subsequent operations will require re-authentication
        
        This method is important for security as it provides a clean way to terminate
        authenticated sessions and prevent unauthorized access to API resources.
        
        Example:
            >>> # Invalidate session on logout
            >>> auth_manager.invalidate_session()
            >>> logger.info("User session invalidated")
            >>> 
            >>> # Subsequent API operations will require re-authentication
            >>> session = auth_manager.get_session()  # Will trigger re-authentication
        """
        # Log session invalidation for audit purposes
        if self.session is not None:
            self.logger.info("Invalidating authentication session", extra={
                'component': 'AuthenticationManager',
                'operation': 'invalidate_session',
                'user_id': self.session.user_id,
                'session_was_valid': self.session.is_valid(),
                'authenticated_at': self.session.authenticated_at.isoformat(),
                'expires_at': self.session.expires_at.isoformat() if self.session.expires_at else None
            })
        else:
            self.logger.debug("Session invalidation requested but no session exists", extra={
                'component': 'AuthenticationManager',
                'operation': 'invalidate_session',
                'had_session': False
            })
        
        # Clear the session from memory
        self.session = None
        
        # Log successful session invalidation
        self.logger.info("Authentication session invalidated successfully", extra={
            'component': 'AuthenticationManager',
            'operation': 'invalidate_session',
            'session_cleared': True
        })
    
    def _determine_region_from_url(self, api_base_url: str) -> Optional[str]:
        """
        Determines the LabArchives region from the API base URL.
        
        This helper method extracts the region information from the API base URL
        to support region-aware API client initialization. It's used internally
        during authentication manager initialization.
        
        Args:
            api_base_url (str): The LabArchives API base URL
            
        Returns:
            Optional[str]: The region code ('US', 'AU', 'UK') or None for default
        """
        if 'auapi.labarchives.com' in api_base_url:
            return 'AU'
        elif 'ukapi.labarchives.com' in api_base_url:
            return 'UK'
        else:
            return 'US'  # Default to US region
    
    def __str__(self) -> str:
        """
        Returns a string representation of the authentication manager.
        
        This method provides a human-readable representation of the authentication
        manager state that includes essential information while protecting sensitive
        data. It's used for logging and debugging purposes.
        
        Returns:
            str: A sanitized string representation of the authentication manager.
        """
        return (f"AuthenticationManager(api_base_url={self.config.api_base_url}, "
                f"has_username={bool(self.config.username)}, "
                f"authenticated={self.is_authenticated()})")
    
    def __repr__(self) -> str:
        """
        Returns a detailed string representation of the authentication manager.
        
        This method provides a detailed representation that includes all manager
        attributes while protecting sensitive information.
        
        Returns:
            str: A detailed string representation of the authentication manager.
        """
        return self.__str__()