"""
LabArchives MCP Server - Main CLI Argument Parser

This module defines and implements the main command-line argument parser for the 
LabArchives MCP Server CLI. It serves as the canonical entry point for parsing and 
dispatching CLI commands, providing a comprehensive interface for server configuration, 
authentication, and operational control.

Key Features:
- Comprehensive argument parsing with global options and subcommands
- Integration with configuration, logging, and validation subsystems
- Support for environment variable integration and precedence rules
- Extensible subcommand architecture for future enhancements
- Robust error handling with user-friendly feedback
- Comprehensive audit logging for all CLI operations

This module implements the following technical specification features:
- F-006: CLI Interface and Configuration - Provides robust, user-friendly, and 
  extensible command-line interface for configuring, launching, and managing the 
  LabArchives MCP Server
- F-008: Comprehensive Audit Logging - Ensures all CLI parsing errors, invalid 
  arguments, and command invocations are logged in structured, auditable format
- F-005: Authentication and Security Management - Integrates CLI argument parsing 
  with secure credential handling and validation
- Centralized Configuration Management - Ensures CLI arguments take precedence over 
  environment variables and config files
- Semantic Versioning and Version Management - Implements --version flag with 
  canonical version display

All CLI operations are designed to be secure, auditable, and production-ready with 
comprehensive error handling and detailed logging for troubleshooting and compliance.
"""

import argparse  # builtin - Provides the ArgumentParser, subparsers, and CLI argument schema enforcement
import os  # builtin - Used for environment variable access and path expansion for config file arguments
import sys  # builtin - Supports CLI exit codes, error output, and process termination

# Internal imports for configuration loading and management
from src.cli.config import load_configuration

# Internal imports for logging setup and audit trail
from src.cli.logging_setup import setup_logging

# Internal imports for exception handling and error reporting
from src.cli.exceptions import LabArchivesMCPException

# Internal imports for subcommand registration and handling
from src.cli.commands.config_cmd import add_config_subparser
from src.cli.commands.authenticate import authenticate_command
from src.cli.commands.start import start_command

# Internal imports for version information
from src.cli.constants import MCP_SERVER_VERSION

# Internal imports for utility functions
from src.cli.utils import sanitize_argv

# =============================================================================
# Global Constants and Configuration
# =============================================================================

# Main command description for CLI help and documentation
# Provides comprehensive overview of the server's purpose and capabilities
MAIN_COMMAND_DESCRIPTION = """LabArchives MCP Server - Read-only access to electronic lab notebooks via MCP protocol.

For help, use --help or see documentation at https://help.labarchives.com/article/using-the-labarchives-mcp-server"""

# Default configuration file name for consistent user experience
# Can be overridden via --config-file argument
DEFAULT_CONFIG_FILE = "labarchives_mcp_config.json"

# =============================================================================
# Main CLI Parser Construction
# =============================================================================

