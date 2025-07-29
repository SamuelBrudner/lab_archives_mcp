"""
LabArchives MCP Server - CLI Commands Package Initializer

This module serves as the package initializer for the 'commands' submodule of the LabArchives MCP Server CLI.
It enables the CLI command group structure by marking the directory as a Python package and exposing the
available CLI command modules for registration and import by the main CLI entrypoint.

The commands package provides modular command structure and extensibility for the CLI system, supporting
the following core commands:
- config_cmd: Configuration management commands (show, validate, reload)
- authenticate: Authentication command for establishing LabArchives API sessions
- start: Server startup command for launching the MCP protocol server

This package initializer facilitates the CLI Interface and Configuration feature (F-006) by providing
a clean, discoverable interface for command registration and execution. It supports the modular design
principle where each command is implemented as a separate module with its own argument parsing and
execution logic.

Key Features:
- Command Module Discovery: Exposes available command modules for CLI parser registration
- Modular Command Structure: Supports independent command modules with clear separation of concerns
- Extensible Design: Allows easy addition of new commands without modifying core CLI infrastructure
- Import Shortcuts: Provides convenient access to command modules for the main CLI system

Technical Specifications Supported:
- F-006: CLI Interface and Configuration - Modular command registration and extensibility
- F-008: Comprehensive Audit Logging - Command-level logging integration
- Centralized Command Management - Unified interface for command discovery and execution

All command modules in this package integrate with the centralized configuration system, logging
framework, and exception handling infrastructure to ensure consistent behavior across the CLI.
"""

# Command module imports - These provide the core CLI functionality
from . import config_cmd  # Configuration management commands (show, validate, reload)
from . import authenticate  # Authentication command for API session establishment
from . import start  # Server startup command for MCP protocol server

# Package metadata for CLI integration
__version__ = "0.1.0"
__author__ = "LabArchives MCP Server Team"

# =============================================================================
# Command Module Registry
# =============================================================================

# Command module registry for programmatic access and registration
# This dictionary maps command names to their respective modules for easy
# discovery and registration by the main CLI parser system
COMMAND_MODULES = {'config': config_cmd, 'authenticate': authenticate, 'start': start}

# Command functions registry for direct handler access
# This dictionary maps command names to their main handler functions
# for direct invocation by the CLI argument parser
COMMAND_HANDLERS = {
    'config': config_cmd.add_config_subparser,  # Returns configured subparser
    'authenticate': authenticate.authenticate_command,  # Direct command handler
    'start': start.start_command,  # Direct command handler
}

# =============================================================================
# Package Interface Functions
# =============================================================================


def get_available_commands():
    """
    Returns a list of available command names for CLI registration.

    This function provides a programmatic way to discover all available
    commands in the package, supporting dynamic command registration
    and help system generation.

    Returns:
        list: List of command names available in this package

    Example:
        >>> from commands import get_available_commands
        >>> commands = get_available_commands()
        >>> print(f"Available commands: {commands}")
        Available commands: ['config', 'authenticate', 'start']
    """
    return list(COMMAND_MODULES.keys())


def get_command_module(command_name):
    """
    Returns the module for a specific command name.

    This function provides programmatic access to command modules,
    supporting dynamic command loading and registration.

    Args:
        command_name (str): Name of the command to retrieve

    Returns:
        module: The command module if found, None otherwise

    Example:
        >>> from commands import get_command_module
        >>> config_module = get_command_module('config')
        >>> print(f"Config module: {config_module}")
    """
    return COMMAND_MODULES.get(command_name)


def get_command_handler(command_name):
    """
    Returns the handler function for a specific command name.

    This function provides direct access to command handler functions,
    supporting programmatic command execution.

    Args:
        command_name (str): Name of the command handler to retrieve

    Returns:
        function: The command handler function if found, None otherwise

    Example:
        >>> from commands import get_command_handler
        >>> auth_handler = get_command_handler('authenticate')
        >>> # auth_handler can now be called with parsed arguments
    """
    return COMMAND_HANDLERS.get(command_name)


# =============================================================================
# Package Exports
# =============================================================================

# Explicit exports for clean package interface
# These are the primary interfaces that external modules should use
__all__ = [
    # Command modules
    'config_cmd',
    'authenticate',
    'start',
    # Registry dictionaries
    'COMMAND_MODULES',
    'COMMAND_HANDLERS',
    # Interface functions
    'get_available_commands',
    'get_command_module',
    'get_command_handler',
    # Package metadata
    '__version__',
    '__author__',
]
