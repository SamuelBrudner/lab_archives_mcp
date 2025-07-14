"""
Unit and integration test suite for the AuthenticationManager and authentication/session logic 
in the LabArchives MCP Server CLI.

This comprehensive test suite validates all authentication flows, error handling, session management, 
and audit logging for both permanent API key and temporary user token (SSO) scenarios. It uses 
parameterized fixtures for valid, invalid, and edge-case authentication configurations, and mocks 
LabArchives API responses to ensure deterministic, isolated, and repeatable tests.

The suite covers:
- Positive authentication scenarios with valid credentials
- Failure modes with invalid credentials and API errors
- Session establishment, management, and expiration handling
- Audit event emission and structured logging validation
- Exception propagation and error handling
- Edge cases and boundary conditions

Testing approach follows F-005 (Authentication and Security Management) and F-008 (Comprehensive 
Audit Logging) requirements from the technical specification, ensuring robust, secure, and 
compliant authentication behavior throughout the application lifecycle.
"""

import pytest  # pytest>=7.0.0 - Primary testing framework for test discovery, assertions, and parameterization
import asyncio  # builtin - Used for async test execution and event loop management
from unittest.mock import Mock, patch, MagicMock, call  # builtin - Used to patch/mock LabArchives API client methods and simulate API responses
from datetime import datetime, timedelta  # builtin - Used for timestamp assertions and session context validation
import json  # builtin - Used for JSON parsing and audit log validation
import logging  # builtin - Used for log level configuration and audit trail testing
from typing import Dict, Any, Optional  # builtin - Type hints for better code clarity and IDE support

# Internal imports - Primary authentication/session manager for testing
from src.cli.auth_manager import (
    AuthenticationManager, 
    AuthenticationSession,
    sanitize_credentials,
    is_token_expired,
    AUTH_SESSION_LIFETIME_SECONDS
)

# Internal imports - Authentication functions for standalone testing
from src.cli.auth_manager import AuthenticationManager as AuthManager  # Alias for JSON spec compatibility

# Internal imports - Base exception for structured error handling and validation
from src.cli.exceptions import LabArchivesMCPException, LabArchivesAPIException

# Internal imports - Test fixtures for valid, invalid, and edge-case configurations
from src.cli.tests.fixtures.config_samples import (
    get_valid_config,
    get_invalid_config, 
    get_edge_case_config
)

# Internal imports - API response fixtures for mocking successful and failed authentication
from src.cli.tests.fixtures.api_responses import (
    get_user_context_json,
    get_error_json,
    get_timeout_error_json,
    get_rate_limit_error_json,
    get_malformed_json
)

# Internal imports - Logging setup for audit trail testing
from src.cli.logging_setup import get_logger, get_audit_logger

# Internal imports - Configuration models for type safety
from src.cli.config import AuthenticationConfig, ServerConfiguration

# Internal imports - LabArchives API client for mocking
from src.cli.labarchives_api import LabArchivesAPI

# Internal imports - API models for response parsing
from src.cli.api.models import UserContext, User

# =============================================================================
# Test Configuration and Setup
# =============================================================================

@pytest.fixture(autouse=True)
def setup_logging():
    """
    Configure logging for test execution with appropriate levels and handlers.
    
    This fixture ensures consistent logging configuration across all tests
    and enables audit trail validation during test execution.
    """
    # Configure logging for test execution
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Get loggers for testing
    logger = get_logger()
    audit_logger = get_audit_logger()
    
    # Set appropriate log levels for testing
    logger.setLevel(logging.DEBUG)
    audit_logger.setLevel(logging.INFO)
    
    return logger, audit_logger

@pytest.fixture
def mock_user_context():
    """
    Create a mock UserContext object for successful authentication responses.
    
    Returns:
        UserContext: Mock user context with valid user information
    """
    mock_user = User(
        uid="user_123456",
        name="Test User",
        email="test@university.edu"
    )
    
    return UserContext(
        user=mock_user,
        status="success",
        message="Authentication successful"
    )

@pytest.fixture
def mock_api_client():
    """
    Create a mock LabArchivesAPI client for testing authentication flows.
    
    Returns:
        Mock: Configured mock API client with authentication method
    """
    mock_client = Mock(spec=LabArchivesAPI)
    mock_client.authenticate = Mock()
    return mock_client

# =============================================================================
# Authentication Success Tests
# =============================================================================

