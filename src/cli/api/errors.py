"""
LabArchives API Error Classes

This module defines the exception classes for LabArchives API interactions,
providing structured error handling for authentication, permission, and
response parsing errors.
"""

from typing import Optional, Dict, Any
from src.cli.exceptions import LabArchivesMCPException


class APIError(LabArchivesMCPException):
    """Base exception for all LabArchives API errors."""
    
    def __init__(self, message: str, code: int = 500, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, code, context)


class APIAuthenticationError(APIError):
    """Exception raised for authentication failures with LabArchives API."""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, 401, context)


class APIPermissionError(APIError):
    """Exception raised for permission/authorization failures with LabArchives API."""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, 403, context)


class APIResponseParseError(APIError):
    """Exception raised for response parsing errors from LabArchives API."""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, 502, context)


class APIRateLimitError(APIError):
    """Exception raised for API rate limit errors from LabArchives API."""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, 429, context)