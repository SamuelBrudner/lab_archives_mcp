"""
LabArchives MCP Server Exception Hierarchy

This module defines the centralized exception hierarchy for the LabArchives MCP Server CLI and server.
Provides base exception classes for all custom errors across the CLI, API, and MCP protocol layers,
supporting robust, structured, and auditable error handling.

All domain-specific exceptions (API, MCP, resource, configuration, authentication, and validation errors)
inherit from these base classes, enabling consistent diagnostics, user feedback, and audit logging
throughout the application.

This module serves as the single source of truth for exception types, error message formatting,
and error context propagation, supporting compliance with SOC2, ISO 27001, and other regulatory
requirements through comprehensive audit trail generation.
"""

from typing import Optional  # Python 3.5+ builtin typing module for type hints


class LabArchivesMCPException(Exception):
    """
    Base exception for all custom errors in the LabArchives MCP Server CLI and server.
    
    This is the root exception class from which all domain-specific exceptions must inherit.
    It provides structured error handling with optional error codes and context objects
    to support comprehensive audit logging, diagnostics, and user-friendly error reporting.
    
    All exceptions in the system inherit from this class to enable centralized error handling,
    consistent logging patterns, and audit trail generation for compliance purposes.
    
    The exception supports three key components:
    - message: Human-readable error description
    - code: Optional numeric error code for programmatic handling
    - context: Optional object containing additional diagnostic information
    
    This design enables robust error handling patterns throughout the application while
    maintaining the flexibility to add domain-specific error information.
    """
    
    def __init__(self, message: str, code: Optional[int] = None, context: Optional[object] = None):
        """
        Initialize the base exception with a message, optional error code, and optional context.
        
        The constructor establishes the foundation for all error handling in the system by
        capturing essential error information that can be used for logging, debugging, and
        user feedback. The context parameter is particularly valuable for audit logging
        as it can contain request details, API responses, or other diagnostic data.
        
        Args:
            message (str): Human-readable error description that will be displayed to users
                          and written to audit logs. Should be clear and actionable.
            code (Optional[int]): Optional numeric error code for programmatic error handling.
                                 Can be used to categorize errors and implement retry logic.
            context (Optional[object]): Optional context object containing additional diagnostic
                                       information such as failed requests, API responses, or
                                       system state. Used for audit logging and debugging.
        
        Example:
            raise LabArchivesMCPException(
                message="Failed to initialize MCP server",
                code=1001,
                context={"config_file": "/path/to/config", "error_details": "..."}
            )
        """
        # Store the error message, code, and context as instance properties for access
        # by logging systems, error handlers, and diagnostic tools
        self.message = message
        self.code = code
        self.context = context
        
        # Initialize the base Exception class with the error message
        # This ensures compatibility with standard Python exception handling
        super().__init__(message)
    
    def __str__(self) -> str:
        """
        Return a string representation of the exception with message and code if present.
        
        This method provides a human-readable representation of the error that includes
        the error message and optionally the error code. This format is used in log
        outputs, error displays, and audit trails.
        
        The string representation is designed to be informative for both end users and
        system administrators, providing enough detail for understanding and resolving
        the error condition.
        
        Returns:
            str: Formatted string containing the error message and code if available.
                 Format: "ErrorMessage" or "ErrorMessage (Code: 1001)"
        
        Example:
            str(exception) -> "Failed to authenticate with LabArchives API (Code: 2001)"
        """
        if self.code is not None:
            return f"{self.message} (Code: {self.code})"
        return self.message