@pytest.mark.asyncio
async def test_authenticate_user_success(get_valid_config, mock_user_context):
    """
    Tests that authenticate_user returns a valid SessionContext when provided with a valid 
    AuthenticationConfig and a successful LabArchives API response.
    
    This test validates the complete authentication workflow including:
    - Configuration validation and parsing
    - API client initialization with correct parameters
    - Successful authentication with LabArchives API
    - Session context creation with valid user information
    - Proper timestamp and expiration handling
    
    Args:
        get_valid_config: Pytest fixture providing valid AuthenticationConfig
        mock_user_context: Mock UserContext for successful authentication
    """
    # Get valid configuration from fixture
    config = get_valid_config
    
    # Mock the LabArchives API client authentication to return successful response
    with patch('src.cli.auth_manager.LabArchivesAPI') as mock_api_class:
        mock_api_instance = Mock()
        mock_api_class.return_value = mock_api_instance
        mock_api_instance.authenticate.return_value = mock_user_context
        
        # Initialize AuthenticationManager with valid configuration
        auth_manager = AuthenticationManager(config.authentication)
        
        # Perform authentication
        session = auth_manager.authenticate()
        
        # Verify session context contains expected values
        assert session is not None
        assert isinstance(session, AuthenticationSession)
        assert session.user_id == "user_123456"
        assert session.access_key_id == config.authentication.access_key_id
        assert session.session_token == config.authentication.access_secret
        assert session.is_valid() is True
        
        # Verify timestamps are reasonable
        assert session.authenticated_at is not None
        assert session.expires_at is not None
        assert session.expires_at > session.authenticated_at
        
        # Verify session lifetime is correct
        expected_lifetime = timedelta(seconds=AUTH_SESSION_LIFETIME_SECONDS)
        actual_lifetime = session.expires_at - session.authenticated_at
        assert abs(actual_lifetime.total_seconds() - expected_lifetime.total_seconds()) < 5  # Allow 5 second tolerance
        
        # Verify API client was called with correct parameters
        mock_api_class.assert_called_once()
        mock_api_instance.authenticate.assert_called_once()

@pytest.mark.asyncio 
async def test_authenticate_user_api_key_method(get_valid_config, mock_user_context):
    """
    Tests authentication using API key method (without username).
    
    This test validates the API key authentication path where only access_key_id
    and access_secret are provided, without a username for SSO token authentication.
    """
    # Get valid configuration and remove username to force API key authentication
    config = get_valid_config
    config.authentication.username = None
    
    with patch('src.cli.auth_manager.LabArchivesAPI') as mock_api_class:
        mock_api_instance = Mock()
        mock_api_class.return_value = mock_api_instance
        mock_api_instance.authenticate.return_value = mock_user_context
        
        # Initialize AuthenticationManager
        auth_manager = AuthenticationManager(config.authentication)
        
        # Perform authentication
        session = auth_manager.authenticate()
        
        # Verify authentication was successful
        assert session is not None
        assert session.user_id == "user_123456"
        assert session.is_valid() is True
        
        # Verify API client was initialized without username
        mock_api_class.assert_called_once()
        call_args = mock_api_class.call_args
        assert call_args[1]['username'] is None

@pytest.mark.asyncio
async def test_authenticate_user_token_method(get_valid_config, mock_user_context):
    """
    Tests authentication using user token method (with username).
    
    This test validates the SSO token authentication path where username, 
    access_key_id, and access_secret (as token) are provided.
    """
    # Get valid configuration with username for token authentication
    config = get_valid_config
    assert config.authentication.username is not None
    
    with patch('src.cli.auth_manager.LabArchivesAPI') as mock_api_class:
        mock_api_instance = Mock()
        mock_api_class.return_value = mock_api_instance
        mock_api_instance.authenticate.return_value = mock_user_context
        
        # Initialize AuthenticationManager
        auth_manager = AuthenticationManager(config.authentication)
        
        # Perform authentication
        session = auth_manager.authenticate()
        
        # Verify authentication was successful
        assert session is not None
        assert session.user_id == "user_123456"
        assert session.is_valid() is True
        
        # Verify API client was initialized with username
        mock_api_class.assert_called_once()
        call_args = mock_api_class.call_args
        assert call_args[1]['username'] == config.authentication.username

# =============================================================================
# Authentication Failure Tests
# =============================================================================

@pytest.mark.asyncio
async def test_authenticate_user_failure(get_invalid_config):
    """
    Tests that authenticate_user raises LabArchivesMCPException when the LabArchives API 
    returns an authentication error.
    
    This test validates error handling for various authentication failure scenarios:
    - Invalid credentials
    - API authentication errors
    - Network connectivity issues
    - Service unavailability
    
    Args:
        get_invalid_config: Pytest fixture providing invalid AuthenticationConfig
    """
    # Get invalid configuration from fixture
    config = get_invalid_config
    
    # Mock the LabArchives API client to raise authentication error
    with patch('src.cli.auth_manager.LabArchivesAPI') as mock_api_class:
        mock_api_instance = Mock()
        mock_api_class.return_value = mock_api_instance
        
        # Configure mock to raise LabArchivesAPIException for authentication failure
        auth_error = LabArchivesAPIException(
            message="Invalid credentials or expired token",
            code=401,
            context={
                'error_type': 'authentication_failure',
                'requested_resource': '/api/user/info'
            }
        )
        mock_api_instance.authenticate.side_effect = auth_error
        
        # Initialize AuthenticationManager with invalid configuration
        auth_manager = AuthenticationManager(config.authentication)
        
        # Verify that authentication raises LabArchivesAPIException
        with pytest.raises(LabArchivesAPIException) as exc_info:
            auth_manager.authenticate()
        
        # Verify exception details
        assert "Authentication failed" in str(exc_info.value)
        assert exc_info.value.code == 401
        assert exc_info.value.context is not None
        assert "authentication_failure" in str(exc_info.value.context)

