"""
LabArchives MCP Server - Logging and Audit System Configuration

This module provides a centralized, reusable setup for Python's logging framework,
supporting configurable log file output, log levels, structured formatting, audit
trail generation, and integration with the application's configuration system.

This module implements:
- F-008: Comprehensive Audit Logging - Structured, configurable logging for all
  system events, data access operations, and errors with audit requirements
- F-006: CLI Interface and Configuration - User-configurable log file paths,
  log levels, and verbosity via CLI arguments and configuration files
- Centralized Configuration Management - Integration with configuration loader
  for dynamic logging settings at startup and on configuration reload
- Error Handling and Diagnostics - Structured, auditable format for all errors,
  warnings, and critical events
- Enhanced Security - URL parameter sanitization and command-line argument scrubbing
  using centralized Security Utilities to prevent credential exposure in logs

All logging operations are designed to be secure, compliant, and production-ready
with support for log rotation, structured output, comprehensive audit trails, and
fail-secure credential protection per security audit requirements.

Public Exports:
- get_logger(): Main application logger instance with default configuration
- get_audit_logger(): Audit logger instance for compliance and security monitoring
- setup_logging(): Primary logging configuration function
- reload_logging(): Runtime logging reconfiguration function
- sanitize_argv(): Enhanced command-line argument sanitization with URL support
- StructuredFormatter: Custom logging formatter for structured output
"""

import logging
import logging.handlers  # builtin - Provides RotatingFileHandler for log rotation
import os  # builtin - Used for file path expansion and directory creation
import sys  # builtin - Used for accessing sys.argv for early argument scrubbing
import json
from typing import Tuple, Optional

# Internal imports for logging configuration and constants
from constants import (
    DEFAULT_LOG_FILE,
    DEFAULT_AUDIT_LOG_FILE,
    DEFAULT_LOG_LEVEL,
    LOG_FORMAT_STRING,
    AUDIT_LOG_FORMAT_STRING,
)

# Import LoggingConfig directly from models.py to avoid circular import with models package
import importlib.util
import os

# Load LoggingConfig directly from models.py file
_models_path = os.path.join(os.path.dirname(__file__), 'models.py')
_spec = importlib.util.spec_from_file_location("models_direct", _models_path)
_models_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_models_module)
LoggingConfig = _models_module.LoggingConfig
from utils import scrub_argv
from security.sanitizers import sanitize_url_params

# =============================================================================
# Global State Management
# =============================================================================

# Global flag to track initialization state and prevent duplicate handlers
# This ensures idempotent setup and prevents multiple handler registration
_LOGGERS_INITIALIZED = False

# Global logger instances for reuse across the application
_MAIN_LOGGER: Optional[logging.Logger] = None
_AUDIT_LOGGER: Optional[logging.Logger] = None

# =============================================================================
# Enhanced Argument Sanitization with URL Parameter Support
# =============================================================================


