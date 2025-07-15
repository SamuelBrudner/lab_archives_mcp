#!/usr/bin/env python3
"""
LabArchives MCP Server - Main CLI Entry Point

This module serves as the main entry point for the LabArchives MCP Server CLI application.
It orchestrates the complete lifecycle of the server from startup to shutdown, handling
CLI argument parsing, configuration loading, logging setup, authentication, MCP server
startup, and graceful shutdown.

This module implements the following technical specification features:
- F-006: CLI Interface and Configuration - CLI argument parsing and configuration loading
- F-005: Authentication and Security Management - Secure credential handling and authentication
- F-001: MCP Protocol Implementation - MCP server initialization and lifecycle management
- F-008: Comprehensive Audit Logging - Structured logging and audit trail generation
- F-003/F-004: Resource Discovery and Content Retrieval - Resource manager coordination
- F-002: LabArchives API Integration - API client coordination and error handling

The main function coordinates all core components, ensures protocol compliance, secure
credential handling, and robust error management while providing user feedback and
status reporting for operational transparency.
"""

import sys  # builtin - System parameters and functions for exit codes and argv access
import signal  # builtin - Signal handling for graceful shutdown (SIGINT, SIGTERM)
import asyncio  # builtin - Async event loop for MCP server operations
import logging  # builtin - Standard logging interface for error and status reporting
import os  # builtin - Operating system interface for environment variables and process management

# Internal imports - CLI argument parsing functionality
from src.cli.cli_parser import parse_and_dispatch_cli

# Internal imports - Configuration management and loading
from src.cli.config import load_configuration

# Internal imports - Logging setup and configuration
from src.cli.logging_setup import setup_logging

# Internal imports - Authentication management for LabArchives API
from src.cli.auth_manager import AuthenticationManager

# Internal imports - Resource management for MCP protocol handlers
from src.cli.resource_manager import ResourceManager

# Internal imports - MCP server implementation using FastMCP
from src.cli.mcp_server import main as mcp_server_main

# Internal imports - Exception handling for structured error management
from src.cli.exceptions import (
    ConfigurationError,
    AuthenticationError,
    StartupError
)

# Internal imports - Version information for display and logging
from src.cli.version import __version__

# =============================================================================
# Global Variables
# =============================================================================

# Main application logger - initialized during startup
logger = logging.getLogger('labarchives_mcp.main')

# Global server instance for signal handling
server_instance = None

# =============================================================================
# Signal Handling Functions
# =============================================================================

def shutdown_handler(signum: int, frame) -> None:
    """
    Handles OS signals for graceful shutdown of the MCP server.
    
    This function provides a clean shutdown mechanism when the server receives
    termination signals (SIGINT, SIGTERM). It logs the shutdown event, performs
    necessary cleanup operations, and exits the process with appropriate status code.
    
    The function ensures that:
    - The shutdown signal is properly logged for audit purposes
    - Any active server operations are cleanly terminated
    - Log buffers are flushed to prevent data loss
    - The process exits with a success code to indicate clean shutdown
    
    Args:
        signum (int): The signal number received (e.g., 2 for SIGINT, 15 for SIGTERM)
        frame: The current stack frame (required by signal handler interface but not used)
    
    Returns:
        None: This function performs cleanup and exits the process
    
    Example:
        >>> # Signal handler is registered during server startup
        >>> signal.signal(signal.SIGINT, shutdown_handler)
        >>> signal.signal(signal.SIGTERM, shutdown_handler)
    """
    global server_instance
    
    # Map signal numbers to human-readable names for logging
    signal_names = {
        signal.SIGINT: "SIGINT (Ctrl+C)",
        signal.SIGTERM: "SIGTERM (Termination Request)"
    }
    
    signal_name = signal_names.get(signum, f"Unknown Signal ({signum})")
    
    # Log the shutdown signal receipt
    logger.info(f"Received shutdown signal: {signal_name}", extra={
        'signal_number': signum,
        'signal_name': signal_name,
        'operation': 'shutdown_handler',
        'event': 'shutdown_initiated'
    })
    
    # Perform server cleanup if server instance exists
    if server_instance:
        try:
            logger.info("Shutting down MCP server instance", extra={
                'operation': 'shutdown_handler',
                'event': 'server_shutdown'
            })
            
            # Perform any necessary server cleanup
            # Note: FastMCP handles most cleanup automatically
            server_instance = None
            
        except Exception as e:
            logger.error(f"Error during server shutdown: {str(e)}", extra={
                'operation': 'shutdown_handler',
                'error': str(e),
                'error_type': type(e).__name__
            })
    
    # Flush all log handlers to ensure messages are written
    for handler in logger.handlers:
        try:
            handler.flush()
        except Exception:
            # Ignore errors during log flushing to prevent infinite loops
            pass
    
    # Log successful shutdown completion
    logger.info("Graceful shutdown completed", extra={
        'operation': 'shutdown_handler',
        'event': 'shutdown_completed'
    })
    
    # Exit the process with success code
    sys.exit(0)


