"""
LabArchives MCP Server - Centralized Configuration Manager

This module provides centralized configuration loading, merging, and validation for the 
LabArchives MCP Server CLI. It serves as the canonical entry point for all configuration 
access, aggregating configuration from multiple sources (CLI arguments, environment 
variables, config files, defaults) into a single, immutable ServerConfiguration object.

Key Features:
- Configuration Source Aggregation: Merges CLI args, environment variables, config files, and defaults
- Precedence Enforcement: CLI > env > file > defaults precedence order
- Comprehensive Validation: Uses dedicated validators for each configuration section
- Runtime Access: Provides dot-notation access to configuration values
- Dynamic Reloading: Supports runtime configuration reloading for operational changes
- Audit Logging: Comprehensive error logging for all configuration operations

This module supports the following features from the technical specification:
- F-005: Authentication and Security Management - Secure credential handling with environment variable support
- F-006: CLI Interface and Configuration - Robust configuration management with validation
- F-007: Scope Limitation and Access Control - Granular access control configuration
- F-008: Comprehensive Audit Logging - Structured error logging for all configuration operations

All configuration operations are designed to be secure, auditable, and production-ready,
with comprehensive error handling and detailed logging for troubleshooting and compliance.
"""

import os  # builtin - Operating system interface for environment variables and file operations
from typing import Dict, Any, Optional, Union  # builtin - Type annotations for function signatures

# Internal imports - Configuration models and structured data
# Import from models.py file (not models package) for configuration classes
import importlib.util
import sys

# Load models.py directly to avoid import conflicts with models package
import os
models_path = os.path.join(os.path.dirname(__file__), "models.py")
models_spec = importlib.util.spec_from_file_location("models", models_path)
models_module = importlib.util.module_from_spec(models_spec)
models_spec.loader.exec_module(models_module)

# Import configuration classes from the loaded module
AuthenticationConfig = models_module.AuthenticationConfig
ScopeConfig = models_module.ScopeConfig
OutputConfig = models_module.OutputConfig
LoggingConfig = models_module.LoggingConfig
ServerConfiguration = models_module.ServerConfiguration

# Internal imports - Configuration validators for comprehensive validation
from src.cli.validators import (
    validate_authentication_config,
    validate_scope_config,
    validate_output_config,
    validate_logging_config,
    validate_server_configuration
)

# Internal imports - Utility functions for file operations and environment variable access
from src.cli.utils import (
    expand_path,
    get_env_var,
    read_json_file
)

# Internal imports - Exception handling for structured error reporting
from src.cli.exceptions import LabArchivesMCPException

# Internal imports - Constants for default values and configuration keys
from src.cli.constants import (
    DEFAULT_API_BASE_URL,
    DEFAULT_LOG_FILE,
    DEFAULT_LOG_LEVEL,
    MCP_SERVER_NAME,
    MCP_SERVER_VERSION
)

# =============================================================================
# Global Configuration Management
# =============================================================================

# Configuration precedence order - defines the hierarchy for configuration value resolution
# CLI arguments have highest precedence, followed by environment variables, config files, and defaults
CONFIG_PRECEDENCE = ["cli_args", "env", "file", "defaults"]

# Configuration cache to store the last loaded ServerConfiguration for reloading and access
# This enables runtime configuration access and supports dynamic reloading operations
_CONFIG_CACHE: Optional[ServerConfiguration] = None

# Track the last used configuration sources for reload operations
_LAST_CLI_ARGS: Optional[Dict[str, Any]] = None
_LAST_CONFIG_FILE_PATH: Optional[str] = None


