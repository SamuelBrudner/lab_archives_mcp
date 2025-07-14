"""
MCP Protocol Error Handling and Exception Management

This module defines the standardized error codes, exception classes, and error handling utilities
for the MCP protocol layer of the LabArchives MCP Server. It provides a comprehensive error
taxonomy for all MCP protocol operations, including protocol violations, resource not found
errors, authentication failures, scope violations, and rate limiting.

The module centralizes error code definitions and implements the MCPError exception hierarchy,
ensuring all errors are represented in a structured, auditable, and protocol-compliant manner.
It supports robust diagnostics, audit logging, and graceful degradation in the face of protocol
or resource errors.

Key Features:
- Standardized MCP protocol error codes following JSON-RPC 2.0 specification
- Comprehensive error messages for user-friendly reporting
- MCPProtocolError class inheriting from MCPError for protocol-specific errors
- Centralized error handling function for converting exceptions to MCP protocol responses
- Extensive audit logging support for compliance and diagnostics
- Structured error responses compatible with MCP clients like Claude Desktop

This module is essential for maintaining protocol compliance, supporting comprehensive audit
trails, and providing robust error handling throughout the MCP server implementation.
"""

from typing import Optional, Dict, Any  # Python 3.5+ builtin typing module for type hints
import logging  # Python 3.0+ builtin logging module for audit and diagnostic logging

# Import the base MCPError class from the centralized exception hierarchy
from src.cli.exceptions import MCPError


# =============================================================================
# MCP Protocol Error Codes
# =============================================================================

# Standardized error codes for all MCP protocol and resource operations
# These codes follow the JSON-RPC 2.0 specification and MCP protocol standards
# to ensure compatibility with MCP clients and proper error handling
MCP_ERROR_CODES: Dict[str, int] = {
    # JSON-RPC 2.0 Standard Error Codes
    # Reference: https://www.jsonrpc.org/specification#error_object
    'INVALID_REQUEST': -32600,      # Invalid JSON-RPC request format or structure
    'METHOD_NOT_FOUND': -32601,     # Requested MCP method is not implemented or available
    'INVALID_PARAMS': -32602,       # Invalid parameters provided to MCP method
    'INTERNAL_ERROR': -32603,       # Internal server error during MCP operation
    
    # MCP Protocol-Specific Error Codes
    # Custom error codes in the server error range (-32000 to -32099)
    'RESOURCE_NOT_FOUND': -32004,   # Requested LabArchives resource not found or inaccessible
    'AUTHENTICATION_FAILED': -32005, # LabArchives API authentication failure
    'SCOPE_VIOLATION': -32006,      # Resource access outside configured scope boundaries
    'RATE_LIMITED': -32007,         # Too many requests, rate limiting enforced
}

# Standardized error messages for all MCP protocol and resource operations
# These messages provide human-readable descriptions that are user-friendly
# while maintaining technical accuracy for diagnostic purposes
MCP_ERROR_MESSAGES: Dict[str, str] = {
    # JSON-RPC 2.0 Standard Error Messages
    'INVALID_REQUEST': 'Invalid JSON-RPC request.',
    'METHOD_NOT_FOUND': 'Requested method not found.',
    'INVALID_PARAMS': 'Invalid parameters for method.',
    'INTERNAL_ERROR': 'Internal server error.',
    
    # MCP Protocol-Specific Error Messages
    'RESOURCE_NOT_FOUND': 'Requested resource not found.',
    'AUTHENTICATION_FAILED': 'Authentication failed.',
    'SCOPE_VIOLATION': 'Resource access is outside the configured scope.',
    'RATE_LIMITED': 'Too many requests. Rate limit exceeded.',
}


# =============================================================================
# MCP Protocol Exception Classes
# =============================================================================

