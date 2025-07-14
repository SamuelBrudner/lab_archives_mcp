"""
LabArchives API Response Fixtures

This module provides static and dynamic fixture data representing LabArchives API responses
for use in unit and integration tests. These fixtures simulate real API responses to enable
deterministic, isolated, and repeatable testing of all API integration code paths.

The fixtures support:
- Notebook list, page list, entry list, and user context responses
- Both JSON and XML response formats from LabArchives API
- Success scenarios with valid data structures
- Error scenarios and malformed data for negative testing
- Deterministic test data for consistent test results

All fixtures are designed to be compatible with the data models defined in
src/cli/api/models.py and support comprehensive testing of API response parsing,
validation, and error handling logic.
"""

from datetime import datetime  # builtin
import json  # builtin

from src.cli.api.models import (
    NotebookListResponse,
    PageListResponse, 
    EntryListResponse,
    UserContextResponse
)


# =============================================================================
# JSON Response Fixtures - Success Scenarios
# =============================================================================

# Valid notebook list response with comprehensive metadata
NOTEBOOK_LIST_JSON = """{
  "notebooks": [
    {
      "id": "nb_123456",
      "name": "Protein Analysis Lab Notebook",
      "description": "Research notebook for protein structure analysis experiments",
      "owner": "researcher@university.edu",
      "created_date": "2024-01-15T10:30:00Z",
      "last_modified": "2024-11-20T14:22:35Z",
      "folder_count": 5,
      "page_count": 24
    },
    {
      "id": "nb_789012",
      "name": "Cell Culture Experiments",
      "description": "Documentation of cell culture protocols and results",
      "owner": "labtech@university.edu",
      "created_date": "2024-02-01T09:00:00Z",
      "last_modified": "2024-11-21T11:15:22Z",
      "folder_count": 3,
      "page_count": 18
    }
  ],
  "status": "success",
  "message": "Successfully retrieved 2 notebooks"
}"""

# Valid page list response for notebook content discovery
PAGE_LIST_JSON = """{
  "pages": [
    {
      "id": "page_789012",
      "notebook_id": "nb_123456",
      "title": "Experiment 1: Protein Purification Protocol",
      "folder_path": "/Experiments/Protein Analysis/Purification",
      "created_date": "2024-01-16T09:15:00Z",
      "last_modified": "2024-11-20T16:45:12Z",
      "entry_count": 8,
      "author": "researcher@university.edu"
    },
    {
      "id": "page_345678",
      "notebook_id": "nb_123456",
      "title": "Experiment 2: Structural Analysis Results",
      "folder_path": "/Experiments/Protein Analysis/Structure",
      "created_date": "2024-01-18T14:30:00Z",
      "last_modified": "2024-11-21T10:20:45Z",
      "entry_count": 12,
      "author": "researcher@university.edu"
    }
  ],
  "status": "success",
  "message": "Successfully retrieved 2 pages from notebook"
}"""

# Valid entry list response with various content types
ENTRY_LIST_JSON = """{
  "entries": [
    {
      "id": "entry_345678",
      "page_id": "page_789012",
      "entry_type": "text",
      "title": "Experimental Procedure",
      "content": "1. Prepare protein sample in buffer solution (50mM Tris-HCl, pH 7.4)\\n2. Centrifuge at 10,000g for 10 minutes\\n3. Collect supernatant and measure protein concentration\\n4. Proceed with purification using affinity chromatography",
      "created_date": "2024-01-16T10:30:00Z",
      "last_modified": "2024-11-20T17:12:48Z",
      "author": "researcher@university.edu",
      "version": 3,
      "metadata": {
        "word_count": 45,
        "mime_type": "text/plain",
        "tags": ["protein", "purification", "experiment", "protocol"]
      }
    },
    {
      "id": "entry_901234",
      "page_id": "page_789012",
      "entry_type": "attachment",
      "title": "Experimental Data File",
      "content": "Raw data from protein purification experiment - contains concentration measurements and chromatography results",
      "created_date": "2024-01-16T15:45:00Z",
      "last_modified": "2024-01-16T15:45:00Z",
      "author": "researcher@university.edu",
      "version": 1,
      "metadata": {
        "file_size": 2048576,
        "mime_type": "application/vnd.ms-excel",
        "filename": "protein_purification_data.xlsx",
        "attachment_count": 1
      }
    }
  ],
  "status": "success",
  "message": "Successfully retrieved 2 entries from page"
}"""