def load_configuration(
    cli_args: Optional[Dict[str, Any]] = None,
    config_file_path: Optional[str] = None
) -> ServerConfiguration:
    """
    Aggregates, merges, and validates all configuration sources into a single ServerConfiguration object.
    
    This function serves as the primary entry point for configuration loading, implementing the
    complete configuration lifecycle from source aggregation through validation and caching.
    It enforces strict precedence rules (CLI > env > file > defaults) and ensures all
    configuration sections are properly validated before returning the final configuration.
    
    The function processes configuration sources in the following order:
    1. Initialize with default values from constants and models
    2. Overlay file-based configuration if config_file_path is provided
    3. Overlay environment variables using standardized environment variable names
    4. Overlay CLI arguments if provided (highest precedence)
    5. Construct and validate all configuration sections
    6. Cache the result for runtime access and reloading
    
    Configuration Sources:
    - Defaults: Hardcoded defaults from constants and model definitions
    - Config File: JSON configuration file with structured settings
    - Environment Variables: OS environment variables with standardized names
    - CLI Arguments: Command-line arguments with highest precedence
    
    Args:
        cli_args (Optional[Dict[str, Any]]): Parsed CLI arguments from argparse or similar.
            Keys should match configuration field names (e.g., 'access_key_id', 'log_level').
            CLI arguments have the highest precedence and will override all other sources.
        config_file_path (Optional[str]): Path to JSON configuration file. Supports user home
            directory expansion (~) and environment variable substitution. If None, file-based
            configuration is skipped.
    
    Returns:
        ServerConfiguration: Fully merged and validated configuration object containing all
            configuration sections (authentication, scope, output, logging) and server metadata.
            The configuration is immutable and cached for runtime access.
    
    Raises:
        LabArchivesMCPException: On configuration validation failure, file access errors, or
            invalid configuration values. All errors include detailed context for debugging
            and audit logging with specific error codes for programmatic handling.
    
    Example:
        >>> # Load configuration with CLI args and config file
        >>> cli_args = {'access_key_id': 'AKID123', 'log_level': 'DEBUG'}
        >>> config = load_configuration(cli_args, '~/labarchives/config.json')
        >>> print(config.authentication.access_key_id)
        'AKID123'
        
        >>> # Load configuration from environment and defaults only
        >>> config = load_configuration()
        >>> print(config.logging.log_level)
        'INFO'
    """
    global _CONFIG_CACHE, _LAST_CLI_ARGS, _LAST_CONFIG_FILE_PATH
    
    try:
        # Store configuration sources for reload operations
        _LAST_CLI_ARGS = cli_args
        _LAST_CONFIG_FILE_PATH = config_file_path
        
        # Step 1: Initialize configuration dictionary with default values
        config_dict = _initialize_default_configuration()
        
        # Step 2: Overlay file-based configuration if provided
        if config_file_path is not None:
            try:
                file_config = _load_file_configuration(config_file_path)
                config_dict = _merge_configuration_dicts(config_dict, file_config, "file")
            except LabArchivesMCPException as e:
                raise LabArchivesMCPException(
                    message=f"Failed to load configuration file: {e.message}",
                    code=1001,
                    context={
                        "operation": "load_configuration",
                        "source": "file",
                        "file_path": config_file_path,
                        "original_error": e.context
                    }
                )
        
        # Step 3: Overlay environment variables
        try:
            env_config = _load_environment_configuration()
            config_dict = _merge_configuration_dicts(config_dict, env_config, "env")
        except LabArchivesMCPException as e:
            raise LabArchivesMCPException(
                message=f"Failed to load environment configuration: {e.message}",
                code=1002,
                context={
                    "operation": "load_configuration",
                    "source": "env",
                    "original_error": e.context
                }
            )
        
        # Step 4: Overlay CLI arguments (highest precedence)
        if cli_args is not None:
            try:
                config_dict = _merge_configuration_dicts(config_dict, cli_args, "cli_args")
            except LabArchivesMCPException as e:
                raise LabArchivesMCPException(
                    message=f"Failed to process CLI arguments: {e.message}",
                    code=1003,
                    context={
                        "operation": "load_configuration",
                        "source": "cli_args",
                        "cli_args": cli_args,
                        "original_error": e.context
                    }
                )
        
        # Step 5: Construct and validate configuration sections
        try:
            server_config = _construct_server_configuration(config_dict)
        except LabArchivesMCPException as e:
            raise LabArchivesMCPException(
                message=f"Failed to construct server configuration: {e.message}",
                code=1004,
                context={
                    "operation": "load_configuration",
                    "source": "construction",
                    "config_dict": config_dict,
                    "original_error": e.context
                }
            )
        
        # Step 6: Validate the complete configuration
        try:
            validate_server_configuration(server_config)
        except LabArchivesMCPException as e:
            raise LabArchivesMCPException(
                message=f"Configuration validation failed: {e.message}",
                code=1005,
                context={
                    "operation": "load_configuration",
                    "source": "validation",
                    "server_config": server_config,
                    "original_error": e.context
                }
            )
        
        # Step 7: Cache the validated configuration for runtime access
        _CONFIG_CACHE = server_config
        
        # Step 8: Return the fully loaded and validated configuration
        return server_config
        
    except LabArchivesMCPException:
        # Re-raise configuration-specific exceptions with full context
        raise
    except Exception as e:
        # Handle any unexpected errors during configuration loading
        raise LabArchivesMCPException(
            message=f"Unexpected error loading configuration: {str(e)}",
            code=1006,
            context={
                "operation": "load_configuration",
                "cli_args": cli_args,
                "config_file_path": config_file_path,
                "error_type": type(e).__name__,
                "error_details": str(e)
            }
        )


