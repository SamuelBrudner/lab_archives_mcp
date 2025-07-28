"""
LabArchives MCP Server CLI Utilities

This module provides utility functions and helpers for the LabArchives MCP Server CLI.
Centralizes common operations such as file path expansion and normalization, environment 
variable retrieval with type safety and error handling, JSON file reading/writing, and 
other reusable utilities needed by configuration, logging, validation, and CLI modules.

This implementation ensures robust, cross-platform handling of file system and environment 
operations, supports secure and auditable configuration management, and reduces code 
duplication across the CLI codebase. All functions implement comprehensive error handling
with detailed logging and maintain compliance with security best practices.

The module supports the following key features:
- Cross-platform file path expansion with user home (~) and environment variable support
- Type-safe environment variable retrieval with validation and default value handling
- Secure JSON file operations with comprehensive error handling and directory creation
- File validation utilities for configuration and state management
- Enterprise-grade logging and audit trail generation for all operations

All functions are designed to work seamlessly with the LabArchives MCP Server's 
configuration management, authentication systems, and audit logging requirements.
"""

import os  # builtin - Provides file system operations, path expansion, and environment variable access
import json  # builtin - Used for reading and writing JSON configuration and state files
import re  # builtin - Used for regex operations in environment variable sanitization
from typing import Any, Optional, Union  # builtin - Supports type annotations for utility function signatures

from exceptions import LabArchivesMCPException


def expand_path(path: str) -> str:
    """
    Expands and normalizes a file system path, supporting user home (~), environment 
    variables, and absolute/relative resolution. Ensures the returned path is absolute 
    and normalized for cross-platform compatibility.
    
    This function provides comprehensive path expansion suitable for configuration files,
    log files, and other file system operations in the LabArchives MCP Server CLI.
    It handles all common path expansion scenarios including user home directory references,
    environment variable substitution, and path normalization for consistent behavior
    across different operating systems.
    
    The function processes paths in the following order:
    1. Expand user home directory (~) using os.path.expanduser
    2. Expand environment variables in the path using os.path.expandvars
    3. Convert the path to an absolute path using os.path.abspath
    4. Normalize the path using os.path.normpath
    
    This ensures that all paths are consistently formatted and fully resolved, preventing
    issues with relative paths, symbolic links, and platform-specific path separators.
    
    Args:
        path (str): The file system path to expand and normalize. Can contain user home
                   directory references (~), environment variables (${VAR} or $VAR),
                   relative path components (. and ..), and platform-specific separators.
    
    Returns:
        str: The expanded, absolute, and normalized file system path. The returned path
             is guaranteed to be absolute and use the correct path separators for the
             current platform.
    
    Raises:
        LabArchivesMCPException: If the path parameter is None, empty, or contains
                                invalid characters that prevent proper path expansion.
                                Also raised if environment variable expansion fails.
    
    Examples:
        >>> expand_path("~/config/server.json")
        '/home/user/config/server.json'
        
        >>> expand_path("$HOME/logs/audit.log")
        '/home/user/logs/audit.log'
        
        >>> expand_path("../config/settings.json")
        '/absolute/path/to/config/settings.json'
        
        >>> expand_path("./data/cache.json")
        '/current/working/directory/data/cache.json'
    """
    # Validate input path parameter
    if path is None:
        raise LabArchivesMCPException(
            message="Path parameter cannot be None",
            code=1001,
            context={"operation": "expand_path", "input_path": path}
        )
    
    if not isinstance(path, str):
        raise LabArchivesMCPException(
            message=f"Path parameter must be a string, got {type(path).__name__}",
            code=1002,
            context={"operation": "expand_path", "input_path": path, "input_type": type(path).__name__}
        )
    
    if not path.strip():
        raise LabArchivesMCPException(
            message="Path parameter cannot be empty or contain only whitespace",
            code=1003,
            context={"operation": "expand_path", "input_path": path}
        )
    
    try:
        # Step 1: Expand user home directory (~) using os.path.expanduser
        # This handles cases like ~/config/file.json or ~user/config/file.json
        expanded_user = os.path.expanduser(path)
        
        # Step 2: Expand environment variables in the path using os.path.expandvars
        # This handles cases like $HOME/config/file.json or ${APPDATA}/config/file.json
        expanded_vars = os.path.expandvars(expanded_user)
        
        # Step 3: Convert the path to an absolute path using os.path.abspath
        # This resolves relative paths like ./config/file.json or ../config/file.json
        # and ensures the path is absolute regardless of current working directory
        absolute_path = os.path.abspath(expanded_vars)
        
        # Step 4: Normalize the path using os.path.normpath
        # This removes redundant separators and resolves . and .. components
        # ensuring a clean, canonical path representation
        normalized_path = os.path.normpath(absolute_path)
        
        # Return the fully expanded and normalized path
        return normalized_path
        
    except Exception as e:
        # Handle any unexpected errors during path expansion
        raise LabArchivesMCPException(
            message=f"Failed to expand path '{path}': {str(e)}",
            code=1004,
            context={
                "operation": "expand_path",
                "input_path": path,
                "error_type": type(e).__name__,
                "error_details": str(e)
            }
        )