class LabArchivesAPIException(LabArchivesMCPException):
    """
    Base exception for all LabArchives API-related errors.
    
    This exception class serves as the parent for all API-specific errors including
    authentication failures, HTTP errors, rate limiting, response parsing errors,
    and permission denied errors. It inherits from LabArchivesMCPException to maintain
    consistency with the overall exception hierarchy.
    
    This class is specifically designed to handle errors that occur during interaction
    with the LabArchives REST API, including network failures, authentication problems,
    authorization issues, and data format errors. The context parameter is particularly
    useful for storing HTTP response objects, request details, and API error responses.
    
    Common use cases include:
    - HTTP 401 authentication failures
    - HTTP 403 permission denied errors
    - HTTP 429 rate limiting responses
    - HTTP 500 server errors
    - Network connectivity issues
    - JSON/XML parsing errors
    - Invalid API responses
    
    The exception supports the same structured error handling pattern as the base class
    while providing semantic meaning for API-related error conditions.
    """
    
    def __init__(self, message: str, code: Optional[int] = None, context: Optional[object] = None):
        """
        Initialize the API exception with a message, optional error code, and optional context.
        
        This constructor delegates to the base LabArchivesMCPException while providing
        semantic meaning for API-related errors. The context parameter is particularly
        valuable for API errors as it can contain the HTTP response object, request
        details, or parsed error responses from the LabArchives API.
        
        Args:
            message (str): Human-readable description of the API error. Should provide
                          clear information about what API operation failed and why.
            code (Optional[int]): Optional numeric error code. Can correspond to HTTP
                                 status codes or custom API error codes.
            context (Optional[object]): Optional context object containing diagnostic
                                       information such as HTTP response objects, request
                                       details, headers, or parsed API error responses.
        
        Example:
            raise LabArchivesAPIException(
                message="Authentication failed: Invalid access key",
                code=401,
                context={"response": http_response, "request_url": "https://api.labarchives.com/..."}
            )
        """
        # Call the parent constructor to establish the base exception properties
        # This ensures consistent error handling patterns across all exception types
        super().__init__(message, code, context)
        
        # Store the parameters as instance properties for access by error handlers,
        # logging systems, and diagnostic tools
        self.message = message
        self.code = code
        self.context = context
    
    def __str__(self) -> str:
        """
        Return a string representation of the API exception with message and code if present.
        
        This method provides a formatted string representation specifically for API errors,
        maintaining consistency with the base exception class while providing clear
        identification of API-related error conditions.
        
        The string format is designed to be informative for both developers and end users,
        providing enough detail to understand and resolve API-related issues.
        
        Returns:
            str: Formatted string containing the API error message and code if available.
                 Format follows the same pattern as the base class for consistency.
        
        Example:
            str(exception) -> "LabArchives API authentication failed (Code: 401)"
        """
        if self.code is not None:
            return f"{self.message} (Code: {self.code})"
        return self.message


class MCPError(LabArchivesMCPException):
    """
    Base exception for all MCP protocol-related errors.
    
    This exception class serves as the parent for all Model Context Protocol (MCP) specific
    errors including protocol violations, resource not found errors, authentication failures,
    scope violations, and rate limiting within the MCP context. It inherits from
    LabArchivesMCPException to maintain consistency with the overall exception hierarchy.
    
    This class is specifically designed to handle errors that occur during MCP protocol
    communication, including JSON-RPC message formatting errors, protocol compliance
    violations, resource access errors, and client-server communication failures.
    
    Note that unlike the other exception classes, MCPError requires a numeric error code
    as MCP protocol errors must conform to JSON-RPC error code standards for proper
    client handling and protocol compliance.
    
    Common MCP error codes include:
    - -32700: Parse error (Invalid JSON)
    - -32600: Invalid request
    - -32601: Method not found
    - -32602: Invalid params
    - -32603: Internal error
    - -32000 to -32099: Server error range
    
    The context parameter is particularly useful for storing MCP request objects,
    protocol messages, and client connection details for debugging and audit purposes.
    """
    
    def __init__(self, message: str, code: int, context: Optional[object] = None):
        """
        Initialize the MCP protocol error with a message, error code, and optional context.
        
        This constructor requires an error code (unlike the optional code in parent classes)
        because MCP protocol errors must conform to JSON-RPC error code standards for
        proper client handling and protocol compliance.
        
        The error code is used by MCP clients to programmatically handle different types
        of protocol errors and implement appropriate retry logic or user feedback.
        
        Args:
            message (str): Human-readable description of the MCP protocol error. Should
                          provide clear information about what protocol operation failed.
            code (int): Required numeric error code following JSON-RPC standards.
                       Must be provided for MCP protocol compliance.
            context (Optional[object]): Optional context object containing diagnostic
                                       information such as the MCP request object, protocol
                                       messages, client connection details, or resource URIs.
        
        Example:
            raise MCPError(
                message="Resource not found: labarchives://notebook/123",
                code=-32602,
                context={"resource_uri": "labarchives://notebook/123", "request_id": "req_456"}
            )
        """
        # Call the parent constructor with the required error code
        # This ensures consistent error handling patterns while maintaining MCP protocol compliance
        super().__init__(message, code, context)
        
        # Store the parameters as instance properties for access by MCP protocol handlers,
        # logging systems, and diagnostic tools
        self.message = message
        self.code = code
        self.context = context
    
    def __str__(self) -> str:
        """
        Return a string representation of the MCP protocol error with message and code.
        
        This method provides a formatted string representation specifically for MCP protocol
        errors, always including the error code since it's required for MCP compliance.
        
        The string format is designed to be informative for both MCP clients and developers,
        providing the error code that clients need for programmatic error handling along
        with the human-readable message.
        
        Returns:
            str: Formatted string containing the MCP error message and code.
                 Format: "ErrorMessage (Code: -32602)" - code is always included
        
        Example:
            str(exception) -> "MCP resource not found (Code: -32602)"
        """
        return f"{self.message} (Code: {self.code})"