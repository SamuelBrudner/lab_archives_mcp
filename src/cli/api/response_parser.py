"""
LabArchives API Response Parser

This module implements parsing, validation, and transformation logic for LabArchives API responses.
Converts raw XML/JSON API responses into structured Pydantic models defined in api/models.py,
handles error detection and raises domain-specific exceptions from api/errors.py for malformed,
incomplete, or invalid responses.

Provides a robust interface for the API client to obtain validated, typed data objects
(notebooks, pages, entries, user context) and to surface parsing/validation errors for
audit logging and diagnostics.

The module supports:
- JSON and XML response format parsing
- Pydantic model validation and type conversion
- Structured error handling with detailed context
- Safe serialization for logging and debugging
- Comprehensive audit trail generation

All functions implement enterprise-grade error handling with detailed logging context
and maintain compliance with data validation and security best practices.
"""

import json  # builtin - JSON parsing and serialization
import xml.etree.ElementTree as ET  # builtin - XML parsing and processing
from typing import Any, Dict, Union, Optional  # builtin - Type annotations

from pydantic import BaseModel, ValidationError  # pydantic>=2.11.7 - Data validation and models

from src.cli.api.models import (
    NotebookListResponse,
    PageListResponse,
    EntryListResponse,
    UserContextResponse
)
from src.cli.api.errors import (
    APIResponseParseError,
    APIError
)


def safe_serialize(obj: Any) -> str:
    """
    Serializes objects to JSON for logging and error reporting, handling non-serializable 
    fields gracefully.
    
    This function provides robust JSON serialization for audit logging and error reporting,
    automatically handling non-serializable objects by converting them to string representations
    or removing problematic fields. It ensures that logging operations never fail due to
    serialization errors while preserving as much diagnostic information as possible.
    
    The function uses a custom JSON encoder that handles common non-serializable types
    including datetime objects, Pydantic models, exception objects, and other complex types
    that may appear in API responses or error contexts.
    
    Args:
        obj (Any): The object to serialize to JSON. Can be any Python object including
                   dictionaries, lists, Pydantic models, exceptions, or complex nested
                   structures.
    
    Returns:
        str: JSON string representation of the object. Non-serializable fields are
             converted to string representations or marked as "<non-serializable>".
    
    Examples:
        >>> safe_serialize({"key": "value", "date": datetime.now()})
        '{"key": "value", "date": "2024-01-01T12:00:00"}'
        
        >>> safe_serialize(ValidationError(...))
        '{"error_type": "ValidationError", "message": "..."}'
    """
    def json_serializer(obj: Any) -> Any:
        """Custom JSON serializer that handles non-serializable objects gracefully."""
        try:
            # Handle datetime objects
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            
            # Handle Pydantic models
            if isinstance(obj, BaseModel):
                return obj.model_dump()
            
            # Handle Exception objects
            if isinstance(obj, Exception):
                return {
                    "error_type": type(obj).__name__,
                    "message": str(obj),
                    "args": obj.args
                }
            
            # Handle objects with __dict__ attribute
            if hasattr(obj, '__dict__'):
                return obj.__dict__
            
            # Handle objects with __str__ method
            if hasattr(obj, '__str__'):
                return str(obj)
            
            # Fallback for truly non-serializable objects
            return f"<non-serializable: {type(obj).__name__}>"
            
        except Exception:
            # Ultimate fallback - return type name if all else fails
            return f"<non-serializable: {type(obj).__name__}>"
    
    try:
        return json.dumps(obj, default=json_serializer, indent=2, ensure_ascii=False)
    except Exception:
        # If JSON serialization completely fails, return a basic string representation
        return f"<serialization-failed: {type(obj).__name__}>"