# =============================================================================
# Main Entry Point Function
# =============================================================================

def main() -> None:
    """
    Main entry point for the CLI application.
    
    This function orchestrates the complete lifecycle of the LabArchives MCP Server,
    from initialization through operation to shutdown. It handles all aspects of
    server startup including argument parsing, configuration loading, logging setup,
    authentication, resource management, and MCP server initialization.
    
    The function implements a comprehensive startup sequence:
    1. Parse CLI arguments using parse_and_dispatch_cli() from cli_parser
    2. Handle special cases like --help and --version display
    3. Load and validate configuration using load_configuration() from config
    4. Initialize logging using setup_logging() from logging_setup
    5. Log startup banner with version and configuration summary
    6. Initialize AuthenticationManager with loaded configuration
    7. Authenticate with LabArchives API using AuthenticationManager
    8. Initialize ResourceManager with authenticated session context
    9. Launch MCP server with resource handlers
    10. Register signal handlers for graceful shutdown
    11. Start the MCP server event loop using asyncio
    12. Handle all errors with appropriate logging and exit codes
    
    Error Handling:
    - ConfigurationError: Invalid or missing configuration parameters
    - AuthenticationError: Failed authentication with LabArchives API
    - StartupError: Server initialization or startup failures
    - KeyboardInterrupt: User interruption (Ctrl+C)
    - General exceptions: Unexpected errors with full context logging
    
    Exit Codes:
    - 0: Success - server started and ran successfully
    - 1: Configuration error - invalid or missing configuration
    - 2: Authentication error - failed to authenticate with LabArchives
    - 3: Startup error - server initialization failed
    - 130: User interruption - KeyboardInterrupt received
    
    Returns:
        None: Exits the process with appropriate status code
    
    Example:
        >>> # Called from console_scripts entry point
        >>> main()
        # Server starts and runs until interrupted or error occurs
    """
    global logger, server_instance
    
    # Initialize exit code for error handling
    exit_code = 0
    
    try:
        # Step 1: Parse CLI arguments using parse_and_dispatch_cli() from cli_parser
        logger.info("Starting LabArchives MCP Server CLI", extra={
            'operation': 'main',
            'event': 'startup_initiated',
            'version': __version__
        })
        
        try:
            args = parse_and_dispatch_cli()
            
            # Log successful argument parsing
            logger.debug("CLI arguments parsed successfully", extra={
                'operation': 'main',
                'event': 'args_parsed',
                'has_config_file': hasattr(args, 'config_file') and args.config_file is not None,
                'verbose': getattr(args, 'verbose', False),
                'quiet': getattr(args, 'quiet', False)
            })
            
        except SystemExit as e:
            # Handle --help or --version which cause SystemExit
            if e.code == 0:
                # Help or version displayed successfully
                return
            else:
                # Argument parsing error
                logger.error("CLI argument parsing failed", extra={
                    'operation': 'main',
                    'event': 'args_parse_error',
                    'exit_code': e.code
                })
                sys.exit(e.code)
                
        except Exception as e:
            logger.error(f"Unexpected error parsing CLI arguments: {str(e)}", extra={
                'operation': 'main',
                'event': 'args_parse_error',
                'error': str(e),
                'error_type': type(e).__name__
            })
            sys.exit(1)
        
        # Step 2: Handle special cases (already handled by parse_and_dispatch_cli)
        # --help and --version are handled by argparse and cause SystemExit
        
        # Check if authenticate command - handle separately
        if hasattr(args, 'command') and args.command == 'authenticate':
            from src.cli.commands.authenticate import authenticate_command
            try:
                exit_code = authenticate_command(args)
                sys.exit(exit_code)
            except Exception as e:
                print(f"Authentication check failed: {str(e)}", file=sys.stderr)
                sys.exit(2)
        
        # Step 3: Load and validate configuration using load_configuration() from config
        logger.info("Loading server configuration", extra={
            'operation': 'main',
            'event': 'config_loading'
        })
        
        try:
            # Convert argparse Namespace to dictionary for configuration loading
            cli_args_dict = vars(args)
            
            # Load configuration from all sources (CLI, env, file, defaults)
            config = load_configuration(
                cli_args=cli_args_dict,
                config_file_path=getattr(args, 'config_file', None)
            )
            
            logger.info("Configuration loaded successfully", extra={
                'operation': 'main',
                'event': 'config_loaded',
                'api_base_url': config.authentication.api_base_url,
                'has_scope_restriction': any([
                    config.scope.notebook_id,
                    config.scope.notebook_name,
                    config.scope.folder_path
                ]),
                'json_ld_enabled': config.output.json_ld_enabled
            })
            
        except Exception as e:
            logger.error(f"Configuration loading failed: {str(e)}", extra={
                'operation': 'main',
                'event': 'config_load_error',
                'error': str(e),
                'error_type': type(e).__name__
            })
            raise ConfigurationError(f"Failed to load configuration: {str(e)}")
        
        # Step 4: Initialize logging using setup_logging() from logging_setup
        logger.info("Initializing logging system", extra={
            'operation': 'main',
            'event': 'logging_init'
        })
        
        try:
            # Set up logging with configuration
            main_logger, audit_logger = setup_logging(config.logging)
            
            # Update the global logger reference
            logger = main_logger
            
            logger.info("Logging system initialized successfully", extra={
                'operation': 'main',
                'event': 'logging_initialized',
                'log_level': config.logging.log_level,
                'log_file': config.logging.log_file,
                'verbose': config.logging.verbose,
                'quiet': config.logging.quiet
            })
            
            # Log to audit logger
            audit_logger.info("LabArchives MCP Server startup initiated", extra={
                'event': 'server_startup',
                'version': __version__,
                'config_source': 'cli_args' if cli_args_dict else 'defaults'
            })
            
        except Exception as e:
            # Use print since logging might not be working
            print(f"ERROR: Failed to initialize logging: {str(e)}", file=sys.stderr)
            raise StartupError(f"Failed to initialize logging: {str(e)}")
        
        # Step 5: Log startup banner with version and configuration summary
        logger.info("=" * 60)
        logger.info(f"LabArchives MCP Server v{__version__}")
        logger.info("=" * 60)
        logger.info("Configuration Summary:")
        logger.info(f"  API Base URL: {config.authentication.api_base_url}")
        logger.info(f"  Authentication: {'Token' if config.authentication.username else 'API Key'}")
        logger.info(f"  Scope Restriction: {'Yes' if any([config.scope.notebook_id, config.scope.notebook_name, config.scope.folder_path]) else 'No'}")
        logger.info(f"  JSON-LD Enabled: {config.output.json_ld_enabled}")
        logger.info(f"  Log Level: {config.logging.log_level}")
        logger.info("=" * 60)
        
        # Step 6: Initialize AuthenticationManager with loaded configuration
        logger.info("Initializing authentication manager", extra={
            'operation': 'main',
            'event': 'auth_manager_init'
        })
        
        try:
            auth_manager = AuthenticationManager(config.authentication)
            
            logger.info("Authentication manager initialized successfully", extra={
                'operation': 'main',
                'event': 'auth_manager_initialized',
                'api_base_url': config.authentication.api_base_url,
                'has_username': bool(config.authentication.username)
            })
            
        except Exception as e:
            logger.error(f"Failed to initialize authentication manager: {str(e)}", extra={
                'operation': 'main',
                'event': 'auth_manager_init_error',
                'error': str(e),
                'error_type': type(e).__name__
            })
            raise StartupError(f"Failed to initialize authentication manager: {str(e)}")
        
        # Step 7: Authenticate with LabArchives API using AuthenticationManager
        logger.info("Authenticating with LabArchives API", extra={
            'operation': 'main',
            'event': 'authentication_start'
        })
        
        try:
            # Perform authentication
            auth_session = auth_manager.authenticate()
            
            logger.info("Authentication successful", extra={
                'operation': 'main',
                'event': 'authentication_success',
                'user_id': auth_session.user_id,
                'authenticated_at': auth_session.authenticated_at.isoformat(),
                'expires_at': auth_session.expires_at.isoformat() if auth_session.expires_at else None
            })
            
            # Log to audit logger
            audit_logger.info("LabArchives API authentication successful", extra={
                'event': 'authentication_success',
                'user_id': auth_session.user_id,
                'auth_method': 'user_token' if config.authentication.username else 'api_key'
            })
            
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}", extra={
                'operation': 'main',
                'event': 'authentication_error',
                'error': str(e),
                'error_type': type(e).__name__
            })
            raise AuthenticationError(f"Failed to authenticate with LabArchives API: {str(e)}")
        
        # Step 8: Initialize ResourceManager with authenticated session context
        logger.info("Initializing resource manager", extra={
            'operation': 'main',
            'event': 'resource_manager_init'
        })
        
        try:
            # Create scope configuration dictionary
            scope_config = {
                'notebook_id': config.scope.notebook_id,
                'notebook_name': config.scope.notebook_name,
                'folder_path': config.scope.folder_path
            }
            
            # Initialize resource manager with authenticated API client
            resource_manager = ResourceManager(
                api_client=auth_manager.api_client,
                scope_config=scope_config,
                jsonld_enabled=config.output.json_ld_enabled
            )
            
            logger.info("Resource manager initialized successfully", extra={
                'operation': 'main',
                'event': 'resource_manager_initialized',
                'scope_config': scope_config,
                'json_ld_enabled': config.output.json_ld_enabled
            })
            
        except Exception as e:
            logger.error(f"Failed to initialize resource manager: {str(e)}", extra={
                'operation': 'main',
                'event': 'resource_manager_init_error',
                'error': str(e),
                'error_type': type(e).__name__
            })
            raise StartupError(f"Failed to initialize resource manager: {str(e)}")
        
        # Step 9: Launch MCP server with resource handlers
        logger.info("Initializing MCP server", extra={
            'operation': 'main',
            'event': 'mcp_server_init'
        })
        
        try:
            # Launch the MCP server
            exit_code = mcp_server_main()
            
            logger.info("MCP server completed", extra={
                'operation': 'main',
                'event': 'mcp_server_completed',
                'exit_code': exit_code
            })
            
            return exit_code
            
        except Exception as e:
            logger.error(f"Failed to run MCP server: {str(e)}", extra={
                'operation': 'main',
                'event': 'mcp_server_error',
                'error': str(e),
                'error_type': type(e).__name__
            })
            raise StartupError(f"Failed to run MCP server: {str(e)}")
        
        # Step 10: Register signal handlers for graceful shutdown
        logger.info("Registering signal handlers for graceful shutdown", extra={
            'operation': 'main',
            'event': 'signal_handlers_init'
        })
        
        try:
            # Register signal handlers for SIGINT and SIGTERM
            signal.signal(signal.SIGINT, shutdown_handler)
            signal.signal(signal.SIGTERM, shutdown_handler)
            
            logger.info("Signal handlers registered successfully", extra={
                'operation': 'main',
                'event': 'signal_handlers_registered',
                'signals': ['SIGINT', 'SIGTERM']
            })
            
        except Exception as e:
            logger.error(f"Failed to register signal handlers: {str(e)}", extra={
                'operation': 'main',
                'event': 'signal_handlers_error',
                'error': str(e),
                'error_type': type(e).__name__
            })
            # Non-fatal error - continue without signal handlers
            logger.warning("Continuing without signal handlers - manual shutdown required")
        
        # Step 11: Start the MCP server event loop using asyncio
        logger.info("Starting MCP server event loop", extra={
            'operation': 'main',
            'event': 'server_start'
        })
        
        try:
            # Log server ready status
            logger.info("LabArchives MCP Server is ready and listening for connections", extra={
                'operation': 'main',
                'event': 'server_ready',
                'server_name': config.server_name,
                'server_version': config.server_version,
                'user_id': auth_session.user_id
            })
            
            # Log to audit logger
            audit_logger.info("MCP server started successfully", extra={
                'event': 'server_start',
                'server_name': config.server_name,
                'server_version': config.server_version,
                'user_id': auth_session.user_id
            })
            
            # Start the server event loop
            # This is a blocking call that runs until the server is stopped
            asyncio.run(server_instance.run())
            
            # If we reach here, the server stopped normally
            logger.info("MCP server stopped normally", extra={
                'operation': 'main',
                'event': 'server_stopped'
            })
            
        except Exception as e:
            logger.error(f"MCP server runtime error: {str(e)}", extra={
                'operation': 'main',
                'event': 'server_runtime_error',
                'error': str(e),
                'error_type': type(e).__name__
            })
            raise StartupError(f"MCP server runtime error: {str(e)}")
        
        # Step 12: Normal shutdown (if we reach here)
        logger.info("LabArchives MCP Server shutdown completed successfully", extra={
            'operation': 'main',
            'event': 'shutdown_completed'
        })
        
        # Log to audit logger
        audit_logger.info("Server shutdown completed", extra={
            'event': 'server_shutdown',
            'reason': 'normal_termination'
        })
        
    except ConfigurationError as e:
        # Handle configuration-related errors
        logger.error(f"Configuration Error: {str(e)}", extra={
            'operation': 'main',
            'event': 'configuration_error',
            'error': str(e),
            'error_type': 'ConfigurationError'
        })
        print(f"Configuration Error: {str(e)}", file=sys.stderr)
        exit_code = 1
        
    except AuthenticationError as e:
        # Handle authentication-related errors
        logger.error(f"Authentication Error: {str(e)}", extra={
            'operation': 'main',
            'event': 'authentication_error',
            'error': str(e),
            'error_type': 'AuthenticationError'
        })
        print(f"Authentication Error: {str(e)}", file=sys.stderr)
        exit_code = 2
        
    except StartupError as e:
        # Handle server startup errors
        logger.error(f"Startup Error: {str(e)}", extra={
            'operation': 'main',
            'event': 'startup_error',
            'error': str(e),
            'error_type': 'StartupError'
        })
        print(f"Startup Error: {str(e)}", file=sys.stderr)
        exit_code = 3
        
    except KeyboardInterrupt:
        # Handle user interruption (Ctrl+C)
        logger.info("Server interrupted by user (Ctrl+C)", extra={
            'operation': 'main',
            'event': 'user_interrupt'
        })
        print("\nServer interrupted by user", file=sys.stderr)
        exit_code = 130
        
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error: {str(e)}", extra={
            'operation': 'main',
            'event': 'unexpected_error',
            'error': str(e),
            'error_type': type(e).__name__
        })
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        exit_code = 1
        
    finally:
        # Ensure cleanup and proper exit
        if logger:
            logger.info(f"LabArchives MCP Server process terminating with exit code {exit_code}", extra={
                'operation': 'main',
                'event': 'process_terminating',
                'exit_code': exit_code
            })
            
            # Flush all log handlers to ensure final messages are written
            for handler in logger.handlers:
                try:
                    handler.flush()
                except Exception:
                    # Ignore errors during final log flushing
                    pass
        
        # Exit with appropriate code
        sys.exit(exit_code)


# =============================================================================
# Module Entry Point
# =============================================================================

if __name__ == "__main__":
    main()