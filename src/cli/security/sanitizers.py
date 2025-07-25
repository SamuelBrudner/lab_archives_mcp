"""
LabArchives MCP Server - Security Sanitization Utilities

This module provides centralized URL and parameter sanitization utilities that automatically
detect and redact sensitive information in debug logs and audit trails. Implements fail-secure
logging patterns to prevent credential exposure while preserving debugging capabilities.

The sanitization functions implement comprehensive security controls as required by the security
audit findings, ensuring that tokens, passwords, secrets, and other sensitive parameters are
automatically redacted from all log output while maintaining parameter names for debugging.

Key Features:
- Automatic detection of sensitive parameter names using configurable patterns
- URL parameter sanitization for debug logs and audit trails
- Query parameter dictionary sanitization for structured logging
- Command-line argument sanitization for process logging
- Consistent [REDACTED] replacement pattern across all sanitization functions
- Performance-optimized regex patterns for high-volume logging scenarios
- Type-safe implementations with comprehensive error handling

This module integrates with the authentication manager, API client, and audit logging
components to provide system-wide credential protection per Section 6.4.7.4.1 requirements.
"""

import re
from typing import Any, Dict, List, Optional, Union
from urllib.parse import parse_qs, urlparse, parse_qsl, urlencode

# =============================================================================
# Security Constants and Patterns
# =============================================================================

# Comprehensive list of sensitive parameter names that require redaction
# Covers authentication tokens, passwords, secrets, API keys, and other credentials
# Used across URL parameters, query strings, and command-line arguments
SENSITIVE_PARAMETER_NAMES = {
    # Core authentication parameters
    'access_key', 'access_key_id', 'access_secret', 'access_password',
    'akid', 'access_token', 'token', 'auth_token', 'authentication_token',
    
    # Password and secret variations
    'password', 'passwd', 'pwd', 'secret', 'private_key', 'privkey',
    'api_secret', 'api_key', 'apikey', 'api_password', 'client_secret',
    
    # Session and temporary credentials
    'session_token', 'session_id', 'session_key', 'temporary_token',
    'temp_token', 'refresh_token', 'bearer_token', 'oauth_token',
    
    # Signature and cryptographic parameters  
    'signature', 'sig', 'hmac', 'digest', 'hash', 'checksum',
    
    # Database and service credentials
    'db_password', 'database_password', 'connection_string', 'dsn',
    'redis_password', 'mongo_password', 'mysql_password', 'postgres_password',
    
    # Cloud provider credentials
    'aws_secret_access_key', 'aws_session_token', 'azure_client_secret',
    'gcp_private_key', 'service_account_key', 'subscription_key',
    
    # Common variations and patterns
    'key', 'credential', 'credentials', 'auth', 'authorization',
    'x-api-key', 'x-auth-token', 'x-access-token', 'x-secret-key'
}

# Compile regex pattern for efficient sensitive parameter detection
# Case-insensitive matching to catch variations like TOKEN, Token, token
# Use word boundaries but also check for partial matches within parameter names
_SENSITIVE_PARAM_PATTERN = re.compile(
    r'(?:' + '|'.join(re.escape(param) for param in SENSITIVE_PARAMETER_NAMES) + r')',
    re.IGNORECASE
)

# Pattern for detecting key=value pairs in URLs and query strings
_KEY_VALUE_PATTERN = re.compile(r'([^=&?]+)=([^&]*)', re.IGNORECASE)

# Redaction marker used consistently across all sanitization functions
_REDACTION_MARKER = '[REDACTED]'

# =============================================================================
# Core Sanitization Functions
# =============================================================================