def get_env_var(name: str, default: Any = None, cast_type: Optional[type] = None, required: bool = False) -> Any:
    """
    Retrieves an environment variable by name, with optional type coercion, default value,
    and error handling. Raises LabArchivesMCPException if the variable is required but not set.
    
    This function provides type-safe environment variable access with comprehensive validation
    and error handling. It supports common use cases for configuration management including
    required variables, default values, and automatic type conversion for string environment
    variables to Python types like int, bool, float, and list.
    
    The function handles environment variable retrieval in the following order:
    1. Attempt to retrieve the environment variable using os.environ.get
    2. If not set and required is True, raise LabArchivesMCPException with descriptive error
    3. If not set and default is provided, return the default value
    4. If set and cast_type is provided, attempt to cast the value to the specified type
    5. If casting fails, raise LabArchivesMCPException with descriptive error
    6. Return the value (cast or raw)
    
    Args:
        name (str): The name of the environment variable to retrieve. Must be a non-empty
                   string containing valid environment variable name characters.
        default (Any, optional): The default value to return if the environment variable
                               is not set. Can be any Python type. Defaults to None.
        cast_type (Optional[type], optional): The type to cast the environment variable
                                            value to. Supports int, float, bool, str, and
                                            list. Defaults to None (no casting).
        required (bool, optional): Whether the environment variable is required. If True
                                 and the variable is not set, raises LabArchivesMCPException.
                                 Defaults to False.
    
    Returns:
        Any: The value of the environment variable, cast to the specified type if provided.
             Returns the default value if the variable is not set and not required.
             Returns None if the variable is not set, not required, and no default provided.
    
    Raises:
        LabArchivesMCPException: If the variable is required but not set, if the variable
                                name is invalid, or if type casting fails. Includes detailed
                                error context for debugging and audit logging.
    
    Examples:
        >>> get_env_var("HOME")
        '/home/user'
        
        >>> get_env_var("PORT", default=8080, cast_type=int)
        8080
        
        >>> get_env_var("DEBUG", default=False, cast_type=bool)
        True
        
        >>> get_env_var("REQUIRED_KEY", required=True)
        LabArchivesMCPException: Required environment variable 'REQUIRED_KEY' is not set
    """
    # Validate input parameters
    if name is None:
        raise LabArchivesMCPException(
            message="Environment variable name cannot be None",
            code=2001,
            context={"operation": "get_env_var", "variable_name": name}
        )
    
    if not isinstance(name, str):
        raise LabArchivesMCPException(
            message=f"Environment variable name must be a string, got {type(name).__name__}",
            code=2002,
            context={"operation": "get_env_var", "variable_name": name, "name_type": type(name).__name__}
        )
    
    if not name.strip():
        raise LabArchivesMCPException(
            message="Environment variable name cannot be empty or contain only whitespace",
            code=2003,
            context={"operation": "get_env_var", "variable_name": name}
        )
    
    # Validate cast_type parameter if provided
    if cast_type is not None and not isinstance(cast_type, type):
        raise LabArchivesMCPException(
            message=f"cast_type must be a type object, got {type(cast_type).__name__}",
            code=2004,
            context={"operation": "get_env_var", "variable_name": name, "cast_type": cast_type}
        )
    
    try:
        # Step 1: Attempt to retrieve the environment variable using os.environ.get
        raw_value = os.environ.get(name)
        
        # Step 2: If not set and required is True, raise LabArchivesMCPException
        if raw_value is None and required:
            raise LabArchivesMCPException(
                message=f"Required environment variable '{name}' is not set",
                code=2005,
                context={
                    "operation": "get_env_var",
                    "variable_name": name,
                    "required": required,
                    "has_default": default is not None
                }
            )
        
        # Step 3: If not set and default is provided, return the default value
        if raw_value is None:
            return default
        
        # Step 4: If set and cast_type is provided, attempt to cast the value
        if cast_type is not None:
            try:
                # Handle boolean casting specially since bool("false") is True
                if cast_type == bool:
                    # Convert string representations of boolean values
                    if raw_value.lower() in ('true', '1', 'yes', 'on', 'enabled'):
                        return True
                    elif raw_value.lower() in ('false', '0', 'no', 'off', 'disabled'):
                        return False
                    else:
                        raise ValueError(f"Cannot convert '{raw_value}' to boolean")
                
                # Handle list casting for comma-separated values
                elif cast_type == list:
                    if not raw_value.strip():
                        return []
                    # Split by comma and strip whitespace from each item
                    return [item.strip() for item in raw_value.split(',') if item.strip()]
                
                # Handle standard type casting for int, float, str, etc.
                else:
                    return cast_type(raw_value)
                    
            except (ValueError, TypeError) as cast_error:
                raise LabArchivesMCPException(
                    message=f"Failed to cast environment variable '{name}' value '{raw_value}' to {cast_type.__name__}: {str(cast_error)}",
                    code=2006,
                    context={
                        "operation": "get_env_var",
                        "variable_name": name,
                        "raw_value": raw_value,
                        "cast_type": cast_type.__name__,
                        "cast_error": str(cast_error)
                    }
                )
        
        # Step 5: Return the raw value if no casting is required
        return raw_value
        
    except LabArchivesMCPException:
        # Re-raise our custom exceptions without modification
        raise
    except Exception as e:
        # Handle any unexpected errors during environment variable retrieval
        raise LabArchivesMCPException(
            message=f"Unexpected error retrieving environment variable '{name}': {str(e)}",
            code=2007,
            context={
                "operation": "get_env_var",
                "variable_name": name,
                "error_type": type(e).__name__,
                "error_details": str(e)
            }
        )