def _parse_xml_to_dict(xml_string: str) -> Dict[str, Any]:
    """
    Converts XML string to dictionary representation for processing.
    
    This helper function parses XML responses from the LabArchives API and converts
    them to dictionary format for consistent processing with JSON responses. It handles
    nested XML structures and preserves data types where possible.
    
    Args:
        xml_string (str): Raw XML response string from LabArchives API
    
    Returns:
        Dict[str, Any]: Dictionary representation of the XML data
    
    Raises:
        APIResponseParseError: If XML parsing fails due to malformed syntax or structure
    """
    try:
        root = ET.fromstring(xml_string)
        
        def xml_to_dict(element):
            """Recursively convert XML element to dictionary."""
            result = {}
            
            # Handle element text content
            if element.text and element.text.strip():
                result['text'] = element.text.strip()
            
            # Handle element attributes
            if element.attrib:
                result['attributes'] = element.attrib
            
            # Handle child elements
            for child in element:
                child_data = xml_to_dict(child)
                if child.tag in result:
                    # Handle multiple elements with same tag
                    if not isinstance(result[child.tag], list):
                        result[child.tag] = [result[child.tag]]
                    result[child.tag].append(child_data)
                else:
                    result[child.tag] = child_data
            
            return result
        
        return {root.tag: xml_to_dict(root)}
        
    except ET.ParseError as e:
        raise APIResponseParseError(
            message=f"Failed to parse XML response: {str(e)}",
            code=422,
            context={
                "xml_string": xml_string[:500] + "..." if len(xml_string) > 500 else xml_string,
                "parse_error": str(e),
                "error_type": "XMLParseError"
            }
        )
    except Exception as e:
        raise APIResponseParseError(
            message=f"Unexpected error parsing XML response: {str(e)}",
            code=500,
            context={
                "xml_string": xml_string[:500] + "..." if len(xml_string) > 500 else xml_string,
                "error_type": type(e).__name__,
                "error_details": str(e)
            }
        )


def parse_notebook_list_response(raw_response: str, format: str) -> NotebookListResponse:
    """
    Parses a raw JSON or XML response from the LabArchives API for notebook listing,
    validates it against the NotebookListResponse model, and returns the structured model.
    
    This function handles the complete parsing and validation pipeline for notebook listing
    responses, including format detection, parsing, Pydantic model validation, and
    comprehensive error handling. It supports both JSON and XML response formats from
    the LabArchives API.
    
    Args:
        raw_response (str): Raw response string from LabArchives API notebook listing endpoint
        format (str): Response format indicator ('json' or 'xml')
    
    Returns:
        NotebookListResponse: Validated and structured notebook list response model containing
                             a list of NotebookMetadata objects and optional status information
    
    Raises:
        APIResponseParseError: If parsing fails due to invalid format, malformed data,
                              or Pydantic validation errors. Includes detailed context
                              for debugging and audit logging.
    
    Examples:
        >>> response = parse_notebook_list_response(json_response, 'json')
        >>> for notebook in response.notebooks:
        ...     print(f"Notebook: {notebook.name} (ID: {notebook.id})")
    """
    try:
        # Step 1: Parse raw response based on format
        if format.lower() == 'json':
            try:
                parsed_data = json.loads(raw_response)
            except json.JSONDecodeError as e:
                raise APIResponseParseError(
                    message=f"Invalid JSON in notebook list response: {str(e)}",
                    code=422,
                    context={
                        "raw_response": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response,
                        "format": format,
                        "json_error": str(e),
                        "error_type": "JSONDecodeError"
                    }
                )
        elif format.lower() == 'xml':
            parsed_data = _parse_xml_to_dict(raw_response)
        else:
            raise APIResponseParseError(
                message=f"Unsupported response format: {format}. Supported formats are 'json' and 'xml'.",
                code=400,
                context={
                    "format": format,
                    "supported_formats": ["json", "xml"],
                    "raw_response": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response
                }
            )
        
        # Step 2: Validate and construct NotebookListResponse model
        try:
            notebook_response = NotebookListResponse(**parsed_data)
            return notebook_response
            
        except ValidationError as e:
            # Convert Pydantic ValidationError to APIResponseParseError
            raise APIResponseParseError(
                message=f"Notebook list response validation failed: {str(e)}",
                code=422,
                context={
                    "raw_response": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response,
                    "format": format,
                    "parsed_data": safe_serialize(parsed_data),
                    "validation_errors": safe_serialize(e.errors()),
                    "error_type": "ValidationError"
                }
            )
        
    except APIResponseParseError:
        # Re-raise our custom exceptions without modification
        raise
    except Exception as e:
        # Handle any unexpected errors during parsing
        raise APIResponseParseError(
            message=f"Unexpected error parsing notebook list response: {str(e)}",
            code=500,
            context={
                "raw_response": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response,
                "format": format,
                "error_type": type(e).__name__,
                "error_details": str(e)
            }
        )