def reload_configuration() -> ServerConfiguration:
    """
    Reloads and revalidates configuration at runtime using the last known sources.
    
    This function supports dynamic configuration reloading for operational scenarios
    such as SIGHUP signal handling, CLI reload commands, or configuration change
    detection. It uses the last known CLI arguments and config file path to
    reload the configuration with the same sources but updated values.
    
    This is particularly useful for:
    - Runtime configuration changes without server restart
    - Environment variable updates
    - Configuration file modifications
    - Operational configuration adjustments
    
    The function maintains the same validation and precedence rules as the
    initial configuration load, ensuring consistency and reliability.
    
    Returns:
        ServerConfiguration: The reloaded and validated configuration object.
            All configuration sections are revalidated and the cache is updated.
    
    Raises:
        LabArchivesMCPException: If configuration has not been loaded previously,
            if reload fails due to validation errors, or if configuration sources
            are no longer accessible. Includes detailed context for debugging.
    
    Example:
        >>> # Initial configuration load
        >>> config = load_configuration(cli_args, config_file_path)
        >>> 
        >>> # Later, reload with updated sources
        >>> updated_config = reload_configuration()
        >>> print(updated_config.logging.log_level)
        'DEBUG'  # Updated from environment variable change
    """
    global _CONFIG_CACHE, _LAST_CLI_ARGS, _LAST_CONFIG_FILE_PATH
    
    try:
        # Verify that configuration has been loaded previously
        if _CONFIG_CACHE is None:
            raise LabArchivesMCPException(
                message="Cannot reload configuration: No configuration has been loaded previously",
                code=2001,
                context={
                    "operation": "reload_configuration",
                    "cache_state": "empty",
                    "last_cli_args": _LAST_CLI_ARGS,
                    "last_config_file_path": _LAST_CONFIG_FILE_PATH
                }
            )
        
        # Reload configuration using the last known sources
        reloaded_config = load_configuration(
            cli_args=_LAST_CLI_ARGS,
            config_file_path=_LAST_CONFIG_FILE_PATH
        )
        
        # Return the reloaded configuration
        return reloaded_config
        
    except LabArchivesMCPException:
        # Re-raise configuration-specific exceptions with full context
        raise
    except Exception as e:
        # Handle any unexpected errors during configuration reloading
        raise LabArchivesMCPException(
            message=f"Unexpected error reloading configuration: {str(e)}",
            code=2002,
            context={
                "operation": "reload_configuration",
                "last_cli_args": _LAST_CLI_ARGS,
                "last_config_file_path": _LAST_CONFIG_FILE_PATH,
                "error_type": type(e).__name__,
                "error_details": str(e)
            }
        )


