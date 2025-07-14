"""
LabArchives MCP Server - Authentication Command Handler

This module implements the CLI command handler for authenticating with the LabArchives API.
This command is responsible for securely validating user credentials (API key, secret/token,
username), establishing an authenticated session with LabArchives, and providing user feedback
on authentication status.

The command integrates with the centralized configuration loader, the AuthManager for session
management, and the logging/audit system to ensure all authentication attempts are validated,
logged, and reported in a user-friendly and compliant manner.

Key Features:
- Secure credential validation and session establishment
- Support for both permanent API keys and temporary user tokens (SSO)
- Comprehensive error handling and user-friendly diagnostics
- Audit logging for all authentication attempts and results
- Integration with centralized configuration management
- CLI subcommand interface for main application integration

This module supports the following technical specification features:
- F-005: Authentication and Security Management - Secure authentication mechanisms
- F-006: CLI Interface and Configuration - CLI command with configuration integration
- F-008: Comprehensive Audit Logging - Structured logging for authentication events
- F-008: Centralized Exception Handling - Structured error handling and reporting

All authentication operations are designed to be secure, auditable, and production-ready
with comprehensive error handling and detailed logging for troubleshooting and compliance.
"""

import sys  # builtin - Python 3.11+ system interface for CLI exit codes and error output
import logging  # builtin - Python 3.11+ logging framework for audit and security event logging
import argparse  # builtin - Python 3.11+ argument parsing for CLI interface

# Internal imports - Authentication manager for secure session establishment
from src.cli.auth_manager import AuthenticationManager

# Internal imports - Configuration loader for centralized configuration management
from src.cli.config import load_configuration

# Internal imports - Logging system setup for audit and security event logging
from src.cli.logging_setup import setup_logging

# Internal imports - Custom exception for structured error handling
from src.cli.exceptions import LabArchivesMCPException

# =============================================================================
# Global Constants
# =============================================================================

# Logger name for authentication command - used for audit trail and debugging
AUTH_COMMAND_LOGGER_NAME = "cli.authenticate"

# =============================================================================
# CLI Command Implementation
# =============================================================================