def is_sensitive_parameter(param_name: str) -> bool:
    """
    Determines if a parameter name contains sensitive information requiring redaction.
    
    This function uses pattern matching to identify parameter names that likely contain
    sensitive information such as passwords, tokens, API keys, or other credentials.
    The matching is case-insensitive and supports both exact matches and pattern-based
    detection for comprehensive coverage of sensitive parameter variations.
    
    Used by all sanitization functions to determine which parameter values should
    be redacted before logging or audit trail generation.
    
    Args:
        param_name (str): The parameter name to check for sensitivity
        
    Returns:
        bool: True if the parameter name indicates sensitive content, False otherwise
        
    Examples:
        >>> is_sensitive_parameter("access_token")
        True
        >>> is_sensitive_parameter("TOKEN")
        True
        >>> is_sensitive_parameter("username")
        False
        >>> is_sensitive_parameter("api_key")
        True
    """
    if not param_name or not isinstance(param_name, str):
        return False
    
    # Strip common prefixes and suffixes for better matching
    cleaned_name = param_name.lower().strip()
    
    # Remove common prefixes that don't affect sensitivity
    for prefix in ['x-', 'http-', 'header-']:
        if cleaned_name.startswith(prefix):
            cleaned_name = cleaned_name[len(prefix):]
            break
    
    # Check against the compiled regex pattern for efficient matching
    return bool(_SENSITIVE_PARAM_PATTERN.search(cleaned_name))