def get_config_value(key: str) -> Any:
    """
    Retrieves a specific configuration value from the loaded ServerConfiguration using dot notation.
    
    This function provides convenient access to configuration values using dot notation
    (e.g., 'authentication.access_key_id', 'logging.log_level') without requiring
    direct access to the configuration object. It supports deep object traversal
    and provides clear error messages for invalid keys.
    
    The function supports accessing any field in the ServerConfiguration object
    hierarchy, including nested configuration sections and their properties.
    
    Supported Key Patterns:
    - 'authentication.access_key_id' - Authentication configuration fields
    - 'scope.notebook_id' - Scope configuration fields
    - 'output.json_ld_enabled' - Output configuration fields
    - 'logging.log_level' - Logging configuration fields
    - 'server_name' - Top-level server metadata
    - 'server_version' - Top-level server metadata
    
    Args:
        key (str): Dot-notation key specifying the configuration value to retrieve.
            Must be a valid path through the ServerConfiguration object hierarchy.
            Case-sensitive and must match exact field names from the configuration models.
    
    Returns:
        Any: The value of the requested configuration key. The type depends on the
            specific configuration field (str, bool, int, Optional[str], etc.).
    
    Raises:
        LabArchivesMCPException: If configuration is not loaded, if the key is invalid
            or not found, or if the key format is incorrect. Includes detailed context
            for debugging and audit logging.
    
    Example:
        >>> # Retrieve authentication configuration
        >>> access_key = get_config_value('authentication.access_key_id')
        >>> print(access_key)
        'AKID1234567890ABCDEF'
        
        >>> # Retrieve logging configuration
        >>> log_level = get_config_value('logging.log_level')
        >>> print(log_level)
        'INFO'
        
        >>> # Retrieve server metadata
        >>> server_name = get_config_value('server_name')
        >>> print(server_name)
        'labarchives-mcp-server'
    """
    global _CONFIG_CACHE
    
    # Validate input parameters
    if key is None:
        raise LabArchivesMCPException(
            message="Configuration key cannot be None",
            code=3001,
            context={"operation": "get_config_value", "key": key}
        )
    
    if not isinstance(key, str):
        raise LabArchivesMCPException(
            message=f"Configuration key must be a string, got {type(key).__name__}",
            code=3002,
            context={"operation": "get_config_value", "key": key, "key_type": type(key).__name__}
        )
    
    if not key.strip():
        raise LabArchivesMCPException(
            message="Configuration key cannot be empty or contain only whitespace",
            code=3003,
            context={"operation": "get_config_value", "key": key}
        )
    
    # Verify that configuration has been loaded
    if _CONFIG_CACHE is None:
        raise LabArchivesMCPException(
            message="Cannot retrieve configuration value: No configuration has been loaded",
            code=3004,
            context={
                "operation": "get_config_value",
                "key": key,
                "cache_state": "empty"
            }
        )
    
    try:
        # Split the key by dots and traverse the configuration object
        key_parts = key.split('.')
        current_value = _CONFIG_CACHE
        
        # Traverse the object hierarchy following the key path
        for i, part in enumerate(key_parts):
            if not hasattr(current_value, part):
                # Build the partial path for error reporting
                partial_path = '.'.join(key_parts[:i+1])
                available_attrs = [attr for attr in dir(current_value) if not attr.startswith('_')]
                
                raise LabArchivesMCPException(
                    message=f"Configuration key '{partial_path}' not found in configuration object",
                    code=3005,
                    context={
                        "operation": "get_config_value",
                        "key": key,
                        "partial_path": partial_path,
                        "available_attributes": available_attrs,
                        "current_object_type": type(current_value).__name__
                    }
                )
            
            # Move to the next level in the object hierarchy
            current_value = getattr(current_value, part)
        
        # Return the final value
        return current_value
        
    except LabArchivesMCPException:
        # Re-raise configuration-specific exceptions with full context
        raise
    except Exception as e:
        # Handle any unexpected errors during value retrieval
        raise LabArchivesMCPException(
            message=f"Unexpected error retrieving configuration value '{key}': {str(e)}",
            code=3006,
            context={
                "operation": "get_config_value",
                "key": key,
                "error_type": type(e).__name__,
                "error_details": str(e)
            }
        )


# =============================================================================
# Internal Configuration Management Functions
# =============================================================================

def _initialize_default_configuration() -> Dict[str, Any]:
    """
    Initializes the configuration dictionary with default values from constants and models.
    
    This function creates the base configuration structure with all required fields
    populated with sensible default values. It serves as the foundation for the
    configuration merging process and ensures that all required fields are present
    even if not specified in other configuration sources.
    
    Returns:
        Dict[str, Any]: Configuration dictionary with default values for all sections.
    """
    return {
        # Authentication configuration defaults
        "access_key_id": None,  # Required field - no default
        "access_secret": None,  # Required field - no default
        "username": None,  # Optional field for token authentication
        "api_base_url": DEFAULT_API_BASE_URL,
        
        # Scope configuration defaults
        "notebook_id": None,  # Optional - no scope limitation by default
        "notebook_name": None,  # Optional - no scope limitation by default
        "folder_path": None,  # Optional - no scope limitation by default
        
        # Output configuration defaults
        "json_ld_enabled": False,  # Disabled by default
        "structured_output": True,  # Enabled by default for consistency
        
        # Logging configuration defaults
        "log_file": DEFAULT_LOG_FILE,
        "log_level": DEFAULT_LOG_LEVEL,
        "verbose": False,  # Disabled by default
        "quiet": False,  # Disabled by default
        
        # Server metadata defaults
        "server_name": MCP_SERVER_NAME,
        "server_version": MCP_SERVER_VERSION
    }