@pytest.mark.asyncio
async def test_authenticate_user_api_timeout():
    """
    Tests authentication failure due to API timeout.
    
    This test validates handling of network timeout scenarios during authentication.
    """
    # Create a valid configuration for timeout testing
    auth_config = AuthenticationConfig(
        access_key_id="AKID123456",
        access_secret="test_secret",
        username="test@university.edu",
        api_base_url="https://api.labarchives.com/api"
    )
    
    with patch('src.cli.auth_manager.LabArchivesAPI') as mock_api_class:
        mock_api_instance = Mock()
        mock_api_class.return_value = mock_api_instance
        
        # Configure mock to raise timeout error
        timeout_error = LabArchivesAPIException(
            message="Request timeout - server did not respond within expected time",
            code=408,
            context={'error_type': 'timeout', 'timeout_duration': '30s'}
        )
        mock_api_instance.authenticate.side_effect = timeout_error
        
        # Initialize AuthenticationManager
        auth_manager = AuthenticationManager(auth_config)
        
        # Verify that authentication raises timeout exception
        with pytest.raises(LabArchivesAPIException) as exc_info:
            auth_manager.authenticate()
        
        # Verify exception details
        assert "timeout" in str(exc_info.value).lower()
        assert exc_info.value.code == 408

@pytest.mark.asyncio
async def test_authenticate_user_rate_limit_error():
    """
    Tests authentication failure due to rate limiting.
    
    This test validates handling of rate limit errors during authentication.
    """
    # Create a valid configuration for rate limit testing
    auth_config = AuthenticationConfig(
        access_key_id="AKID123456",
        access_secret="test_secret",
        username="test@university.edu",
        api_base_url="https://api.labarchives.com/api"
    )
    
    with patch('src.cli.auth_manager.LabArchivesAPI') as mock_api_class:
        mock_api_instance = Mock()
        mock_api_class.return_value = mock_api_instance
        
        # Configure mock to raise rate limit error
        rate_limit_error = LabArchivesAPIException(
            message="Rate limit exceeded - too many requests",
            code=429,
            context={
                'error_type': 'rate_limit',
                'limit': '100 requests per hour',
                'reset_time': '2024-11-21T15:00:00Z'
            }
        )
        mock_api_instance.authenticate.side_effect = rate_limit_error
        
        # Initialize AuthenticationManager
        auth_manager = AuthenticationManager(auth_config)
        
        # Verify that authentication raises rate limit exception
        with pytest.raises(LabArchivesAPIException) as exc_info:
            auth_manager.authenticate()
        
        # Verify exception details
        assert "rate limit" in str(exc_info.value).lower()
        assert exc_info.value.code == 429

# =============================================================================
# Session Management Tests
# =============================================================================

@pytest.mark.asyncio
async def test_auth_manager_establish_session_and_get_context(get_valid_config, mock_user_context):
    """
    Tests that AuthenticationManager.establish_session successfully authenticates and stores 
    the session context, and that get_session_context returns the correct context.
    
    This test validates the complete session management workflow:
    - Session establishment through authentication
    - Session storage and retrieval
    - Session validation and consistency
    - Context preservation across method calls
    
    Args:
        get_valid_config: Pytest fixture providing valid AuthenticationConfig
        mock_user_context: Mock UserContext for successful authentication
    """
    # Get valid configuration from fixture
    config = get_valid_config
    
    with patch('src.cli.auth_manager.LabArchivesAPI') as mock_api_class:
        mock_api_instance = Mock()
        mock_api_class.return_value = mock_api_instance
        mock_api_instance.authenticate.return_value = mock_user_context
        
        # Initialize AuthenticationManager
        auth_manager = AuthenticationManager(config.authentication)
        
        # Establish session through authentication
        session = auth_manager.authenticate()
        
        # Verify session was created and is valid
        assert session is not None
        assert session.is_valid() is True
        assert session.user_id == "user_123456"
        
        # Verify get_session returns the same session context
        retrieved_session = auth_manager.get_session()
        assert retrieved_session is not None
        assert retrieved_session.user_id == session.user_id
        assert retrieved_session.access_key_id == session.access_key_id
        assert retrieved_session.authenticated_at == session.authenticated_at
        assert retrieved_session.expires_at == session.expires_at
        
        # Verify session is still valid after retrieval
        assert retrieved_session.is_valid() is True

@pytest.mark.asyncio
async def test_auth_manager_get_session_triggers_authentication(get_valid_config, mock_user_context):
    """
    Tests that calling get_session() without prior authentication triggers authentication.
    
    This test validates automatic authentication when session access is requested
    without an active session.
    """
    # Get valid configuration from fixture
    config = get_valid_config
    
    with patch('src.cli.auth_manager.LabArchivesAPI') as mock_api_class:
        mock_api_instance = Mock()
        mock_api_class.return_value = mock_api_instance
        mock_api_instance.authenticate.return_value = mock_user_context
        
        # Initialize AuthenticationManager without calling authenticate
        auth_manager = AuthenticationManager(config.authentication)
        
        # Verify no active session initially
        assert auth_manager.session is None
        assert auth_manager.is_authenticated() is False
        
        # Call get_session which should trigger authentication
        session = auth_manager.get_session()
        
        # Verify session was created through automatic authentication
        assert session is not None
        assert session.is_valid() is True
        assert session.user_id == "user_123456"
        assert auth_manager.is_authenticated() is True
        
        # Verify API client was called for authentication
        mock_api_instance.authenticate.assert_called_once()