def sanitize_argv(argv: list) -> list:
    """
    Enhanced command-line argument sanitization with URL parameter redaction support.

    This function extends the basic command-line argument scrubbing functionality to also
    detect and sanitize URLs that may be passed as command-line arguments. It combines
    traditional argument scrubbing (for flags like --password, --token) with URL parameter
    sanitization to ensure that sensitive query parameters within URLs are also redacted.

    The function integrates with the centralized Security Utilities module to provide
    consistent parameter masking policies across all logging operations, as required by
    the security audit findings for comprehensive credential protection.

    Features:
    - Traditional command-line flag value redaction (--password secret123)
    - URL parameter sanitization for URLs passed as arguments
    - Integration with centralized security utilities for consistent policies
    - Support for both separated (--flag value) and combined (--flag=value) formats
    - Automatic detection of URLs within command-line arguments
    - Fail-secure redaction that preserves argument structure for debugging

    Args:
        argv (list): List of command-line arguments to sanitize. Can be None or empty.

    Returns:
        list: Sanitized argument list with sensitive values and URL parameters redacted.
              All sensitive content is replaced with '[REDACTED]' markers while preserving
              argument names and URL structure for debugging purposes.

    Raises:
        None: This function is designed to be fail-safe and will not raise exceptions,
              ensuring that logging setup can proceed even if sanitization encounters
              unexpected input formats.

    Examples:
        >>> sanitize_argv(['--password', 'secret123', '--verbose'])
        ['--password', '[REDACTED]', '--verbose']

        >>> sanitize_argv(['--url', 'https://api.com/data?token=abc123&id=456'])
        ['--url', 'https://api.com/data?token=[REDACTED]&id=456']

        >>> sanitize_argv(['--api-key=secret123', '--endpoint=https://api.com?key=xyz'])
        ['--api-key=[REDACTED]', '--endpoint=https://api.com?key=[REDACTED]']
    """
    # Handle None or empty argv gracefully
    if not argv:
        return []

    try:
        # Step 1: Apply basic command-line argument scrubbing using existing utilities
        # This handles traditional credential flags like --password, --token, etc.
        # Filter to string arguments only for scrub_argv, preserve non-strings as-is
        string_args = [arg for arg in argv if isinstance(arg, str)]
        non_string_args = [(i, arg) for i, arg in enumerate(argv) if not isinstance(arg, str)]

        # Apply basic scrubbing to string arguments
        if string_args:
            scrubbed_strings = scrub_argv(string_args)
        else:
            scrubbed_strings = []

        # Reconstruct the full argument list with original positions preserved
        scrubbed_args = []
        string_index = 0
        for i, arg in enumerate(argv):
            if isinstance(arg, str):
                scrubbed_args.append(scrubbed_strings[string_index])
                string_index += 1
            else:
                scrubbed_args.append(arg)

        # Step 2: Apply URL parameter sanitization to detect URLs in arguments
        # This ensures that any URLs passed as argument values also get sanitized
        enhanced_args = []

        for arg in scrubbed_args:
            if not isinstance(arg, str):
                # Preserve non-string arguments as-is
                enhanced_args.append(arg)
                continue

            # Check if this argument contains a URL (either as standalone value or in --flag=value format)
            if '://' in arg:
                # Argument contains a URL - need to sanitize URL parameters
                # Check if '=' appears BEFORE '://' (indicating --flag=URL format)
                # vs. after '://' (indicating URL query parameters)
                url_start = arg.find('://')
                equals_pos = arg.find('=')

                if equals_pos != -1 and equals_pos < url_start:
                    # Handle --flag=URL format (= comes before ://)
                    key, url_value = arg.split('=', 1)
                    sanitized_url = sanitize_url_params(url_value)
                    enhanced_args.append(f"{key}={sanitized_url}")
                else:
                    # Handle standalone URL argument (no = before ://, or = is in query params)
                    sanitized_url = sanitize_url_params(arg)
                    enhanced_args.append(sanitized_url)
            else:
                # No URL detected - preserve the already scrubbed argument
                enhanced_args.append(arg)

        return enhanced_args

    except Exception:
        # Fail-safe: If sanitization encounters any errors, fall back to basic scrubbing
        # This ensures that logging setup can always proceed, even with unexpected input
        try:
            return scrub_argv(argv)
        except Exception:
            # Ultimate fallback: return original argv if all sanitization fails
            # This prevents logging initialization from failing due to sanitization errors
            return argv or []


# =============================================================================
# Structured Logging Formatter
# =============================================================================


