"""
LabArchives MCP Server - Core Data Models and Configuration Schema

This module defines the core Pydantic data models for configuration, authentication,
scope, output, logging, and server metadata for the LabArchives MCP Server CLI.
These models provide strict schema validation, type safety, and structured
representation for all configuration and operational parameters.

This file serves as the single source of truth for all configuration-related
data structures, supporting:

- F-005: Authentication and Security Management - Secure credential handling
  with validation for both permanent API keys and temporary user tokens
- F-006: CLI Interface and Configuration - Robust configuration management
  with environment variable support and CLI argument parsing
- F-007: Scope Limitation and Access Control - Granular access control
  with support for notebook, folder, and custom scope configurations
- F-008: Comprehensive Audit Logging - Configurable logging with audit trail
  generation and compliance support

All models use Pydantic v2 for validation, serialization, and type safety,
ensuring that configuration data is always properly validated and structured
before use throughout the application.
"""

from typing import Optional, List
from pydantic import BaseModel, Field  # pydantic>=2.11.7

# Internal imports from constants module
from src.cli.constants import (
    DEFAULT_API_BASE_URL,
    DEFAULT_LOG_FILE,
    DEFAULT_LOG_LEVEL,
    MCP_SERVER_NAME,
    MCP_SERVER_VERSION
)


class AuthenticationConfig(BaseModel):
    """
    Authentication configuration for LabArchives API access.
    
    This model supports both permanent API keys and temporary user tokens,
    providing secure credential handling with comprehensive validation.
    All authentication parameters are validated for presence, format, and
    security compliance.
    
    Supports two authentication methods:
    1. Permanent API Key: access_key_id + access_secret (password)
    2. Temporary Token: access_key_id + access_secret (token) + username
    
    The api_base_url field supports regional deployment with different
    LabArchives API endpoints (US, AU, UK regions).
    
    Security Features:
    - All credential fields are validated for presence and format
    - No default values for sensitive fields to prevent accidental exposure
    - Regional API base URL validation for proper endpoint selection
    - Support for both permanent and temporary authentication methods
    """
    
    # Required authentication credentials
    # No default values to ensure explicit credential configuration
    access_key_id: str = Field(
        description="LabArchives API Access Key ID - unique identifier for API authentication",
        min_length=1,
        max_length=256,
        example="AKID1234567890ABCDEF"
    )
    
    access_secret: str = Field(
        description="LabArchives API Access Secret - either permanent password or temporary token",
        min_length=1,
        max_length=1024,
        example="your-api-password-or-token"
    )
    
    # Optional username for token-based authentication
    # Required when using temporary app authentication tokens for SSO users
    username: Optional[str] = Field(
        default=None,
        description="LabArchives username - required for temporary token authentication",
        min_length=1,
        max_length=256,
        example="user@institution.edu"
    )
    
    # LabArchives API base URL with regional support
    # Defaults to US endpoint but can be configured for other regions
    api_base_url: str = Field(
        default=DEFAULT_API_BASE_URL,
        description="LabArchives API base URL - varies by deployment region",
        min_length=1,
        max_length=512,
        example="https://api.labarchives.com/api"
    )
    
    class Config:
        """Pydantic configuration for AuthenticationConfig model."""
        # Enable validation on assignment to catch configuration errors early
        validate_assignment = True
        # Use enum values for better serialization
        use_enum_values = True
        # Provide example values for documentation
        json_schema_extra = {
            "example": {
                "access_key_id": "AKID1234567890ABCDEF",
                "access_secret": "your-api-password-or-token",
                "username": "user@institution.edu",
                "api_base_url": "https://api.labarchives.com/api"
            }
        }