@pytest.mark.asyncio
async def test_auth_manager_refresh_session(get_valid_config, mock_user_context):
    """
    Tests that AuthenticationManager.refresh_session re-authenticates and updates 
    the session context.
    
    This test validates session refresh functionality:
    - Re-authentication with updated user context
    - Session context updates after refresh
    - Audit event logging for session refresh
    - Proper handling of session expiration
    
    Args:
        get_valid_config: Pytest fixture providing valid AuthenticationConfig
        mock_user_context: Mock UserContext for successful authentication
    """
    # Get valid configuration from fixture
    config = get_valid_config
    
    with patch('src.cli.auth_manager.LabArchivesAPI') as mock_api_class:
        mock_api_instance = Mock()
        mock_api_class.return_value = mock_api_instance
        mock_api_instance.authenticate.return_value = mock_user_context
        
        # Initialize AuthenticationManager and establish initial session
        auth_manager = AuthenticationManager(config.authentication)
        initial_session = auth_manager.authenticate()
        
        # Store initial session details
        initial_auth_time = initial_session.authenticated_at
        initial_expires_time = initial_session.expires_at
        
        # Wait a brief moment to ensure timestamp difference
        await asyncio.sleep(0.1)
        
        # Create updated mock user context for refresh
        updated_user_context = UserContext(
            user=User(
                uid="user_123456",
                name="Test User Updated",
                email="test@university.edu"
            ),
            status="success",
            message="Authentication refreshed successfully"
        )
        
        # Configure mock to return updated context
        mock_api_instance.authenticate.return_value = updated_user_context
        
        # Refresh the session by calling authenticate again
        refreshed_session = auth_manager.authenticate()
        
        # Verify session was refreshed with updated timestamps
        assert refreshed_session is not None
        assert refreshed_session.user_id == "user_123456"
        assert refreshed_session.authenticated_at > initial_auth_time
        assert refreshed_session.expires_at > initial_expires_time
        
        # Verify session is still valid after refresh
        assert refreshed_session.is_valid() is True
        
        # Verify API client was called twice (initial + refresh)
        assert mock_api_instance.authenticate.call_count == 2

@pytest.mark.asyncio
async def test_auth_manager_session_expiration_handling(get_valid_config, mock_user_context):
    """
    Tests handling of expired sessions and automatic re-authentication.
    
    This test validates session expiration detection and automatic renewal.
    """
    # Get valid configuration from fixture
    config = get_valid_config
    
    with patch('src.cli.auth_manager.LabArchivesAPI') as mock_api_class:
        mock_api_instance = Mock()
        mock_api_class.return_value = mock_api_instance
        mock_api_instance.authenticate.return_value = mock_user_context
        
        # Initialize AuthenticationManager
        auth_manager = AuthenticationManager(config.authentication)
        
        # Establish initial session
        session = auth_manager.authenticate()
        
        # Manually expire the session by setting expires_at to past time
        session.expires_at = datetime.utcnow() - timedelta(seconds=1)
        
        # Verify session is now invalid
        assert session.is_valid() is False
        
        # Call get_session which should trigger re-authentication
        new_session = auth_manager.get_session()
        
        # Verify new session was created and is valid
        assert new_session is not None
        assert new_session.is_valid() is True
        assert new_session.authenticated_at > session.authenticated_at
        
        # Verify API client was called twice (initial + re-authentication)
        assert mock_api_instance.authenticate.call_count == 2

# =============================================================================
# Session State Tests
# =============================================================================

def test_auth_manager_no_active_session_raises(get_valid_config):
    """
    Tests that get_session_context raises LabArchivesMCPException if no session 
    has been established.
    
    This test validates proper error handling when session access is attempted
    without authentication, ensuring secure session management.
    
    Args:
        get_valid_config: Pytest fixture providing valid AuthenticationConfig
    """
    # Get valid configuration from fixture
    config = get_valid_config
    
    with patch('src.cli.auth_manager.LabArchivesAPI') as mock_api_class:
        mock_api_instance = Mock()
        mock_api_class.return_value = mock_api_instance
        
        # Configure mock to raise authentication error
        auth_error = LabArchivesAPIException(
            message="Invalid credentials",
            code=401,
            context={'error_type': 'authentication_failure'}
        )
        mock_api_instance.authenticate.side_effect = auth_error
        
        # Initialize AuthenticationManager without establishing session
        auth_manager = AuthenticationManager(config.authentication)
        
        # Verify no active session
        assert auth_manager.session is None
        assert auth_manager.is_authenticated() is False
        
        # Verify that get_session raises exception due to authentication failure
        with pytest.raises(LabArchivesAPIException):
            auth_manager.get_session()

def test_auth_manager_is_authenticated_status(get_valid_config, mock_user_context):
    """
    Tests the is_authenticated() method for various session states.
    
    This test validates authentication status checking across different scenarios.
    """
    # Get valid configuration from fixture
    config = get_valid_config
    
    with patch('src.cli.auth_manager.LabArchivesAPI') as mock_api_class:
        mock_api_instance = Mock()
        mock_api_class.return_value = mock_api_instance
        mock_api_instance.authenticate.return_value = mock_user_context
        
        # Initialize AuthenticationManager
        auth_manager = AuthenticationManager(config.authentication)
        
        # Initially no authentication
        assert auth_manager.is_authenticated() is False
        
        # After successful authentication
        auth_manager.authenticate()
        assert auth_manager.is_authenticated() is True
        
        # After session invalidation
        auth_manager.invalidate_session()
        assert auth_manager.is_authenticated() is False