def parse_page_list_response(raw_response: str, format: str) -> PageListResponse:
    """
    Parses a raw JSON or XML response from the LabArchives API for page listing,
    validates it against the PageListResponse model, and returns the structured model.
    
    This function handles the complete parsing and validation pipeline for page listing
    responses, including format detection, parsing, Pydantic model validation, and
    comprehensive error handling. It supports both JSON and XML response formats from
    the LabArchives API.
    
    Args:
        raw_response (str): Raw response string from LabArchives API page listing endpoint
        format (str): Response format indicator ('json' or 'xml')
    
    Returns:
        PageListResponse: Validated and structured page list response model containing
                         a list of PageMetadata objects and optional status information
    
    Raises:
        APIResponseParseError: If parsing fails due to invalid format, malformed data,
                              or Pydantic validation errors. Includes detailed context
                              for debugging and audit logging.
    
    Examples:
        >>> response = parse_page_list_response(json_response, 'json')
        >>> for page in response.pages:
        ...     print(f"Page: {page.title} (ID: {page.id})")
    """
    try:
        # Step 1: Parse raw response based on format
        if format.lower() == 'json':
            try:
                parsed_data = json.loads(raw_response)
            except json.JSONDecodeError as e:
                raise APIResponseParseError(
                    message=f"Invalid JSON in page list response: {str(e)}",
                    code=422,
                    context={
                        "raw_response": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response,
                        "format": format,
                        "json_error": str(e),
                        "error_type": "JSONDecodeError"
                    }
                )
        elif format.lower() == 'xml':
            parsed_data = _parse_xml_to_dict(raw_response)
        else:
            raise APIResponseParseError(
                message=f"Unsupported response format: {format}. Supported formats are 'json' and 'xml'.",
                code=400,
                context={
                    "format": format,
                    "supported_formats": ["json", "xml"],
                    "raw_response": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response
                }
            )
        
        # Step 2: Validate and construct PageListResponse model
        try:
            page_response = PageListResponse(**parsed_data)
            return page_response
            
        except ValidationError as e:
            # Convert Pydantic ValidationError to APIResponseParseError
            raise APIResponseParseError(
                message=f"Page list response validation failed: {str(e)}",
                code=422,
                context={
                    "raw_response": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response,
                    "format": format,
                    "parsed_data": safe_serialize(parsed_data),
                    "validation_errors": safe_serialize(e.errors()),
                    "error_type": "ValidationError"
                }
            )
        
    except APIResponseParseError:
        # Re-raise our custom exceptions without modification
        raise
    except Exception as e:
        # Handle any unexpected errors during parsing
        raise APIResponseParseError(
            message=f"Unexpected error parsing page list response: {str(e)}",
            code=500,
            context={
                "raw_response": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response,
                "format": format,
                "error_type": type(e).__name__,
                "error_details": str(e)
            }
        )