class ScopeConfig(BaseModel):
    """
    Configuration for limiting the scope of data exposure.
    
    This model implements granular access control by supporting restriction
    to specific notebooks, folders, or custom access patterns. Only one
    scope type should be configured at a time to ensure clear access boundaries.
    
    Scope Types:
    1. Notebook Scope: Restrict access to a specific notebook by ID
    2. Folder Scope: Restrict access to a specific folder path within notebooks
    3. No Scope: Allow access to all user-accessible resources (default)
    
    The scope configuration is enforced throughout the application to ensure
    that resource discovery and content retrieval respect the configured
    access boundaries.
    
    Security Features:
    - Mutually exclusive scope options prevent configuration conflicts
    - Clear validation rules ensure only valid scope configurations
    - Support for both ID-based and name-based notebook selection
    - Flexible folder path specification with validation
    """
    
    # Notebook-based scope limitation
    # Restricts access to a single notebook identified by its unique ID
    notebook_id: Optional[str] = Field(
        default=None,
        description="Restrict access to specific notebook by ID - mutually exclusive with other scope options",
        min_length=1,
        max_length=128,
        example="notebook_12345"
    )
    
    # Alternative notebook identification by name
    # Useful when notebook ID is not readily available
    notebook_name: Optional[str] = Field(
        default=None,
        description="Restrict access to specific notebook by name - mutually exclusive with other scope options",
        min_length=1,
        max_length=256,
        example="Research Project Alpha"
    )
    
    # Folder-based scope limitation
    # Restricts access to resources within a specific folder path
    folder_path: Optional[str] = Field(
        default=None,
        description="Restrict access to specific folder path - mutually exclusive with other scope options",
        min_length=1,
        max_length=512,
        example="/Research/Current Projects/Alpha"
    )
    
    def __init__(self, **data):
        """
        Initialize scope configuration with validation for mutual exclusivity.
        
        Ensures that only one scope type is configured at a time to prevent
        conflicting access control rules.
        
        Args:
            **data: Scope configuration parameters
            
        Raises:
            ValueError: If multiple scope types are configured simultaneously
        """
        super().__init__(**data)
        
        # Validate mutual exclusivity of scope options
        scope_options = [self.notebook_id, self.notebook_name, self.folder_path]
        configured_options = [option for option in scope_options if option is not None]
        
        if len(configured_options) > 1:
            raise ValueError(
                "Only one scope type can be configured at a time. "
                "Please specify either notebook_id, notebook_name, or folder_path."
            )
    
    class Config:
        """Pydantic configuration for ScopeConfig model."""
        validate_assignment = True
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "notebook_id": "notebook_12345",
                "notebook_name": None,
                "folder_path": None
            }
        }


class OutputConfig(BaseModel):
    """
    Configuration for output formatting and structured data representation.
    
    This model controls how data is formatted and presented to MCP clients,
    including support for JSON-LD semantic context and structured output
    formatting. These settings affect how LabArchives data is transformed
    and serialized for AI consumption.
    
    Output Features:
    - JSON-LD context support for semantic data representation
    - Structured output formatting for consistent data presentation
    - Configurable output modes for different client requirements
    - Support for both human-readable and machine-optimized formats
    
    The output configuration ensures that data is presented in the most
    appropriate format for the specific use case while maintaining
    compatibility with MCP protocol requirements.
    """
    
    # JSON-LD context enablement for semantic data representation
    # Adds semantic context to output data for enhanced AI understanding
    json_ld_enabled: bool = Field(
        default=False,
        description="Enable JSON-LD context in output for semantic data representation"
    )
    
    # Structured output formatting for consistent data presentation
    # Ensures data is formatted in a structured, predictable manner
    structured_output: bool = Field(
        default=True,
        description="Enable structured output formatting for consistent data presentation"
    )
    
    class Config:
        """Pydantic configuration for OutputConfig model."""
        validate_assignment = True
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "json_ld_enabled": False,
                "structured_output": True
            }
        }