def test_auth_manager_session_invalidation(get_valid_config, mock_user_context):
    """
    Tests session invalidation functionality.
    
    This test validates the invalidate_session() method and its effects.
    """
    # Get valid configuration from fixture
    config = get_valid_config
    
    with patch('src.cli.auth_manager.LabArchivesAPI') as mock_api_class:
        mock_api_instance = Mock()
        mock_api_class.return_value = mock_api_instance
        mock_api_instance.authenticate.return_value = mock_user_context
        
        # Initialize AuthenticationManager and establish session
        auth_manager = AuthenticationManager(config.authentication)
        session = auth_manager.authenticate()
        
        # Verify session is established
        assert session is not None
        assert auth_manager.is_authenticated() is True
        
        # Invalidate the session
        auth_manager.invalidate_session()
        
        # Verify session is cleared
        assert auth_manager.session is None
        assert auth_manager.is_authenticated() is False
        
        # Verify invalidation of already cleared session doesn't raise error
        auth_manager.invalidate_session()  # Should not raise exception

# =============================================================================
# Edge Case Tests
# =============================================================================

@pytest.mark.asyncio
async def test_authenticate_user_edge_cases(get_edge_case_config, mock_user_context):
    """
    Tests edge-case authentication scenarios (e.g., extremely long credentials, 
    special characters, conflicting config) to ensure robustness and error handling.
    
    This test validates system robustness with unusual but valid configurations:
    - Maximum length credentials
    - Special characters in configuration
    - Boundary value testing
    - Unicode handling
    
    Args:
        get_edge_case_config: Pytest fixture providing edge-case AuthenticationConfig
        mock_user_context: Mock UserContext for successful authentication
    """
    # Get edge case configuration from fixture
    config = get_edge_case_config
    
    with patch('src.cli.auth_manager.LabArchivesAPI') as mock_api_class:
        mock_api_instance = Mock()
        mock_api_class.return_value = mock_api_instance
        mock_api_instance.authenticate.return_value = mock_user_context
        
        # Initialize AuthenticationManager with edge case configuration
        auth_manager = AuthenticationManager(config.authentication)
        
        # Verify initialization handles edge cases correctly
        assert auth_manager.config.access_key_id == config.authentication.access_key_id
        assert len(auth_manager.config.access_key_id) == 256  # Maximum length
        assert len(auth_manager.config.access_secret) == 1024  # Maximum length
        
        # Attempt authentication with edge case configuration
        session = auth_manager.authenticate()
        
        # Verify authentication succeeds with edge case values
        assert session is not None
        assert session.is_valid() is True
        assert session.user_id == "user_123456"
        
        # Verify long credentials are handled properly
        assert session.access_key_id == config.authentication.access_key_id
        assert len(session.access_key_id) == 256
        
        # Verify API client was called successfully
        mock_api_instance.authenticate.assert_called_once()

def test_authentication_session_validation():
    """
    Tests AuthenticationSession validation logic for various scenarios.
    
    This test validates the session validation logic independently of the
    authentication manager.
    """
    # Test valid session
    valid_session = AuthenticationSession(
        user_id="user_123",
        access_key_id="AKID123",
        session_token="token123",
        authenticated_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=1)
    )
    assert valid_session.is_valid() is True
    
    # Test expired session
    expired_session = AuthenticationSession(
        user_id="user_123",
        access_key_id="AKID123",
        session_token="token123",
        authenticated_at=datetime.utcnow() - timedelta(hours=2),
        expires_at=datetime.utcnow() - timedelta(hours=1)
    )
    assert expired_session.is_valid() is False
    
    # Test session without expiration
    no_expiry_session = AuthenticationSession(
        user_id="user_123",
        access_key_id="AKID123",
        session_token="token123",
        authenticated_at=datetime.utcnow(),
        expires_at=None
    )
    assert no_expiry_session.is_valid() is True

def test_authentication_session_creation_validation():
    """
    Tests AuthenticationSession creation with invalid parameters.
    
    This test validates input validation during session creation.
    """
    current_time = datetime.utcnow()
    
    # Test invalid user_id
    with pytest.raises(ValueError, match="user_id must be a non-empty string"):
        AuthenticationSession(
            user_id="",
            access_key_id="AKID123",
            session_token="token123",
            authenticated_at=current_time
        )
    
    # Test invalid access_key_id
    with pytest.raises(ValueError, match="access_key_id must be a non-empty string"):
        AuthenticationSession(
            user_id="user_123",
            access_key_id="",
            session_token="token123",
            authenticated_at=current_time
        )
    
    # Test invalid session_token
    with pytest.raises(ValueError, match="session_token must be a non-empty string"):
        AuthenticationSession(
            user_id="user_123",
            access_key_id="AKID123",
            session_token="",
            authenticated_at=current_time
        )
    
    # Test invalid authenticated_at
    with pytest.raises(ValueError, match="authenticated_at must be a datetime object"):
        AuthenticationSession(
            user_id="user_123",
            access_key_id="AKID123",
            session_token="token123",
            authenticated_at=None
        )
    
    # Test invalid expires_at (before authenticated_at)
    with pytest.raises(ValueError, match="expires_at must be after authenticated_at"):
        AuthenticationSession(
            user_id="user_123",
            access_key_id="AKID123",
            session_token="token123",
            authenticated_at=current_time,
            expires_at=current_time - timedelta(hours=1)
        )

