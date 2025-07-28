"""
Constants for LabArchives MCP Server

This module contains all the constant values used throughout the LabArchives MCP Server,
including default values, URLs, timeouts, and other configuration constants.
"""

# Export list for explicit module interface definition
__all__ = [
    # API Configuration Constants
    'DEFAULT_API_BASE_URL',
    'AU_API_BASE_URL',
    'UK_API_BASE_URL',
    'DEFAULT_TIMEOUT_SECONDS',
    'DEFAULT_RETRY_COUNT',
    'DEFAULT_RETRY_BACKOFF',
    # Region Configuration
    'SUPPORTED_REGIONS',
    'REGION_API_BASE_URLS',
    # Security and Scope Constants - Required for security validators module
    'SUPPORTED_SCOPE_TYPES',
    # MCP Configuration
    'MCP_RESOURCE_URI_SCHEME',
    'MCP_SERVER_NAME',
    'MCP_SERVER_VERSION',
    'DEFAULT_PROTOCOL_VERSION',
    # Logging Configuration
    'DEFAULT_LOG_FILE',
    'DEFAULT_AUDIT_LOG_FILE',
    'DEFAULT_LOG_LEVEL',
    'LOG_FORMAT_STRING',
    'AUDIT_LOG_FORMAT_STRING',
    # CLI Configuration
    'DEFAULT_CLI_CONFIG_FILE',
]

# Default LabArchives API configuration
DEFAULT_API_BASE_URL = "https://api.labarchives.com"
AU_API_BASE_URL = "https://auapi.labarchives.com"
UK_API_BASE_URL = "https://ukapi.labarchives.com"
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_BACKOFF = 2

# Supported regions
SUPPORTED_REGIONS = ["US", "AU", "UK"]

# Region API base URLs mapping
REGION_API_BASE_URLS = {
    "US": DEFAULT_API_BASE_URL,
    "AU": AU_API_BASE_URL,
    "UK": UK_API_BASE_URL,
}

# Supported scope types
SUPPORTED_SCOPE_TYPES = ["notebook_id", "notebook_name", "folder_path"]

# MCP Resource URI Scheme
MCP_RESOURCE_URI_SCHEME = "labarchives://"

# MCP Protocol Version (as per MCP specification 2024-11-05)
DEFAULT_PROTOCOL_VERSION = "2024-11-05"

# Default log configuration
DEFAULT_LOG_FILE = "labarchives_mcp.log"
DEFAULT_AUDIT_LOG_FILE = "labarchives_mcp_audit.log"
DEFAULT_LOG_LEVEL = "INFO"

# Default CLI configuration file
DEFAULT_CLI_CONFIG_FILE = "labarchives_mcp_config.json"

# Log format strings
LOG_FORMAT_STRING = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
AUDIT_LOG_FORMAT_STRING = "%(asctime)s - AUDIT - %(name)s - %(levelname)s - %(message)s"

# MCP Server information
MCP_SERVER_NAME = "labarchives-mcp"
MCP_SERVER_VERSION = "1.0.0"