def parse_entry_list_response(raw_response: str, format: str) -> EntryListResponse:
    """
    Parses a raw JSON or XML response from the LabArchives API for entry listing/content,
    validates it against the EntryListResponse model, and returns the structured model.
    
    This function handles the complete parsing and validation pipeline for entry listing
    and content responses, including format detection, parsing, Pydantic model validation,
    and comprehensive error handling. It supports both JSON and XML response formats from
    the LabArchives API.
    
    Args:
        raw_response (str): Raw response string from LabArchives API entry listing/content endpoint
        format (str): Response format indicator ('json' or 'xml')
    
    Returns:
        EntryListResponse: Validated and structured entry list response model containing
                          a list of EntryContent objects and optional status information
    
    Raises:
        APIResponseParseError: If parsing fails due to invalid format, malformed data,
                              or Pydantic validation errors. Includes detailed context
                              for debugging and audit logging.
    
    Examples:
        >>> response = parse_entry_list_response(json_response, 'json')
        >>> for entry in response.entries:
        ...     print(f"Entry: {entry.title} (Type: {entry.entry_type})")
    """
    try:
        # Step 1: Parse raw response based on format
        if format.lower() == 'json':
            try:
                parsed_data = json.loads(raw_response)
            except json.JSONDecodeError as e:
                raise APIResponseParseError(
                    message=f"Invalid JSON in entry list response: {str(e)}",
                    code=422,
                    context={
                        "raw_response": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response,
                        "format": format,
                        "json_error": str(e),
                        "error_type": "JSONDecodeError"
                    }
                )
        elif format.lower() == 'xml':
            parsed_data = _parse_xml_to_dict(raw_response)
        else:
            raise APIResponseParseError(
                message=f"Unsupported response format: {format}. Supported formats are 'json' and 'xml'.",
                code=400,
                context={
                    "format": format,
                    "supported_formats": ["json", "xml"],
                    "raw_response": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response
                }
            )
        
        # Step 2: Validate and construct EntryListResponse model
        try:
            entry_response = EntryListResponse(**parsed_data)
            return entry_response
            
        except ValidationError as e:
            # Convert Pydantic ValidationError to APIResponseParseError
            raise APIResponseParseError(
                message=f"Entry list response validation failed: {str(e)}",
                code=422,
                context={
                    "raw_response": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response,
                    "format": format,
                    "parsed_data": safe_serialize(parsed_data),
                    "validation_errors": safe_serialize(e.errors()),
                    "error_type": "ValidationError"
                }
            )
        
    except APIResponseParseError:
        # Re-raise our custom exceptions without modification
        raise
    except Exception as e:
        # Handle any unexpected errors during parsing
        raise APIResponseParseError(
            message=f"Unexpected error parsing entry list response: {str(e)}",
            code=500,
            context={
                "raw_response": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response,
                "format": format,
                "error_type": type(e).__name__,
                "error_details": str(e)
            }
        )


def parse_user_context_response(raw_response: str, format: str) -> UserContextResponse:
    """
    Parses a raw JSON or XML response from the LabArchives API for user context,
    validates it against the UserContextResponse model, and returns the structured model.
    
    This function handles the complete parsing and validation pipeline for user context
    responses, including format detection, parsing, Pydantic model validation, and
    comprehensive error handling. It supports both JSON and XML response formats from
    the LabArchives API.
    
    Args:
        raw_response (str): Raw response string from LabArchives API user context endpoint
        format (str): Response format indicator ('json' or 'xml')
    
    Returns:
        UserContextResponse: Validated and structured user context response model containing
                            a UserContext object and optional status information
    
    Raises:
        APIResponseParseError: If parsing fails due to invalid format, malformed data,
                              or Pydantic validation errors. Includes detailed context
                              for debugging and audit logging.
    
    Examples:
        >>> response = parse_user_context_response(json_response, 'json')
        >>> user = response.user
        >>> print(f"User: {user.name} ({user.email})")
    """
    try:
        # Step 1: Parse raw response based on format
        if format.lower() == 'json':
            try:
                parsed_data = json.loads(raw_response)
            except json.JSONDecodeError as e:
                raise APIResponseParseError(
                    message=f"Invalid JSON in user context response: {str(e)}",
                    code=422,
                    context={
                        "raw_response": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response,
                        "format": format,
                        "json_error": str(e),
                        "error_type": "JSONDecodeError"
                    }
                )
        elif format.lower() == 'xml':
            parsed_data = _parse_xml_to_dict(raw_response)
        else:
            raise APIResponseParseError(
                message=f"Unsupported response format: {format}. Supported formats are 'json' and 'xml'.",
                code=400,
                context={
                    "format": format,
                    "supported_formats": ["json", "xml"],
                    "raw_response": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response
                }
            )
        
        # Step 2: Validate and construct UserContextResponse model
        try:
            user_response = UserContextResponse(**parsed_data)
            return user_response
            
        except ValidationError as e:
            # Convert Pydantic ValidationError to APIResponseParseError
            raise APIResponseParseError(
                message=f"User context response validation failed: {str(e)}",
                code=422,
                context={
                    "raw_response": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response,
                    "format": format,
                    "parsed_data": safe_serialize(parsed_data),
                    "validation_errors": safe_serialize(e.errors()),
                    "error_type": "ValidationError"
                }
            )
        
    except APIResponseParseError:
        # Re-raise our custom exceptions without modification
        raise
    except Exception as e:
        # Handle any unexpected errors during parsing
        raise APIResponseParseError(
            message=f"Unexpected error parsing user context response: {str(e)}",
            code=500,
            context={
                "raw_response": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response,
                "format": format,
                "error_type": type(e).__name__,
                "error_details": str(e)
            }
        )