class MCPProtocolError(MCPError):
    """
    Exception class for all MCP protocol-specific errors.
    
    This class inherits from MCPError and provides a standard interface for error code,
    message, and optional context. It is used for protocol violations, method not found
    errors, invalid parameters, resource access failures, and other protocol-level errors.
    
    The class ensures all MCP protocol errors are properly structured with the required
    error code (following JSON-RPC 2.0 standards), human-readable message, and optional
    context object for diagnostic information.
    
    Common use cases include:
    - Invalid JSON-RPC request format (-32600)
    - Unimplemented MCP methods (-32601)
    - Invalid method parameters (-32602)
    - Internal server errors (-32603)
    - Resource not found errors (-32004)
    - Authentication failures (-32005)
    - Scope violations (-32006)
    - Rate limiting (-32007)
    
    The context parameter can contain additional diagnostic information such as:
    - Original protocol request object
    - Resource URI being accessed
    - Authentication details (excluding sensitive data)
    - Client connection information
    - Timestamp and request ID for audit trails
    
    Example:
        raise MCPProtocolError(
            message="Resource not found: labarchives://notebook/123",
            code=MCP_ERROR_CODES['RESOURCE_NOT_FOUND'],
            context={
                "resource_uri": "labarchives://notebook/123",
                "request_id": "req_456",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        )
    """
    
    def __init__(self, message: str, code: int, context: Optional[Any] = None):
        """
        Initialize the MCPProtocolError with a message, error code, and optional context.
        
        This constructor ensures that all MCP protocol errors are properly structured
        with the required components for JSON-RPC 2.0 compliance and MCP protocol
        specifications. The error code is required for proper client handling and
        protocol compliance.
        
        Args:
            message (str): Human-readable error description that will be displayed to
                          users and included in error responses. Should be clear and
                          actionable, providing enough information for troubleshooting.
            code (int): Numeric error code following JSON-RPC 2.0 standards. Should
                       use one of the standardized codes from MCP_ERROR_CODES for
                       consistency and proper client handling.
            context (Optional[Any]): Optional context object containing additional
                                    diagnostic information such as the protocol request,
                                    resource URI, client details, or other relevant data
                                    for debugging and audit logging.
        
        Example:
            error = MCPProtocolError(
                message="Invalid parameters for resources/read method",
                code=MCP_ERROR_CODES['INVALID_PARAMS'],
                context={"method": "resources/read", "params": {"uri": "invalid_uri"}}
            )
        """
        # Call the parent MCPError constructor with the provided parameters
        # This ensures proper initialization of the base exception hierarchy
        # and maintains consistency with the overall exception framework
        super().__init__(message, code, context)
        
        # Store the parameters as instance properties for access by error handlers,
        # logging systems, diagnostic tools, and MCP protocol response generators
        self.message = message
        self.code = code
        self.context = context
    
    def __str__(self) -> str:
        """
        Return a string representation of the MCP protocol error with message and code.
        
        This method provides a formatted string representation specifically for MCP
        protocol errors, always including the error code since it's required for
        MCP protocol compliance and client error handling.
        
        The string format is designed to be informative for both MCP clients and
        developers, providing the error code that clients need for programmatic
        error handling along with the human-readable message for user display.
        
        Returns:
            str: Formatted string containing the MCP error message and code.
                 Format: "ErrorMessage (Code: -32602)" - code is always included
                 for MCP protocol compliance and client compatibility.
        
        Example:
            str(error) -> "Resource not found: labarchives://notebook/123 (Code: -32004)"
        """
        return f"{self.message} (Code: {self.code})"


# =============================================================================
# MCP Protocol Error Handler
# =============================================================================

