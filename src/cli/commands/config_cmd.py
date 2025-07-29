"""
LabArchives MCP Server - Configuration Management CLI Commands

This module implements the 'config' subcommand and its subcommands for the LabArchives MCP Server CLI.
Provides CLI entry points for configuration management, including displaying the current configuration,
validating configuration files and environment variables, and supporting dynamic reloading.

This module integrates with the centralized configuration loader, validation subsystem, and exception
framework to ensure robust, user-friendly, and auditable configuration operations. The module is
designed to be registered as a subparser in the main CLI parser, supporting modular command
registration and extensibility.

Key Features:
- F-006: CLI Interface and Configuration - Provides a command-line interface for configuration
  management, including commands to show, validate, and reload configuration. Ensures user-friendly,
  auditable, and robust configuration operations.
- F-008: Comprehensive Audit Logging - Ensures that all configuration operations (show, validate,
  reload) are logged in a structured, auditable format, supporting compliance and diagnostics.
- Centralized Configuration Management - Integrates with the centralized configuration loader and
  validator to ensure all configuration sources (CLI, environment, config file) are merged,
  validated, and accessible for CLI operations.
- Error Handling and User Feedback - Handles configuration errors, validation failures, and user
  mistakes gracefully, providing actionable error messages and logging all issues for audit and
  compliance.

All configuration commands support comprehensive error handling, detailed logging, and user-friendly
output formatting to ensure robust operation in production environments.
"""

import argparse  # builtin - Provides the ArgumentParser, subparsers, and CLI argument schema enforcement
import os  # builtin - Used for environment variable access and path expansion for config file arguments
import json  # builtin - Used for pretty-printing configuration as JSON for the 'show' command
import sys  # builtin - Supports CLI exit codes and error output

# Internal imports for configuration loading and management
from config import load_configuration, reload_configuration, get_config_value

# Internal imports for configuration validation
from validators import validate_server_configuration

# Internal imports for exception handling
from exceptions import LabArchivesMCPException

# Internal imports for data models
from models import ServerConfiguration

# Internal imports for logging setup
from logging_setup import setup_logging

# Internal imports for utility functions
from utils import expand_path

# =============================================================================
# Global Constants
# =============================================================================

# Configuration command description for CLI help and documentation
CONFIG_COMMAND_DESCRIPTION = (
    "LabArchives MCP Server configuration management commands (show, validate, reload)."
)

# =============================================================================
# Main Configuration Command Functions
# =============================================================================