def parse_api_response(raw_response: str, format: str, response_type: str) -> BaseModel:
    """
    Generic parser for LabArchives API responses. Determines the response type and
    delegates to the appropriate parsing function.
    
    This function serves as a unified entry point for parsing all types of LabArchives
    API responses. It provides a consistent interface for the API client while internally
    delegating to specialized parsing functions based on the response type. This design
    supports extensibility and maintainability while ensuring consistent error handling
    across all response types.
    
    Args:
        raw_response (str): Raw response string from LabArchives API
        format (str): Response format indicator ('json' or 'xml')
        response_type (str): Type of response to parse ('notebook_list', 'page_list',
                           'entry_list', or 'user_context')
    
    Returns:
        BaseModel: Validated and structured response model. The specific type depends
                  on the response_type parameter:
                  - 'notebook_list': NotebookListResponse
                  - 'page_list': PageListResponse
                  - 'entry_list': EntryListResponse
                  - 'user_context': UserContextResponse
    
    Raises:
        APIError: If the response_type is unknown or unsupported
        APIResponseParseError: If parsing fails due to invalid format, malformed data,
                              or validation errors (propagated from specific parsers)
    
    Examples:
        >>> response = parse_api_response(raw_data, 'json', 'notebook_list')
        >>> if isinstance(response, NotebookListResponse):
        ...     print(f"Found {len(response.notebooks)} notebooks")
        
        >>> response = parse_api_response(raw_data, 'xml', 'user_context')
        >>> if isinstance(response, UserContextResponse):
        ...     print(f"User: {response.user.name}")
    """
    try:
        # Validate response_type parameter
        if not response_type:
            raise APIError(
                message="Response type parameter is required",
                code=400,
                context={
                    "raw_response": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response,
                    "format": format,
                    "response_type": response_type,
                    "supported_types": ["notebook_list", "page_list", "entry_list", "user_context"]
                }
            )
        
        # Delegate to appropriate parsing function based on response type
        response_type_lower = response_type.lower()
        
        if response_type_lower == 'notebook_list':
            return parse_notebook_list_response(raw_response, format)
        elif response_type_lower == 'page_list':
            return parse_page_list_response(raw_response, format)
        elif response_type_lower == 'entry_list':
            return parse_entry_list_response(raw_response, format)
        elif response_type_lower == 'user_context':
            return parse_user_context_response(raw_response, format)
        else:
            # Unsupported response type
            raise APIError(
                message=f"Unknown response type: {response_type}. Supported types are: notebook_list, page_list, entry_list, user_context.",
                code=400,
                context={
                    "raw_response": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response,
                    "format": format,
                    "response_type": response_type,
                    "supported_types": ["notebook_list", "page_list", "entry_list", "user_context"]
                }
            )
        
    except (APIError, APIResponseParseError):
        # Re-raise our custom exceptions without modification
        raise
    except Exception as e:
        # Handle any unexpected errors during parsing dispatch
        raise APIError(
            message=f"Unexpected error in API response parsing: {str(e)}",
            code=500,
            context={
                "raw_response": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response,
                "format": format,
                "response_type": response_type,
                "error_type": type(e).__name__,
                "error_details": str(e)
            }
        )


# Export all public functions for external use
__all__ = [
    "parse_notebook_list_response",
    "parse_page_list_response",
    "parse_entry_list_response",
    "parse_user_context_response",
    "parse_api_response",
    "safe_serialize"
]