def handle_mcp_error(exc: Exception, context: Optional[Any] = None) -> Dict[str, Any]:
    """
    Centralized error handler for MCP protocol operations.
    
    This function converts exceptions (including MCPError instances and generic exceptions)
    into structured MCP protocol error responses that comply with JSON-RPC 2.0 standards.
    It provides consistent error handling across all MCP operations, ensuring proper
    client compatibility and comprehensive audit logging.
    
    The function supports mapping of known error types to appropriate MCP error codes
    and messages, while providing fallback handling for unknown exceptions. It also
    ensures that all errors are properly logged for audit trail and diagnostic purposes.
    
    Key features:
    - Automatic mapping of MCPError instances to protocol responses
    - Mapping of common Python exceptions to appropriate MCP error codes
    - Fallback handling for unknown exceptions using INTERNAL_ERROR
    - Comprehensive audit logging with structured error information
    - Context preservation for diagnostic and debugging purposes
    - JSON-RPC 2.0 compliant error response format
    
    Args:
        exc (Exception): The exception to be converted to an MCP protocol error
                        response. Can be an MCPError instance, a common Python
                        exception, or any other exception type.
        context (Optional[Any]): Optional context object containing additional
                                diagnostic information such as the original request,
                                client connection details, or operation parameters.
                                This context is merged with exception context if present.
    
    Returns:
        Dict[str, Any]: Structured MCP protocol error object suitable for JSON-RPC
                       error responses. Contains 'code', 'message', and optionally
                       'data' fields following JSON-RPC 2.0 error object specification.
    
    Example:
        try:
            # Some MCP operation that might fail
            result = perform_mcp_operation()
        except Exception as e:
            error_response = handle_mcp_error(e, context={"operation": "resources/read"})
            # Returns: {
            #     "code": -32004,
            #     "message": "Requested resource not found.",
            #     "data": {"operation": "resources/read", "exception_type": "ResourceNotFound"}
            # }
    """
    # Initialize the logger for audit trail and diagnostic logging
    # This ensures all errors are properly recorded for compliance and debugging
    logger = logging.getLogger(__name__)
    
    # Initialize variables for error code, message, and combined context
    error_code: int
    error_message: str
    combined_context: Dict[str, Any] = {}
    
    # Add the provided context to the combined context if available
    if context is not None:
        combined_context.update({"handler_context": context})
    
    # Check if the exception is an MCPError instance (including MCPProtocolError)
    # These exceptions already have the proper structure for MCP protocol responses
    if isinstance(exc, MCPError):
        # Extract the error code and message from the MCPError instance
        error_code = exc.code
        error_message = exc.message
        
        # Add the exception context to the combined context if available
        if exc.context is not None:
            combined_context.update({"exception_context": exc.context})
        
        # Log the MCP error with full context for audit trail
        logger.error(
            f"MCP protocol error: {error_message} (Code: {error_code})",
            extra={
                "error_code": error_code,
                "error_message": error_message,
                "exception_type": type(exc).__name__,
                "context": combined_context
            }
        )
    
    # Handle known Python exception types and map them to appropriate MCP error codes
    elif isinstance(exc, ValueError):
        # ValueError typically indicates invalid input parameters
        error_code = MCP_ERROR_CODES['INVALID_PARAMS']
        error_message = MCP_ERROR_MESSAGES['INVALID_PARAMS']
        combined_context.update({"original_error": str(exc), "exception_type": "ValueError"})
        
        logger.error(
            f"Parameter validation error mapped to MCP error: {error_message}",
            extra={
                "error_code": error_code,
                "original_exception": str(exc),
                "context": combined_context
            }
        )
    
    elif isinstance(exc, KeyError):
        # KeyError often indicates missing required parameters or resources
        error_code = MCP_ERROR_CODES['RESOURCE_NOT_FOUND']
        error_message = MCP_ERROR_MESSAGES['RESOURCE_NOT_FOUND']
        combined_context.update({"original_error": str(exc), "exception_type": "KeyError"})
        
        logger.error(
            f"Resource access error mapped to MCP error: {error_message}",
            extra={
                "error_code": error_code,
                "original_exception": str(exc),
                "context": combined_context
            }
        )
    
    elif isinstance(exc, PermissionError):
        # PermissionError indicates authentication or authorization failures
        error_code = MCP_ERROR_CODES['AUTHENTICATION_FAILED']
        error_message = MCP_ERROR_MESSAGES['AUTHENTICATION_FAILED']
        combined_context.update({"original_error": str(exc), "exception_type": "PermissionError"})
        
        logger.error(
            f"Permission error mapped to MCP error: {error_message}",
            extra={
                "error_code": error_code,
                "original_exception": str(exc),
                "context": combined_context
            }
        )
    
    elif isinstance(exc, ConnectionError):
        # ConnectionError indicates network or API connectivity issues
        error_code = MCP_ERROR_CODES['INTERNAL_ERROR']
        error_message = MCP_ERROR_MESSAGES['INTERNAL_ERROR']
        combined_context.update({"original_error": str(exc), "exception_type": "ConnectionError"})
        
        logger.error(
            f"Connection error mapped to MCP error: {error_message}",
            extra={
                "error_code": error_code,
                "original_exception": str(exc),
                "context": combined_context
            }
        )
    
    else:
        # Handle unknown exception types with a generic internal error
        error_code = MCP_ERROR_CODES['INTERNAL_ERROR']
        error_message = MCP_ERROR_MESSAGES['INTERNAL_ERROR']
        combined_context.update({
            "original_error": str(exc),
            "exception_type": type(exc).__name__,
            "unknown_exception": True
        })
        
        logger.error(
            f"Unknown exception mapped to MCP internal error: {error_message}",
            extra={
                "error_code": error_code,
                "original_exception": str(exc),
                "exception_type": type(exc).__name__,
                "context": combined_context
            }
        )
    
    # Construct the structured MCP protocol error response
    # This format follows JSON-RPC 2.0 error object specification
    error_response: Dict[str, Any] = {
        "code": error_code,
        "message": error_message
    }
    
    # Add the combined context as the 'data' field if any context is available
    # This provides additional diagnostic information for debugging and audit purposes
    if combined_context:
        error_response["data"] = combined_context
    
    # Log the final error response for audit trail and diagnostic purposes
    logger.info(
        f"Generated MCP protocol error response: {error_response}",
        extra={
            "error_response": error_response,
            "audit_event": "mcp_error_response_generated"
        }
    )
    
    return error_response