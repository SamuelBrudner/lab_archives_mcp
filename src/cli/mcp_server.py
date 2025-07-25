"""
LabArchives MCP Server - Main Entrypoint and Server Orchestration with Session Refresh

This module serves as the main entrypoint and orchestration layer for the LabArchives MCP Server.
It initializes the MCP protocol stack, configures the resource and authentication managers,
loads validated configuration, sets up logging, and launches the main MCP protocol session loop
with automatic session refresh capability to handle authentication failures seamlessly.

The server integrates all core components—configuration, authentication, resource management,
protocol handler, and logging—ensuring strict compliance with the MCP specification and
robust error handling. It provides a production-ready, auditable, and secure MCP server
process for AI-to-LabArchives integration with continuous session management.

Key Features:
- F-001: MCP Protocol Implementation - Initializes and runs the MCP protocol stack
- F-002: LabArchives API Integration - Bootstraps the LabArchives API client
- F-003: Resource Discovery and Listing - Configures the resource manager
- F-004: Content Retrieval and Contextualization - Enables content retrieval
- F-005: Authentication and Security Management - Initializes authentication with session refresh
- F-006: CLI Interface and Configuration - Loads and validates configuration
- F-007: Scope Limitation and Access Control - Enforces scope settings
- F-008: Comprehensive Audit Logging - Initializes structured logging with security events

Enhanced Session Management:
- Automatic detection of 401 authentication errors during protocol operations
- Seamless session refresh using AuthenticationManager.refresh_session() capability
- Exponential backoff retry logic to prevent API overwhelming
- Comprehensive audit logging of session refresh events for security monitoring
- Fail-safe error handling that maintains MCP protocol compliance during re-authentication

The server is responsible for process lifecycle management, startup/shutdown, session continuity,
and top-level exception handling, providing a production-ready MCP server process with
enterprise-grade session management capabilities.
"""

import sys  # builtin - Access to stdin, stdout for protocol I/O, and sys.exit for process termination
import os  # builtin - Environment variable access and process signals for shutdown
import signal  # builtin - Graceful shutdown handling via signal handlers (SIGINT, SIGTERM)
import logging  # builtin - Logging of server startup, shutdown, and fatal errors
import traceback  # builtin - Detailed error reporting for uncaught exceptions
import time  # builtin - Time delays for retry mechanisms and session management

# Internal imports - Configuration management for loading and validating server configuration
from src.cli.config import load_configuration

# Internal imports - Configuration models for type safety and validation
from src.cli.models import ServerConfiguration

# Internal imports - Authentication management for secure LabArchives API access
from src.cli.auth_manager import AuthenticationManager

# Internal imports - LabArchives API client for authenticated data retrieval
from src.cli.api.client import LabArchivesAPIClient

# Internal imports - MCP resource manager for resource discovery and content retrieval
from src.cli.mcp.resources import MCPResourceManager

# Internal imports - MCP protocol handler for managing protocol sessions
from src.cli.mcp.protocol import MCPProtocolHandler

# Internal imports - Logging setup for audit trails and operational monitoring
from src.cli.logging_setup import setup_logging, get_logger

# Internal imports - Version information for server identification
from src.cli.version import __version__

# =============================================================================
# Global Constants
# =============================================================================

# Server logger name for consistent logging identification
SERVER_LOGGER_NAME = "mcp.server"


# =============================================================================
# Session Management Functions
# =============================================================================