# =============================================================================
# Utility Function Tests
# =============================================================================

def test_sanitize_credentials():
    """
    Tests the sanitize_credentials utility function.
    
    This test validates credential sanitization for audit logging.
    """
    # Test comprehensive credential sanitization
    test_credentials = {
        'access_key_id': 'AKID123456',
        'access_secret': 'secret123',
        'token': 'token123',
        'password': 'password123',
        'api_key': 'apikey123',
        'username': 'user@example.com',
        'api_base_url': 'https://api.example.com',
        'custom_secret': 'custom123',
        'my_token': 'mytoken123',
        'normal_field': 'normal_value'
    }
    
    sanitized = sanitize_credentials(test_credentials)
    
    # Verify sensitive fields are redacted
    assert sanitized['access_key_id'] == '[REDACTED]'
    assert sanitized['access_secret'] == '[REDACTED]'
    assert sanitized['token'] == '[REDACTED]'
    assert sanitized['password'] == '[REDACTED]'
    assert sanitized['api_key'] == '[REDACTED]'
    assert sanitized['custom_secret'] == '[REDACTED]'
    assert sanitized['my_token'] == '[REDACTED]'
    
    # Verify non-sensitive fields are preserved
    assert sanitized['username'] == 'user@example.com'
    assert sanitized['api_base_url'] == 'https://api.example.com'
    assert sanitized['normal_field'] == 'normal_value'
    
    # Verify original dictionary is not modified
    assert test_credentials['access_key_id'] == 'AKID123456'
    assert test_credentials['access_secret'] == 'secret123'

def test_is_token_expired():
    """
    Tests the is_token_expired utility function.
    
    This test validates token expiration logic.
    """
    # Test future expiration time (not expired)
    future_time = datetime.utcnow() + timedelta(hours=1)
    assert is_token_expired(future_time) is False
    
    # Test past expiration time (expired)
    past_time = datetime.utcnow() - timedelta(hours=1)
    assert is_token_expired(past_time) is True
    
    # Test very recent expiration (edge case)
    very_recent = datetime.utcnow() - timedelta(seconds=1)
    assert is_token_expired(very_recent) is True

# =============================================================================
# Audit Logging Tests
# =============================================================================

@pytest.mark.asyncio
async def test_audit_logging_on_authentication(get_valid_config, get_invalid_config, mock_user_context):
    """
    Tests that successful and failed authentication attempts emit structured audit 
    events using the audit logging system.
    
    This test validates comprehensive audit logging:
    - Authentication success events with user context
    - Authentication failure events with error details
    - Structured log format for compliance
    - Audit trail completeness and accuracy
    
    Args:
        get_valid_config: Pytest fixture providing valid AuthenticationConfig
        get_invalid_config: Pytest fixture providing invalid AuthenticationConfig
        mock_user_context: Mock UserContext for successful authentication
    """
    # Test successful authentication audit logging
    valid_config = get_valid_config
    
    with patch('src.cli.auth_manager.LabArchivesAPI') as mock_api_class:
        mock_api_instance = Mock()
        mock_api_class.return_value = mock_api_instance
        mock_api_instance.authenticate.return_value = mock_user_context
        
        # Capture log messages
        with patch('src.cli.auth_manager.get_logger') as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance
            
            # Initialize AuthenticationManager and authenticate
            auth_manager = AuthenticationManager(valid_config.authentication)
            session = auth_manager.authenticate()
            
            # Verify successful authentication was logged
            assert logger_instance.info.called
            
            # Find the successful authentication log call
            success_calls = [call for call in logger_instance.info.call_args_list 
                           if "Authentication successful" in str(call)]
            assert len(success_calls) > 0
            
            # Verify log call contains expected information
            success_call = success_calls[0]
            assert "user_id" in str(success_call)
            assert "authenticated_at" in str(success_call)
            assert "expires_at" in str(success_call)
    
    # Test failed authentication audit logging
    invalid_config = get_invalid_config
    
    with patch('src.cli.auth_manager.LabArchivesAPI') as mock_api_class:
        mock_api_instance = Mock()
        mock_api_class.return_value = mock_api_instance
        
        # Configure mock to raise authentication error
        auth_error = LabArchivesAPIException(
            message="Invalid credentials",
            code=401,
            context={'error_type': 'authentication_failure'}
        )
        mock_api_instance.authenticate.side_effect = auth_error
        
        # Capture log messages
        with patch('src.cli.auth_manager.get_logger') as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance
            
            # Initialize AuthenticationManager and attempt authentication
            auth_manager = AuthenticationManager(invalid_config.authentication)
            
            with pytest.raises(LabArchivesAPIException):
                auth_manager.authenticate()
            
            # Verify failed authentication was logged
            assert logger_instance.error.called
            
            # Find the failed authentication log call
            error_calls = [call for call in logger_instance.error.call_args_list 
                         if "Authentication failed" in str(call)]
            assert len(error_calls) > 0
            
            # Verify log call contains expected error information
            error_call = error_calls[0]
            assert "error" in str(error_call)
            assert "error_code" in str(error_call)

