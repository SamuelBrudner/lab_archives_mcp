"""
LabArchives MCP Server - MCP Protocol Package

This package provides the complete MCP (Model Context Protocol) implementation for the LabArchives
MCP Server, exposing all protocol handlers, resource managers, data models, and error handling
components necessary for AI-to-data integration through the standardized MCP protocol.

This __init__.py file serves as the unified import surface for the MCP protocol stack, enabling
other components (such as CLI entrypoints or main server processes) to easily access all MCP
protocol functionality through a single import. It provides a clean separation between the
protocol implementation and the application layers while maintaining full functionality.

Key Exposed Components:

Protocol Handler Layer:
- MCPProtocolHandler: Main protocol handler for managing MCP session lifecycle
- parse_jsonrpc_message: JSON-RPC 2.0 message parsing and validation
- build_jsonrpc_response: JSON-RPC 2.0 response construction
- route_mcp_request: MCP request routing and handler dispatch

Resource Management Layer:
- MCPResourceManager: Core resource discovery and content retrieval manager
- parse_resource_uri: MCP resource URI parsing and validation
- is_resource_in_scope: Resource scope validation and access control

Data Models Layer:
- MCPResource: Basic resource representation for listing operations
- MCPResourceContent: Detailed content representation for reading operations
- MCPResourceListResponse: Response model for resources/list requests
- MCPResourceReadResponse: Response model for resources/read requests
- labarchives_to_mcp_resource: LabArchives to MCP model transformation
- MCP_JSONLD_CONTEXT: JSON-LD context for semantic enrichment

Error Handling Layer:
- handle_mcp_error: Centralized error handling for MCP operations
- MCP_ERROR_CODES: Standardized error codes for protocol compliance
- MCP_ERROR_MESSAGES: Human-readable error messages for user feedback
- MCPProtocolError: Exception class for MCP protocol-specific errors

All components are production-ready, extensively documented, and designed for enterprise-grade
deployment with comprehensive audit logging, security controls, and error handling throughout.
"""

# =============================================================================
# Protocol Handler Layer - Core MCP Protocol Implementation
# =============================================================================

# Import the main protocol handler class for MCP session management
from .protocol import MCPProtocolHandler

# Import JSON-RPC 2.0 message processing functions
from .protocol import parse_jsonrpc_message
from .protocol import build_jsonrpc_response

# Import request routing functionality
from .protocol import route_mcp_request

# =============================================================================
# Resource Management Layer - Resource Discovery and Content Retrieval
# =============================================================================

# Import the main resource manager class
from .resources import MCPResourceManager

# Import resource URI parsing and validation utilities
from .resources import parse_resource_uri

# Import scope validation and access control functions
from .resources import is_resource_in_scope

# =============================================================================
# Data Models Layer - MCP Protocol Data Structures
# =============================================================================

# Import core MCP resource models
from .models import MCPResource
from .models import MCPResourceContent

# Import MCP protocol response models
from .models import MCPResourceListResponse
from .models import MCPResourceReadResponse

# Import data transformation utilities
from .models import labarchives_to_mcp_resource

# Import JSON-LD context for semantic enrichment
from .models import MCP_JSONLD_CONTEXT

# =============================================================================
# Error Handling Layer - Comprehensive Error Management
# =============================================================================

# Import centralized error handling function
from .errors import handle_mcp_error

# Import standardized error codes and messages
from .errors import MCP_ERROR_CODES
from .errors import MCP_ERROR_MESSAGES

# Import MCP protocol exception class
from .errors import MCPProtocolError

# =============================================================================
# Package Exports - Public API Surface
# =============================================================================

# Define the complete public API for the MCP protocol package
# This ensures only the intended components are exposed when using 'from mcp import *'
__all__ = [
    # Protocol Handler Layer
    "MCPProtocolHandler",
    "parse_jsonrpc_message",
    "build_jsonrpc_response",
    "route_mcp_request",
    # Resource Management Layer
    "MCPResourceManager",
    "parse_resource_uri",
    "is_resource_in_scope",
    # Data Models Layer
    "MCPResource",
    "MCPResourceContent",
    "MCPResourceListResponse",
    "MCPResourceReadResponse",
    "labarchives_to_mcp_resource",
    "MCP_JSONLD_CONTEXT",
    # Error Handling Layer
    "handle_mcp_error",
    "MCP_ERROR_CODES",
    "MCP_ERROR_MESSAGES",
    "MCPProtocolError",
]