def run_protocol_with_session_refresh(protocol_handler, auth_manager, stdin, stdout, logger, audit_logger, max_retries=3) -> None:
    """
    Run the MCP protocol session with automatic session refresh capability.
    
    This function wraps the protocol session loop with retry logic that can detect
    authentication failures (401 errors) and automatically refresh the session by
    calling AuthenticationManager.refresh_session() and retrying the failed operation
    seamlessly without interrupting MCP protocol operations.
    
    Args:
        protocol_handler: The MCPProtocolHandler instance to run
        auth_manager: The AuthenticationManager instance for session refresh
        stdin: Standard input stream for MCP protocol
        stdout: Standard output stream for MCP protocol
        logger: Main logger for operational messages
        audit_logger: Audit logger for security events
        max_retries: Maximum number of session refresh attempts (default: 3)
    
    Returns:
        None: Function runs until protocol session ends or unrecoverable error
        
    Raises:
        Exception: Re-raises any non-authentication related exceptions
    """
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            logger.info("Starting MCP protocol session loop", extra={
                "attempt": retry_count + 1,
                "max_retries": max_retries + 1,
                "operation": "protocol_session_start"
            })
            
            # Run the protocol session - this blocks until session ends or error
            protocol_handler.run_session(stdin, stdout)
            
            # If we reach here, the session ended normally
            logger.info("MCP protocol session ended normally", extra={
                "operation": "protocol_session_end",
                "retry_count": retry_count
            })
            return
            
        except Exception as e:
            # Check if this is an authentication-related error that warrants session refresh
            if is_authentication_error(e):
                retry_count += 1
                
                if retry_count <= max_retries:
                    logger.warning(f"Authentication error detected, attempting session refresh (attempt {retry_count}/{max_retries})", extra={
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "retry_count": retry_count,
                        "max_retries": max_retries,
                        "operation": "session_refresh_attempt"
                    })
                    
                    audit_logger.warning("Session refresh triggered by authentication failure", extra={
                        "event": "session_refresh_required",
                        "error_type": type(e).__name__,
                        "retry_attempt": retry_count,
                        "max_retries": max_retries
                    })
                    
                    try:
                        # Attempt to refresh the session using the AuthenticationManager
                        logger.info("Refreshing authentication session...", extra={
                            "operation": "session_refresh",
                            "retry_attempt": retry_count
                        })
                        
                        refreshed_session = auth_manager.refresh_session()
                        
                        logger.info("Session refreshed successfully, retrying protocol operation", extra={
                            "user_id": refreshed_session.user_id if hasattr(refreshed_session, 'user_id') else "unknown",
                            "operation": "session_refresh_success",
                            "retry_attempt": retry_count
                        })
                        
                        audit_logger.info("Authentication session refreshed successfully", extra={
                            "event": "session_refresh_success",
                            "user_id": refreshed_session.user_id if hasattr(refreshed_session, 'user_id') else "unknown",
                            "retry_attempt": retry_count
                        })
                        
                        # Add exponential backoff delay before retry to prevent overwhelming the API
                        backoff_delay = min(2 ** (retry_count - 1), 10)  # Cap at 10 seconds
                        if backoff_delay > 0:
                            logger.debug(f"Applying exponential backoff delay: {backoff_delay} seconds", extra={
                                "backoff_delay": backoff_delay,
                                "retry_attempt": retry_count,
                                "operation": "session_refresh_backoff"
                            })
                            time.sleep(backoff_delay)
                        
                        # Continue the loop to retry the protocol session
                        continue
                        
                    except Exception as refresh_error:
                        logger.error(f"Session refresh failed on attempt {retry_count}: {str(refresh_error)}", extra={
                            "error_type": type(refresh_error).__name__,
                            "error_message": str(refresh_error),
                            "retry_attempt": retry_count,
                            "operation": "session_refresh_failure"
                        })
                        
                        audit_logger.error("Session refresh attempt failed", extra={
                            "event": "session_refresh_failure",
                            "error_type": type(refresh_error).__name__,
                            "error_message": str(refresh_error),
                            "retry_attempt": retry_count
                        })
                        
                        # If this wasn't the last retry, continue the loop
                        if retry_count < max_retries:
                            continue
                        else:
                            # Max retries exceeded, re-raise the refresh error
                            logger.error("Maximum session refresh retries exceeded, giving up", extra={
                                "max_retries": max_retries,
                                "operation": "session_refresh_exhausted"
                            })
                            raise refresh_error
                else:
                    # Max retries exceeded for authentication errors
                    logger.error(f"Maximum authentication retry attempts exceeded ({max_retries}), terminating session", extra={
                        "max_retries": max_retries,
                        "final_error_type": type(e).__name__,
                        "final_error_message": str(e),
                        "operation": "max_retries_exceeded"
                    })
                    
                    audit_logger.error("Session terminated due to persistent authentication failures", extra={
                        "event": "session_termination_auth_failure",
                        "max_retries": max_retries,
                        "final_error_type": type(e).__name__
                    })
                    
                    raise e
            else:
                # Non-authentication error, re-raise immediately
                logger.error(f"Non-authentication error during protocol session: {str(e)}", extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "operation": "protocol_session_error"
                })
                raise e