class StructuredFormatter(logging.Formatter):
    """
    Custom logging formatter for structured log output with JSON and key-value support.

    This formatter enhances log records with structured data representation,
    supporting both JSON and key-value formatting for audit and diagnostic purposes.
    It extracts timestamp, level, component, message, and optional context from
    log records and formats them as structured strings for improved parsing
    and analysis.

    Features:
    - Structured JSON output for machine parsing
    - Key-value pair formatting for human readability
    - Context preservation for audit trails
    - Consistent timestamp formatting
    - Component identification for debugging

    The formatter supports both regular application logs and audit-specific
    logs with appropriate formatting for each use case.
    """

    def __init__(self, fmt: str = LOG_FORMAT_STRING, use_json: bool = False):
        """
        Initialize the formatter with specified format string or JSON mode.

        Args:
            fmt: Format string for log output (default: LOG_FORMAT_STRING)
            use_json: Enable JSON-structured output for machine parsing
        """
        super().__init__(fmt)
        self.use_json = use_json

    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record as a structured string with enhanced context.

        Extracts timestamp, level, component, message, and any extra context
        from the log record and formats it as either JSON or key-value pairs
        for improved audit and diagnostic capabilities.

        Args:
            record: The log record to format

        Returns:
            The formatted log record string with structured data
        """
        # Extract core log record information
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        level = record.levelname
        component = record.name
        message = record.getMessage()

        # Extract additional context from record if available
        context = {}

        # Check for custom attributes in the log record
        for attr_name in dir(record):
            if not attr_name.startswith('_') and attr_name not in {
                'name',
                'msg',
                'args',
                'levelname',
                'levelno',
                'pathname',
                'filename',
                'module',
                'exc_info',
                'exc_text',
                'stack_info',
                'lineno',
                'funcName',
                'created',
                'msecs',
                'relativeCreated',
                'thread',
                'threadName',
                'processName',
                'process',
                'message',
                'asctime',
            }:
                attr_value = getattr(record, attr_name)
                # Only include JSON-serializable attributes
                if isinstance(attr_value, (str, int, float, bool, type(None), list, dict)):
                    context[attr_name] = attr_value
                elif hasattr(attr_value, '__str__'):
                    # Convert other types to string representation
                    context[attr_name] = str(attr_value)

        # Format as JSON for machine parsing
        if self.use_json:
            structured_data = {
                "timestamp": timestamp,
                "level": level,
                "component": component,
                "message": message,
            }

            # Add context if available
            if context:
                structured_data["context"] = context

            # Add exception information if present
            if record.exc_info:
                structured_data["exception"] = self.formatException(record.exc_info)

            return json.dumps(structured_data, ensure_ascii=False)

        # Format as key-value pairs for human readability
        else:
            formatted_message = f"{timestamp} [{level}] {component}: {message}"

            # Append context information if available
            if context:
                context_str = " ".join([f"{k}={v}" for k, v in context.items()])
                formatted_message += f" | {context_str}"

            # Add exception information if present
            if record.exc_info:
                formatted_message += f"\n{self.formatException(record.exc_info)}"

            return formatted_message


# =============================================================================
# Core Logging Setup Functions
# =============================================================================


def setup_logging(
    logging_config: LoggingConfig,
) -> Tuple[logging.Logger, logging.Logger]:
    """
    Initialize the main application logger and audit logger with comprehensive configuration.

    This function configures both file and console logging with appropriate handlers,
    formatters, and log levels based on the provided LoggingConfig. It ensures
    idempotent setup by checking the global initialization state and prevents
    duplicate handler registration.

    Features:
    - Configurable log file output with automatic directory creation
    - Console output with appropriate formatting
    - Log rotation for file handlers to prevent disk space issues
    - Separate audit logger for compliance and security monitoring
    - Verbose and quiet mode support for different operational needs
    - Structured logging format for enhanced diagnostics

    Args:
        logging_config: LoggingConfig object containing log file, level, and verbosity settings

    Returns:
        Tuple of (main_logger, audit_logger) - The configured logger instances

    Raises:
        OSError: If log directory creation fails
        ValueError: If log level is invalid
    """
    global _LOGGERS_INITIALIZED, _MAIN_LOGGER, _AUDIT_LOGGER

    # CRITICAL: Scrub argv before any logging configuration occurs to prevent
    # credential leakage in logs. This must be the first operation to ensure
    # complete secret redaction from all logging paths per Section 0.2.1 requirement.
    # Enhanced sanitization now includes URL parameter redaction using Security Utilities.
    # Update sys.argv in place to ensure scrubbed version is used throughout the application.
    sys.argv[:] = sanitize_argv(sys.argv)

    # Check if logging has already been initialized to prevent duplicate handlers
    if _LOGGERS_INITIALIZED and _MAIN_LOGGER and _AUDIT_LOGGER:
        return _MAIN_LOGGER, _AUDIT_LOGGER

    # Determine log file path from configuration or use default
    log_file = logging_config.log_file or DEFAULT_LOG_FILE

    # Determine log level from configuration or use default
    log_level = logging_config.log_level or DEFAULT_LOG_LEVEL

    # Validate log level
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")

    # Create log directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError as e:
            raise OSError(f"Failed to create log directory '{log_dir}': {e}")

    # Create and configure main application logger
    _MAIN_LOGGER = logging.getLogger("labarchives_mcp")
    _MAIN_LOGGER.setLevel(numeric_level)

    # Clear any existing handlers to prevent duplicates
    _MAIN_LOGGER.handlers.clear()

    # Create rotating file handler for main logger
    if log_file:
        try:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB max file size
                backupCount=5,  # Keep 5 backup files
            )
            file_handler.setLevel(numeric_level)

            # Use structured formatter for file output
            file_formatter = StructuredFormatter(LOG_FORMAT_STRING, use_json=False)
            file_handler.setFormatter(file_formatter)

            _MAIN_LOGGER.addHandler(file_handler)
        except Exception as e:
            # If file handler creation fails, log warning but continue
            print(f"Warning: Failed to create file handler for {log_file}: {e}")

    # Create console handler for main logger
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)

    # Use standard formatter for console output
    console_formatter = logging.Formatter(LOG_FORMAT_STRING)
    console_handler.setFormatter(console_formatter)

    _MAIN_LOGGER.addHandler(console_handler)

    # Apply verbose/quiet mode settings
    if logging_config.verbose:
        # Enable debug level for verbose mode
        _MAIN_LOGGER.setLevel(logging.DEBUG)
        for handler in _MAIN_LOGGER.handlers:
            handler.setLevel(logging.DEBUG)
    elif logging_config.quiet:
        # Set to warning level for quiet mode
        _MAIN_LOGGER.setLevel(logging.WARNING)
        for handler in _MAIN_LOGGER.handlers:
            handler.setLevel(logging.WARNING)

    # Create and configure audit logger as separate instance
    _AUDIT_LOGGER = logging.getLogger("labarchives_mcp.audit")
    _AUDIT_LOGGER.setLevel(logging.INFO)  # Audit logs are always INFO level

    # Clear any existing handlers
    _AUDIT_LOGGER.handlers.clear()

    # Create audit log file path
    audit_log_file = DEFAULT_AUDIT_LOG_FILE
    if log_file:
        audit_log_dir = os.path.dirname(log_file)
        if audit_log_dir:
            audit_log_file = os.path.join(audit_log_dir, DEFAULT_AUDIT_LOG_FILE)

    # Create rotating file handler for audit logger
    try:
        audit_file_handler = logging.handlers.RotatingFileHandler(
            audit_log_file,
            maxBytes=50 * 1024 * 1024,  # 50MB max file size for audit logs
            backupCount=10,  # Keep 10 backup files for audit compliance
        )
        audit_file_handler.setLevel(logging.INFO)

        # Use structured formatter for audit logs
        audit_formatter = StructuredFormatter(AUDIT_LOG_FORMAT_STRING, use_json=True)
        audit_file_handler.setFormatter(audit_formatter)

        _AUDIT_LOGGER.addHandler(audit_file_handler)
    except Exception as e:
        # If audit file handler creation fails, log error but continue
        _MAIN_LOGGER.error(f"Failed to create audit file handler for {audit_log_file}: {e}")

    # Prevent audit logger from propagating to root logger
    _AUDIT_LOGGER.propagate = False

    # Mark loggers as initialized
    _LOGGERS_INITIALIZED = True

    # Log successful initialization
    _MAIN_LOGGER.info(
        f"Logging initialized - Main log: {log_file}, Audit log: {audit_log_file}, Level: {log_level}"
    )
    _AUDIT_LOGGER.info("Audit logging initialized", extra={"event": "audit_system_start"})

    return _MAIN_LOGGER, _AUDIT_LOGGER


def get_logger() -> logging.Logger:
    """
    Retrieve the main application logger, initializing with defaults if necessary.

    This function provides access to the main application logger for modules
    that need to log events without direct access to the configuration. If
    the logger has not been initialized, it will be set up with default
    LoggingConfig settings.

    Returns:
        The main application logger instance
    """
    global _MAIN_LOGGER, _LOGGERS_INITIALIZED

    # Initialize with default settings if not already configured
    if not _LOGGERS_INITIALIZED or not _MAIN_LOGGER:
        default_config = LoggingConfig()
        setup_logging(default_config)

    return _MAIN_LOGGER


def get_audit_logger() -> logging.Logger:
    """
    Retrieve the audit logger, initializing with defaults if necessary.

    This function provides access to the audit logger for modules that need
    to log audit events without direct access to the configuration. If the
    logger has not been initialized, it will be set up with default
    LoggingConfig settings.

    Returns:
        The audit logger instance
    """
    global _AUDIT_LOGGER, _LOGGERS_INITIALIZED

    # Initialize with default settings if not already configured
    if not _LOGGERS_INITIALIZED or not _AUDIT_LOGGER:
        default_config = LoggingConfig()
        setup_logging(default_config)

    return _AUDIT_LOGGER


def reload_logging(
    logging_config: LoggingConfig,
) -> Tuple[logging.Logger, logging.Logger]:
    """
    Reconfigure the logging system at runtime with new configuration settings.

    This function allows for dynamic reconfiguration of the logging system,
    typically used after configuration reload events. It removes all existing
    handlers from both main and audit loggers and reinitializes them with
    the new configuration.

    Features:
    - Complete handler cleanup to prevent resource leaks
    - Fresh configuration application
    - Maintains audit trail continuity
    - Supports runtime configuration changes

    Args:
        logging_config: New LoggingConfig with updated settings

    Returns:
        Tuple of (main_logger, audit_logger) - The reconfigured logger instances
    """
    global _LOGGERS_INITIALIZED, _MAIN_LOGGER, _AUDIT_LOGGER

    # Log the reconfiguration event before removing handlers
    if _MAIN_LOGGER:
        _MAIN_LOGGER.info("Reconfiguring logging system with new settings")

    if _AUDIT_LOGGER:
        _AUDIT_LOGGER.info(
            "Logging configuration reload initiated", extra={"event": "logging_reload"}
        )

    # Remove all existing handlers from both loggers
    if _MAIN_LOGGER:
        for handler in _MAIN_LOGGER.handlers[:]:
            handler.close()
            _MAIN_LOGGER.removeHandler(handler)

    if _AUDIT_LOGGER:
        for handler in _AUDIT_LOGGER.handlers[:]:
            handler.close()
            _AUDIT_LOGGER.removeHandler(handler)

    # Reset initialization state to force fresh setup
    _LOGGERS_INITIALIZED = False
    _MAIN_LOGGER = None
    _AUDIT_LOGGER = None

    # Reinitialize with new configuration
    return setup_logging(logging_config)
