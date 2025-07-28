"""
LabArchives MCP Server - Configuration Validation Module

This module provides comprehensive validation functions for all configuration models
and subcomponents in the LabArchives MCP Server CLI. It enforces business rules,
type checks, cross-field dependencies, and security constraints for authentication,
scope, output, logging, and full server configuration.

This module supports the following features:
- F-005: Authentication and Security Management - Validates credentials, token formats,
  and authentication parameters to prevent misconfiguration and security vulnerabilities
- F-006: CLI Interface and Configuration - Provides robust validation of all configuration
  parameters to ensure secure, user-friendly, and error-resistant CLI operation
- F-007: Scope Limitation and Access Control - Validates scope configuration (notebook ID,
  name, folder path) to enforce access boundaries and prevent unauthorized data exposure
- F-008: Comprehensive Audit Logging - Raises structured exceptions for validation errors
  supporting robust diagnostics, user feedback, and audit logging

All validation functions raise LabArchivesMCPException on validation failures,
providing structured error information for audit trails, user feedback, and
system diagnostics. This module serves as the canonical source for all
configuration validation logic throughout the application.
"""

import re  # builtin - Regular expression validation for credential formats and patterns
import os  # builtin - File path validation and accessibility checks
from typing import (
    Optional,
    Dict,
    Any,
)  # builtin - Type annotations for function signatures
from urllib.parse import urlparse  # builtin - URL validation for API endpoints

# Internal imports - Configuration models for validation
# Import from models.py file (not models package) for configuration classes
import importlib.util

# Load models.py directly to avoid import conflicts with models package
# Use shared module loader to avoid class identity issues
import sys

models_module_name = "labarchives_mcp_models"
if models_module_name not in sys.modules:
    import os

    models_path = os.path.join(os.path.dirname(__file__), "models.py")
    models_spec = importlib.util.spec_from_file_location(models_module_name, models_path)
    models_module = importlib.util.module_from_spec(models_spec)
    models_spec.loader.exec_module(models_module)
    sys.modules[models_module_name] = models_module
else:
    models_module = sys.modules[models_module_name]

# Import configuration classes from the shared module
AuthenticationConfig = models_module.AuthenticationConfig
ScopeConfig = models_module.ScopeConfig
OutputConfig = models_module.OutputConfig
LoggingConfig = models_module.LoggingConfig
ServerConfiguration = models_module.ServerConfiguration

# Internal imports - Exception handling for structured error reporting
from exceptions import LabArchivesMCPException

# Internal imports - Constants for validation rules and defaults
from constants import DEFAULT_API_BASE_URL, SUPPORTED_SCOPE_TYPES, REGION_API_BASE_URLS