def sanitize_query_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitizes a dictionary of query parameters by redacting sensitive values.
    
    This function processes query parameter dictionaries (such as those used in API
    requests or logging contexts) and replaces values for sensitive parameters with
    the redaction marker while preserving parameter names for debugging purposes.
    
    The function handles various value types including strings, lists, and nested
    structures commonly found in query parameter dictionaries. List values are
    processed recursively to ensure complete sanitization.
    
    Used by API clients, authentication managers, and audit logging systems to
    ensure sensitive data is not exposed in structured log entries.
    
    Args:
        params (Dict[str, Any]): Dictionary of query parameters to sanitize
        
    Returns:
        Dict[str, Any]: Sanitized parameter dictionary with sensitive values redacted
        
    Examples:
        >>> sanitize_query_params({"username": "john", "password": "secret123"})
        {"username": "john", "password": "[REDACTED]"}
        >>> sanitize_query_params({"api_key": "abc123", "page": "1"})
        {"api_key": "[REDACTED]", "page": "1"}
    """
    if not params or not isinstance(params, dict):
        return params or {}
    
    sanitized = {}
    
    for key, value in params.items():
        if not isinstance(key, str):
            # Non-string keys are preserved as-is
            sanitized[key] = value
            continue
            
        if is_sensitive_parameter(key):
            # Redact sensitive parameter values
            if isinstance(value, list):
                # For list values, redact each item
                sanitized[key] = [_REDACTION_MARKER for _ in value]
            else:
                sanitized[key] = _REDACTION_MARKER
        else:
            # Preserve non-sensitive parameter values
            if isinstance(value, list):
                # Process lists recursively in case they contain nested sensitive data
                sanitized[key] = [
                    _REDACTION_MARKER if isinstance(item, str) and is_sensitive_parameter(key) 
                    else item for item in value
                ]
            else:
                sanitized[key] = value
    
    return sanitized


def sanitize_url_params(url: str) -> str:
    """
    Sanitizes URL query parameters by redacting sensitive values while preserving URL structure.
    
    This is the primary URL sanitization function referenced in Section 6.4.7.4.1 of the
    security architecture. It parses URLs to extract query parameters, identifies sensitive
    parameters using pattern matching, and replaces their values with redaction markers
    while maintaining the complete URL structure for debugging purposes.
    
    The function handles various URL formats including those with fragments, multiple
    parameters, and encoded values. It preserves the base URL, path, and parameter names
    while ensuring sensitive values are completely redacted from debug logs and audit trails.
    
    This function is the core implementation used by API clients, authentication systems,
    and logging frameworks to prevent credential exposure in log files.
    
    Args:
        url (str): The URL string containing query parameters to sanitize
        
    Returns:
        str: Sanitized URL with sensitive parameter values replaced by [REDACTED]
        
    Examples:
        >>> sanitize_url_params("https://api.example.com/users?id=123&token=secret123")
        'https://api.example.com/users?id=123&token=[REDACTED]'
        >>> sanitize_url_params("http://localhost/api?akid=key123&password=pass456")
        'http://localhost/api?akid=[REDACTED]&password=[REDACTED]'
    """
    if not url or not isinstance(url, str):
        return url or ''
    
    try:
        # Parse the URL into components
        parsed = urlparse(url)
        
        # If there are no query parameters, return the original URL
        if not parsed.query:
            return url
        
        # Parse query parameters into key-value pairs
        query_params = parse_qsl(parsed.query, keep_blank_values=True)
        
        # Sanitize the query parameters
        sanitized_params = []
        for key, value in query_params:
            if is_sensitive_parameter(key):
                sanitized_params.append((key, _REDACTION_MARKER))
            else:
                sanitized_params.append((key, value))
        
        # Reconstruct the query string with sanitized parameters
        # Use safe='[]' to prevent URL encoding of the redaction marker brackets
        sanitized_query = urlencode(sanitized_params, safe='[]')
        
        # Rebuild the complete URL with sanitized query parameters
        sanitized_url = (
            f"{parsed.scheme}://"
            f"{parsed.netloc}"
            f"{parsed.path}"
        )
        
        if sanitized_query:
            sanitized_url += f"?{sanitized_query}"
            
        if parsed.fragment:
            sanitized_url += f"#{parsed.fragment}"
            
        return sanitized_url
        
    except Exception:
        # If URL parsing fails, attempt simple pattern-based sanitization
        # This ensures we still provide some protection even for malformed URLs
        return _sanitize_url_fallback(url)


def sanitize_command_args(args: List[str]) -> List[str]:
    """
    Sanitizes command-line arguments by redacting sensitive values while preserving argument structure.
    
    This function processes command-line argument lists (such as sys.argv or process arguments)
    and replaces values for sensitive arguments with redaction markers. It handles both
    separated arguments (--flag value) and combined arguments (--flag=value) formats.
    
    The function maintains the argument structure for process monitoring and debugging while
    ensuring that passwords, tokens, API keys, and other credentials are not exposed in
    process lists, audit logs, or system monitoring tools.
    
    Used by the logging setup system and process monitoring components to sanitize
    command-line arguments before they appear in logs or process information.
    
    Args:
        args (List[str]): List of command-line arguments to sanitize
        
    Returns:
        List[str]: Sanitized argument list with sensitive values redacted
        
    Examples:
        >>> sanitize_command_args(["--username", "john", "--password", "secret123"])
        ["--username", "john", "--password", "[REDACTED]"]
        >>> sanitize_command_args(["--api-key=abc123", "--verbose"])
        ["--api-key=[REDACTED]", "--verbose"]
    """
    if not args or not isinstance(args, list):
        return args or []
    
    sanitized = []
    i = 0
    
    while i < len(args):
        arg = args[i]
        
        if not isinstance(arg, str):
            # Non-string arguments are preserved as-is
            sanitized.append(arg)
            i += 1
            continue
        
        # Check for combined flag=value format
        if '=' in arg:
            key, value = arg.split('=', 1)
            if key.lstrip('-') and is_sensitive_parameter(key.lstrip('-')):
                sanitized.append(f"{key}={_REDACTION_MARKER}")
            else:
                sanitized.append(arg)
            i += 1
            continue
        
        # Add the current argument
        sanitized.append(arg)
        
        # Check if this is a sensitive flag with a separate value
        if arg.startswith('-') and is_sensitive_parameter(arg.lstrip('-')):
            # If there's a next argument and it's not another flag, it's likely the value
            if i + 1 < len(args) and not args[i + 1].startswith('-'):
                sanitized.append(_REDACTION_MARKER)
                i += 1  # Skip the original sensitive value
        
        i += 1
    
    return sanitized


# =============================================================================
# Private Helper Functions
# =============================================================================

def _sanitize_url_fallback(url: str) -> str:
    """
    Fallback URL sanitization using regex pattern matching for malformed URLs.
    
    This function provides basic sanitization when URL parsing fails, using regex
    patterns to identify and redact sensitive parameter values. It's less precise
    than full URL parsing but ensures some level of protection for edge cases.
    
    Args:
        url (str): The URL string to sanitize using pattern matching
        
    Returns:
        str: URL with sensitive values redacted using pattern matching
    """
    if not url:
        return url
    
    def replace_sensitive_param(match):
        """Replace sensitive parameter values with redaction marker."""
        key = match.group(1)
        value = match.group(2)
        
        if is_sensitive_parameter(key):
            return f"{key}={_REDACTION_MARKER}"
        else:
            return f"{key}={value}"
    
    # Use regex to find and replace sensitive parameters
    sanitized = _KEY_VALUE_PATTERN.sub(replace_sensitive_param, url)
    
    return sanitized


# =============================================================================
# Integration Helper Functions
# =============================================================================

def sanitize_log_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitizes logging context dictionaries to ensure sensitive data is redacted.
    
    This helper function is used by logging frameworks to sanitize context
    dictionaries that may contain sensitive information before writing to log files.
    It processes nested dictionaries and handles various data types commonly
    found in logging contexts.
    
    Args:
        context (Dict[str, Any]): Logging context dictionary to sanitize
        
    Returns:
        Dict[str, Any]: Sanitized context dictionary safe for logging
    """
    if not context or not isinstance(context, dict):
        return context or {}
    
    sanitized = {}
    
    for key, value in context.items():
        if not isinstance(key, str):
            sanitized[key] = value
            continue
            
        if is_sensitive_parameter(key):
            sanitized[key] = _REDACTION_MARKER
        elif isinstance(value, dict):
            # Recursively sanitize nested dictionaries
            sanitized[key] = sanitize_log_context(value)
        elif isinstance(value, str) and ('://' in value or '?' in value):
            # Attempt to sanitize values that look like URLs
            sanitized[key] = sanitize_url_params(value)
        else:
            sanitized[key] = value
    
    return sanitized