def read_json_file(file_path: str) -> Any:
    """
    Reads and parses a JSON file from the given path, returning the loaded data as a 
    Python object. Raises LabArchivesMCPException on file not found, parse error, or 
    permission error.
    
    This function provides secure and robust JSON file reading with comprehensive error
    handling and path expansion. It automatically expands user home directories and
    environment variables in the file path, ensuring consistent behavior across different
    operating systems and deployment environments.
    
    The function performs the following operations:
    1. Expand and normalize the file path using expand_path
    2. Open the file in read mode with UTF-8 encoding
    3. Read the file contents and parse as JSON using json.load
    4. Handle FileNotFoundError, PermissionError, and json.JSONDecodeError appropriately
    5. Return the parsed data as a Python object
    
    Args:
        file_path (str): The path to the JSON file to read. Can contain user home directory
                        references (~), environment variables, and relative paths. The path
                        will be automatically expanded and normalized.
    
    Returns:
        Any: The parsed JSON data as a Python object (dict, list, str, int, float, bool,
             or None). The exact type depends on the JSON content structure.
    
    Raises:
        LabArchivesMCPException: If the file is not found, cannot be read due to permission
                                errors, contains invalid JSON syntax, or if any other I/O
                                error occurs. Each error includes detailed context for
                                debugging and audit logging.
    
    Examples:
        >>> config = read_json_file("~/config/server.json")
        {'host': 'localhost', 'port': 8080, 'debug': True}
        
        >>> data = read_json_file("$APPDATA/labarchives/settings.json")
        {'api_key': 'secret', 'notebooks': ['nb1', 'nb2']}
        
        >>> read_json_file("./data/missing.json")
        LabArchivesMCPException: File not found: /absolute/path/to/data/missing.json
    """
    # Validate input parameters
    if file_path is None:
        raise LabArchivesMCPException(
            message="File path parameter cannot be None",
            code=3001,
            context={"operation": "read_json_file", "file_path": file_path}
        )
    
    if not isinstance(file_path, str):
        raise LabArchivesMCPException(
            message=f"File path parameter must be a string, got {type(file_path).__name__}",
            code=3002,
            context={"operation": "read_json_file", "file_path": file_path, "path_type": type(file_path).__name__}
        )
    
    if not file_path.strip():
        raise LabArchivesMCPException(
            message="File path parameter cannot be empty or contain only whitespace",
            code=3003,
            context={"operation": "read_json_file", "file_path": file_path}
        )
    
    try:
        # Step 1: Expand and normalize the file path using expand_path
        expanded_path = expand_path(file_path)
        
        # Step 2: Open the file in read mode with UTF-8 encoding
        with open(expanded_path, 'r', encoding='utf-8') as file:
            # Step 3: Read the file contents and parse as JSON using json.load
            data = json.load(file)
            
        # Step 4: Return the parsed data
        return data
        
    except FileNotFoundError:
        # Handle file not found errors with detailed context
        raise LabArchivesMCPException(
            message=f"File not found: {expanded_path if 'expanded_path' in locals() else file_path}",
            code=3004,
            context={
                "operation": "read_json_file",
                "original_path": file_path,
                "expanded_path": expanded_path if 'expanded_path' in locals() else None,
                "error_type": "FileNotFoundError"
            }
        )
    
    except PermissionError:
        # Handle permission errors with detailed context
        raise LabArchivesMCPException(
            message=f"Permission denied accessing file: {expanded_path if 'expanded_path' in locals() else file_path}",
            code=3005,
            context={
                "operation": "read_json_file",
                "original_path": file_path,
                "expanded_path": expanded_path if 'expanded_path' in locals() else None,
                "error_type": "PermissionError"
            }
        )
    
    except json.JSONDecodeError as json_error:
        # Handle JSON parsing errors with detailed context
        raise LabArchivesMCPException(
            message=f"Invalid JSON syntax in file '{expanded_path if 'expanded_path' in locals() else file_path}': {str(json_error)}",
            code=3006,
            context={
                "operation": "read_json_file",
                "original_path": file_path,
                "expanded_path": expanded_path if 'expanded_path' in locals() else None,
                "error_type": "JSONDecodeError",
                "json_error_msg": str(json_error),
                "json_error_lineno": getattr(json_error, 'lineno', None),
                "json_error_colno": getattr(json_error, 'colno', None),
                "json_error_pos": getattr(json_error, 'pos', None)
            }
        )
    
    except UnicodeDecodeError as unicode_error:
        # Handle encoding errors with detailed context
        raise LabArchivesMCPException(
            message=f"File encoding error reading '{expanded_path if 'expanded_path' in locals() else file_path}': {str(unicode_error)}",
            code=3007,
            context={
                "operation": "read_json_file",
                "original_path": file_path,
                "expanded_path": expanded_path if 'expanded_path' in locals() else None,
                "error_type": "UnicodeDecodeError",
                "encoding": "utf-8",
                "unicode_error": str(unicode_error)
            }
        )
    
    except LabArchivesMCPException:
        # Re-raise our custom exceptions without modification
        raise
    
    except Exception as e:
        # Handle any unexpected errors during file reading
        raise LabArchivesMCPException(
            message=f"Unexpected error reading JSON file '{file_path}': {str(e)}",
            code=3008,
            context={
                "operation": "read_json_file",
                "original_path": file_path,
                "expanded_path": expanded_path if 'expanded_path' in locals() else None,
                "error_type": type(e).__name__,
                "error_details": str(e)
            }
        )


