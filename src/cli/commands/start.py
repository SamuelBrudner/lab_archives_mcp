"""
LabArchives MCP Server CLI - Start Command Implementation

This module implements the CLI 'start' command for launching the LabArchives MCP Server.
This file acts as the operational entrypoint for starting the MCP server process from
the CLI, orchestrating configuration loading, logging setup, authentication, resource
manager instantiation, and protocol server startup.

The start command ensures robust error handling, audit logging, and user feedback, and
is invoked by the main CLI parser when the 'start' subcommand is used. The command is
designed for both interactive CLI use and programmatic invocation by MCP clients
(e.g., Claude Desktop).

Key Features:
- Configuration Loading: Loads and validates configuration from CLI args, environment
  variables, and config files with comprehensive error handling
- Logging Setup: Initializes structured logging with configurable verbosity and audit trails
- Authentication: Establishes secure authentication sessions with LabArchives API
- Resource Management: Instantiates resource manager with scope enforcement and access control
- Protocol Handling: Manages MCP protocol session with comprehensive error handling
- Graceful Shutdown: Handles interrupts and EOF conditions for clean termination
- Audit Logging: Comprehensive logging of all operations for compliance and debugging

This module supports the following technical specification features:
- F-001: MCP Protocol Implementation - Initializes and launches MCP protocol server
- F-005: Authentication and Security Management - Handles secure credential loading
- F-006: CLI Interface and Configuration - Provides operational CLI entrypoint
- F-008: Comprehensive Audit Logging - Initializes structured logging for all events

All operations are designed to be secure, auditable, and production-ready with
comprehensive error handling and detailed logging for troubleshooting and compliance.
"""

import sys  # builtin - Access to stdin/stdout for protocol communication and process exit
import os  # builtin - Environment variable access and process management
import logging  # builtin - Logging of server events, errors, and diagnostics
import traceback  # builtin - Detailed error reporting and diagnostics for uncaught exceptions

# Internal imports for configuration management
from config import load_configuration

# Internal imports for logging setup
from logging_setup import setup_logging

# Internal imports for authentication management
from auth_manager import AuthenticationManager

# Internal imports for resource management
from resource_manager import ResourceManager

# Internal imports for MCP protocol handling
from mcp.protocol import MCPProtocolHandler

# Internal imports for exception handling
from exceptions import LabArchivesMCPException, MCPError

# =============================================================================
# Global Constants
# =============================================================================

# Logger name for the start command
START_LOGGER_NAME = "cli.commands.start"

# =============================================================================
# Main Start Command Implementation
# =============================================================================