# Valid user context response for authentication scenarios
USER_CONTEXT_JSON = """{
  "user": {
    "uid": "user_987654",
    "name": "Dr. Sarah Johnson",
    "email": "sarah.johnson@university.edu",
    "roles": ["researcher", "notebook_owner", "collaborator"]
  },
  "status": "success",
  "message": "User context retrieved successfully"
}"""


# =============================================================================
# XML Response Fixtures - Success Scenarios
# =============================================================================

# Valid notebook list response in XML format
NOTEBOOK_LIST_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response>
    <notebooks>
        <notebook id="nb_123456" name="Protein Analysis Lab Notebook" description="Research notebook for protein structure analysis experiments" owner="researcher@university.edu" created_date="2024-01-15T10:30:00Z" last_modified="2024-11-20T14:22:35Z" folder_count="5" page_count="24" />
        <notebook id="nb_789012" name="Cell Culture Experiments" description="Documentation of cell culture protocols and results" owner="labtech@university.edu" created_date="2024-02-01T09:00:00Z" last_modified="2024-11-21T11:15:22Z" folder_count="3" page_count="18" />
    </notebooks>
    <status>success</status>
    <message>Successfully retrieved 2 notebooks</message>
</response>"""

# Valid page list response in XML format
PAGE_LIST_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response>
    <pages>
        <page id="page_789012" notebook_id="nb_123456" title="Experiment 1: Protein Purification Protocol" folder_path="/Experiments/Protein Analysis/Purification" created_date="2024-01-16T09:15:00Z" last_modified="2024-11-20T16:45:12Z" entry_count="8" author="researcher@university.edu" />
        <page id="page_345678" notebook_id="nb_123456" title="Experiment 2: Structural Analysis Results" folder_path="/Experiments/Protein Analysis/Structure" created_date="2024-01-18T14:30:00Z" last_modified="2024-11-21T10:20:45Z" entry_count="12" author="researcher@university.edu" />
    </pages>
    <status>success</status>
    <message>Successfully retrieved 2 pages from notebook</message>
</response>"""

# Valid entry list response in XML format
ENTRY_LIST_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response>
    <entries>
        <entry id="entry_345678" page_id="page_789012" entry_type="text" title="Experimental Procedure" content="1. Prepare protein sample in buffer solution (50mM Tris-HCl, pH 7.4)&#10;2. Centrifuge at 10,000g for 10 minutes&#10;3. Collect supernatant and measure protein concentration&#10;4. Proceed with purification using affinity chromatography" created_date="2024-01-16T10:30:00Z" last_modified="2024-11-20T17:12:48Z" author="researcher@university.edu" version="3" />
        <entry id="entry_901234" page_id="page_789012" entry_type="attachment" title="Experimental Data File" content="Raw data from protein purification experiment - contains concentration measurements and chromatography results" created_date="2024-01-16T15:45:00Z" last_modified="2024-01-16T15:45:00Z" author="researcher@university.edu" version="1" />
    </entries>
    <status>success</status>
    <message>Successfully retrieved 2 entries from page</message>
</response>"""

# Valid user context response in XML format
USER_CONTEXT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response>
    <user uid="user_987654" name="Dr. Sarah Johnson" email="sarah.johnson@university.edu" roles="researcher,notebook_owner,collaborator" />
    <status>success</status>
    <message>User context retrieved successfully</message>
</response>"""


# =============================================================================
# Error and Malformed Response Fixtures
# =============================================================================

# Malformed JSON response for testing error handling
MALFORMED_JSON = """{
  "notebooks": [
    {
      "id": "nb_123456",
      "name": "Test Notebook",
      "missing_required_field": true,
      "invalid_date": "not-a-date",
      "invalid_count": "not-a-number"
    }
  ],
  "status": 123,
  "incomplete_object": {
    "missing_closing_brace": true"""