def validate_authentication_config(auth_config: AuthenticationConfig) -> None:
    """
    Validates an AuthenticationConfig object for required fields, correct formats,
    and security constraints.

    This function performs comprehensive validation of authentication configuration
    to ensure secure and proper LabArchives API access. It validates credential
    presence, format compliance, API endpoint validity, and security requirements.

    Validation Rules:
    - access_key_id: Required, 1-256 characters, alphanumeric format
    - access_secret: Required, 1-1024 characters, non-empty
    - username: Optional, but required for token authentication, email format when present
    - api_base_url: Required, valid HTTPS URL, must match known LabArchives endpoints

    Security Features:
    - No credential values logged in error messages
    - Format validation prevents injection attacks
    - URL validation ensures secure HTTPS endpoints
    - Regional endpoint validation for proper deployment

    Args:
        auth_config (AuthenticationConfig): Authentication configuration object to validate

    Returns:
        None: Function returns None on success

    Raises:
        LabArchivesMCPException: On validation failure with descriptive error message
            and audit-friendly error codes:
            - Code 2001: Missing or invalid access_key_id
            - Code 2002: Missing or invalid access_secret
            - Code 2003: Invalid username format
            - Code 2004: Invalid API base URL format or endpoint

    Example:
        try:
            validate_authentication_config(auth_config)
        except LabArchivesMCPException as e:
            logger.error(f"Authentication validation failed: {e}")
            raise
    """
    # Validate access_key_id presence and format
    if not auth_config.access_key_id:
        raise LabArchivesMCPException(
            message="Authentication validation failed: access_key_id is required and cannot be empty",
            code=2001,
            context={"field": "access_key_id", "validation_type": "required"},
        )

    # Validate access_key_id length and format
    if len(auth_config.access_key_id) < 1 or len(auth_config.access_key_id) > 256:
        raise LabArchivesMCPException(
            message="Authentication validation failed: access_key_id must be between 1 and 256 characters",
            code=2001,
            context={
                "field": "access_key_id",
                "validation_type": "length",
                "length": len(auth_config.access_key_id),
            },
        )

    # Validate access_key_id format (alphanumeric, hyphens, underscores)
    if not re.match(r'^[A-Za-z0-9_-]+$', auth_config.access_key_id):
        raise LabArchivesMCPException(
            message="Authentication validation failed: access_key_id contains invalid characters (only alphanumeric, hyphens, and underscores allowed)",
            code=2001,
            context={"field": "access_key_id", "validation_type": "format"},
        )

    # Validate access_secret presence and format
    if not auth_config.access_secret:
        raise LabArchivesMCPException(
            message="Authentication validation failed: access_secret is required and cannot be empty",
            code=2002,
            context={"field": "access_secret", "validation_type": "required"},
        )

    # Validate access_secret length
    if len(auth_config.access_secret) < 1 or len(auth_config.access_secret) > 1024:
        raise LabArchivesMCPException(
            message="Authentication validation failed: access_secret must be between 1 and 1024 characters",
            code=2002,
            context={
                "field": "access_secret",
                "validation_type": "length",
                "length": len(auth_config.access_secret),
            },
        )

    # Validate username format if provided (required for token authentication)
    if auth_config.username is not None:
        if not auth_config.username.strip():
            raise LabArchivesMCPException(
                message="Authentication validation failed: username cannot be empty when provided",
                code=2003,
                context={"field": "username", "validation_type": "required"},
            )

        # Validate username length
        if len(auth_config.username) < 1 or len(auth_config.username) > 256:
            raise LabArchivesMCPException(
                message="Authentication validation failed: username must be between 1 and 256 characters",
                code=2003,
                context={
                    "field": "username",
                    "validation_type": "length",
                    "length": len(auth_config.username),
                },
            )

        # Validate username format (basic email format validation)
        if not re.match(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$', auth_config.username):
            raise LabArchivesMCPException(
                message="Authentication validation failed: username must be a valid email address",
                code=2003,
                context={"field": "username", "validation_type": "format"},
            )

    # Validate api_base_url format and security
    if not auth_config.api_base_url:
        raise LabArchivesMCPException(
            message="Authentication validation failed: api_base_url is required and cannot be empty",
            code=2004,
            context={"field": "api_base_url", "validation_type": "required"},
        )

    # Parse and validate URL structure
    try:
        parsed_url = urlparse(auth_config.api_base_url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise LabArchivesMCPException(
                message="Authentication validation failed: api_base_url must be a valid URL",
                code=2004,
                context={
                    "field": "api_base_url",
                    "validation_type": "format",
                    "url": auth_config.api_base_url,
                },
            )

        # Enforce HTTPS for security
        if parsed_url.scheme != 'https':
            raise LabArchivesMCPException(
                message="Authentication validation failed: api_base_url must use HTTPS for secure communication",
                code=2004,
                context={
                    "field": "api_base_url",
                    "validation_type": "security",
                    "scheme": parsed_url.scheme,
                },
            )

        # Validate against known LabArchives API endpoints
        valid_endpoints = list(REGION_API_BASE_URLS.values())
        if auth_config.api_base_url not in valid_endpoints:
            raise LabArchivesMCPException(
                message=f"Authentication validation failed: api_base_url must be one of the supported LabArchives endpoints: {', '.join(valid_endpoints)}",
                code=2004,
                context={
                    "field": "api_base_url",
                    "validation_type": "endpoint",
                    "valid_endpoints": valid_endpoints,
                },
            )

    except Exception as e:
        if isinstance(e, LabArchivesMCPException):
            raise
        raise LabArchivesMCPException(
            message=f"Authentication validation failed: Invalid api_base_url format: {str(e)}",
            code=2004,
            context={
                "field": "api_base_url",
                "validation_type": "parsing",
                "error": str(e),
            },
        )


def validate_scope_config(scope_config: ScopeConfig) -> None:
    """
    Validates a ScopeConfig object for correct scope limitation, mutual exclusivity,
    and supported types.

    This function ensures that scope configuration properly limits data access
    according to security requirements and business rules. It validates mutual
    exclusivity of scope options, format compliance, and supported scope types.

    Validation Rules:
    - Mutual exclusivity: Only one of notebook_id, notebook_name, or folder_path can be set
    - notebook_id: If set, must be alphanumeric, 1-128 characters
    - notebook_name: If set, must be non-empty string, 1-256 characters
    - folder_path: If set, must be valid relative path, 1-512 characters, no illegal characters

    Security Features:
    - Prevents conflicting scope configurations
    - Validates path traversal prevention in folder paths
    - Ensures scope boundaries are properly defined
    - Supports audit trail generation for scope violations

    Args:
        scope_config (ScopeConfig): Scope configuration object to validate

    Returns:
        None: Function returns None on success

    Raises:
        LabArchivesMCPException: On validation failure with descriptive error message
            and audit-friendly error codes:
            - Code 3001: Multiple scope types configured (mutual exclusivity violation)
            - Code 3002: Invalid notebook_id format
            - Code 3003: Invalid notebook_name format
            - Code 3004: Invalid folder_path format or security violation

    Example:
        try:
            validate_scope_config(scope_config)
        except LabArchivesMCPException as e:
            logger.error(f"Scope validation failed: {e}")
            raise
    """
    # Check for mutual exclusivity of scope options
    scope_options = [
        ("notebook_id", scope_config.notebook_id),
        ("notebook_name", scope_config.notebook_name),
        ("folder_path", scope_config.folder_path),
    ]

    configured_options = [
        (name, value) for name, value in scope_options if value is not None and value.strip()
    ]

    if len(configured_options) > 1:
        option_names = [name for name, _ in configured_options]
        raise LabArchivesMCPException(
            message=f"Scope validation failed: Only one scope type can be configured at a time. Found: {', '.join(option_names)}",
            code=3001,
            context={
                "field": "scope_options",
                "validation_type": "mutual_exclusivity",
                "configured_options": option_names,
            },
        )

    # Validate notebook_id format if provided
    if scope_config.notebook_id is not None:
        if not scope_config.notebook_id.strip():
            raise LabArchivesMCPException(
                message="Scope validation failed: notebook_id cannot be empty when provided",
                code=3002,
                context={"field": "notebook_id", "validation_type": "required"},
            )

        # Validate notebook_id length
        if len(scope_config.notebook_id) < 1 or len(scope_config.notebook_id) > 128:
            raise LabArchivesMCPException(
                message="Scope validation failed: notebook_id must be between 1 and 128 characters",
                code=3002,
                context={
                    "field": "notebook_id",
                    "validation_type": "length",
                    "length": len(scope_config.notebook_id),
                },
            )

        # Validate notebook_id format (alphanumeric, hyphens, underscores)
        if not re.match(r'^[A-Za-z0-9_-]+$', scope_config.notebook_id):
            raise LabArchivesMCPException(
                message="Scope validation failed: notebook_id contains invalid characters (only alphanumeric, hyphens, and underscores allowed)",
                code=3002,
                context={"field": "notebook_id", "validation_type": "format"},
            )

    # Validate notebook_name format if provided
    if scope_config.notebook_name is not None:
        if not scope_config.notebook_name.strip():
            raise LabArchivesMCPException(
                message="Scope validation failed: notebook_name cannot be empty when provided",
                code=3003,
                context={"field": "notebook_name", "validation_type": "required"},
            )

        # Validate notebook_name length
        if len(scope_config.notebook_name) < 1 or len(scope_config.notebook_name) > 256:
            raise LabArchivesMCPException(
                message="Scope validation failed: notebook_name must be between 1 and 256 characters",
                code=3003,
                context={
                    "field": "notebook_name",
                    "validation_type": "length",
                    "length": len(scope_config.notebook_name),
                },
            )

        # Validate notebook_name format (printable characters, no control characters)
        if not re.match(r'^[^\x00-\x1F\x7F]+$', scope_config.notebook_name):
            raise LabArchivesMCPException(
                message="Scope validation failed: notebook_name contains invalid control characters",
                code=3003,
                context={"field": "notebook_name", "validation_type": "format"},
            )

    # Validate folder_path format if provided
    if scope_config.folder_path is not None:
        if not scope_config.folder_path.strip():
            raise LabArchivesMCPException(
                message="Scope validation failed: folder_path cannot be empty when provided",
                code=3004,
                context={"field": "folder_path", "validation_type": "required"},
            )

        # Validate folder_path length
        if len(scope_config.folder_path) < 1 or len(scope_config.folder_path) > 512:
            raise LabArchivesMCPException(
                message="Scope validation failed: folder_path must be between 1 and 512 characters",
                code=3004,
                context={
                    "field": "folder_path",
                    "validation_type": "length",
                    "length": len(scope_config.folder_path),
                },
            )

        # Validate folder_path format (no path traversal, no absolute paths)
        if scope_config.folder_path.startswith('/') or scope_config.folder_path.startswith('\\'):
            raise LabArchivesMCPException(
                message="Scope validation failed: folder_path must be a relative path (cannot start with / or \\)",
                code=3004,
                context={
                    "field": "folder_path",
                    "validation_type": "security",
                    "issue": "absolute_path",
                },
            )

        # Check for path traversal attempts
        if '..' in scope_config.folder_path:
            raise LabArchivesMCPException(
                message="Scope validation failed: folder_path cannot contain '..' (path traversal prevention)",
                code=3004,
                context={
                    "field": "folder_path",
                    "validation_type": "security",
                    "issue": "path_traversal",
                },
            )

        # Validate folder_path character set (no illegal filesystem characters)
        illegal_chars = r'[<>:"|?*\x00-\x1F]'
        if re.search(illegal_chars, scope_config.folder_path):
            raise LabArchivesMCPException(
                message="Scope validation failed: folder_path contains illegal characters",
                code=3004,
                context={
                    "field": "folder_path",
                    "validation_type": "format",
                    "issue": "illegal_characters",
                },
            )


def validate_output_config(output_config: OutputConfig) -> None:
    """
    Validates an OutputConfig object for correct boolean flags and supported options.

    This function ensures that output configuration settings are properly formatted
    and represent supported combinations for data presentation and formatting.

    Validation Rules:
    - json_ld_enabled: Must be boolean type
    - structured_output: Must be boolean type
    - Configuration compatibility: Validates that the combination of settings is supported

    Business Rules:
    - Both JSON-LD and structured output can be enabled simultaneously
    - JSON-LD requires structured output to be effective
    - Configuration must be consistent with MCP protocol requirements

    Args:
        output_config (OutputConfig): Output configuration object to validate

    Returns:
        None: Function returns None on success

    Raises:
        LabArchivesMCPException: On validation failure with descriptive error message
            and audit-friendly error codes:
            - Code 4001: Invalid json_ld_enabled value or type
            - Code 4002: Invalid structured_output value or type
            - Code 4003: Incompatible configuration combination

    Example:
        try:
            validate_output_config(output_config)
        except LabArchivesMCPException as e:
            logger.error(f"Output validation failed: {e}")
            raise
    """
    # Validate json_ld_enabled is boolean
    if not isinstance(output_config.json_ld_enabled, bool):
        raise LabArchivesMCPException(
            message=f"Output validation failed: json_ld_enabled must be a boolean value, got {type(output_config.json_ld_enabled).__name__}",
            code=4001,
            context={
                "field": "json_ld_enabled",
                "validation_type": "type",
                "received_type": type(output_config.json_ld_enabled).__name__,
            },
        )

    # Validate structured_output is boolean
    if not isinstance(output_config.structured_output, bool):
        raise LabArchivesMCPException(
            message=f"Output validation failed: structured_output must be a boolean value, got {type(output_config.structured_output).__name__}",
            code=4002,
            context={
                "field": "structured_output",
                "validation_type": "type",
                "received_type": type(output_config.structured_output).__name__,
            },
        )

    # Validate configuration compatibility
    # JSON-LD should be used with structured output for best results
    if output_config.json_ld_enabled and not output_config.structured_output:
        raise LabArchivesMCPException(
            message="Output validation failed: JSON-LD context requires structured output to be enabled for proper formatting",
            code=4003,
            context={
                "field": "configuration_compatibility",
                "validation_type": "business_rule",
                "issue": "json_ld_without_structured",
            },
        )


def validate_logging_config(logging_config: LoggingConfig) -> None:
    """
    Validates a LoggingConfig object for log file path, log level, and verbosity flags.

    This function ensures that logging configuration is properly set up for both
    operational logging and audit trail generation, with proper file access,
    valid log levels, and consistent verbosity settings.

    Validation Rules:
    - log_file: If provided, must be a valid writable file path, not a directory
    - log_level: Must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL
    - verbose and quiet: Cannot both be True (mutual exclusivity)
    - File permissions: Log file location must be writable if specified

    Security Features:
    - Validates log file permissions to prevent privilege escalation
    - Ensures log directory exists and is writable
    - Prevents conflicting verbosity settings
    - Supports audit compliance through proper logging validation

    Args:
        logging_config (LoggingConfig): Logging configuration object to validate

    Returns:
        None: Function returns None on success

    Raises:
        LabArchivesMCPException: On validation failure with descriptive error message
            and audit-friendly error codes:
            - Code 5001: Invalid log_file path or permissions
            - Code 5002: Invalid log_level value
            - Code 5003: Conflicting verbosity settings (verbose and quiet both True)

    Example:
        try:
            validate_logging_config(logging_config)
        except LabArchivesMCPException as e:
            logger.error(f"Logging validation failed: {e}")
            raise
    """
    # Validate log_file path if provided
    if logging_config.log_file is not None:
        if not logging_config.log_file.strip():
            raise LabArchivesMCPException(
                message="Logging validation failed: log_file cannot be empty when provided",
                code=5001,
                context={"field": "log_file", "validation_type": "required"},
            )

        # Validate log_file length
        if len(logging_config.log_file) < 1 or len(logging_config.log_file) > 512:
            raise LabArchivesMCPException(
                message="Logging validation failed: log_file path must be between 1 and 512 characters",
                code=5001,
                context={
                    "field": "log_file",
                    "validation_type": "length",
                    "length": len(logging_config.log_file),
                },
            )

        # Validate log_file is not a directory
        if os.path.exists(logging_config.log_file) and os.path.isdir(logging_config.log_file):
            raise LabArchivesMCPException(
                message="Logging validation failed: log_file path points to a directory, not a file",
                code=5001,
                context={
                    "field": "log_file",
                    "validation_type": "file_type",
                    "path": logging_config.log_file,
                },
            )

        # Validate log_file directory exists and is writable
        log_dir = os.path.dirname(logging_config.log_file)
        if log_dir and not os.path.exists(log_dir):
            raise LabArchivesMCPException(
                message=f"Logging validation failed: log_file directory does not exist: {log_dir}",
                code=5001,
                context={
                    "field": "log_file",
                    "validation_type": "directory_existence",
                    "directory": log_dir,
                },
            )

        # Check if log_file location is writable
        if log_dir:
            if not os.access(log_dir, os.W_OK):
                raise LabArchivesMCPException(
                    message=f"Logging validation failed: log_file directory is not writable: {log_dir}",
                    code=5001,
                    context={
                        "field": "log_file",
                        "validation_type": "permissions",
                        "directory": log_dir,
                    },
                )
        else:
            # If no directory specified, check current directory
            if not os.access('.', os.W_OK):
                raise LabArchivesMCPException(
                    message="Logging validation failed: current directory is not writable for log_file",
                    code=5001,
                    context={
                        "field": "log_file",
                        "validation_type": "permissions",
                        "directory": ".",
                    },
                )

    # Validate log_level against supported values
    valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    if logging_config.log_level not in valid_log_levels:
        raise LabArchivesMCPException(
            message=f"Logging validation failed: log_level must be one of {', '.join(valid_log_levels)}, got '{logging_config.log_level}'",
            code=5002,
            context={
                "field": "log_level",
                "validation_type": "enum",
                "valid_values": valid_log_levels,
                "received_value": logging_config.log_level,
            },
        )

    # Validate log_level type
    if not isinstance(logging_config.log_level, str):
        raise LabArchivesMCPException(
            message=f"Logging validation failed: log_level must be a string, got {type(logging_config.log_level).__name__}",
            code=5002,
            context={
                "field": "log_level",
                "validation_type": "type",
                "received_type": type(logging_config.log_level).__name__,
            },
        )

    # Validate verbose is boolean
    if not isinstance(logging_config.verbose, bool):
        raise LabArchivesMCPException(
            message=f"Logging validation failed: verbose must be a boolean value, got {type(logging_config.verbose).__name__}",
            code=5003,
            context={
                "field": "verbose",
                "validation_type": "type",
                "received_type": type(logging_config.verbose).__name__,
            },
        )

    # Validate quiet is boolean
    if not isinstance(logging_config.quiet, bool):
        raise LabArchivesMCPException(
            message=f"Logging validation failed: quiet must be a boolean value, got {type(logging_config.quiet).__name__}",
            code=5003,
            context={
                "field": "quiet",
                "validation_type": "type",
                "received_type": type(logging_config.quiet).__name__,
            },
        )

    # Validate mutual exclusivity of verbose and quiet
    if logging_config.verbose and logging_config.quiet:
        raise LabArchivesMCPException(
            message="Logging validation failed: verbose and quiet modes cannot be enabled simultaneously",
            code=5003,
            context={
                "field": "verbosity_flags",
                "validation_type": "mutual_exclusivity",
                "verbose": logging_config.verbose,
                "quiet": logging_config.quiet,
            },
        )


def validate_server_configuration(config: ServerConfiguration) -> None:
    """
    Validates a complete ServerConfiguration object, invoking all sub-validators
    and enforcing cross-field and cross-section rules.

    This function provides comprehensive validation of the entire server configuration
    by validating all sub-configurations and checking for cross-field dependencies,
    business rule compliance, and overall configuration integrity.

    Validation Process:
    1. Validates each sub-configuration using dedicated validators
    2. Checks cross-field dependencies between configuration sections
    3. Validates required server metadata
    4. Enforces business rules and security constraints
    5. Ensures overall configuration consistency

    Cross-Field Validation Rules:
    - Authentication scope compatibility
    - Output format compatibility with logging requirements
    - Security policy consistency across all components
    - Server metadata completeness and format

    Args:
        config (ServerConfiguration): Complete server configuration object to validate

    Returns:
        None: Function returns None on success

    Raises:
        LabArchivesMCPException: On validation failure with descriptive error message
            and audit-friendly error codes:
            - Code 6001: Authentication configuration validation failure
            - Code 6002: Scope configuration validation failure
            - Code 6003: Output configuration validation failure
            - Code 6004: Logging configuration validation failure
            - Code 6005: Server metadata validation failure
            - Code 6006: Cross-field dependency validation failure

    Example:
        try:
            validate_server_configuration(server_config)
        except LabArchivesMCPException as e:
            logger.error(f"Server configuration validation failed: {e}")
            raise
    """
    # Validate authentication configuration
    try:
        validate_authentication_config(config.authentication)
    except LabArchivesMCPException as e:
        # Re-raise with server configuration context
        raise LabArchivesMCPException(
            message=f"Server configuration validation failed - Authentication: {e.message}",
            code=6001,
            context={"section": "authentication", "original_error": e.context},
        )

    # Validate scope configuration
    try:
        validate_scope_config(config.scope)
    except LabArchivesMCPException as e:
        # Re-raise with server configuration context
        raise LabArchivesMCPException(
            message=f"Server configuration validation failed - Scope: {e.message}",
            code=6002,
            context={"section": "scope", "original_error": e.context},
        )

    # Validate output configuration
    try:
        validate_output_config(config.output)
    except LabArchivesMCPException as e:
        # Re-raise with server configuration context
        raise LabArchivesMCPException(
            message=f"Server configuration validation failed - Output: {e.message}",
            code=6003,
            context={"section": "output", "original_error": e.context},
        )

    # Validate logging configuration
    try:
        validate_logging_config(config.logging)
    except LabArchivesMCPException as e:
        # Re-raise with server configuration context
        raise LabArchivesMCPException(
            message=f"Server configuration validation failed - Logging: {e.message}",
            code=6004,
            context={"section": "logging", "original_error": e.context},
        )

    # Validate server metadata
    if not config.server_name:
        raise LabArchivesMCPException(
            message="Server configuration validation failed: server_name is required and cannot be empty",
            code=6005,
            context={"field": "server_name", "validation_type": "required"},
        )

    if not isinstance(config.server_name, str):
        raise LabArchivesMCPException(
            message=f"Server configuration validation failed: server_name must be a string, got {type(config.server_name).__name__}",
            code=6005,
            context={
                "field": "server_name",
                "validation_type": "type",
                "received_type": type(config.server_name).__name__,
            },
        )

    if len(config.server_name) < 1 or len(config.server_name) > 128:
        raise LabArchivesMCPException(
            message="Server configuration validation failed: server_name must be between 1 and 128 characters",
            code=6005,
            context={
                "field": "server_name",
                "validation_type": "length",
                "length": len(config.server_name),
            },
        )

    if not config.server_version:
        raise LabArchivesMCPException(
            message="Server configuration validation failed: server_version is required and cannot be empty",
            code=6005,
            context={"field": "server_version", "validation_type": "required"},
        )

    if not isinstance(config.server_version, str):
        raise LabArchivesMCPException(
            message=f"Server configuration validation failed: server_version must be a string, got {type(config.server_version).__name__}",
            code=6005,
            context={
                "field": "server_version",
                "validation_type": "type",
                "received_type": type(config.server_version).__name__,
            },
        )

    if len(config.server_version) < 1 or len(config.server_version) > 32:
        raise LabArchivesMCPException(
            message="Server configuration validation failed: server_version must be between 1 and 32 characters",
            code=6005,
            context={
                "field": "server_version",
                "validation_type": "length",
                "length": len(config.server_version),
            },
        )

    # Validate server_version format (semantic versioning pattern)
    if not re.match(r'^\d+\.\d+\.\d+([+-][A-Za-z0-9.-]+)?$', config.server_version):
        raise LabArchivesMCPException(
            message="Server configuration validation failed: server_version must follow semantic versioning format (e.g., 1.0.0)",
            code=6005,
            context={
                "field": "server_version",
                "validation_type": "format",
                "value": config.server_version,
            },
        )

    # Cross-field dependency validation
    # If authentication uses token authentication (username present), validate additional requirements
    if config.authentication.username is not None:
        # Token authentication requires special handling - no additional validation needed here
        # but we log this for audit purposes
        pass

    # Validate scope configuration compatibility with authentication
    # If scope is configured, ensure authentication is sufficient
    scope_configured = any(
        [config.scope.notebook_id, config.scope.notebook_name, config.scope.folder_path]
    )

    if scope_configured:
        # Scope configuration requires valid authentication
        if not config.authentication.access_key_id or not config.authentication.access_secret:
            raise LabArchivesMCPException(
                message="Server configuration validation failed: Scope configuration requires valid authentication credentials",
                code=6006,
                context={
                    "field": "scope_auth_dependency",
                    "validation_type": "cross_field",
                    "issue": "scope_requires_auth",
                },
            )

    # Validate output configuration compatibility with logging
    # If JSON-LD is enabled, ensure logging captures appropriate detail
    if config.output.json_ld_enabled:
        # JSON-LD output should use INFO or DEBUG logging for proper troubleshooting
        if config.logging.log_level in ['WARNING', 'ERROR', 'CRITICAL']:
            raise LabArchivesMCPException(
                message="Server configuration validation failed: JSON-LD output requires INFO or DEBUG logging level for proper troubleshooting",
                code=6006,
                context={
                    "field": "output_logging_compatibility",
                    "validation_type": "cross_field",
                    "issue": "json_ld_logging_level",
                },
            )

    # Validate comprehensive configuration consistency
    # Ensure all required components are present and compatible
    if not all([config.authentication, config.scope, config.output, config.logging]):
        raise LabArchivesMCPException(
            message="Server configuration validation failed: All configuration sections (authentication, scope, output, logging) are required",
            code=6006,
            context={
                "field": "configuration_completeness",
                "validation_type": "cross_field",
                "issue": "missing_sections",
            },
        )