# =============================================================================
# Package Metadata and Version Information
# =============================================================================

# Package version and metadata for identification and debugging
__version__ = "0.1.0"
__author__ = "LabArchives MCP Server Team"
__description__ = "MCP Protocol Implementation for LabArchives Electronic Lab Notebook Integration"
__license__ = "MIT"

# MCP protocol version supported by this implementation
__mcp_protocol_version__ = "2024-11-05"

# Supported MCP capabilities exposed by this package
__mcp_capabilities__ = {
    "resources": {"subscribe": False, "listChanged": False},
    "tools": {},
    "prompts": {},
    "logging": {},
}

# =============================================================================
# Package Configuration and Constants
# =============================================================================

# URI scheme for LabArchives MCP resources
MCP_RESOURCE_URI_SCHEME = "labarchives://"

# Default MIME type for MCP resource content
MCP_RESOURCE_MIME_TYPE = "application/json"

# Maximum supported resource URI length
MAX_RESOURCE_URI_LENGTH = 500

# Package logger name for consistent logging across all MCP components
MCP_LOGGER_NAME = "mcp"

# =============================================================================
# Package Initialization and Validation
# =============================================================================


# Validate that all required components are available
def _validate_package_integrity():
    """
    Validates that all required MCP protocol components are properly imported and available.

    This function performs a comprehensive check of all exported components to ensure
    the package is in a valid state for use. It verifies that all classes, functions,
    and constants are properly imported and accessible.

    Raises:
        ImportError: If any required component is missing or not properly imported
        AttributeError: If any component is missing required attributes or methods
    """
    # Validate protocol handler components
    if not hasattr(MCPProtocolHandler, 'handle_message'):
        raise ImportError("MCPProtocolHandler missing required handle_message method")

    if not hasattr(MCPProtocolHandler, 'run_session'):
        raise ImportError("MCPProtocolHandler missing required run_session method")

    # Validate resource manager components
    if not hasattr(MCPResourceManager, 'list_resources'):
        raise ImportError("MCPResourceManager missing required list_resources method")

    if not hasattr(MCPResourceManager, 'read_resource'):
        raise ImportError("MCPResourceManager missing required read_resource method")

    # Validate data model components
    if not hasattr(MCPResource, 'dict'):
        raise ImportError("MCPResource missing required dict method")

    if not hasattr(MCPResourceContent, 'dict'):
        raise ImportError("MCPResourceContent missing required dict method")

    # Validate error handling components
    if not isinstance(MCP_ERROR_CODES, dict):
        raise ImportError("MCP_ERROR_CODES is not a dictionary")

    if not isinstance(MCP_ERROR_MESSAGES, dict):
        raise ImportError("MCP_ERROR_MESSAGES is not a dictionary")

    # Validate JSON-LD context
    if not isinstance(MCP_JSONLD_CONTEXT, dict):
        raise ImportError("MCP_JSONLD_CONTEXT is not a dictionary")

    if "@context" not in MCP_JSONLD_CONTEXT:
        raise ImportError("MCP_JSONLD_CONTEXT missing required @context field")


# Perform package validation on import
try:
    _validate_package_integrity()
except (ImportError, AttributeError) as e:
    # Log the validation error for debugging
    import logging

    logger = logging.getLogger(MCP_LOGGER_NAME)
    logger.error(f"MCP package validation failed: {e}")
    raise

# =============================================================================
# Package Import Success Confirmation
# =============================================================================

# Log successful package initialization for audit trail
import logging

logger = logging.getLogger(MCP_LOGGER_NAME)
logger.info(
    f"MCP protocol package initialized successfully",
    extra={
        "package_version": __version__,
        "mcp_protocol_version": __mcp_protocol_version__,
        "exported_components": len(__all__),
        "capabilities": __mcp_capabilities__,
    },
)