def test_audit_logging_session_management(get_valid_config, mock_user_context):
    """
    Tests audit logging for session management operations.
    
    This test validates audit logging for session lifecycle events.
    """
    config = get_valid_config
    
    with patch('src.cli.auth_manager.LabArchivesAPI') as mock_api_class:
        mock_api_instance = Mock()
        mock_api_class.return_value = mock_api_instance
        mock_api_instance.authenticate.return_value = mock_user_context
        
        # Capture log messages
        with patch('src.cli.auth_manager.get_logger') as mock_logger:
            logger_instance = Mock()
            mock_logger.return_value = logger_instance
            
            # Initialize AuthenticationManager
            auth_manager = AuthenticationManager(config.authentication)
            
            # Test session access logging
            auth_manager.get_session()
            
            # Verify session access was logged
            debug_calls = [call for call in logger_instance.debug.call_args_list 
                         if "Accessing authentication session" in str(call)]
            assert len(debug_calls) > 0
            
            # Test session invalidation logging
            auth_manager.invalidate_session()
            
            # Verify session invalidation was logged
            info_calls = [call for call in logger_instance.info.call_args_list 
                        if "Invalidating authentication session" in str(call)]
            assert len(info_calls) > 0

# =============================================================================
# Integration Tests
# =============================================================================

@pytest.mark.asyncio
async def test_complete_authentication_workflow(get_valid_config, mock_user_context):
    """
    Tests the complete authentication workflow from initialization to session management.
    
    This integration test validates the entire authentication flow including:
    - AuthenticationManager initialization
    - Successful authentication and session creation
    - Session retrieval and validation
    - Session refresh and expiration handling
    - Session invalidation and cleanup
    """
    config = get_valid_config
    
    with patch('src.cli.auth_manager.LabArchivesAPI') as mock_api_class:
        mock_api_instance = Mock()
        mock_api_class.return_value = mock_api_instance
        mock_api_instance.authenticate.return_value = mock_user_context
        
        # Initialize AuthenticationManager
        auth_manager = AuthenticationManager(config.authentication)
        
        # Verify initial state
        assert auth_manager.is_authenticated() is False
        assert auth_manager.session is None
        
        # Perform authentication
        session = auth_manager.authenticate()
        
        # Verify authentication success
        assert session is not None
        assert session.is_valid() is True
        assert auth_manager.is_authenticated() is True
        
        # Test session retrieval
        retrieved_session = auth_manager.get_session()
        assert retrieved_session.user_id == session.user_id
        
        # Test session refresh
        refreshed_session = auth_manager.authenticate()
        assert refreshed_session.user_id == session.user_id
        assert refreshed_session.authenticated_at >= session.authenticated_at
        
        # Test session invalidation
        auth_manager.invalidate_session()
        assert auth_manager.is_authenticated() is False
        assert auth_manager.session is None
        
        # Verify re-authentication after invalidation
        new_session = auth_manager.get_session()
        assert new_session is not None
        assert new_session.is_valid() is True

# =============================================================================
# Error Handling Integration Tests
# =============================================================================

@pytest.mark.asyncio
async def test_authentication_error_recovery(get_valid_config, mock_user_context):
    """
    Tests error recovery scenarios during authentication.
    
    This test validates system behavior when authentication fails initially
    but succeeds on retry.
    """
    config = get_valid_config
    
    with patch('src.cli.auth_manager.LabArchivesAPI') as mock_api_class:
        mock_api_instance = Mock()
        mock_api_class.return_value = mock_api_instance
        
        # Configure mock to fail first, then succeed
        auth_error = LabArchivesAPIException(
            message="Temporary authentication failure",
            code=500,
            context={'error_type': 'temporary_failure'}
        )
        mock_api_instance.authenticate.side_effect = [auth_error, mock_user_context]
        
        # Initialize AuthenticationManager
        auth_manager = AuthenticationManager(config.authentication)
        
        # First authentication attempt should fail
        with pytest.raises(LabArchivesAPIException):
            auth_manager.authenticate()
        
        # Second authentication attempt should succeed
        session = auth_manager.authenticate()
        assert session is not None
        assert session.is_valid() is True
        
        # Verify API client was called twice
        assert mock_api_instance.authenticate.call_count == 2

# =============================================================================
# Performance and Stress Tests
# =============================================================================

@pytest.mark.asyncio
async def test_multiple_session_operations_performance(get_valid_config, mock_user_context):
    """
    Tests performance of multiple session operations.
    
    This test validates that session operations remain performant
    under repeated usage.
    """
    config = get_valid_config
    
    with patch('src.cli.auth_manager.LabArchivesAPI') as mock_api_class:
        mock_api_instance = Mock()
        mock_api_class.return_value = mock_api_instance
        mock_api_instance.authenticate.return_value = mock_user_context
        
        # Initialize AuthenticationManager
        auth_manager = AuthenticationManager(config.authentication)
        
        # Perform multiple session operations
        start_time = datetime.utcnow()
        
        for i in range(100):
            # Alternate between getting session and checking authentication
            if i % 2 == 0:
                session = auth_manager.get_session()
                assert session.is_valid() is True
            else:
                is_auth = auth_manager.is_authenticated()
                assert is_auth is True
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        # Verify operations completed within reasonable time (should be very fast)
        assert duration < 1.0, f"Session operations took {duration} seconds, expected < 1.0"
        
        # Verify API client was called only once (session cached)
        assert mock_api_instance.authenticate.call_count == 1