def is_authentication_error(exception: Exception) -> bool:
    """
    Determine if an exception represents an authentication error that warrants session refresh.
    
    This function analyzes exception types and messages to identify authentication-related
    failures including 401 Unauthorized responses, session expiration, and token invalidity.
    
    Args:
        exception: The exception to analyze
        
    Returns:
        bool: True if the exception indicates an authentication failure, False otherwise
    """
    # Check exception type names for authentication-related errors
    error_type = type(exception).__name__
    error_message = str(exception).lower()
    
    # List of exception types that typically indicate authentication failures
    auth_error_types = [
        'AuthenticationError',
        'AuthError',
        'UnauthorizedError',
        'InvalidTokenError',
        'TokenExpiredError',
        'SessionExpiredError',
        'CredentialsError'
    ]
    
    # Check if the exception type indicates authentication failure
    if error_type in auth_error_types:
        return True
    
    # Check for HTTP 401 status codes in various formats
    if any(pattern in error_message for pattern in [
        '401',
        'unauthorized',
        'authentication failed',
        'invalid token',
        'token expired',
        'session expired',
        'credentials invalid',
        'access denied',
        'authentication required'
    ]):
        return True
    
    # Check for specific LabArchives API authentication error patterns
    if any(pattern in error_message for pattern in [
        'invalid access key',
        'invalid signature',
        'authentication signature',
        'hmac verification failed',
        'api key not found',
        'user token invalid'
    ]):
        return True
    
    return False


# =============================================================================
# Signal Handling Functions
# =============================================================================

def handle_shutdown_signal(signum: int, frame) -> None:
    """
    Signal handler for SIGINT and SIGTERM. Logs shutdown event and exits the process.
    
    This function provides graceful shutdown handling for the MCP server process.
    It logs the shutdown event for audit purposes and terminates the process
    cleanly to ensure proper resource cleanup and logging finalization.
    
    Args:
        signum (int): The signal number received (SIGINT=2, SIGTERM=15)
        frame: The current stack frame (not used but required by signal handler interface)
    
    Returns:
        None: This function does not return as it terminates the process
    """
    # Get the server logger for shutdown logging
    logger = get_logger()
    
    # Map signal numbers to human-readable names for logging
    signal_names = {
        signal.SIGINT: "SIGINT",
        signal.SIGTERM: "SIGTERM"
    }
    signal_name = signal_names.get(signum, f"Signal {signum}")
    
    # Log the shutdown event with signal information
    logger.info(f"Received shutdown signal {signal_name}, terminating server gracefully", extra={
        "signal_number": signum,
        "signal_name": signal_name,
        "operation": "shutdown"
    })
    
    # Flush all log handlers to ensure shutdown is recorded
    for handler in logger.handlers:
        handler.flush()
    
    # Exit the process cleanly with success code
    sys.exit(0)


# =============================================================================
# Main Server Function
# =============================================================================