def authenticate_command(args: argparse.Namespace) -> int:
    """
    CLI entry point for authenticating with the LabArchives API.
    
    This function serves as the main entry point for the authenticate CLI command,
    implementing the complete authentication workflow from configuration loading
    through session establishment and user feedback. It handles both successful
    authentication and error conditions in a secure, auditable manner.
    
    The function performs the following operations:
    1. Load and validate configuration from all sources (CLI, env, file, defaults)
    2. Initialize the logging system with the loaded configuration
    3. Create and configure the AuthManager instance
    4. Attempt to establish an authenticated session with LabArchives
    5. Provide user feedback on authentication status (success/failure)
    6. Log all authentication events for audit and compliance purposes
    7. Return appropriate exit codes for CLI integration
    
    Authentication Process:
    - Validates credentials (API key, secret/token, username)
    - Determines authentication method (permanent API key vs temporary user token)
    - Establishes secure session with LabArchives API
    - Handles authentication failures with clear error messages
    - Maintains comprehensive audit trail of all authentication attempts
    
    Args:
        args (argparse.Namespace): Parsed CLI arguments containing configuration
            overrides, file paths, and command-line options. The args object
            is converted to a dictionary and passed to the configuration loader
            for proper precedence handling.
    
    Returns:
        int: Exit code indicating command success or failure:
            - 0: Authentication successful, session established
            - 1: Configuration loading or validation failed
            - 2: Authentication failed (invalid credentials, API errors, etc.)
            - 3: Unexpected error during authentication process
    
    Error Handling:
        All errors are handled gracefully with appropriate user feedback:
        - Configuration errors: Clear messages about invalid or missing config
        - Authentication errors: Specific feedback about credential issues
        - API errors: Network, service, or permission problems
        - Unexpected errors: Generic error handling with audit logging
    
    Example:
        >>> # Called from main CLI with parsed arguments
        >>> exit_code = authenticate_command(args)
        >>> if exit_code == 0:
        ...     print("Authentication successful")
        >>> else:
        ...     print("Authentication failed")
    """
    # Initialize logger for authentication command
    logger = None
    
    try:
        # Step 1: Load configuration from all sources with proper precedence
        # Convert argparse.Namespace to dict for configuration loader
        cli_args_dict = vars(args) if args else {}
        config_file_path = cli_args_dict.get('config_file')
        
        # Load and validate configuration from all sources
        config = load_configuration(
            cli_args=cli_args_dict,
            config_file_path=config_file_path
        )
        
        # Step 2: Initialize logging system with loaded configuration
        main_logger, audit_logger = setup_logging(config.logging)
        logger = logging.getLogger(AUTH_COMMAND_LOGGER_NAME)
        
        # Log authentication command start for audit purposes
        logger.info("Starting authentication command", extra={
            'component': 'authenticate_command',
            'operation': 'start',
            'config_file': config_file_path,
            'has_cli_args': bool(cli_args_dict),
            'api_base_url': config.authentication.api_base_url,
            'has_username': bool(config.authentication.username),
            'auth_method': 'user_token' if config.authentication.username else 'api_key'
        })
        
        # Step 3: Create and configure AuthManager instance
        auth_manager = AuthenticationManager(config.authentication)
        
        # Log AuthManager initialization for audit purposes
        logger.info("AuthManager initialized successfully", extra={
            'component': 'authenticate_command',
            'operation': 'auth_manager_init',
            'auth_manager_created': True,
            'api_base_url': config.authentication.api_base_url
        })
        
        # Step 4: Attempt to establish authenticated session
        logger.info("Attempting to establish authentication session", extra={
            'component': 'authenticate_command',
            'operation': 'establish_session',
            'auth_method': 'user_token' if config.authentication.username else 'api_key'
        })
        
        # Call the authentication method to establish session
        session = auth_manager.authenticate()
        
        # Step 5: Handle successful authentication
        if session and session.is_valid():
            # Extract user information from session for feedback
            user_id = session.user_id
            user_identifier = config.authentication.username or config.authentication.access_key_id
            
            # Provide success feedback to the user
            success_message = f"Authentication successful! Authenticated as user: {user_identifier} (UID: {user_id})"
            print(success_message)
            
            # Log successful authentication for audit purposes
            logger.info("Authentication completed successfully", extra={
                'component': 'authenticate_command',
                'operation': 'establish_session',
                'result': 'success',
                'user_id': user_id,
                'user_identifier': user_identifier,
                'session_valid': session.is_valid(),
                'authenticated_at': session.authenticated_at.isoformat(),
                'expires_at': session.expires_at.isoformat() if session.expires_at else None
            })
            
            # Return success exit code
            return 0
        else:
            # Handle case where session is invalid (should not happen with proper error handling)
            error_message = "Authentication failed: Invalid session established"
            print(error_message, file=sys.stderr)
            
            # Log the invalid session error
            logger.error("Authentication failed with invalid session", extra={
                'component': 'authenticate_command',
                'operation': 'establish_session',
                'result': 'failure',
                'error': 'invalid_session',
                'session_exists': session is not None,
                'session_valid': session.is_valid() if session else False
            })
            
            # Return authentication failure exit code
            return 2
            
    except LabArchivesMCPException as e:
        # Handle configuration and authentication specific errors
        error_message = f"Authentication failed: {str(e)}"
        print(error_message, file=sys.stderr)
        
        # Log the structured error for audit purposes
        if logger:
            logger.error("Authentication failed with LabArchivesMCPException", extra={
                'component': 'authenticate_command',
                'operation': 'establish_session',
                'result': 'failure',
                'error': str(e),
                'error_code': e.code,
                'error_context': e.context,
                'error_type': type(e).__name__
            })
        else:
            # Fallback logging if main logger is not available
            print(f"Error logging failed - {error_message}", file=sys.stderr)
        
        # Determine appropriate exit code based on error type
        if e.code and e.code >= 1000 and e.code < 2000:
            # Configuration errors (1000-1999)
            return 1
        elif e.code and e.code >= 2000 and e.code < 3000:
            # Authentication errors (2000-2999)
            return 2
        else:
            # Other LabArchivesMCPException errors
            return 2
            
    except Exception as e:
        # Handle any unexpected errors during authentication
        error_message = f"Unexpected error during authentication: {str(e)}"
        print(error_message, file=sys.stderr)
        
        # Log the unexpected error for audit purposes
        if logger:
            logger.error("Unexpected error during authentication", extra={
                'component': 'authenticate_command',
                'operation': 'establish_session',
                'result': 'failure',
                'error': str(e),
                'error_type': type(e).__name__,
                'unexpected_error': True
            })
        else:
            # Fallback logging if main logger is not available
            print(f"Error logging failed - {error_message}", file=sys.stderr)
        
        # Return unexpected error exit code
        return 3
    
    finally:
        # Log authentication command completion for audit purposes
        if logger:
            logger.info("Authentication command completed", extra={
                'component': 'authenticate_command',
                'operation': 'complete'
            })