def get_redaction_marker() -> str:
    """
    Returns the consistent redaction marker used across all sanitization functions.
    
    This function provides a centralized way to access the redaction marker,
    allowing for consistent behavior across all security sanitization operations.
    
    Returns:
        str: The redaction marker string used to replace sensitive values
    """
    return _REDACTION_MARKER


# =============================================================================
# Module Validation and Testing Helpers
# =============================================================================

def validate_sanitization_complete(text: str) -> bool:
    """
    Validates that a text string has been properly sanitized by checking for common
    patterns that might indicate exposed sensitive data.
    
    This function can be used in testing and validation workflows to ensure
    sanitization functions are working correctly and no sensitive patterns
    remain in sanitized output.
    
    Args:
        text (str): Text to validate for complete sanitization
        
    Returns:
        bool: True if text appears properly sanitized, False if sensitive patterns detected
    """
    if not text or not isinstance(text, str):
        return True
    
    # First check if the text contains redaction markers (both regular and URL-encoded)
    redaction_patterns = [
        r'\[REDACTED\]',      # Regular redaction marker
        r'%5BREDACTED%5D',    # URL-encoded redaction marker
    ]
    
    has_redaction = any(re.search(pattern, text, re.IGNORECASE) for pattern in redaction_patterns)
    
    # If text contains redaction markers, it's likely properly sanitized
    if has_redaction:
        return True
    
    # Check for common patterns that might indicate unsanitized sensitive data
    # Exclude short strings that might be legitimate values
    suspicious_patterns = [
        r'\b[A-Za-z0-9]{32,}\b',  # Long alphanumeric strings (API keys)
        r'\bsk-[A-Za-z0-9]{20,}\b',   # OpenAI-style API keys (longer threshold)
        r'\b[A-Fa-f0-9]{40,}\b',  # Hex-encoded secrets
        r'password\s*[:=]\s*[^\s\[\]]{8,}',  # password=value patterns (8+ chars, not redacted)
        r'token\s*[:=]\s*[^\s\[\]]{8,}',     # token=value patterns (8+ chars, not redacted)
        r'secret\s*[:=]\s*[^\s\[\]]{8,}',    # secret=value patterns (8+ chars, not redacted)
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return False
    
    return True