def build_cli_parser() -> argparse.ArgumentParser:
    """
    Constructs and returns the top-level ArgumentParser for the CLI, registering all global options and subcommands.
    
    This function creates the main CLI parser with comprehensive argument definitions, 
    including global options that apply to all subcommands and the subcommand structure 
    for start, authenticate, and config operations. The parser supports environment 
    variable integration, dynamic help text, and extensibility for future subcommands.
    
    The parser architecture follows these principles:
    - Global options are available to all subcommands
    - Subcommands provide specialized functionality with their own arguments
    - Help text is comprehensive and user-friendly
    - Version information is easily accessible
    - Error handling is built into the parser structure
    
    Global Options:
    - --config-file: Path to JSON configuration file (supports ~ expansion)
    - --log-file: Path to log file for output (supports ~ expansion)
    - --verbose: Enable verbose logging and output
    - --quiet: Suppress non-error output
    - --version: Display version information and exit
    
    Subcommands:
    - start: Launch the MCP server process
    - authenticate: Validate credentials and test authentication
    - config: Configuration management (show, validate, reload)
    
    Returns:
        argparse.ArgumentParser: The fully constructed CLI argument parser with all
            global options, subcommands, and help text configured. Ready for argument
            parsing and command dispatch.
    
    Example:
        >>> parser = build_cli_parser()
        >>> args = parser.parse_args(['start', '--verbose'])
        >>> print(args.command)  # 'start'
        >>> print(args.verbose)  # True
    """
    try:
        # Create the main ArgumentParser with comprehensive description and formatting
        parser = argparse.ArgumentParser(
            prog='labarchives-mcp',
            description=MAIN_COMMAND_DESCRIPTION,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            add_help=True
        )
        
        # Add global options that apply to all subcommands
        # These options are processed before subcommand-specific arguments
        
        # Configuration file option with default value and help text
        parser.add_argument(
            '--config-file',
            type=str,
            default=None,
            help=f'Path to JSON configuration file (default: {DEFAULT_CONFIG_FILE}). '
                 'Supports ~ expansion for home directory. CLI arguments take precedence '
                 'over configuration file values.'
        )
        
        # Log file option for output redirection
        parser.add_argument(
            '--log-file',
            type=str,
            default=None,
            help='Path to log file for output. If not specified, logs to console. '
                 'Supports ~ expansion for home directory. Log rotation is enabled '
                 'with 10MB max size and 5 backup files.'
        )
        
        # Verbose mode for enhanced logging and output
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose logging and output. Sets log level to DEBUG and '
                 'provides detailed information about all operations. Useful for '
                 'troubleshooting and development.'
        )
        
        # Quiet mode for suppressing non-error output
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Suppress non-error output. Sets log level to WARNING and reduces '
                 'console output to essential information only. Useful for '
                 'automated scripts and production environments.'
        )
        
        # Version flag for displaying version information
        parser.add_argument(
            '--version',
            action='version',
            version=f'%(prog)s {MCP_SERVER_VERSION}',
            help='Display version information and exit. Shows the current version '
                 'of the LabArchives MCP Server CLI.'
        )
        
        # Create subparsers for different commands
        # This enables the command structure: labarchives-mcp <command> [options]
        subparsers = parser.add_subparsers(
            dest='command',
            title='Available Commands',
            description='Choose a command to execute. Use <command> --help for '
                       'command-specific help and options.',
            help='Command to execute'
        )
        
        # Register the 'start' subcommand for launching the MCP server
        start_parser = subparsers.add_parser(
            'start',
            help='Launch the LabArchives MCP Server',
            description='Starts the LabArchives MCP Server process, establishing '
                       'authentication with LabArchives API and beginning MCP protocol '
                       'communication with clients. The server runs until interrupted '
                       'or the client disconnects.'
        )
        
        # Add start-specific arguments
        start_parser.add_argument(
            '-k', '--access-key-id',
            type=str,
            help='LabArchives API access key ID. Can also be set via '
                 'LABARCHIVES_AKID environment variable. Required for authentication.'
        )
        
        start_parser.add_argument(
            '-p', '--access-secret',
            type=str,
            help='LabArchives API access secret or user token. Can also be set via '
                 'LABARCHIVES_SECRET environment variable. Required for authentication.'
        )
        
        start_parser.add_argument(
            '--username',
            type=str,
            help='Username for token-based authentication (SSO users). Can also be '
                 'set via LABARCHIVES_USER environment variable. Required when using '
                 'temporary user tokens instead of permanent API keys.'
        )
        
        start_parser.add_argument(
            '--api-base-url',
            type=str,
            help='LabArchives API base URL. Defaults to https://api.labarchives.com/api. '
                 'Use https://auapi.labarchives.com/api for Australian deployments. '
                 'Can also be set via LABARCHIVES_API_BASE environment variable.'
        )
        
        start_parser.add_argument(
            '--notebook-id',
            type=str,
            help='Limit access to a specific notebook by ID. When set, only the '
                 'specified notebook will be accessible through the MCP interface. '
                 'Mutually exclusive with --notebook-name and --folder-path.'
        )
        
        start_parser.add_argument(
            '--notebook-name',
            type=str,
            help='Limit access to a specific notebook by name. When set, only the '
                 'specified notebook will be accessible through the MCP interface. '
                 'Mutually exclusive with --notebook-id and --folder-path.'
        )
        
        start_parser.add_argument(
            '--folder-path',
            type=str,
            help='Limit access to a specific folder path. When set, only resources '
                 'within the specified folder will be accessible through the MCP '
                 'interface. Mutually exclusive with --notebook-id and --notebook-name.'
        )
        
        start_parser.add_argument(
            '--json-ld',
            action='store_true',
            help='Enable JSON-LD output format for enhanced semantic context. '
                 'Provides richer metadata for AI processing but increases response size.'
        )
        
        # Set the handler function for the start command
        start_parser.set_defaults(func=start_command)
        
        # Register the 'authenticate' subcommand for credential validation
        auth_parser = subparsers.add_parser(
            'authenticate',
            help='Validate credentials and test authentication',
            description='Tests authentication with the LabArchives API using the '
                       'provided credentials. Validates API key/secret or username/token '
                       'combinations and reports authentication status. Useful for '
                       'verifying configuration before starting the server.'
        )
        
        # Add authenticate-specific arguments (same as start for credential validation)
        auth_parser.add_argument(
            '-k', '--access-key-id',
            type=str,
            help='LabArchives API access key ID. Can also be set via '
                 'LABARCHIVES_AKID environment variable. Required for authentication.'
        )
        
        auth_parser.add_argument(
            '-p', '--access-secret',
            type=str,
            help='LabArchives API access secret or user token. Can also be set via '
                 'LABARCHIVES_SECRET environment variable. Required for authentication.'
        )
        
        auth_parser.add_argument(
            '--username',
            type=str,
            help='Username for token-based authentication (SSO users). Can also be '
                 'set via LABARCHIVES_USER environment variable. Required when using '
                 'temporary user tokens instead of permanent API keys.'
        )
        
        auth_parser.add_argument(
            '--api-base-url',
            type=str,
            help='LabArchives API base URL. Defaults to https://api.labarchives.com/api. '
                 'Use https://auapi.labarchives.com/api for Australian deployments. '
                 'Can also be set via LABARCHIVES_API_BASE environment variable.'
        )
        
        # Set the handler function for the authenticate command
        auth_parser.set_defaults(func=authenticate_command)
        
        # Register the 'config' subparser and its subcommands using add_config_subparser
        # This adds the config show, validate, and reload subcommands
        config_parser = subparsers.add_parser(
            'config',
            help='Configuration management operations',
            description='Manage server configuration including displaying current settings, '
                       'validating configuration files, and reloading configuration at runtime.'
        )
        
        # Add config subcommands using the dedicated function
        add_config_subparser(config_parser)
        
        # Return the fully constructed parser
        return parser
        
    except Exception as e:
        # Handle any unexpected errors during parser construction
        raise LabArchivesMCPException(
            message=f"Failed to build CLI parser: {str(e)}",
            code=9001,
            context={
                "operation": "build_cli_parser",
                "error_type": type(e).__name__,
                "error_details": str(e)
            }
        )