def main() -> int:
    """
    Main entrypoint for the LabArchives MCP Server process.
    
    This function orchestrates the complete server initialization and execution lifecycle:
    1. Loads and validates configuration from all sources
    2. Initializes logging and audit systems
    3. Sets up authentication and API client components
    4. Configures resource management and protocol handling
    5. Registers signal handlers for graceful shutdown
    6. Launches the MCP protocol session loop
    7. Handles all errors with comprehensive logging and cleanup
    
    The function ensures that all components are properly initialized and integrated
    before starting the protocol session, providing robust error handling and
    comprehensive audit logging throughout the server lifecycle.
    
    Returns:
        int: Exit code (0 for success, nonzero for error)
    """
    # Initialize variables for cleanup in finally block
    server_config = None
    logger = None
    
    try:
        # Step 1: Load and validate configuration using load_configuration()
        print("Loading LabArchives MCP Server configuration...")
        server_config = load_configuration()
        
        # Step 2: Initialize logging and audit logging using setup_logging()
        print("Initializing logging system...")
        main_logger, audit_logger = setup_logging(server_config.logging)
        logger = main_logger
        
        # Step 3: Log server startup, version, and configuration summary
        logger.info("Starting LabArchives MCP Server", extra={
            "server_name": server_config.server_name,
            "server_version": server_config.server_version,
            "package_version": __version__,
            "api_base_url": server_config.authentication.api_base_url,
            "log_level": server_config.logging.log_level,
            "json_ld_enabled": server_config.output.json_ld_enabled,
            "has_scope_restriction": any([
                server_config.scope.notebook_id,
                server_config.scope.notebook_name,
                server_config.scope.folder_path
            ])
        })
        
        # Log configuration summary for audit purposes
        audit_logger.info("Server configuration loaded", extra={
            "event": "server_startup",
            "server_name": server_config.server_name,
            "server_version": server_config.server_version,
            "api_base_url": server_config.authentication.api_base_url,
            "scope_type": "notebook" if server_config.scope.notebook_id else "folder" if server_config.scope.folder_path else "all",
            "json_ld_enabled": server_config.output.json_ld_enabled
        })
        
        # Step 4: Initialize the LabArchivesAPIClient with credentials from configuration
        logger.info("Initializing LabArchives API client...")
        api_client = LabArchivesAPIClient(
            access_key_id=server_config.authentication.access_key_id,
            access_password=server_config.authentication.access_secret,
            username=server_config.authentication.username,
            api_base_url=server_config.authentication.api_base_url
        )
        
        # Step 5: Initialize the AuthenticationManager and authenticate with LabArchives API
        logger.info("Initializing authentication manager...")
        auth_manager = AuthenticationManager(server_config.authentication)
        
        logger.info("Authenticating with LabArchives API...")
        auth_session = auth_manager.authenticate()
        
        # Log successful authentication for audit purposes
        audit_logger.info("Authentication successful", extra={
            "event": "authentication_success",
            "user_id": auth_session.user_id,
            "auth_method": "user_token" if server_config.authentication.username else "api_key"
        })
        
        # Step 6: Initialize the MCPResourceManager with the API client, scope config, and JSON-LD flag
        logger.info("Initializing MCP resource manager...")
        scope_config = {
            "notebook_id": server_config.scope.notebook_id,
            "notebook_name": server_config.scope.notebook_name,
            "folder_path": server_config.scope.folder_path
        }
        
        resource_manager = MCPResourceManager(
            api_client=api_client,
            scope_config=scope_config,
            jsonld_enabled=server_config.output.json_ld_enabled
        )
        
        # Step 7: Initialize the MCPProtocolHandler with the resource manager
        logger.info("Initializing MCP protocol handler...")
        protocol_handler = MCPProtocolHandler(resource_manager)
        
        # Step 8: Register signal handlers for SIGINT and SIGTERM for graceful shutdown
        logger.info("Registering signal handlers for graceful shutdown...")
        signal.signal(signal.SIGINT, handle_shutdown_signal)
        signal.signal(signal.SIGTERM, handle_shutdown_signal)
        
        # Log successful server initialization with session refresh capability
        logger.info("LabArchives MCP Server initialization completed successfully with session refresh capability", extra={
            "server_name": server_config.server_name,
            "server_version": server_config.server_version,
            "status": "ready",
            "session_refresh_enabled": True,
            "user_id": auth_session.user_id
        })
        
        audit_logger.info("Server initialization completed with enhanced authentication", extra={
            "event": "server_ready",
            "server_name": server_config.server_name,
            "server_version": server_config.server_version,
            "user_id": auth_session.user_id,
            "session_refresh_enabled": True,
            "authentication_method": "user_token" if server_config.authentication.username else "api_key"
        })
        
        # Step 9: Run the MCP protocol session loop with session refresh capability
        logger.info("Starting MCP protocol session loop with session refresh capability...")
        run_protocol_with_session_refresh(
            protocol_handler=protocol_handler,
            auth_manager=auth_manager,
            stdin=sys.stdin,
            stdout=sys.stdout,
            logger=logger,
            audit_logger=audit_logger,
            max_retries=3
        )
        
        # If we reach here, the session ended normally
        logger.info("MCP protocol session ended normally")
        audit_logger.info("Server shutdown completed", extra={
            "event": "server_shutdown",
            "reason": "normal_termination"
        })
        
        return 0
        
    except KeyboardInterrupt:
        # Step 10: Handle KeyboardInterrupt (Ctrl+C) for graceful shutdown
        if logger:
            logger.info("Server interrupted by user (Ctrl+C)", extra={
                "shutdown_reason": "keyboard_interrupt",
                "session_refresh_enabled": True
            })
            
            # Log session termination for audit purposes
            if 'audit_logger' in locals():
                audit_logger.info("Server shutdown via keyboard interrupt", extra={
                    "event": "server_shutdown",
                    "reason": "keyboard_interrupt",
                    "shutdown_type": "graceful"
                })
        else:
            print("Server interrupted by user (Ctrl+C)")
            print("Session refresh capability was active during shutdown.")
        
        return 0
        
    except Exception as e:
        # Step 11: Handle all exceptions with comprehensive error logging and session context
        error_message = f"Unexpected error during server execution: {str(e)}"
        error_traceback = traceback.format_exc()
        
        # Determine if this is an authentication-related error for specialized handling
        is_auth_error = is_authentication_error(e)
        
        if logger:
            logger.error(error_message, extra={
                "error_type": type(e).__name__,
                "error_details": str(e),
                "traceback": error_traceback,
                "operation": "main",
                "is_authentication_error": is_auth_error,
                "session_refresh_capable": True
            })
            
            # Additional logging for authentication-related failures
            if is_auth_error:
                logger.error("Authentication-related error during server execution", extra={
                    "error_type": type(e).__name__,
                    "error_details": str(e),
                    "operation": "authentication_failure",
                    "recommendation": "Check authentication credentials and LabArchives API accessibility"
                })
                
                # Log to audit logger for security monitoring
                if 'audit_logger' in locals():
                    audit_logger.error("Server terminated due to authentication failure", extra={
                        "event": "server_termination_auth_error",
                        "error_type": type(e).__name__,
                        "error_details": str(e)
                    })
        else:
            print(f"ERROR: {error_message}")
            print(f"Traceback:\n{error_traceback}")
            if is_auth_error:
                print("NOTE: This appears to be an authentication-related error. Please verify your credentials and API access.")
        
        return 1
        
    finally:
        # Ensure proper cleanup and final logging
        if logger:
            logger.info("LabArchives MCP Server process terminating")
            
            # Flush all log handlers to ensure final messages are written
            for handler in logger.handlers:
                handler.flush()


# =============================================================================
# Module Entry Point
# =============================================================================

if __name__ == "__main__":
    # Execute the main function and exit with the returned code
    exit_code = main()
    sys.exit(exit_code)