def add_config_subparser(
    main_parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    """
    Registers the 'config' subparser and its subcommands ('show', 'validate', 'reload') with the main CLI parser.

    Each subcommand is linked to its handler function. This function is called by the main CLI parser during
    initialization to register all configuration-related CLI commands with appropriate argument parsing and
    handler assignment.

    The function creates a hierarchical CLI structure where:
    - 'config' is the main subcommand
    - 'show', 'validate', and 'reload' are subcommands under 'config'
    - Each subcommand has its own argument parser and handler function

    This design enables modular command registration and extensibility while maintaining clear separation
    of concerns between different configuration operations.

    Args:
        main_parser (argparse.ArgumentParser): The main CLI parser to which the 'config' subparser
                                             will be added. This parser should already be initialized
                                             and ready to accept subparsers.

    Returns:
        argparse.ArgumentParser: The updated parser with the 'config' subparser and subcommands registered.
                               The returned parser includes all the configuration command handlers and
                               argument definitions.

    Example:
        >>> main_parser = argparse.ArgumentParser()
        >>> updated_parser = add_config_subparser(main_parser)
        >>> # Now main_parser supports: config show, config validate, config reload
    """
    try:
        # Create a 'config' subparser with description CONFIG_COMMAND_DESCRIPTION
        config_subparsers = main_parser.add_subparsers(
            dest='config_command',
            title='Configuration Commands',
            description=CONFIG_COMMAND_DESCRIPTION,
            help='Configuration management operations',
        )

        # Add subcommands: 'show', 'validate', and 'reload'

        # For 'show', register show_config_command as the handler
        show_parser = config_subparsers.add_parser(
            'show',
            help='Display the current configuration with all merged sources',
            description='Shows the current server configuration after merging CLI arguments, environment variables, and config files.',
        )
        show_parser.add_argument(
            '--config-file',
            type=str,
            help='Path to configuration file to load and display',
        )
        show_parser.add_argument(
            '--format',
            choices=['json', 'yaml'],
            default='json',
            help='Output format for configuration display (default: json)',
        )
        show_parser.set_defaults(func=show_config_command)

        # For 'validate', register validate_config_command as the handler
        validate_parser = config_subparsers.add_parser(
            'validate',
            help='Validate the current configuration for errors and compliance',
            description='Validates the server configuration from all sources and reports any errors or warnings.',
        )
        validate_parser.add_argument(
            '--config-file', type=str, help='Path to configuration file to validate'
        )
        validate_parser.add_argument(
            '--strict',
            action='store_true',
            help='Enable strict validation mode with enhanced checks',
        )
        validate_parser.set_defaults(func=validate_config_command)

        # For 'reload', register reload_config_command as the handler
        reload_parser = config_subparsers.add_parser(
            'reload',
            help='Reload configuration at runtime from all sources',
            description='Reloads and revalidates configuration from CLI arguments, environment variables, and config files.',
        )
        reload_parser.add_argument(
            '--config-file', type=str, help='Path to configuration file to reload'
        )
        reload_parser.add_argument(
            '--verify',
            action='store_true',
            help='Verify configuration after reload and display summary',
        )
        reload_parser.set_defaults(func=reload_config_command)

        # Return the updated parser
        return main_parser

    except Exception as e:
        # Handle any unexpected errors during subparser registration
        raise LabArchivesMCPException(
            message=f"Failed to register config subparser: {str(e)}",
            code=5001,
            context={
                "operation": "add_config_subparser",
                "error_type": type(e).__name__,
                "error_details": str(e),
            },
        )


def show_config_command(args: argparse.Namespace) -> int:
    """
    Implements the 'config show' CLI command.

    Loads the current configuration (merging CLI args, environment, config file), pretty-prints it as JSON,
    and exits. Handles errors gracefully and logs the operation for audit. The function provides a
    comprehensive view of the current configuration state, including all merged sources and their
    precedence resolution.

    The command performs the following operations:
    1. Initialize logging system for audit trail
    2. Load configuration from all sources (CLI, environment, config file)
    3. Pretty-print the configuration as JSON to stdout
    4. Log the operation as an audit event
    5. Handle errors gracefully with user-friendly messages

    Args:
        args (argparse.Namespace): Parsed CLI arguments containing configuration options such as
                                 config_file path, output format, and other command-specific parameters.

    Returns:
        int: Exit code (0 for success, nonzero for error). A return value of 0 indicates successful
             configuration loading and display. Non-zero values indicate various error conditions
             such as configuration loading failures, validation errors, or file access issues.

    Example:
        >>> args = argparse.Namespace(config_file='/path/to/config.json', format='json')
        >>> exit_code = show_config_command(args)
        >>> print(f"Command completed with exit code: {exit_code}")
    """
    try:
        # Initialize logging system for audit trail
        logger = None
        audit_logger = None

        try:
            # Set up basic logging to capture the operation
            from models import LoggingConfig

            default_logging_config = LoggingConfig()
            main_logger, audit_logger = setup_logging(default_logging_config)
            logger = main_logger

            # Log the start of the show configuration operation
            audit_logger.info(
                "Configuration show command initiated",
                extra={
                    "operation": "config_show",
                    "config_file": getattr(args, 'config_file', None),
                    "format": getattr(args, 'format', 'json'),
                },
            )

        except Exception as logging_error:
            # If logging setup fails, continue without logging but print warning
            print(
                f"Warning: Failed to initialize logging: {logging_error}",
                file=sys.stderr,
            )

        # Load the current configuration using load_configuration, passing CLI args and config file path if provided
        config_file_path = getattr(args, 'config_file', None)
        if config_file_path:
            config_file_path = expand_path(config_file_path)

        # Convert args namespace to dictionary for configuration loading
        cli_args_dict = vars(args) if args else {}

        # Load configuration from all sources
        try:
            server_config = load_configuration(
                cli_args=cli_args_dict, config_file_path=config_file_path
            )
        except LabArchivesMCPException as config_error:
            error_msg = f"Failed to load configuration: {config_error.message}"
            print(error_msg, file=sys.stderr)

            if logger:
                logger.error(
                    error_msg,
                    extra={
                        "error_code": config_error.code,
                        "context": config_error.context,
                    },
                )
            if audit_logger:
                audit_logger.error(
                    "Configuration show command failed - configuration loading error",
                    extra={
                        "operation": "config_show",
                        "error": config_error.message,
                        "error_code": config_error.code,
                    },
                )

            return 1

        # Pretty-print the configuration as JSON to stdout
        try:
            output_format = getattr(args, 'format', 'json')

            if output_format == 'json':
                # Convert ServerConfiguration to dictionary for JSON serialization
                config_dict = server_config.dict()

                # Pretty-print with indentation for readability
                json_output = json.dumps(config_dict, indent=2, ensure_ascii=False, sort_keys=True)
                print(json_output)

            else:
                # Handle other formats (currently only json is supported)
                print(f"Unsupported output format: {output_format}", file=sys.stderr)
                if logger:
                    logger.warning(f"Unsupported output format requested: {output_format}")
                return 1

        except Exception as format_error:
            error_msg = f"Failed to format configuration output: {str(format_error)}"
            print(error_msg, file=sys.stderr)

            if logger:
                logger.error(error_msg, extra={"error_type": type(format_error).__name__})
            if audit_logger:
                audit_logger.error(
                    "Configuration show command failed - output formatting error",
                    extra={
                        "operation": "config_show",
                        "error": str(format_error),
                        "format": output_format,
                    },
                )

            return 1

        # Log the operation as an audit event
        if audit_logger:
            audit_logger.info(
                "Configuration show command completed successfully",
                extra={
                    "operation": "config_show",
                    "config_file": config_file_path,
                    "format": output_format,
                    "result": "success",
                },
            )

        if logger:
            logger.info(f"Configuration displayed successfully in {output_format} format")

        # Return exit code 0 for success
        return 0

    except KeyboardInterrupt:
        # Handle user interruption gracefully
        print("\nOperation cancelled by user", file=sys.stderr)
        return 130  # Standard exit code for SIGINT

    except Exception as e:
        # If an error occurs, print a user-friendly error message, log the error, and return a nonzero exit code
        error_msg = f"Unexpected error in config show command: {str(e)}"
        print(error_msg, file=sys.stderr)

        if logger:
            logger.error(error_msg, extra={"error_type": type(e).__name__})
        if audit_logger:
            audit_logger.error(
                "Configuration show command failed - unexpected error",
                extra={
                    "operation": "config_show",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

        return 1


def validate_config_command(args: argparse.Namespace) -> int:
    """
    Implements the 'config validate' CLI command.

    Loads and validates the current configuration, reporting any errors or warnings. Exits with code 0 if valid,
    nonzero if invalid. Logs the operation for audit. The function provides comprehensive validation of all
    configuration sources and reports detailed error information to help users resolve configuration issues.

    The command performs the following operations:
    1. Initialize logging system for audit trail
    2. Load configuration from all sources (CLI, environment, config file)
    3. Validate the configuration using validate_server_configuration
    4. Report validation results with detailed error information
    5. Log the operation and results for audit purposes

    Args:
        args (argparse.Namespace): Parsed CLI arguments containing configuration options such as
                                 config_file path, strict validation mode, and other command-specific parameters.

    Returns:
        int: Exit code (0 for valid, nonzero for invalid or error). A return value of 0 indicates that the
             configuration is valid and ready for use. Non-zero values indicate validation failures,
             configuration loading errors, or other issues that prevent successful validation.

    Example:
        >>> args = argparse.Namespace(config_file='/path/to/config.json', strict=True)
        >>> exit_code = validate_config_command(args)
        >>> print(f"Validation completed with exit code: {exit_code}")
    """
    try:
        # Initialize logging system for audit trail
        logger = None
        audit_logger = None

        try:
            # Set up basic logging to capture the operation
            from models import LoggingConfig

            default_logging_config = LoggingConfig()
            main_logger, audit_logger = setup_logging(default_logging_config)
            logger = main_logger

            # Log the start of the validate configuration operation
            audit_logger.info(
                "Configuration validate command initiated",
                extra={
                    "operation": "config_validate",
                    "config_file": getattr(args, 'config_file', None),
                    "strict": getattr(args, 'strict', False),
                },
            )

        except Exception as logging_error:
            # If logging setup fails, continue without logging but print warning
            print(
                f"Warning: Failed to initialize logging: {logging_error}",
                file=sys.stderr,
            )

        # Load the current configuration using load_configuration
        config_file_path = getattr(args, 'config_file', None)
        if config_file_path:
            config_file_path = expand_path(config_file_path)

        # Convert args namespace to dictionary for configuration loading
        cli_args_dict = vars(args) if args else {}

        # Load configuration from all sources
        try:
            server_config = load_configuration(
                cli_args=cli_args_dict, config_file_path=config_file_path
            )
        except LabArchivesMCPException as config_error:
            error_msg = f"Configuration loading failed: {config_error.message}"
            print(error_msg, file=sys.stderr)

            if logger:
                logger.error(
                    error_msg,
                    extra={
                        "error_code": config_error.code,
                        "context": config_error.context,
                    },
                )
            if audit_logger:
                audit_logger.error(
                    "Configuration validate command failed - configuration loading error",
                    extra={
                        "operation": "config_validate",
                        "error": config_error.message,
                        "error_code": config_error.code,
                    },
                )

            return 1

        # Validate the configuration using validate_server_configuration
        try:
            validate_server_configuration(server_config)

            # If valid, print a success message and log the operation
            success_msg = "✓ Configuration validation successful"
            print(success_msg)

            if logger:
                logger.info("Configuration validation completed successfully")
            if audit_logger:
                audit_logger.info(
                    "Configuration validate command completed successfully",
                    extra={
                        "operation": "config_validate",
                        "config_file": config_file_path,
                        "strict": getattr(args, 'strict', False),
                        "result": "valid",
                    },
                )

            # Display configuration summary if requested
            if getattr(args, 'strict', False):
                print("\nConfiguration Summary:")
                print(f"  Server: {server_config.server_name} v{server_config.server_version}")
                print(f"  API Base URL: {server_config.authentication.api_base_url}")
                print(f"  Log Level: {server_config.logging.log_level}")

                # Show scope configuration if set
                if server_config.scope.notebook_id:
                    print(f"  Scope: Notebook ID {server_config.scope.notebook_id}")
                elif server_config.scope.notebook_name:
                    print(f"  Scope: Notebook '{server_config.scope.notebook_name}'")
                elif server_config.scope.folder_path:
                    print(f"  Scope: Folder '{server_config.scope.folder_path}'")
                else:
                    print(f"  Scope: All accessible resources")

            return 0

        except LabArchivesMCPException as validation_error:
            # If invalid, print detailed error messages, log the error, and return a nonzero exit code
            error_msg = f"✗ Configuration validation failed: {validation_error.message}"
            print(error_msg, file=sys.stderr)

            # Print additional context if available
            if validation_error.context:
                print(f"  Context: {validation_error.context}", file=sys.stderr)

            # Provide actionable guidance based on error code
            if validation_error.code in [2001, 2002]:  # Authentication errors
                print(
                    "  Suggestion: Check your LABARCHIVES_AKID and LABARCHIVES_SECRET environment variables",
                    file=sys.stderr,
                )
            elif validation_error.code in [3001, 3002, 3003, 3004]:  # Scope errors
                print(
                    "  Suggestion: Review your scope configuration (notebook_id, notebook_name, or folder_path)",
                    file=sys.stderr,
                )
            elif validation_error.code in [5001, 5002]:  # Logging errors
                print(
                    "  Suggestion: Check your log file path and permissions",
                    file=sys.stderr,
                )

            if logger:
                logger.error(
                    error_msg,
                    extra={
                        "error_code": validation_error.code,
                        "context": validation_error.context,
                    },
                )
            if audit_logger:
                audit_logger.error(
                    "Configuration validate command failed - validation error",
                    extra={
                        "operation": "config_validate",
                        "error": validation_error.message,
                        "error_code": validation_error.code,
                        "context": validation_error.context,
                    },
                )

            return 1

    except KeyboardInterrupt:
        # Handle user interruption gracefully
        print("\nValidation cancelled by user", file=sys.stderr)
        return 130  # Standard exit code for SIGINT

    except Exception as e:
        # Handle any unexpected errors during validation
        error_msg = f"Unexpected error in config validate command: {str(e)}"
        print(error_msg, file=sys.stderr)

        if logger:
            logger.error(error_msg, extra={"error_type": type(e).__name__})
        if audit_logger:
            audit_logger.error(
                "Configuration validate command failed - unexpected error",
                extra={
                    "operation": "config_validate",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

        return 1


def reload_config_command(args: argparse.Namespace) -> int:
    """
    Implements the 'config reload' CLI command.

    Reloads the configuration at runtime, re-aggregating from all sources and re-validating. Prints a success
    or error message and logs the operation for audit. The function supports dynamic configuration changes
    without requiring a full server restart, making it suitable for operational scenarios.

    The command performs the following operations:
    1. Initialize logging system for audit trail
    2. Call reload_configuration with the current CLI arguments and config file path
    3. Validate the reloaded configuration
    4. Report reload results with optional verification
    5. Log the operation and results for audit purposes

    Args:
        args (argparse.Namespace): Parsed CLI arguments containing configuration options such as
                                 config_file path, verification mode, and other command-specific parameters.

    Returns:
        int: Exit code (0 for success, nonzero for error). A return value of 0 indicates successful
             configuration reload and validation. Non-zero values indicate reload failures,
             validation errors, or other issues that prevent successful configuration reload.

    Example:
        >>> args = argparse.Namespace(config_file='/path/to/config.json', verify=True)
        >>> exit_code = reload_config_command(args)
        >>> print(f"Reload completed with exit code: {exit_code}")
    """
    try:
        # Initialize logging system for audit trail
        logger = None
        audit_logger = None

        try:
            # Set up basic logging to capture the operation
            from models import LoggingConfig

            default_logging_config = LoggingConfig()
            main_logger, audit_logger = setup_logging(default_logging_config)
            logger = main_logger

            # Log the start of the reload configuration operation
            audit_logger.info(
                "Configuration reload command initiated",
                extra={
                    "operation": "config_reload",
                    "config_file": getattr(args, 'config_file', None),
                    "verify": getattr(args, 'verify', False),
                },
            )

        except Exception as logging_error:
            # If logging setup fails, continue without logging but print warning
            print(
                f"Warning: Failed to initialize logging: {logging_error}",
                file=sys.stderr,
            )

        # Call reload_configuration with the current CLI arguments and config file path
        config_file_path = getattr(args, 'config_file', None)
        if config_file_path:
            config_file_path = expand_path(config_file_path)

        # Convert args namespace to dictionary for configuration loading
        cli_args_dict = vars(args) if args else {}

        # Attempt to reload configuration
        try:
            # First, load the configuration to update the global state
            server_config = load_configuration(
                cli_args=cli_args_dict, config_file_path=config_file_path
            )

            # Then call reload_configuration to refresh from all sources
            reloaded_config = reload_configuration()

        except LabArchivesMCPException as reload_error:
            error_msg = f"Configuration reload failed: {reload_error.message}"
            print(error_msg, file=sys.stderr)

            if logger:
                logger.error(
                    error_msg,
                    extra={
                        "error_code": reload_error.code,
                        "context": reload_error.context,
                    },
                )
            if audit_logger:
                audit_logger.error(
                    "Configuration reload command failed - reload error",
                    extra={
                        "operation": "config_reload",
                        "error": reload_error.message,
                        "error_code": reload_error.code,
                    },
                )

            return 1

        # Validate the reloaded configuration
        try:
            validate_server_configuration(reloaded_config)

            # If successful, print a success message and log the reload event
            success_msg = "✓ Configuration reloaded successfully"
            print(success_msg)

            if logger:
                logger.info("Configuration reloaded and validated successfully")
            if audit_logger:
                audit_logger.info(
                    "Configuration reload command completed successfully",
                    extra={
                        "operation": "config_reload",
                        "config_file": config_file_path,
                        "verify": getattr(args, 'verify', False),
                        "result": "success",
                    },
                )

            # Display verification summary if requested
            if getattr(args, 'verify', False):
                print("\nReloaded Configuration Summary:")
                print(f"  Server: {reloaded_config.server_name} v{reloaded_config.server_version}")
                print(f"  API Base URL: {reloaded_config.authentication.api_base_url}")
                print(f"  Log Level: {reloaded_config.logging.log_level}")

                # Show scope configuration if set
                if reloaded_config.scope.notebook_id:
                    print(f"  Scope: Notebook ID {reloaded_config.scope.notebook_id}")
                elif reloaded_config.scope.notebook_name:
                    print(f"  Scope: Notebook '{reloaded_config.scope.notebook_name}'")
                elif reloaded_config.scope.folder_path:
                    print(f"  Scope: Folder '{reloaded_config.scope.folder_path}'")
                else:
                    print(f"  Scope: All accessible resources")

                # Show output configuration
                print(
                    f"  JSON-LD: {'Enabled' if reloaded_config.output.json_ld_enabled else 'Disabled'}"
                )
                print(
                    f"  Structured Output: {'Enabled' if reloaded_config.output.structured_output else 'Disabled'}"
                )

                # Show logging configuration
                log_file = reloaded_config.logging.log_file or "console only"
                print(f"  Log File: {log_file}")
                print(f"  Verbose: {'Enabled' if reloaded_config.logging.verbose else 'Disabled'}")
                print(f"  Quiet: {'Enabled' if reloaded_config.logging.quiet else 'Disabled'}")

            return 0

        except LabArchivesMCPException as validation_error:
            # If validation fails after reload, report the error
            error_msg = (
                f"Configuration reload succeeded but validation failed: {validation_error.message}"
            )
            print(error_msg, file=sys.stderr)

            if logger:
                logger.error(
                    error_msg,
                    extra={
                        "error_code": validation_error.code,
                        "context": validation_error.context,
                    },
                )
            if audit_logger:
                audit_logger.error(
                    "Configuration reload command failed - validation error after reload",
                    extra={
                        "operation": "config_reload",
                        "error": validation_error.message,
                        "error_code": validation_error.code,
                    },
                )

            return 1

    except KeyboardInterrupt:
        # Handle user interruption gracefully
        print("\nReload cancelled by user", file=sys.stderr)
        return 130  # Standard exit code for SIGINT

    except Exception as e:
        # If an error occurs, print a user-friendly error message, log the error, and return a nonzero exit code
        error_msg = f"Unexpected error in config reload command: {str(e)}"
        print(error_msg, file=sys.stderr)

        if logger:
            logger.error(error_msg, extra={"error_type": type(e).__name__})
        if audit_logger:
            audit_logger.error(
                "Configuration reload command failed - unexpected error",
                extra={
                    "operation": "config_reload",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

        return 1
