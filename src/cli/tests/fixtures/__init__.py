"""
Test fixtures package for LabArchives MCP Server.

This package provides reusable test fixtures, mock data, and test utilities
for unit and integration tests of the LabArchives MCP Server. It supports
the testing strategy outlined in the technical specification, enabling
deterministic and isolated test cases.

The fixtures package contains:
- Mock LabArchives API responses
- Sample notebook, page, and entry data
- MCP protocol message fixtures
- Authentication and session fixtures
- Configuration test data

Test fixtures are designed to support the comprehensive testing approach
including unit tests, integration tests, and end-to-end testing scenarios.
"""

# Package metadata
__version__ = "0.1.0"
__author__ = "LabArchives MCP Server Team"

# Common test constants used across multiple test modules
TEST_NOTEBOOK_ID = "nb_test_123"
TEST_PAGE_ID = "page_test_456"
TEST_ENTRY_ID = "entry_test_789"
TEST_USER_ID = "user_test_12345"

# Common test configuration values
TEST_ACCESS_KEY_ID = "test_access_key_id"
TEST_ACCESS_SECRET = "test_access_secret"  
TEST_USERNAME = "test@example.com"
TEST_API_BASE_URL = "https://api.labarchives.com/api"

# MCP protocol test constants
MCP_PROTOCOL_VERSION = "2024-11-05"
MCP_SERVER_NAME = "labarchives-mcp-server"
MCP_SERVER_VERSION = "0.1.0"

def get_test_notebook_data():
    """
    Return standard test notebook data for consistent testing.
    
    Returns:
        dict: Sample notebook metadata structure
    """
    return {
        "id": TEST_NOTEBOOK_ID,
        "name": "Test Lab Notebook",
        "description": "Sample notebook for testing purposes",
        "owner": TEST_USERNAME,
        "created_date": "2024-01-01T00:00:00Z",
        "last_modified": "2024-01-01T12:00:00Z",
        "folder_count": 3,
        "page_count": 5
    }

def get_test_page_data():
    """
    Return standard test page data for consistent testing.
    
    Returns:
        dict: Sample page metadata structure
    """
    return {
        "id": TEST_PAGE_ID,
        "notebook_id": TEST_NOTEBOOK_ID,
        "title": "Test Page",
        "folder_path": "/Test Folder",
        "created_date": "2024-01-01T10:00:00Z",
        "last_modified": "2024-01-01T14:00:00Z",
        "entry_count": 3,
        "author": TEST_USERNAME
    }

def get_test_entry_data():
    """
    Return standard test entry data for consistent testing.
    
    Returns:
        dict: Sample entry content structure
    """
    return {
        "id": TEST_ENTRY_ID,
        "page_id": TEST_PAGE_ID,
        "entry_type": "text",
        "title": "Test Entry",
        "content": "Sample test content for experimental data",
        "created_date": "2024-01-01T11:00:00Z",
        "last_modified": "2024-01-01T13:00:00Z",
        "author": TEST_USERNAME,
        "version": 1,
        "metadata": {"test_flag": True}
    }

def get_test_mcp_resource_uri():
    """
    Return standard MCP resource URI for testing.
    
    Returns:
        str: Sample MCP resource URI
    """
    return f"labarchives://notebook/{TEST_NOTEBOOK_ID}"

def get_test_mcp_page_uri():
    """
    Return standard MCP page resource URI for testing.
    
    Returns:
        str: Sample MCP page resource URI
    """
    return f"labarchives://notebook/{TEST_NOTEBOOK_ID}/page/{TEST_PAGE_ID}"

def get_test_mcp_entry_uri():
    """
    Return standard MCP entry resource URI for testing.
    
    Returns:
        str: Sample MCP entry resource URI
    """
    return f"labarchives://entry/{TEST_ENTRY_ID}"

def get_test_auth_credentials():
    """
    Return standard test authentication credentials.
    
    Returns:
        dict: Test authentication configuration
    """
    return {
        "access_key_id": TEST_ACCESS_KEY_ID,
        "access_secret": TEST_ACCESS_SECRET,
        "username": TEST_USERNAME,
        "api_base_url": TEST_API_BASE_URL
    }

def get_test_mcp_capabilities():
    """
    Return standard MCP server capabilities for testing.
    
    Returns:
        dict: MCP server capabilities structure
    """
    return {
        "protocol_version": MCP_PROTOCOL_VERSION,
        "server_name": MCP_SERVER_NAME,
        "server_version": MCP_SERVER_VERSION,
        "capabilities": {
            "resources": True,
            "tools": False,
            "prompts": False,
            "logging": True
        }
    }

def get_test_scope_config():
    """
    Return standard test scope configuration.
    
    Returns:
        dict: Test scope configuration structure
    """
    return {
        "notebook_id": TEST_NOTEBOOK_ID,
        "notebook_name": "Test Lab Notebook",
        "folder_path": "/Test Folder"
    }

# Export commonly used test utilities and constants
__all__ = [
    "TEST_NOTEBOOK_ID",
    "TEST_PAGE_ID", 
    "TEST_ENTRY_ID",
    "TEST_USER_ID",
    "TEST_ACCESS_KEY_ID",
    "TEST_ACCESS_SECRET",
    "TEST_USERNAME",
    "TEST_API_BASE_URL",
    "MCP_PROTOCOL_VERSION",
    "MCP_SERVER_NAME",
    "MCP_SERVER_VERSION",
    "get_test_notebook_data",
    "get_test_page_data",
    "get_test_entry_data",
    "get_test_mcp_resource_uri",
    "get_test_mcp_page_uri",
    "get_test_mcp_entry_uri",
    "get_test_auth_credentials",
    "get_test_mcp_capabilities",
    "get_test_scope_config"
]