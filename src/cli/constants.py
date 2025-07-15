"""
Constants for LabArchives MCP Server

This module contains all the constant values used throughout the LabArchives MCP Server,
including default values, URLs, timeouts, and other configuration constants.
"""

# Default LabArchives API configuration
DEFAULT_API_BASE_URL = "https://api.labarchives.com"
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_BACKOFF = 2

# MCP Resource URI Scheme
MCP_RESOURCE_URI_SCHEME = "labarchives://"

# Default log configuration
DEFAULT_LOG_FILE = "labarchives_mcp.log"
DEFAULT_AUDIT_LOG_FILE = "labarchives_mcp_audit.log"
DEFAULT_LOG_LEVEL = "INFO"

# Log format strings
LOG_FORMAT_STRING = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
AUDIT_LOG_FORMAT_STRING = "%(asctime)s - AUDIT - %(name)s - %(levelname)s - %(message)s"

# MCP Server information
MCP_SERVER_NAME = "labarchives-mcp"
MCP_SERVER_VERSION = "1.0.0"