def _load_file_configuration(config_file_path: str) -> Dict[str, Any]:
    """
    Loads configuration from a JSON file with comprehensive error handling.
    
    Args:
        config_file_path (str): Path to the JSON configuration file.
    
    Returns:
        Dict[str, Any]: Configuration dictionary loaded from the file.
    
    Raises:
        LabArchivesMCPException: On file access or parsing errors.
    """
    try:
        # Read and parse the JSON configuration file
        file_config = read_json_file(config_file_path)
        
        # Validate that the loaded configuration is a dictionary
        if not isinstance(file_config, dict):
            raise LabArchivesMCPException(
                message=f"Configuration file must contain a JSON object, got {type(file_config).__name__}",
                code=4001,
                context={
                    "operation": "_load_file_configuration",
                    "file_path": config_file_path,
                    "config_type": type(file_config).__name__
                }
            )
        
        return file_config
        
    except LabArchivesMCPException:
        # Re-raise configuration-specific exceptions
        raise
    except Exception as e:
        # Handle any unexpected errors during file loading
        raise LabArchivesMCPException(
            message=f"Unexpected error loading configuration file '{config_file_path}': {str(e)}",
            code=4002,
            context={
                "operation": "_load_file_configuration",
                "file_path": config_file_path,
                "error_type": type(e).__name__,
                "error_details": str(e)
            }
        )


def _load_environment_configuration() -> Dict[str, Any]:
    """
    Loads configuration from environment variables with type conversion.
    
    This function reads all supported environment variables and converts them
    to appropriate types for the configuration system. It handles optional
    variables gracefully and provides type-safe conversion.
    
    Returns:
        Dict[str, Any]: Configuration dictionary loaded from environment variables.
    
    Raises:
        LabArchivesMCPException: On environment variable access or conversion errors.
    """
    try:
        env_config = {}
        
        # Authentication environment variables
        access_key_id = get_env_var("LABARCHIVES_AKID")
        if access_key_id is not None:
            env_config["access_key_id"] = access_key_id
        
        access_secret = get_env_var("LABARCHIVES_SECRET")
        if access_secret is not None:
            env_config["access_secret"] = access_secret
        
        username = get_env_var("LABARCHIVES_USER")
        if username is not None:
            env_config["username"] = username
        
        api_base_url = get_env_var("LABARCHIVES_API_BASE")
        if api_base_url is not None:
            env_config["api_base_url"] = api_base_url
        
        # Scope environment variables
        notebook_id = get_env_var("LABARCHIVES_NOTEBOOK_ID")
        if notebook_id is not None:
            env_config["notebook_id"] = notebook_id
        
        notebook_name = get_env_var("LABARCHIVES_NOTEBOOK_NAME")
        if notebook_name is not None:
            env_config["notebook_name"] = notebook_name
        
        folder_path = get_env_var("LABARCHIVES_FOLDER_PATH")
        if folder_path is not None:
            env_config["folder_path"] = folder_path
        
        # Output environment variables
        json_ld_enabled = get_env_var("LABARCHIVES_JSON_LD_ENABLED", cast_type=bool)
        if json_ld_enabled is not None:
            env_config["json_ld_enabled"] = json_ld_enabled
        
        structured_output = get_env_var("LABARCHIVES_STRUCTURED_OUTPUT", cast_type=bool)
        if structured_output is not None:
            env_config["structured_output"] = structured_output
        
        # Logging environment variables
        log_file = get_env_var("LABARCHIVES_LOG_FILE")
        if log_file is not None:
            env_config["log_file"] = log_file
        
        log_level = get_env_var("LABARCHIVES_LOG_LEVEL")
        if log_level is not None:
            env_config["log_level"] = log_level
        
        verbose = get_env_var("LABARCHIVES_VERBOSE", cast_type=bool)
        if verbose is not None:
            env_config["verbose"] = verbose
        
        quiet = get_env_var("LABARCHIVES_QUIET", cast_type=bool)
        if quiet is not None:
            env_config["quiet"] = quiet
        
        # Server metadata environment variables
        server_name = get_env_var("LABARCHIVES_SERVER_NAME")
        if server_name is not None:
            env_config["server_name"] = server_name
        
        server_version = get_env_var("LABARCHIVES_SERVER_VERSION")
        if server_version is not None:
            env_config["server_version"] = server_version
        
        return env_config
        
    except LabArchivesMCPException:
        # Re-raise configuration-specific exceptions
        raise
    except Exception as e:
        # Handle any unexpected errors during environment loading
        raise LabArchivesMCPException(
            message=f"Unexpected error loading environment configuration: {str(e)}",
            code=5001,
            context={
                "operation": "_load_environment_configuration",
                "error_type": type(e).__name__,
                "error_details": str(e)
            }
        )