# API error response for authentication and authorization failures
ERROR_JSON = """{
  "status": "error",
  "error_code": "AUTH_001",
  "message": "Invalid credentials or expired token",
  "timestamp": "2024-11-21T14:30:00Z",
  "details": {
    "error_type": "authentication_failure",
    "requested_resource": "/api/notebooks/list",
    "user_id": null
  }
}"""

# Network timeout error response
TIMEOUT_ERROR_JSON = """{
  "status": "error",
  "error_code": "NETWORK_001",
  "message": "Request timeout - server did not respond within expected time",
  "timestamp": "2024-11-21T14:35:00Z",
  "details": {
    "error_type": "timeout",
    "timeout_duration": "30s",
    "retry_after": "5s"
  }
}"""

# Rate limiting error response
RATE_LIMIT_ERROR_JSON = """{
  "status": "error",
  "error_code": "RATE_001",
  "message": "Rate limit exceeded - too many requests",
  "timestamp": "2024-11-21T14:40:00Z",
  "details": {
    "error_type": "rate_limit",
    "limit": "100 requests per hour",
    "reset_time": "2024-11-21T15:00:00Z"
  }
}"""

# Invalid XML response for testing XML parsing error handling
MALFORMED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response>
    <notebooks>
        <notebook id="nb_123456" name="Test Notebook" invalid_attr=
        <!-- Missing closing tag and malformed attribute -->
    </notebooks>
    <status>error</status>
    <!-- Missing closing response tag -->"""


# =============================================================================
# Fixture Retrieval Functions
# =============================================================================

def get_notebook_list_json() -> str:
    """
    Returns a valid JSON string representing a successful notebook list API response.
    
    This fixture provides a comprehensive notebook list response with multiple notebooks
    containing realistic metadata fields including IDs, names, descriptions, ownership,
    timestamps, and content counts. Used for testing notebook discovery functionality.
    
    Returns:
        str: JSON string for notebook list response with success status
    """
    return NOTEBOOK_LIST_JSON


def get_page_list_json() -> str:
    """
    Returns a valid JSON string representing a successful page list API response.
    
    This fixture provides a page list response with multiple pages containing
    hierarchical information including notebook relationships, folder paths,
    and entry counts. Used for testing page discovery within notebooks.
    
    Returns:
        str: JSON string for page list response with success status
    """
    return PAGE_LIST_JSON


def get_entry_list_json() -> str:
    """
    Returns a valid JSON string representing a successful entry list API response.
    
    This fixture provides an entry list response with multiple entries of different
    types (text, attachment) including content, metadata, and version information.
    Used for testing content retrieval and parsing functionality.
    
    Returns:
        str: JSON string for entry list response with success status
    """
    return ENTRY_LIST_JSON


def get_user_context_json() -> str:
    """
    Returns a valid JSON string representing a successful user context API response.
    
    This fixture provides a user context response with comprehensive user information
    including unique ID, profile details, and role assignments. Used for testing
    authentication and authorization workflows.
    
    Returns:
        str: JSON string for user context response with success status
    """
    return USER_CONTEXT_JSON


def get_notebook_list_xml() -> str:
    """
    Returns a valid XML string representing a successful notebook list API response.
    
    This fixture provides the same notebook list data as the JSON version but in
    XML format for testing XML response parsing capabilities. Includes proper
    XML declaration and structured element hierarchy.
    
    Returns:
        str: XML string for notebook list response with success status
    """
    return NOTEBOOK_LIST_XML


def get_page_list_xml() -> str:
    """
    Returns a valid XML string representing a successful page list API response.
    
    This fixture provides the same page list data as the JSON version but in
    XML format for testing XML response parsing capabilities. Includes proper
    attribute encoding and hierarchical structure.
    
    Returns:
        str: XML string for page list response with success status
    """
    return PAGE_LIST_XML


def get_entry_list_xml() -> str:
    """
    Returns a valid XML string representing a successful entry list API response.
    
    This fixture provides the same entry list data as the JSON version but in
    XML format for testing XML response parsing capabilities. Includes proper
    content encoding and special character handling.
    
    Returns:
        str: XML string for entry list response with success status
    """
    return ENTRY_LIST_XML


def get_user_context_xml() -> str:
    """
    Returns a valid XML string representing a successful user context API response.
    
    This fixture provides the same user context data as the JSON version but in
    XML format for testing XML response parsing capabilities. Includes proper
    attribute formatting and comma-separated role lists.
    
    Returns:
        str: XML string for user context response with success status
    """
    return USER_CONTEXT_XML


def get_malformed_json() -> str:
    """
    Returns a malformed JSON string to test error handling and validation failures.
    
    This fixture provides intentionally malformed JSON data with missing required
    fields, invalid data types, and incomplete structure. Used for testing the
    system's ability to handle malformed API responses gracefully.
    
    Returns:
        str: Malformed JSON string with various structural and data errors
    """
    return MALFORMED_JSON


def get_error_json() -> str:
    """
    Returns a JSON string representing an error response from the API.
    
    This fixture provides a structured error response representing authentication
    failures, authorization issues, or other API errors. Used for testing error
    handling logic and user-friendly error message generation.
    
    Returns:
        str: Error JSON string with structured error information
    """
    return ERROR_JSON


def get_timeout_error_json() -> str:
    """
    Returns a JSON string representing a network timeout error response.
    
    This fixture provides a structured error response for network timeout scenarios
    to test timeout handling, retry logic, and graceful degradation functionality.
    
    Returns:
        str: Timeout error JSON string with retry information
    """
    return TIMEOUT_ERROR_JSON


def get_rate_limit_error_json() -> str:
    """
    Returns a JSON string representing a rate limiting error response.
    
    This fixture provides a structured error response for rate limiting scenarios
    to test rate limit handling, backoff strategies, and user notification logic.
    
    Returns:
        str: Rate limit error JSON string with limit and reset information
    """
    return RATE_LIMIT_ERROR_JSON


def get_malformed_xml() -> str:
    """
    Returns a malformed XML string to test XML parsing error handling.
    
    This fixture provides intentionally malformed XML data with missing closing
    tags, invalid attributes, and incomplete structure. Used for testing the
    system's ability to handle malformed XML responses gracefully.
    
    Returns:
        str: Malformed XML string with various structural errors
    """
    return MALFORMED_XML


# =============================================================================
# Dynamic Fixture Generation Functions
# =============================================================================

def create_notebook_response(notebook_count: int = 1, include_errors: bool = False) -> str:
    """
    Creates a dynamic notebook list response with specified number of notebooks.
    
    This function generates notebook list responses with configurable content for
    testing various scenarios including large result sets, empty responses, and
    error conditions. Supports both success and error response generation.
    
    Args:
        notebook_count: Number of notebooks to include in response (default: 1)
        include_errors: Whether to include error status in response (default: False)
        
    Returns:
        str: JSON string with dynamically generated notebook list response
    """
    notebooks = []
    
    for i in range(notebook_count):
        notebook = {
            "id": f"nb_{1000000 + i}",
            "name": f"Generated Notebook {i + 1}",
            "description": f"Dynamically generated notebook {i + 1} for testing",
            "owner": f"testuser{i + 1}@university.edu",
            "created_date": datetime.now().isoformat() + "Z",
            "last_modified": datetime.now().isoformat() + "Z",
            "folder_count": (i + 1) * 2,
            "page_count": (i + 1) * 5
        }
        notebooks.append(notebook)
    
    response = {
        "notebooks": notebooks,
        "status": "error" if include_errors else "success",
        "message": f"Generated {notebook_count} notebooks for testing"
    }
    
    return json.dumps(response, indent=2)


def create_empty_response(response_type: str = "notebooks") -> str:
    """
    Creates an empty response for testing scenarios with no data.
    
    This function generates empty API responses for testing edge cases where
    no data is available, such as empty notebooks, pages with no entries, or
    users with no accessible content.
    
    Args:
        response_type: Type of response to create ("notebooks", "pages", "entries", "user")
        
    Returns:
        str: JSON string with empty response of specified type
    """
    response_templates = {
        "notebooks": {
            "notebooks": [],
            "status": "success",
            "message": "No notebooks found for user"
        },
        "pages": {
            "pages": [],
            "status": "success", 
            "message": "No pages found in notebook"
        },
        "entries": {
            "entries": [],
            "status": "success",
            "message": "No entries found on page"
        },
        "user": {
            "user": None,
            "status": "error",
            "message": "User not found or not authenticated"
        }
    }
    
    return json.dumps(response_templates.get(response_type, {}), indent=2)


# =============================================================================
# Response Validation Functions
# =============================================================================

def validate_notebook_response(response_json: str) -> bool:
    """
    Validates a notebook list response against the expected schema.
    
    This function parses and validates notebook list responses to ensure they
    conform to the expected data structure and contain valid data types. Used
    for testing response validation logic.
    
    Args:
        response_json: JSON string to validate
        
    Returns:
        bool: True if response is valid, False otherwise
    """
    try:
        response_data = json.loads(response_json)
        # Use Pydantic model for validation
        NotebookListResponse(**response_data)
        return True
    except (json.JSONDecodeError, ValueError, TypeError):
        return False


def validate_page_response(response_json: str) -> bool:
    """
    Validates a page list response against the expected schema.
    
    This function parses and validates page list responses to ensure they
    conform to the expected data structure and contain valid data types. Used
    for testing response validation logic.
    
    Args:
        response_json: JSON string to validate
        
    Returns:
        bool: True if response is valid, False otherwise
    """
    try:
        response_data = json.loads(response_json)
        # Use Pydantic model for validation
        PageListResponse(**response_data)
        return True
    except (json.JSONDecodeError, ValueError, TypeError):
        return False


def validate_entry_response(response_json: str) -> bool:
    """
    Validates an entry list response against the expected schema.
    
    This function parses and validates entry list responses to ensure they
    conform to the expected data structure and contain valid data types. Used
    for testing response validation logic.
    
    Args:
        response_json: JSON string to validate
        
    Returns:
        bool: True if response is valid, False otherwise
    """
    try:
        response_data = json.loads(response_json)
        # Use Pydantic model for validation
        EntryListResponse(**response_data)
        return True
    except (json.JSONDecodeError, ValueError, TypeError):
        return False


def validate_user_response(response_json: str) -> bool:
    """
    Validates a user context response against the expected schema.
    
    This function parses and validates user context responses to ensure they
    conform to the expected data structure and contain valid data types. Used
    for testing response validation logic.
    
    Args:
        response_json: JSON string to validate
        
    Returns:
        bool: True if response is valid, False otherwise
    """
    try:
        response_data = json.loads(response_json)
        # Use Pydantic model for validation
        UserContextResponse(**response_data)
        return True
    except (json.JSONDecodeError, ValueError, TypeError):
        return False


# =============================================================================
# Test Fixture Registry
# =============================================================================

# Registry of all available test fixtures for automated testing
FIXTURE_REGISTRY = {
    "notebook_list_json": get_notebook_list_json,
    "page_list_json": get_page_list_json,
    "entry_list_json": get_entry_list_json,
    "user_context_json": get_user_context_json,
    "notebook_list_xml": get_notebook_list_xml,
    "page_list_xml": get_page_list_xml,
    "entry_list_xml": get_entry_list_xml,
    "user_context_xml": get_user_context_xml,
    "malformed_json": get_malformed_json,
    "error_json": get_error_json,
    "timeout_error_json": get_timeout_error_json,
    "rate_limit_error_json": get_rate_limit_error_json,
    "malformed_xml": get_malformed_xml
}


def get_fixture(fixture_name: str) -> str:
    """
    Retrieves a test fixture by name from the registry.
    
    This function provides a centralized way to access all available test fixtures
    for automated testing scenarios. Supports both static and dynamic fixture
    retrieval based on the fixture name.
    
    Args:
        fixture_name: Name of the fixture to retrieve
        
    Returns:
        str: The requested fixture data
        
    Raises:
        KeyError: If the fixture name is not found in the registry
    """
    if fixture_name not in FIXTURE_REGISTRY:
        raise KeyError(f"Fixture '{fixture_name}' not found in registry")
    
    return FIXTURE_REGISTRY[fixture_name]()


def list_available_fixtures() -> list:
    """
    Returns a list of all available fixture names.
    
    This function provides a way to discover all available test fixtures for
    documentation and testing purposes. Useful for automated test generation
    and fixture validation.
    
    Returns:
        list: List of available fixture names
    """
    return list(FIXTURE_REGISTRY.keys())