def parse_and_dispatch_cli(argv: list[str] = None) -> int:
    """
    Parses CLI arguments, dispatches to the appropriate subcommand handler, and manages error handling, logging, and exit codes.
    
    This function serves as the main entry point for CLI processing, orchestrating 
    the complete command lifecycle from argument parsing through command execution 
    and error handling. It integrates with configuration loading, logging setup, 
    and audit trail generation to provide comprehensive operational support.
    
    The function follows this processing flow:
    1. Build the CLI parser using build_cli_parser()
    2. Parse arguments from argv or sys.argv[1:]
    3. Handle special cases like --version and missing subcommands
    4. Set up logging using the parsed configuration
    5. Dispatch to the appropriate subcommand handler
    6. Handle all errors with appropriate logging and user feedback
    7. Return appropriate exit codes for shell integration
    
    Error Handling:
    - LabArchivesMCPException: Application-specific errors with structured logging
    - argparse.ArgumentError: CLI argument parsing errors with user guidance
    - General exceptions: Unexpected errors with comprehensive logging
    - KeyboardInterrupt: Graceful shutdown on user interruption
    
    Exit Codes:
    - 0: Success - command completed successfully
    - 1: General error - configuration, validation, or execution failure
    - 2: Authentication error - credential or permission issues
    - 3: Protocol error - MCP protocol or communication issues
    - 130: User interruption - KeyboardInterrupt or similar
    
    Args:
        argv (list[str], optional): Command line arguments to parse. If None, 
            uses sys.argv[1:]. Allows for programmatic invocation with custom 
            arguments for testing and integration purposes.
    
    Returns:
        int: Exit code indicating success (0) or failure (nonzero). The exit code 
            provides information about the type of failure for shell scripting 
            and process management.
    
    Example:
        >>> # Parse and execute CLI command
        >>> exit_code = parse_and_dispatch_cli(['start', '--verbose'])
        >>> print(f"Command completed with exit code: {exit_code}")
        
        >>> # Handle authentication command
        >>> exit_code = parse_and_dispatch_cli(['authenticate', '--access-key-id', 'AKID123'])
        >>> if exit_code == 0:
        ...     print("Authentication successful")
    """
    # Initialize logger for CLI operations
    logger = None
    
    try:
        # Step 1: Build the CLI parser using build_cli_parser
        try:
            parser = build_cli_parser()
        except LabArchivesMCPException as e:
            # Handle parser construction errors
            print(f"CLI Parser Error: {e.message}", file=sys.stderr)
            return 1
        except Exception as e:
            # Handle unexpected parser construction errors
            print(f"Unexpected error building CLI parser: {str(e)}", file=sys.stderr)
            return 1
        
        # Step 2: Parse arguments from argv or sys.argv[1:]
        try:
            if argv is None:
                argv = sys.argv[1:]
            
            args = parser.parse_args(argv)
            
        except SystemExit as e:
            # Handle argparse SystemExit (help, version, or parse errors)
            # argparse calls sys.exit() directly, so we catch SystemExit
            return e.code if e.code is not None else 0
        except Exception as e:
            # Handle unexpected parsing errors
            print(f"Argument parsing error: {str(e)}", file=sys.stderr)
            return 1
        
        # Step 3: Handle special cases
        
        # If no subcommand is provided, print help and exit 1
        if not hasattr(args, 'command') or args.command is None:
            parser.print_help()
            print("\nError: No command specified. Use --help for usage information.", file=sys.stderr)
            return 1
        
        # Step 4: Set up logging using configuration
        # Load configuration to get logging settings
        try:
            # Convert args to dictionary for configuration loading
            cli_args_dict = vars(args)
            
            # Load configuration from all sources
            config = load_configuration(
                cli_args=cli_args_dict,
                config_file_path=args.config_file
            )
            
            # Set up logging using the loaded configuration
            main_logger, audit_logger = setup_logging(config.logging)
            logger = main_logger
            
            # Log the CLI command invocation for audit purposes
            audit_logger.info(
                "CLI command invoked",
                extra={
                    "event": "cli_command_start",
                    "command": args.command,
                    "argv": sanitize_argv(argv),  # Sanitize sensitive arguments
                    "config_file": args.config_file,
                    "verbose": getattr(args, 'verbose', False),
                    "quiet": getattr(args, 'quiet', False)
                }
            )
            
            logger.info(f"CLI command '{args.command}' invoked", extra={
                "operation": "parse_and_dispatch_cli",
                "command": args.command,
                "has_config_file": bool(args.config_file),
                "verbose": getattr(args, 'verbose', False),
                "quiet": getattr(args, 'quiet', False)
            })
            
        except LabArchivesMCPException as e:
            # Handle configuration loading errors
            print(f"Configuration Error: {e.message}", file=sys.stderr)
            return 1
        except Exception as e:
            # Handle unexpected configuration or logging errors
            print(f"Initialization error: {str(e)}", file=sys.stderr)
            return 1
        
        # Step 5: Dispatch to the handler function for the selected subcommand
        try:
            # Get the handler function from the parsed args
            handler_func = getattr(args, 'func', None)
            
            if handler_func is None:
                # This shouldn't happen with proper subparser setup
                logger.error("No handler function found for command", extra={
                    "operation": "parse_and_dispatch_cli",
                    "command": args.command,
                    "error": "missing_handler"
                })
                print(f"Error: No handler found for command '{args.command}'", file=sys.stderr)
                return 1
            
            # Call the handler function with the parsed arguments
            logger.info(f"Dispatching to handler for command '{args.command}'", extra={
                "operation": "parse_and_dispatch_cli",
                "command": args.command,
                "handler": handler_func.__name__
            })
            
            # Execute the command handler
            if args.command == 'start':
                # Start command expects a dictionary of arguments
                exit_code = handler_func(cli_args_dict)
            elif args.command == 'authenticate':
                # Authenticate command expects the args namespace
                exit_code = handler_func(args)
            elif args.command == 'config':
                # Config command is handled by the config subparsers
                # The handler function is set by add_config_subparser
                exit_code = handler_func(args)
            else:
                # Generic handler invocation for future commands
                exit_code = handler_func(args)
            
            # Log command completion
            logger.info(f"Command '{args.command}' completed", extra={
                "operation": "parse_and_dispatch_cli",
                "command": args.command,
                "exit_code": exit_code,
                "success": exit_code == 0
            })
            
            audit_logger.info(
                "CLI command completed",
                extra={
                    "event": "cli_command_complete",
                    "command": args.command,
                    "exit_code": exit_code,
                    "success": exit_code == 0
                }
            )
            
            return exit_code
            
        except Exception as e:
            # Handle errors during command execution
            logger.error(f"Command execution failed: {str(e)}", extra={
                "operation": "parse_and_dispatch_cli",
                "command": args.command,
                "error": str(e),
                "error_type": type(e).__name__
            })
            
            audit_logger.error(
                "CLI command execution failed",
                extra={
                    "event": "cli_command_error",
                    "command": args.command,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            
            print(f"Command execution error: {str(e)}", file=sys.stderr)
            return 1
    
    except LabArchivesMCPException as e:
        # Step 6: Catch LabArchivesMCPException and print/log user-friendly error message
        error_message = f"LabArchives MCP Error: {str(e)}"
        print(error_message, file=sys.stderr)
        
        if logger:
            logger.error(error_message, extra={
                "operation": "parse_and_dispatch_cli",
                "error": str(e),
                "error_code": e.code,
                "error_context": e.context,
                "error_type": type(e).__name__
            })
        
        # Return appropriate exit code based on error type
        if e.code and e.code >= 2000 and e.code < 3000:
            return 2  # Authentication errors
        elif e.code and e.code >= 3000 and e.code < 4000:
            return 3  # Protocol errors
        else:
            return 1  # General errors
    
    except argparse.ArgumentError as e:
        # Step 7: Catch argparse.ArgumentError and print/log user-friendly error message
        error_message = f"Argument Error: {str(e)}"
        print(error_message, file=sys.stderr)
        print("Use --help for usage information.", file=sys.stderr)
        
        if logger:
            logger.error(error_message, extra={
                "operation": "parse_and_dispatch_cli",
                "error": str(e),
                "error_type": "ArgumentError"
            })
        
        return 1
    
    except KeyboardInterrupt:
        # Step 8: Handle user interruption gracefully
        print("\nOperation cancelled by user", file=sys.stderr)
        
        if logger:
            logger.info("CLI operation cancelled by user", extra={
                "operation": "parse_and_dispatch_cli",
                "interruption": "keyboard_interrupt"
            })
        
        return 130  # Standard exit code for SIGINT
    
    except Exception as e:
        # Step 9: Catch any other Exception and print/log fatal error message
        error_message = f"Unexpected error: {str(e)}"
        print(error_message, file=sys.stderr)
        
        if logger:
            logger.error(error_message, extra={
                "operation": "parse_and_dispatch_cli",
                "error": str(e),
                "error_type": type(e).__name__,
                "unexpected_error": True
            })
        
        return 1