def start_command(cli_args: dict) -> int:
    """
    CLI entrypoint for starting the LabArchives MCP Server.

    This function orchestrates the complete server startup process including configuration
    loading, logging setup, authentication, resource manager instantiation, and protocol
    server startup. It handles all startup errors, logs audit events, and provides user
    feedback. The function is designed for both interactive CLI use and process spawning
    by MCP clients.

    The startup process follows these steps:
    1. Load and validate configuration from CLI arguments, environment variables, and config files
    2. Initialize logging system with the configured settings
    3. Log server startup information and configuration summary
    4. Establish authentication session with LabArchives API
    5. Log authentication success and user context
    6. Instantiate ResourceManager with authenticated API client and scope configuration
    7. Instantiate MCPProtocolHandler with the resource manager
    8. Run the main protocol session loop with stdin/stdout communication
    9. Handle graceful shutdown on interrupts or EOF
    10. Provide comprehensive error handling and user feedback

    Args:
        cli_args (dict): Parsed CLI arguments from argparse or similar CLI parser.
                        Contains all configuration parameters passed via command line.

    Returns:
        int: Exit code indicating success (0) or failure (nonzero).
             - 0: Successful server startup and clean shutdown
             - 1: Configuration or initialization error
             - 2: Authentication failure
             - 3: Resource manager initialization failure
             - 4: Protocol handler initialization failure
             - 5: Runtime error during operation
             - 99: Unexpected fatal error

    Raises:
        SystemExit: On fatal errors that prevent server startup or operation.
                   All exceptions are caught and converted to appropriate exit codes.

    Example:
        >>> cli_args = {
        ...     'access_key_id': 'AKID123456',
        ...     'access_secret': 'secret123',
        ...     'log_level': 'INFO',
        ...     'verbose': False
        ... }
        >>> exit_code = start_command(cli_args)
        >>> # Server runs until interrupted or EOF
    """
    # Initialize logger with default configuration for early logging
    # This ensures we can log startup events even if configuration loading fails
    logger = logging.getLogger(START_LOGGER_NAME)

    try:
        # Step 1: Load and validate configuration using load_configuration, passing cli_args
        logger.info(
            "Loading and validating configuration",
            extra={
                "operation": "start_command",
                "step": "load_configuration",
                "cli_args_present": bool(cli_args),
            },
        )

        try:
            config = load_configuration(cli_args=cli_args)

            # Log successful configuration loading
            logger.info(
                "Configuration loaded successfully",
                extra={
                    "operation": "start_command",
                    "step": "load_configuration",
                    "server_name": config.server_name,
                    "server_version": config.server_version,
                    "api_base_url": config.authentication.api_base_url,
                    "has_scope": any(
                        [
                            config.scope.notebook_id,
                            config.scope.notebook_name,
                            config.scope.folder_path,
                        ]
                    ),
                },
            )

        except LabArchivesMCPException as e:
            logger.error(
                "Configuration loading failed",
                extra={
                    "operation": "start_command",
                    "step": "load_configuration",
                    "error": str(e),
                    "error_code": e.code,
                    "error_context": e.context,
                },
            )
            print(f"Configuration Error: {e}", file=sys.stderr)
            return 1

        # Step 2: Initialize logging using setup_logging with the loaded logging configuration
        logger.info(
            "Initializing logging system",
            extra={
                "operation": "start_command",
                "step": "setup_logging",
                "log_level": config.logging.log_level,
                "log_file": config.logging.log_file,
                "verbose": config.logging.verbose,
                "quiet": config.logging.quiet,
            },
        )

        try:
            main_logger, audit_logger = setup_logging(config.logging)

            # Switch to the properly configured logger
            logger = main_logger

            # Log successful logging initialization
            logger.info(
                "Logging system initialized successfully",
                extra={
                    "operation": "start_command",
                    "step": "setup_logging",
                    "log_level": config.logging.log_level,
                    "log_file": config.logging.log_file,
                },
            )

        except Exception as e:
            print(f"Logging initialization failed: {e}", file=sys.stderr)
            return 1

        # Step 3: Log server startup, version, and configuration summary
        logger.info(
            "Starting LabArchives MCP Server",
            extra={
                "operation": "start_command",
                "step": "server_startup",
                "server_name": config.server_name,
                "server_version": config.server_version,
                "api_base_url": config.authentication.api_base_url,
                "auth_method": ("user_token" if config.authentication.username else "api_key"),
                "scope_type": (
                    "notebook_id"
                    if config.scope.notebook_id
                    else (
                        "notebook_name"
                        if config.scope.notebook_name
                        else ("folder_path" if config.scope.folder_path else "unrestricted")
                    )
                ),
                "json_ld_enabled": config.output.json_ld_enabled,
                "structured_output": config.output.structured_output,
            },
        )

        # Step 4: Establish authentication/session using AuthenticationManager.authenticate
        logger.info(
            "Establishing authentication session",
            extra={
                "operation": "start_command",
                "step": "authentication",
                "api_base_url": config.authentication.api_base_url,
                "auth_method": ("user_token" if config.authentication.username else "api_key"),
            },
        )

        try:
            auth_manager = AuthenticationManager(config.authentication)
            session = auth_manager.authenticate()

            # Step 5: Log authentication success and user/session context
            logger.info(
                "Authentication successful",
                extra={
                    "operation": "start_command",
                    "step": "authentication",
                    "user_id": session.user_id,
                    "access_key_id": session.access_key_id,
                    "authenticated_at": session.authenticated_at.isoformat(),
                    "expires_at": (session.expires_at.isoformat() if session.expires_at else None),
                    "session_valid": session.is_valid(),
                },
            )

            # Log authentication success to audit logger
            audit_logger.info(
                "Authentication session established",
                extra={
                    "event": "authentication_success",
                    "user_id": session.user_id,
                    "access_key_id": session.access_key_id,
                    "authenticated_at": session.authenticated_at.isoformat(),
                },
            )

        except LabArchivesMCPException as e:
            logger.error(
                "Authentication failed",
                extra={
                    "operation": "start_command",
                    "step": "authentication",
                    "error": str(e),
                    "error_code": e.code,
                    "error_context": e.context,
                },
            )
            audit_logger.error(
                "Authentication failed",
                extra={
                    "event": "authentication_failure",
                    "error": str(e),
                    "error_code": e.code,
                },
            )
            print(f"Authentication Error: {e}", file=sys.stderr)
            return 2

        # Step 6: Instantiate the ResourceManager with the authenticated API client, scope config, and JSON-LD flag
        logger.info(
            "Initializing resource manager",
            extra={
                "operation": "start_command",
                "step": "resource_manager_init",
                "scope_config": {
                    "notebook_id": config.scope.notebook_id,
                    "notebook_name": config.scope.notebook_name,
                    "folder_path": config.scope.folder_path,
                },
                "json_ld_enabled": config.output.json_ld_enabled,
            },
        )

        try:
            # Create the ResourceManager with the authenticated API client and configuration
            resource_manager = ResourceManager(
                api_client=auth_manager.api_client,
                scope_config={
                    "notebook_id": config.scope.notebook_id,
                    "notebook_name": config.scope.notebook_name,
                    "folder_path": config.scope.folder_path,
                },
                jsonld_enabled=config.output.json_ld_enabled,
            )

            logger.info(
                "Resource manager initialized successfully",
                extra={
                    "operation": "start_command",
                    "step": "resource_manager_init",
                    "scope_configured": any(
                        [
                            config.scope.notebook_id,
                            config.scope.notebook_name,
                            config.scope.folder_path,
                        ]
                    ),
                },
            )

        except Exception as e:
            logger.error(
                "Resource manager initialization failed",
                extra={
                    "operation": "start_command",
                    "step": "resource_manager_init",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            print(f"Resource Manager Error: {e}", file=sys.stderr)
            return 3

        # Step 7: Instantiate the MCPProtocolHandler with the resource manager
        logger.info(
            "Initializing MCP protocol handler",
            extra={
                "operation": "start_command",
                "step": "protocol_handler_init",
                "server_name": config.server_name,
                "server_version": config.server_version,
            },
        )

        try:
            protocol_handler = MCPProtocolHandler(resource_manager)

            logger.info(
                "MCP protocol handler initialized successfully",
                extra={
                    "operation": "start_command",
                    "step": "protocol_handler_init",
                    "protocol_version": "2024-11-05",
                },
            )

        except Exception as e:
            logger.error(
                "MCP protocol handler initialization failed",
                extra={
                    "operation": "start_command",
                    "step": "protocol_handler_init",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            print(f"Protocol Handler Error: {e}", file=sys.stderr)
            return 4

        # Step 8: Run the main protocol session loop using MCPProtocolHandler.run_session, passing sys.stdin and sys.stdout
        logger.info(
            "Starting MCP protocol session",
            extra={
                "operation": "start_command",
                "step": "protocol_session",
                "server_ready": True,
            },
        )

        # Log to audit logger that the server is now ready
        audit_logger.info(
            "MCP server ready for client connections",
            extra={
                "event": "server_ready",
                "server_name": config.server_name,
                "server_version": config.server_version,
                "user_id": session.user_id,
            },
        )

        try:
            # Run the main protocol session loop
            protocol_handler.run_session(sys.stdin, sys.stdout)

            # Log normal session completion
            logger.info(
                "MCP protocol session completed",
                extra={
                    "operation": "start_command",
                    "step": "protocol_session",
                    "completion_reason": "normal",
                },
            )

            audit_logger.info(
                "MCP server session completed normally",
                extra={
                    "event": "session_completed",
                    "user_id": session.user_id,
                    "completion_reason": "normal",
                },
            )

            return 0

        except (KeyboardInterrupt, EOFError) as e:
            # Step 9: Handle KeyboardInterrupt or EOFError for graceful shutdown
            interruption_type = "keyboard_interrupt" if isinstance(e, KeyboardInterrupt) else "eof"

            logger.info(
                f"MCP protocol session interrupted by {interruption_type}",
                extra={
                    "operation": "start_command",
                    "step": "protocol_session",
                    "interruption_type": interruption_type,
                },
            )

            audit_logger.info(
                "MCP server session interrupted",
                extra={
                    "event": "session_interrupted",
                    "user_id": session.user_id,
                    "interruption_type": interruption_type,
                },
            )

            print(
                f"Server shutting down gracefully ({interruption_type})",
                file=sys.stderr,
            )
            return 0

        except Exception as e:
            logger.error(
                "Runtime error during protocol session",
                extra={
                    "operation": "start_command",
                    "step": "protocol_session",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

            audit_logger.error(
                "MCP server runtime error",
                extra={
                    "event": "runtime_error",
                    "user_id": session.user_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

            print(f"Runtime Error: {e}", file=sys.stderr)
            return 5

    except (LabArchivesMCPException, MCPError) as e:
        # Step 10: On any LabArchivesMCPException or MCPError, log the error, print a user-friendly message, and exit with a nonzero code
        logger.error(
            "MCP server startup failed",
            extra={
                "operation": "start_command",
                "error": str(e),
                "error_code": getattr(e, 'code', None),
                "error_context": getattr(e, 'context', None),
                "error_type": type(e).__name__,
            },
        )

        # Print user-friendly error message
        print(f"Server Startup Error: {e}", file=sys.stderr)

        # Return appropriate exit code based on error type
        if isinstance(e, MCPError):
            return 4  # Protocol handler error
        else:
            return 1  # General MCP error

    except Exception as e:
        # Step 11: On any other uncaught Exception, log the full traceback, print a fatal error message, and exit with a nonzero code
        logger.error(
            "Unexpected fatal error during server startup",
            extra={
                "operation": "start_command",
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc(),
            },
        )

        # Print fatal error message with traceback
        print(f"Fatal Error: {e}", file=sys.stderr)
        print("Full traceback:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

        return 99  # Unexpected fatal error