def _merge_configuration_dicts(
    base_config: Dict[str, Any],
    overlay_config: Dict[str, Any],
    source_name: str
) -> Dict[str, Any]:
    """
    Merges two configuration dictionaries with overlay precedence.
    
    This function implements the configuration merging logic that respects
    precedence rules. Values from the overlay configuration take precedence
    over values in the base configuration, but only if they are not None.
    
    Args:
        base_config (Dict[str, Any]): Base configuration dictionary.
        overlay_config (Dict[str, Any]): Overlay configuration dictionary.
        source_name (str): Name of the configuration source for error reporting.
    
    Returns:
        Dict[str, Any]: Merged configuration dictionary with overlay precedence.
    
    Raises:
        LabArchivesMCPException: On merge errors or invalid configuration structure.
    """
    try:
        # Create a copy of the base configuration to avoid mutation
        merged_config = base_config.copy()
        
        # Overlay non-None values from the overlay configuration
        for key, value in overlay_config.items():
            if value is not None:
                merged_config[key] = value
        
        return merged_config
        
    except Exception as e:
        # Handle any unexpected errors during configuration merging
        raise LabArchivesMCPException(
            message=f"Unexpected error merging configuration from {source_name}: {str(e)}",
            code=6001,
            context={
                "operation": "_merge_configuration_dicts",
                "source_name": source_name,
                "base_config": base_config,
                "overlay_config": overlay_config,
                "error_type": type(e).__name__,
                "error_details": str(e)
            }
        )


def _construct_server_configuration(config_dict: Dict[str, Any]) -> ServerConfiguration:
    """
    Constructs a ServerConfiguration object from the merged configuration dictionary.
    
    This function creates all the individual configuration section objects
    (AuthenticationConfig, ScopeConfig, OutputConfig, LoggingConfig) and
    combines them into a single ServerConfiguration object.
    
    Args:
        config_dict (Dict[str, Any]): Merged configuration dictionary with all values.
    
    Returns:
        ServerConfiguration: Constructed configuration object with all sections.
    
    Raises:
        LabArchivesMCPException: On construction errors or missing required fields.
    """
    try:
        # Construct authentication configuration
        auth_config = AuthenticationConfig(
            access_key_id=config_dict.get("access_key_id"),
            access_secret=config_dict.get("access_secret"),
            username=config_dict.get("username"),
            api_base_url=config_dict.get("api_base_url", DEFAULT_API_BASE_URL)
        )
        
        # Validate authentication configuration
        validate_authentication_config(auth_config)
        
        # Construct scope configuration
        scope_config = ScopeConfig(
            notebook_id=config_dict.get("notebook_id"),
            notebook_name=config_dict.get("notebook_name"),
            folder_path=config_dict.get("folder_path")
        )
        
        # Validate scope configuration
        validate_scope_config(scope_config)
        
        # Construct output configuration
        output_config = OutputConfig(
            json_ld_enabled=config_dict.get("json_ld_enabled", False),
            structured_output=config_dict.get("structured_output", True)
        )
        
        # Validate output configuration
        validate_output_config(output_config)
        
        # Construct logging configuration
        logging_config = LoggingConfig(
            log_file=config_dict.get("log_file", DEFAULT_LOG_FILE),
            log_level=config_dict.get("log_level", DEFAULT_LOG_LEVEL),
            verbose=config_dict.get("verbose", False),
            quiet=config_dict.get("quiet", False)
        )
        
        # Validate logging configuration
        validate_logging_config(logging_config)
        
        # Construct server configuration
        server_config = ServerConfiguration(
            authentication=auth_config,
            scope=scope_config,
            output=output_config,
            logging=logging_config,
            server_name=config_dict.get("server_name", MCP_SERVER_NAME),
            server_version=config_dict.get("server_version", MCP_SERVER_VERSION)
        )
        
        return server_config
        
    except LabArchivesMCPException:
        # Re-raise configuration-specific exceptions
        raise
    except Exception as e:
        # Handle any unexpected errors during configuration construction
        raise LabArchivesMCPException(
            message=f"Unexpected error constructing server configuration: {str(e)}",
            code=7001,
            context={
                "operation": "_construct_server_configuration",
                "config_dict": config_dict,
                "error_type": type(e).__name__,
                "error_details": str(e)
            }
        )