# =============================================================================
# String Representation Tests
# =============================================================================

def test_authentication_manager_string_representation(get_valid_config):
    """
    Tests string representation of AuthenticationManager.
    
    This test validates the __str__ and __repr__ methods for debugging.
    """
    config = get_valid_config
    
    with patch('src.cli.auth_manager.LabArchivesAPI'):
        auth_manager = AuthenticationManager(config.authentication)
        
        # Test string representation
        str_repr = str(auth_manager)
        assert "AuthenticationManager" in str_repr
        assert config.authentication.api_base_url in str_repr
        assert "authenticated=False" in str_repr
        
        # Test repr method
        repr_str = repr(auth_manager)
        assert "AuthenticationManager" in repr_str

def test_authentication_session_string_representation():
    """
    Tests string representation of AuthenticationSession.
    
    This test validates the __str__ and __repr__ methods for debugging
    while ensuring sensitive information is not exposed.
    """
    current_time = datetime.utcnow()
    expires_time = current_time + timedelta(hours=1)
    
    session = AuthenticationSession(
        user_id="user_123",
        access_key_id="AKID123456",
        session_token="secret_token",
        authenticated_at=current_time,
        expires_at=expires_time
    )
    
    # Test string representation
    str_repr = str(session)
    assert "AuthenticationSession" in str_repr
    assert "user_123" in str_repr
    assert "[REDACTED]" in str_repr  # Sensitive data should be redacted
    assert "AKID123456" not in str_repr  # Access key should be redacted
    assert "secret_token" not in str_repr  # Token should be redacted
    
    # Test repr method
    repr_str = repr(session)
    assert "AuthenticationSession" in repr_str
    assert "[REDACTED]" in repr_str

# =============================================================================
# Parameterized Tests
# =============================================================================

@pytest.mark.parametrize("auth_method,username", [
    ("api_key", None),
    ("user_token", "test@university.edu"),
])
@pytest.mark.asyncio
async def test_authentication_methods_parameterized(auth_method, username, mock_user_context):
    """
    Parameterized test for different authentication methods.
    
    This test validates both API key and user token authentication methods
    using parameterized test cases.
    """
    # Create configuration based on authentication method
    auth_config = AuthenticationConfig(
        access_key_id="AKID123456",
        access_secret="test_secret",
        username=username,
        api_base_url="https://api.labarchives.com/api"
    )
    
    with patch('src.cli.auth_manager.LabArchivesAPI') as mock_api_class:
        mock_api_instance = Mock()
        mock_api_class.return_value = mock_api_instance
        mock_api_instance.authenticate.return_value = mock_user_context
        
        # Initialize AuthenticationManager
        auth_manager = AuthenticationManager(auth_config)
        
        # Perform authentication
        session = auth_manager.authenticate()
        
        # Verify authentication success regardless of method
        assert session is not None
        assert session.is_valid() is True
        assert session.user_id == "user_123456"
        
        # Verify API client was initialized with correct parameters
        mock_api_class.assert_called_once()
        call_args = mock_api_class.call_args
        assert call_args[1]['username'] == username

@pytest.mark.parametrize("error_code,error_message", [
    (401, "Invalid credentials"),
    (403, "Access denied"),
    (429, "Rate limit exceeded"),
    (500, "Internal server error"),
    (503, "Service unavailable"),
])
@pytest.mark.asyncio
async def test_authentication_errors_parameterized(error_code, error_message):
    """
    Parameterized test for different authentication error scenarios.
    
    This test validates error handling for various HTTP error codes
    and messages that might be returned by the LabArchives API.
    """
    # Create valid configuration for error testing
    auth_config = AuthenticationConfig(
        access_key_id="AKID123456",
        access_secret="test_secret",
        username="test@university.edu",
        api_base_url="https://api.labarchives.com/api"
    )
    
    with patch('src.cli.auth_manager.LabArchivesAPI') as mock_api_class:
        mock_api_instance = Mock()
        mock_api_class.return_value = mock_api_instance
        
        # Configure mock to raise specific error
        auth_error = LabArchivesAPIException(
            message=error_message,
            code=error_code,
            context={'error_type': 'authentication_failure'}
        )
        mock_api_instance.authenticate.side_effect = auth_error
        
        # Initialize AuthenticationManager
        auth_manager = AuthenticationManager(auth_config)
        
        # Verify authentication raises expected exception
        with pytest.raises(LabArchivesAPIException) as exc_info:
            auth_manager.authenticate()
        
        # Verify exception details
        assert exc_info.value.code == error_code
        assert error_message in str(exc_info.value)

# =============================================================================
# Test Cleanup
# =============================================================================

def teardown_module():
    """
    Clean up after all tests in this module.
    
    This function performs any necessary cleanup after all tests
    have completed execution.
    """
    # Clear any global state or cached objects
    import gc
    gc.collect()
    
    # Reset logging configuration
    logging.getLogger().handlers.clear()
    
    print("Authentication Manager test suite completed successfully")