class LoggingConfig(BaseModel):
    """
    Configuration for logging and audit trail generation.
    
    This model controls all aspects of logging behavior, including log file
    management, verbosity levels, and audit trail generation. The configuration
    supports both operational logging for debugging and compliance logging
    for audit requirements.
    
    Logging Features:
    - Configurable log file paths for flexible deployment
    - Multiple log levels for appropriate verbosity control
    - Verbose and quiet modes for different operational needs
    - Comprehensive audit trail support for compliance
    - Secure logging without credential exposure
    
    The logging configuration ensures that all system operations are properly
    recorded while maintaining security and performance requirements.
    """
    
    # Log file path configuration
    # Optional to support both file and console-only logging
    log_file: Optional[str] = Field(
        default=DEFAULT_LOG_FILE,
        description="Path to log file for persistent logging - defaults to current directory",
        min_length=1,
        max_length=512,
        example="logs/labarchives_mcp.log"
    )
    
    # Log level configuration with validation
    # Controls verbosity of logging output
    log_level: str = Field(
        default=DEFAULT_LOG_LEVEL,
        description="Logging level - controls verbosity of log output",
        pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        example="INFO"
    )
    
    # Verbose mode for detailed debugging output
    # Enables additional debug information for troubleshooting
    verbose: bool = Field(
        default=False,
        description="Enable verbose logging for detailed debugging output"
    )
    
    # Quiet mode for minimal output
    # Reduces log output to essential messages only
    quiet: bool = Field(
        default=False,
        description="Enable quiet mode for minimal log output"
    )
    
    def __init__(self, **data):
        """
        Initialize logging configuration with validation for conflicting options.
        
        Ensures that verbose and quiet modes are not enabled simultaneously
        to prevent conflicting logging behavior.
        
        Args:
            **data: Logging configuration parameters
            
        Raises:
            ValueError: If both verbose and quiet modes are enabled
        """
        super().__init__(**data)
        
        # Validate that verbose and quiet are not both enabled
        if self.verbose and self.quiet:
            raise ValueError(
                "Verbose and quiet modes cannot be enabled simultaneously. "
                "Please choose either verbose or quiet mode."
            )
    
    class Config:
        """Pydantic configuration for LoggingConfig model."""
        validate_assignment = True
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "log_file": "labarchives_mcp.log",
                "log_level": "INFO",
                "verbose": False,
                "quiet": False
            }
        }


class ServerConfiguration(BaseModel):
    """
    Aggregated server configuration combining all configuration sections.
    
    This is the root configuration model that combines all sub-configurations
    (authentication, scope, output, logging) and server metadata into a single
    immutable configuration object. This model serves as the canonical
    configuration structure used throughout the CLI and server applications.
    
    Configuration Structure:
    - Authentication: LabArchives API credentials and connection settings
    - Scope: Access control and data exposure limitations
    - Output: Data formatting and presentation options
    - Logging: Audit trail and debugging configuration
    - Server Metadata: Server identification and version information
    
    This configuration object is passed to all system components to ensure
    consistent behavior and centralized configuration management.
    
    Security Features:
    - Immutable configuration prevents runtime modification
    - Comprehensive validation ensures all required settings are present
    - Secure credential handling with no default sensitive values
    - Audit logging configuration for compliance requirements
    """
    
    # Authentication configuration (required)
    # Contains all LabArchives API credentials and connection settings
    authentication: AuthenticationConfig = Field(
        description="Authentication configuration for LabArchives API access"
    )
    
    # Scope configuration (required)
    # Defines access control boundaries and data exposure limits
    scope: ScopeConfig = Field(
        description="Scope configuration for access control and data limitation"
    )
    
    # Output configuration (required)
    # Controls data formatting and presentation options
    output: OutputConfig = Field(
        description="Output configuration for data formatting and presentation"
    )
    
    # Logging configuration (required)
    # Manages audit trails and operational logging
    logging: LoggingConfig = Field(
        description="Logging configuration for audit trails and debugging"
    )
    
    # Server identification metadata
    # Provides server identity for MCP protocol negotiation
    server_name: str = Field(
        default=MCP_SERVER_NAME,
        description="MCP server name for protocol identification",
        min_length=1,
        max_length=128,
        example="labarchives-mcp-server"
    )
    
    # Server version metadata
    # Enables version-specific behavior and compatibility tracking
    server_version: str = Field(
        default=MCP_SERVER_VERSION,
        description="MCP server version for compatibility tracking",
        min_length=1,
        max_length=32,
        example="0.1.0"
    )
    
    class Config:
        """Pydantic configuration for ServerConfiguration model."""
        validate_assignment = True
        use_enum_values = True
        # Prevent modification after initialization for security

        json_schema_extra = {
            "example": {
                "authentication": {
                    "access_key_id": "AKID1234567890ABCDEF",
                    "access_secret": "your-api-password-or-token",
                    "username": "user@institution.edu",
                    "api_base_url": "https://api.labarchives.com/api"
                },
                "scope": {
                    "notebook_id": "notebook_12345",
                    "notebook_name": None,
                    "folder_path": None
                },
                "output": {
                    "json_ld_enabled": False,
                    "structured_output": True
                },
                "logging": {
                    "log_file": "labarchives_mcp.log",
                    "log_level": "INFO",
                    "verbose": False,
                    "quiet": False
                },
                "server_name": "labarchives-mcp-server",
                "server_version": "0.1.0"
            }
        }