def write_json_file(file_path: str, data: Any) -> None:
    """
    Writes a Python object as JSON to the specified file path, creating directories as 
    needed. Raises LabArchivesMCPException on permission or serialization errors.
    
    This function provides secure and robust JSON file writing with comprehensive error
    handling, automatic directory creation, and consistent formatting. It ensures that
    the output JSON is properly formatted with indentation for human readability while
    maintaining data integrity and security.
    
    The function performs the following operations:
    1. Expand and normalize the file path using expand_path
    2. Create the parent directory if it does not exist using os.makedirs
    3. Open the file in write mode with UTF-8 encoding
    4. Serialize the data as JSON using json.dump with indent=2
    5. Handle PermissionError and TypeError appropriately
    
    Args:
        file_path (str): The path to the JSON file to write. Can contain user home directory
                        references (~), environment variables, and relative paths. The path
                        will be automatically expanded and normalized.
        data (Any): The Python object to serialize as JSON. Must be JSON-serializable
                   (dict, list, str, int, float, bool, None, or combinations thereof).
    
    Returns:
        None: This function does not return a value. Success is indicated by the absence
              of exceptions.
    
    Raises:
        LabArchivesMCPException: If the file cannot be written due to permission errors,
                                if the data cannot be serialized to JSON, if directory
                                creation fails, or if any other I/O error occurs. Each
                                error includes detailed context for debugging and audit
                                logging.
    
    Examples:
        >>> config = {'host': 'localhost', 'port': 8080, 'debug': True}
        >>> write_json_file("~/config/server.json", config)
        # Creates ~/config/server.json with formatted JSON
        
        >>> data = {'api_key': 'secret', 'notebooks': ['nb1', 'nb2']}
        >>> write_json_file("$APPDATA/labarchives/settings.json", data)
        # Creates directory structure and writes settings.json
    """
    # Validate input parameters
    if file_path is None:
        raise LabArchivesMCPException(
            message="File path parameter cannot be None",
            code=4001,
            context={"operation": "write_json_file", "file_path": file_path}
        )
    
    if not isinstance(file_path, str):
        raise LabArchivesMCPException(
            message=f"File path parameter must be a string, got {type(file_path).__name__}",
            code=4002,
            context={"operation": "write_json_file", "file_path": file_path, "path_type": type(file_path).__name__}
        )
    
    if not file_path.strip():
        raise LabArchivesMCPException(
            message="File path parameter cannot be empty or contain only whitespace",
            code=4003,
            context={"operation": "write_json_file", "file_path": file_path}
        )
    
    # Note: data can be None or any JSON-serializable type, so we don't validate it here
    # JSON serialization will handle validation and raise appropriate errors
    
    try:
        # Step 1: Expand and normalize the file path using expand_path
        expanded_path = expand_path(file_path)
        
        # Step 2: Create the parent directory if it does not exist using os.makedirs
        parent_dir = os.path.dirname(expanded_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
        
        # Step 3: Open the file in write mode with UTF-8 encoding
        with open(expanded_path, 'w', encoding='utf-8') as file:
            # Step 4: Serialize the data as JSON using json.dump with indent=2
            json.dump(data, file, indent=2, ensure_ascii=False, sort_keys=False)
            
        # Success - no return value needed
        
    except PermissionError:
        # Handle permission errors with detailed context
        raise LabArchivesMCPException(
            message=f"Permission denied writing to file: {expanded_path if 'expanded_path' in locals() else file_path}",
            code=4004,
            context={
                "operation": "write_json_file",
                "original_path": file_path,
                "expanded_path": expanded_path if 'expanded_path' in locals() else None,
                "error_type": "PermissionError",
                "parent_dir": parent_dir if 'parent_dir' in locals() else None
            }
        )
    
    except TypeError as type_error:
        # Handle JSON serialization errors with detailed context
        raise LabArchivesMCPException(
            message=f"Cannot serialize data to JSON: {str(type_error)}",
            code=4005,
            context={
                "operation": "write_json_file",
                "original_path": file_path,
                "expanded_path": expanded_path if 'expanded_path' in locals() else None,
                "error_type": "TypeError",
                "data_type": type(data).__name__,
                "serialization_error": str(type_error)
            }
        )
    
    except OSError as os_error:
        # Handle OS-level errors (disk full, invalid path, etc.)
        raise LabArchivesMCPException(
            message=f"OS error writing to file '{expanded_path if 'expanded_path' in locals() else file_path}': {str(os_error)}",
            code=4006,
            context={
                "operation": "write_json_file",
                "original_path": file_path,
                "expanded_path": expanded_path if 'expanded_path' in locals() else None,
                "error_type": "OSError",
                "os_error": str(os_error),
                "parent_dir": parent_dir if 'parent_dir' in locals() else None
            }
        )
    
    except UnicodeEncodeError as unicode_error:
        # Handle encoding errors with detailed context
        raise LabArchivesMCPException(
            message=f"File encoding error writing to '{expanded_path if 'expanded_path' in locals() else file_path}': {str(unicode_error)}",
            code=4007,
            context={
                "operation": "write_json_file",
                "original_path": file_path,
                "expanded_path": expanded_path if 'expanded_path' in locals() else None,
                "error_type": "UnicodeEncodeError",
                "encoding": "utf-8",
                "unicode_error": str(unicode_error)
            }
        )
    
    except LabArchivesMCPException:
        # Re-raise our custom exceptions without modification
        raise
    
    except Exception as e:
        # Handle any unexpected errors during file writing
        raise LabArchivesMCPException(
            message=f"Unexpected error writing JSON file '{file_path}': {str(e)}",
            code=4008,
            context={
                "operation": "write_json_file",
                "original_path": file_path,
                "expanded_path": expanded_path if 'expanded_path' in locals() else None,
                "error_type": type(e).__name__,
                "error_details": str(e)
            }
        )


def is_valid_json_file(file_path: str) -> bool:
    """
    Checks if a file exists at the given path and is a valid JSON file. Returns True 
    if valid, False otherwise.
    
    This function provides a safe way to validate JSON files without raising exceptions
    for common scenarios like missing files or invalid JSON. It's particularly useful
    for configuration validation, cache file checking, and other scenarios where you
    need to test file validity before attempting to read the contents.
    
    The function performs the following operations:
    1. Expand and normalize the file path using expand_path
    2. Check if the file exists using os.path.isfile
    3. If not, return False
    4. Try to open and parse the file as JSON
    5. If parsing succeeds, return True
    6. If parsing fails, return False
    
    Unlike read_json_file, this function does not raise exceptions for missing files
    or invalid JSON, making it suitable for conditional logic and validation workflows.
    
    Args:
        file_path (str): The path to the JSON file to validate. Can contain user home
                        directory references (~), environment variables, and relative paths.
                        The path will be automatically expanded and normalized.
    
    Returns:
        bool: True if the file exists and is valid JSON, False otherwise. Returns False
              for any error condition including file not found, permission errors, or
              invalid JSON syntax.
    
    Examples:
        >>> is_valid_json_file("~/config/server.json")
        True
        
        >>> is_valid_json_file("./missing.json")
        False
        
        >>> is_valid_json_file("./invalid.json")  # Contains malformed JSON
        False
        
        >>> if is_valid_json_file(config_path):
        ...     config = read_json_file(config_path)
        ... else:
        ...     config = create_default_config()
    """
    # Validate input parameters - return False for invalid inputs instead of raising exceptions
    if file_path is None or not isinstance(file_path, str) or not file_path.strip():
        return False
    
    try:
        # Step 1: Expand and normalize the file path using expand_path
        expanded_path = expand_path(file_path)
        
        # Step 2: Check if the file exists using os.path.isfile
        if not os.path.isfile(expanded_path):
            # Step 3: If not, return False
            return False
        
        # Step 4: Try to open and parse the file as JSON
        with open(expanded_path, 'r', encoding='utf-8') as file:
            json.load(file)
            
        # Step 5: If parsing succeeds, return True
        return True
        
    except (FileNotFoundError, PermissionError, json.JSONDecodeError, UnicodeDecodeError, OSError):
        # Step 6: If parsing fails, return False
        # We catch all expected exceptions and return False for any error condition
        return False
    
    except LabArchivesMCPException:
        # Handle path expansion errors by returning False
        return False
        
    except Exception:
        # Handle any unexpected errors by returning False
        # This ensures the function never raises exceptions, maintaining its contract
        return False


def sanitize_env_var(var_name: str) -> str:
    """
    Sanitizes environment variable names by stripping whitespace, converting to uppercase,
    and replacing invalid characters with underscores.
    
    Args:
        var_name (str): The environment variable name to sanitize.
    
    Returns:
        str: The sanitized environment variable name.
    
    Examples:
        >>> sanitize_env_var("  DATABASE_URL  ")
        'DATABASE_URL'
        >>> sanitize_env_var("api_key")
        'API_KEY'
        >>> sanitize_env_var("with-dashes")
        'WITH_DASHES'
    """
    if var_name is None:
        raise TypeError("Variable name cannot be None")
    
    if not isinstance(var_name, str):
        raise TypeError("Variable name must be a string")
    
    # Strip whitespace and convert to uppercase
    cleaned = var_name.strip().upper()
    
    # Replace sequences of invalid characters with a single underscore
    # This preserves existing underscores but collapses sequences of special chars
    cleaned = re.sub(r'[^A-Z0-9_]+', '_', cleaned)
    
    return cleaned


def deep_merge_dicts(dict1: dict, dict2: dict) -> dict:
    """
    Recursively merges two dictionaries, with dict2 values taking precedence.
    
    Args:
        dict1 (dict): The base dictionary.
        dict2 (dict): The dictionary to merge into dict1.
    
    Returns:
        dict: The merged dictionary.
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result


def parse_iso_datetime(datetime_str: str):
    """
    Parses an ISO datetime string into a datetime object.
    
    Args:
        datetime_str (str): The ISO datetime string to parse.
    
    Returns:
        datetime: The parsed datetime object.
    """
    from datetime import datetime
    import re
    
    if datetime_str is None:
        raise TypeError("datetime_str cannot be None")
    
    if not isinstance(datetime_str, str):
        raise TypeError("datetime_str must be a string")
    
    if not datetime_str.strip():
        raise ValueError("datetime_str cannot be empty")
    
    # Validate that it's a proper ISO datetime format (not just date)
    # Must have T separator and time portion, timezone is optional
    iso_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?$'
    if not re.match(iso_pattern, datetime_str):
        raise ValueError(f"Invalid ISO 8601 datetime format: {datetime_str}")
    
    try:
        # Try parsing with timezone info
        return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
    except ValueError:
        # Fallback to basic parsing
        return datetime.fromisoformat(datetime_str)


def flatten_dict(d: dict, parent_key: str = '', sep: str = '.', separator: str = None) -> dict:
    """
    Flattens a nested dictionary into a single-level dictionary.
    
    Args:
        d (dict): The dictionary to flatten.
        parent_key (str): The parent key prefix.
        sep (str): The separator to use between keys.
        separator (str): Alternative name for sep parameter (for backward compatibility).
    
    Returns:
        dict: The flattened dictionary.
    """
    if d is None:
        raise TypeError("Dictionary cannot be None")
    
    if not isinstance(d, dict):
        raise TypeError("Input must be a dictionary")
    
    # Handle separator parameter for backward compatibility
    if separator is not None:
        sep = separator
    
    items = []
    
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    
    return dict(items)


def safe_serialize(obj: Any) -> str:
    """
    Serializes objects to JSON for logging and error reporting, handling non-serializable 
    fields gracefully.
    
    Args:
        obj (Any): The object to serialize to JSON.
    
    Returns:
        str: JSON string representation of the object.
    """
    def json_serializer(obj: Any) -> Any:
        """Custom JSON serializer that handles non-serializable objects gracefully."""
        try:
            # Handle datetime objects
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            
            # Handle Pydantic models
            if hasattr(obj, 'model_dump'):
                return obj.model_dump()
            
            # Handle exceptions
            if isinstance(obj, Exception):
                return {
                    'error_type': type(obj).__name__,
                    'message': str(obj)
                }
            
            # Handle other objects by converting to string
            return str(obj)
        except Exception:
            return "<non-serializable>"
    
    try:
        return json.dumps(obj, default=json_serializer, indent=2)
    except Exception:
        return f"<serialization-error: {type(obj).__name__}>"


def scrub_argv(argv: list) -> list:
    """
    Scrubs command-line arguments to prevent sensitive credentials from appearing in logs.
    
    This function is specifically designed for logging integration and creates a sanitized
    copy of argv with credential values replaced by '[REDACTED]' before any logging occurs.
    It provides comprehensive credential scrubbing for all credential-passing flags to
    guarantee that secrets never enter the logging pipeline.
    
    The function handles both flag-value pairs ('--access-key', 'secret123') and
    --flag=value format ('--access-key=secret123') for comprehensive credential scrubbing.
    This early argv scrubbing ensures complete compliance with security auditing requirements
    by blocking any literal secret/token strings from appearing in logs.
    
    Args:
        argv (list): List of command-line arguments to scrub. Can be None or empty.
    
    Returns:
        list: Scrubbed copy of arguments with sensitive values replaced by '[REDACTED]'.
              Returns empty list if argv is None or empty.
    
    Examples:
        >>> scrub_argv(['--access-key', 'secret123', '--verbose'])
        ['--access-key', '[REDACTED]', '--verbose']
        
        >>> scrub_argv(['--access-key=secret123', '--password=pass456'])
        ['--access-key=[REDACTED]', '--password=[REDACTED]']
        
        >>> scrub_argv(['-k', 'key123', '-p', 'pass456'])
        ['-k', '[REDACTED]', '-p', '[REDACTED]']
    """
    # Handle None or empty argv
    if not argv:
        return []
    
    # Create a copy to avoid modifying the original
    scrubbed = []
    
    # Define all credential-passing flags that need redaction
    credential_flags = {
        '-k', '--access-key', '--access-key-id',
        '-p', '--password',
        '--token', '--secret', '--key', '--credential',
        '--access-secret', '--api-key', '--api-secret'
    }
    
    i = 0
    while i < len(argv):
        arg = argv[i]
        
        # Check for --flag=value format first
        if '=' in arg:
            key, value = arg.split('=', 1)
            if key in credential_flags:
                scrubbed.append(f"{key}=[REDACTED]")
            else:
                scrubbed.append(arg)
        else:
            # Add the current argument
            scrubbed.append(arg)
            
            # Check if this is a credential flag with separate value
            if arg in credential_flags:
                # If there's a next argument and it's not another flag, redact it
                if i + 1 < len(argv) and not argv[i + 1].startswith('-'):
                    scrubbed.append('[REDACTED]')
                    i += 1  # Skip the original value
        
        i += 1
    
    return scrubbed


def sanitize_argv(argv: list) -> list:
    """
    Sanitizes command-line arguments to prevent sensitive credentials from appearing in logs.
    
    This function replaces values for sensitive arguments like --access-key-id, --access-secret,
    and their short forms with '[REDACTED]' markers while preserving the argument structure.
    
    Args:
        argv (list): List of command-line arguments to sanitize.
    
    Returns:
        list: Sanitized list of arguments with sensitive values replaced.
    
    Examples:
        >>> sanitize_argv(['--access-key-id', 'secret123', '--verbose'])
        ['--access-key-id', '[REDACTED]', '--verbose']
    """
    if not argv:
        return []
    
    sanitized = []
    sensitive_args = {
        '--access-key-id', '-k',
        '--access-secret', '-p',
        '--password',
        '--token',
        '--secret',
        '--key',
        '--credential'
    }
    
    i = 0
    while i < len(argv):
        arg = argv[i]
        sanitized.append(arg)
        
        # Check if this is a sensitive argument
        if arg in sensitive_args:
            # If there's a next argument and it's not another flag, redact it
            if i + 1 < len(argv) and not argv[i + 1].startswith('-'):
                sanitized.append('[REDACTED]')
                i += 1  # Skip the original value
        # Check for --arg=value format
        elif '=' in arg:
            key, value = arg.split('=', 1)
            if key in sensitive_args:
                sanitized[-1] = f"{key}=[REDACTED]"
        
        i += 1
    
    return sanitized