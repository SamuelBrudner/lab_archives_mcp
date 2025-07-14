"""
Unit and Integration Tests for ResourceManager Class

This test module validates resource discovery (listing), content retrieval (reading), 
scope enforcement, error handling, and integration with the LabArchives API client.
It uses static and dynamic fixtures to simulate LabArchives API responses, 
configuration scenarios, and error conditions.

The tests ensure that the ResourceManager correctly orchestrates resource operations,
enforces scope and permissions, transforms LabArchives data to MCP resource models,
and handles all error and edge cases as specified. The module is critical for
regression prevention, protocol compliance, and robust, auditable resource management.

Test Coverage:
- F-003: Resource Discovery and Listing - Validates hierarchical navigation and MCP URI generation
- F-004: Content Retrieval and Contextualization - Validates content fetching and transformation
- F-007: Scope Limitation and Access Control - Validates scope restrictions and error handling
- F-008: Comprehensive Audit Logging - Validates logging of all operations and errors
- Deterministic and Isolated Testing - Uses mocked API responses for consistent results
"""

import pytest  # pytest>=7.0.0 - Python testing framework for fixtures and parameterized tests
import unittest.mock  # builtin - For mocking LabArchivesAPIClient and simulating API responses
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import List, Dict, Any

# Import system under test
from src.cli.resource_manager import ResourceManager, parse_resource_uri, is_resource_in_scope

# Import API client and models for mocking
from src.cli.api.client import LabArchivesAPIClient
from src.cli.api.models import (
    NotebookMetadata, PageMetadata, EntryContent,
    NotebookListResponse, PageListResponse, EntryListResponse
)

# Import exceptions for error handling validation
from src.cli.exceptions import LabArchivesMCPException
from src.cli.api.errors import APIError, APIAuthenticationError, APIPermissionError

# Import test fixtures for configuration and API responses
from src.cli.tests.fixtures.config_samples import get_valid_config, get_invalid_config
from src.cli.tests.fixtures.api_responses import (
    get_notebook_list_json, get_page_list_json, get_entry_list_json, get_error_json
)

# Import MCP models for response validation
from src.cli.mcp.models import MCPResource, MCPResourceContent

# Import constants
from src.cli.constants import MCP_RESOURCE_URI_SCHEME


class TestResourceManagerInitialization:
    """Test ResourceManager initialization and configuration validation."""
    
    def test_resource_manager_initialization_valid_config(self, get_valid_config):
        """Test successful ResourceManager initialization with valid configuration."""
        config = get_valid_config
        
        # Create mock API client
        mock_api_client = Mock(spec=LabArchivesAPIClient)
        
        # Create scope configuration
        scope_config = {
            "notebook_id": config.scope.notebook_id,
            "notebook_name": config.scope.notebook_name,
            "folder_path": config.scope.folder_path
        }
        
        # Initialize ResourceManager
        resource_manager = ResourceManager(
            api_client=mock_api_client,
            scope_config=scope_config,
            jsonld_enabled=config.output.json_ld_enabled
        )
        
        # Validate initialization
        assert resource_manager.api_client == mock_api_client
        assert resource_manager.scope_config == scope_config
        assert resource_manager.jsonld_enabled == config.output.json_ld_enabled
        assert resource_manager.logger is not None
    
    def test_resource_manager_initialization_invalid_config(self):
        """Test ResourceManager initialization fails with invalid configuration."""
        # Test with None API client
        with pytest.raises(ValueError, match="API client is required"):
            ResourceManager(
                api_client=None,
                scope_config={},
                jsonld_enabled=False
            )
        
        # Test with None scope config
        mock_api_client = Mock(spec=LabArchivesAPIClient)
        with pytest.raises(ValueError, match="Scope configuration is required"):
            ResourceManager(
                api_client=mock_api_client,
                scope_config=None,
                jsonld_enabled=False
            )


class TestResourceManagerListResources:
    """Test ResourceManager.list_resources functionality."""
    
    @pytest.fixture
    def mock_api_client(self):
        """Create a mock LabArchivesAPIClient for testing."""
        return Mock(spec=LabArchivesAPIClient)
    
    @pytest.fixture
    def resource_manager_no_scope(self, mock_api_client):
        """Create ResourceManager with no scope limitations."""
        return ResourceManager(
            api_client=mock_api_client,
            scope_config={},
            jsonld_enabled=False
        )
    
    @pytest.fixture
    def resource_manager_notebook_scope(self, mock_api_client):
        """Create ResourceManager with notebook scope limitation."""
        return ResourceManager(
            api_client=mock_api_client,
            scope_config={"notebook_id": "nb_123456"},
            jsonld_enabled=False
        )
    
    @pytest.fixture
    def resource_manager_name_scope(self, mock_api_client):
        """Create ResourceManager with notebook name scope limitation."""
        return ResourceManager(
            api_client=mock_api_client,
            scope_config={"notebook_name": "Test Notebook"},
            jsonld_enabled=False
        )
    
    @pytest.fixture
    def sample_notebooks(self):
        """Create sample notebook metadata for testing."""
        return [
            NotebookMetadata(
                id="nb_123456",
                name="Protein Analysis Lab Notebook",
                description="Research notebook for protein structure analysis experiments",
                owner="researcher@university.edu",
                created_date=datetime(2024, 1, 15, 10, 30, 0),
                last_modified=datetime(2024, 11, 20, 14, 22, 35),
                folder_count=5,
                page_count=24
            ),
            NotebookMetadata(
                id="nb_789012",
                name="Cell Culture Experiments",
                description="Documentation of cell culture protocols and results",
                owner="labtech@university.edu",
                created_date=datetime(2024, 2, 1, 9, 0, 0),
                last_modified=datetime(2024, 11, 21, 11, 15, 22),
                folder_count=3,
                page_count=18
            )
        ]
    
    @pytest.fixture
    def sample_pages(self):
        """Create sample page metadata for testing."""
        return [
            PageMetadata(
                id="page_789012",
                notebook_id="nb_123456",
                title="Experiment 1: Protein Purification Protocol",
                folder_path="/Experiments/Protein Analysis/Purification",
                created_date=datetime(2024, 1, 16, 9, 15, 0),
                last_modified=datetime(2024, 11, 20, 16, 45, 12),
                entry_count=8,
                author="researcher@university.edu"
            ),
            PageMetadata(
                id="page_345678",
                notebook_id="nb_123456",
                title="Experiment 2: Structural Analysis Results",
                folder_path="/Experiments/Protein Analysis/Structure",
                created_date=datetime(2024, 1, 18, 14, 30, 0),
                last_modified=datetime(2024, 11, 21, 10, 20, 45),
                entry_count=12,
                author="researcher@university.edu"
            )
        ]
    
    def test_list_resources_success_all_notebooks(self, resource_manager_no_scope, 
                                                 mock_api_client, sample_notebooks):
        """Test successful resource listing returns all accessible notebooks."""
        # Mock API client response
        mock_api_client.list_notebooks.return_value = NotebookListResponse(
            notebooks=sample_notebooks
        )
        
        # Call list_resources
        resources = resource_manager_no_scope.list_resources()
        
        # Validate results
        assert len(resources) == 2
        assert isinstance(resources[0], MCPResource)
        assert isinstance(resources[1], MCPResource)
        
        # Validate first notebook resource
        assert resources[0].uri == "labarchives://notebook/nb_123456"
        assert resources[0].name == "Protein Analysis Lab Notebook"
        assert resources[0].description == "Research notebook for protein structure analysis experiments"
        assert resources[0].metadata["owner"] == "researcher@university.edu"
        assert resources[0].metadata["page_count"] == 24
        
        # Validate second notebook resource
        assert resources[1].uri == "labarchives://notebook/nb_789012"
        assert resources[1].name == "Cell Culture Experiments"
        assert resources[1].description == "Documentation of cell culture protocols and results"
        assert resources[1].metadata["owner"] == "labtech@university.edu"
        assert resources[1].metadata["page_count"] == 18
        
        # Verify API client was called correctly
        mock_api_client.list_notebooks.assert_called_once()
    
    def test_list_resources_success_notebook_scope(self, resource_manager_notebook_scope,
                                                  mock_api_client, sample_pages):
        """Test successful resource listing with notebook scope returns pages."""
        # Mock API client response
        mock_api_client.list_pages.return_value = PageListResponse(
            pages=sample_pages
        )
        
        # Call list_resources
        resources = resource_manager_notebook_scope.list_resources()
        
        # Validate results
        assert len(resources) == 2
        assert isinstance(resources[0], MCPResource)
        assert isinstance(resources[1], MCPResource)
        
        # Validate first page resource
        assert resources[0].uri == "labarchives://notebook/nb_123456/page/page_789012"
        assert resources[0].name == "Experiment 1: Protein Purification Protocol"
        assert resources[0].metadata["notebook_id"] == "nb_123456"
        assert resources[0].metadata["entry_count"] == 8
        
        # Validate second page resource
        assert resources[1].uri == "labarchives://notebook/nb_123456/page/page_345678"
        assert resources[1].name == "Experiment 2: Structural Analysis Results"
        assert resources[1].metadata["notebook_id"] == "nb_123456"
        assert resources[1].metadata["entry_count"] == 12
        
        # Verify API client was called correctly
        mock_api_client.list_pages.assert_called_once_with("nb_123456")
    
    def test_list_resources_success_name_scope(self, resource_manager_name_scope,
                                              mock_api_client, sample_notebooks, sample_pages):
        """Test successful resource listing with notebook name scope."""
        # Mock API client responses
        mock_api_client.list_notebooks.return_value = NotebookListResponse(
            notebooks=sample_notebooks
        )
        mock_api_client.list_pages.return_value = PageListResponse(
            pages=sample_pages
        )
        
        # Call list_resources
        resources = resource_manager_name_scope.list_resources()
        
        # Validate results - should find notebook by name and return its pages
        assert len(resources) == 2
        assert isinstance(resources[0], MCPResource)
        assert isinstance(resources[1], MCPResource)
        
        # Verify API client was called correctly
        mock_api_client.list_notebooks.assert_called_once()
        mock_api_client.list_pages.assert_called_once_with("nb_123456")
    
    def test_list_resources_notebook_name_not_found(self, resource_manager_name_scope,
                                                   mock_api_client, sample_notebooks):
        """Test resource listing returns empty list when notebook name not found."""
        # Mock API client response with notebooks that don't match the scope
        mock_api_client.list_notebooks.return_value = NotebookListResponse(
            notebooks=sample_notebooks
        )
        
        # Create resource manager with non-existent notebook name
        resource_manager = ResourceManager(
            api_client=mock_api_client,
            scope_config={"notebook_name": "Non-existent Notebook"},
            jsonld_enabled=False
        )
        
        # Call list_resources
        resources = resource_manager.list_resources()
        
        # Validate results - should return empty list
        assert len(resources) == 0
        
        # Verify API client was called correctly
        mock_api_client.list_notebooks.assert_called_once()
    
    def test_list_resources_api_authentication_error(self, resource_manager_no_scope,
                                                    mock_api_client):
        """Test list_resources handles API authentication errors correctly."""
        # Mock API client to raise authentication error
        mock_api_client.list_notebooks.side_effect = APIAuthenticationError(
            message="Authentication failed",
            code=401
        )
        
        # Call list_resources and expect LabArchivesMCPException
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager_no_scope.list_resources()
        
        # Validate exception details
        assert exc_info.value.code == 401
        assert "Authentication failed" in str(exc_info.value)
    
    def test_list_resources_api_permission_error(self, resource_manager_notebook_scope,
                                                mock_api_client):
        """Test list_resources handles API permission errors correctly."""
        # Mock API client to raise permission error
        mock_api_client.list_pages.side_effect = APIPermissionError(
            message="Access denied to notebook",
            code=403
        )
        
        # Call list_resources and expect LabArchivesMCPException
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager_notebook_scope.list_resources()
        
        # Validate exception details
        assert exc_info.value.code == 403
        assert "Access denied to notebook" in str(exc_info.value)
    
    def test_list_resources_api_general_error(self, resource_manager_no_scope,
                                             mock_api_client):
        """Test list_resources handles general API errors correctly."""
        # Mock API client to raise general API error
        mock_api_client.list_notebooks.side_effect = APIError(
            message="Server error",
            code=500
        )
        
        # Call list_resources and expect LabArchivesMCPException
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager_no_scope.list_resources()
        
        # Validate exception details
        assert exc_info.value.code == 500
        assert "Failed to list notebooks" in str(exc_info.value)
    
    def test_list_resources_unexpected_error(self, resource_manager_no_scope,
                                           mock_api_client):
        """Test list_resources handles unexpected errors correctly."""
        # Mock API client to raise unexpected error
        mock_api_client.list_notebooks.side_effect = ValueError("Unexpected error")
        
        # Call list_resources and expect LabArchivesMCPException
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager_no_scope.list_resources()
        
        # Validate exception details
        assert exc_info.value.code == 500
        assert "Unexpected error during resource listing" in str(exc_info.value)


class TestResourceManagerReadResource:
    """Test ResourceManager.read_resource functionality."""
    
    @pytest.fixture
    def mock_api_client(self):
        """Create a mock LabArchivesAPIClient for testing."""
        return Mock(spec=LabArchivesAPIClient)
    
    @pytest.fixture
    def resource_manager_no_scope(self, mock_api_client):
        """Create ResourceManager with no scope limitations."""
        return ResourceManager(
            api_client=mock_api_client,
            scope_config={},
            jsonld_enabled=False
        )
    
    @pytest.fixture
    def resource_manager_with_jsonld(self, mock_api_client):
        """Create ResourceManager with JSON-LD enabled."""
        return ResourceManager(
            api_client=mock_api_client,
            scope_config={},
            jsonld_enabled=True
        )
    
    @pytest.fixture
    def resource_manager_notebook_scope(self, mock_api_client):
        """Create ResourceManager with notebook scope limitation."""
        return ResourceManager(
            api_client=mock_api_client,
            scope_config={"notebook_id": "nb_123456"},
            jsonld_enabled=False
        )
    
    @pytest.fixture
    def sample_notebook(self):
        """Create sample notebook metadata for testing."""
        return NotebookMetadata(
            id="nb_123456",
            name="Protein Analysis Lab Notebook",
            description="Research notebook for protein structure analysis experiments",
            owner="researcher@university.edu",
            created_date=datetime(2024, 1, 15, 10, 30, 0),
            last_modified=datetime(2024, 11, 20, 14, 22, 35),
            folder_count=5,
            page_count=24
        )
    
    @pytest.fixture
    def sample_page(self):
        """Create sample page metadata for testing."""
        return PageMetadata(
            id="page_789012",
            notebook_id="nb_123456",
            title="Experiment 1: Protein Purification Protocol",
            folder_path="/Experiments/Protein Analysis/Purification",
            created_date=datetime(2024, 1, 16, 9, 15, 0),
            last_modified=datetime(2024, 11, 20, 16, 45, 12),
            entry_count=8,
            author="researcher@university.edu"
        )
    
    @pytest.fixture
    def sample_entry(self):
        """Create sample entry content for testing."""
        return EntryContent(
            id="entry_345678",
            page_id="page_789012",
            entry_type="text",
            title="Experimental Procedure",
            content="1. Prepare protein sample in buffer solution (50mM Tris-HCl, pH 7.4)\n2. Centrifuge at 10,000g for 10 minutes\n3. Collect supernatant and measure protein concentration\n4. Proceed with purification using affinity chromatography",
            created_date=datetime(2024, 1, 16, 10, 30, 0),
            last_modified=datetime(2024, 11, 20, 17, 12, 48),
            author="researcher@university.edu",
            version=3,
            metadata={"word_count": 45, "tags": ["protein", "purification", "experiment"]}
        )
    
    def test_read_resource_success_notebook(self, resource_manager_no_scope, mock_api_client,
                                          sample_notebook, sample_page):
        """Test successful reading of notebook resource content."""
        # Mock API client responses
        mock_api_client.list_notebooks.return_value = NotebookListResponse(
            notebooks=[sample_notebook]
        )
        mock_api_client.list_pages.return_value = PageListResponse(
            pages=[sample_page]
        )
        
        # Call read_resource
        resource_content = resource_manager_no_scope.read_resource(
            "labarchives://notebook/nb_123456"
        )
        
        # Validate response type
        assert isinstance(resource_content, MCPResourceContent)
        
        # Validate content structure
        assert resource_content.content["id"] == "nb_123456"
        assert resource_content.content["name"] == "Protein Analysis Lab Notebook"
        assert resource_content.content["description"] == "Research notebook for protein structure analysis experiments"
        assert resource_content.content["owner"] == "researcher@university.edu"
        assert len(resource_content.content["pages"]) == 1
        
        # Validate page in content
        page = resource_content.content["pages"][0]
        assert page["id"] == "page_789012"
        assert page["title"] == "Experiment 1: Protein Purification Protocol"
        assert page["entry_count"] == 8
        
        # Validate metadata
        assert resource_content.metadata["resource_type"] == "notebook"
        assert resource_content.metadata["notebook_id"] == "nb_123456"
        assert resource_content.metadata["owner"] == "researcher@university.edu"
        assert resource_content.metadata["total_pages"] == 1
        assert "retrieved_at" in resource_content.metadata
        
        # Validate no JSON-LD context (disabled)
        assert resource_content.context is None
        
        # Verify API client was called correctly
        mock_api_client.list_notebooks.assert_called_once()
        mock_api_client.list_pages.assert_called_once_with("nb_123456")
    
    def test_read_resource_success_page(self, resource_manager_no_scope, mock_api_client,
                                       sample_page, sample_entry):
        """Test successful reading of page resource content."""
        # Mock API client responses
        mock_api_client.list_pages.return_value = PageListResponse(
            pages=[sample_page]
        )
        mock_api_client.list_entries.return_value = EntryListResponse(
            entries=[sample_entry]
        )
        
        # Call read_resource
        resource_content = resource_manager_no_scope.read_resource(
            "labarchives://notebook/nb_123456/page/page_789012"
        )
        
        # Validate response type
        assert isinstance(resource_content, MCPResourceContent)
        
        # Validate content structure
        assert resource_content.content["id"] == "page_789012"
        assert resource_content.content["notebook_id"] == "nb_123456"
        assert resource_content.content["title"] == "Experiment 1: Protein Purification Protocol"
        assert resource_content.content["folder_path"] == "/Experiments/Protein Analysis/Purification"
        assert resource_content.content["author"] == "researcher@university.edu"
        assert resource_content.content["entry_count"] == 8
        assert len(resource_content.content["entries"]) == 1
        
        # Validate entry in content
        entry = resource_content.content["entries"][0]
        assert entry["id"] == "entry_345678"
        assert entry["entry_type"] == "text"
        assert entry["title"] == "Experimental Procedure"
        assert entry["author"] == "researcher@university.edu"
        assert entry["version"] == 3
        assert "content_preview" in entry
        
        # Validate metadata
        assert resource_content.metadata["resource_type"] == "page"
        assert resource_content.metadata["page_id"] == "page_789012"
        assert resource_content.metadata["notebook_id"] == "nb_123456"
        assert resource_content.metadata["folder_path"] == "/Experiments/Protein Analysis/Purification"
        assert resource_content.metadata["author"] == "researcher@university.edu"
        assert resource_content.metadata["total_entries"] == 1
        assert "retrieved_at" in resource_content.metadata
        
        # Verify API client was called correctly
        mock_api_client.list_pages.assert_called_once_with("nb_123456")
        mock_api_client.list_entries.assert_called_once_with("page_789012")
    
    def test_read_resource_success_entry(self, resource_manager_no_scope, mock_api_client,
                                        sample_entry):
        """Test successful reading of entry resource content."""
        # Mock API client response
        mock_api_client.get_entry_content.return_value = EntryListResponse(
            entries=[sample_entry]
        )
        
        # Call read_resource
        resource_content = resource_manager_no_scope.read_resource(
            "labarchives://entry/entry_345678"
        )
        
        # Validate response type
        assert isinstance(resource_content, MCPResourceContent)
        
        # Validate content structure
        assert resource_content.content["id"] == "entry_345678"
        assert resource_content.content["page_id"] == "page_789012"
        assert resource_content.content["entry_type"] == "text"
        assert resource_content.content["title"] == "Experimental Procedure"
        assert resource_content.content["author"] == "researcher@university.edu"
        assert resource_content.content["version"] == 3
        assert "1. Prepare protein sample" in resource_content.content["content"]
        
        # Validate metadata
        assert resource_content.metadata["resource_type"] == "entry"
        assert resource_content.metadata["page_id"] == "page_789012"
        assert resource_content.metadata["entry_type"] == "text"
        assert resource_content.metadata["version"] == 3
        assert resource_content.metadata["author"] == "researcher@university.edu"
        assert "retrieved_at" in resource_content.metadata
        
        # Verify API client was called correctly
        mock_api_client.get_entry_content.assert_called_once_with("entry_345678")
    
    def test_read_resource_success_entry_with_jsonld(self, resource_manager_with_jsonld,
                                                    mock_api_client, sample_entry):
        """Test successful reading of entry resource content with JSON-LD context."""
        # Mock API client response
        mock_api_client.get_entry_content.return_value = EntryListResponse(
            entries=[sample_entry]
        )
        
        # Call read_resource
        resource_content = resource_manager_with_jsonld.read_resource(
            "labarchives://entry/entry_345678"
        )
        
        # Validate response type
        assert isinstance(resource_content, MCPResourceContent)
        
        # Validate JSON-LD context is present
        assert resource_content.context is not None
        assert "@context" in resource_content.context
        assert "@vocab" in resource_content.context["@context"]
        assert resource_content.context["@context"]["@vocab"] == "https://schema.org/"
        
        # Verify API client was called correctly
        mock_api_client.get_entry_content.assert_called_once_with("entry_345678")
    
    def test_read_resource_invalid_uri(self, resource_manager_no_scope):
        """Test read_resource handles invalid URI format correctly."""
        # Call read_resource with invalid URI
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager_no_scope.read_resource("invalid://uri/format")
        
        # Validate exception details
        assert exc_info.value.code == 400
        assert "Invalid resource URI scheme" in str(exc_info.value)
    
    def test_read_resource_scope_violation(self, resource_manager_notebook_scope):
        """Test read_resource enforces scope limitations correctly."""
        # Call read_resource with URI outside scope
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager_notebook_scope.read_resource("labarchives://notebook/nb_999999")
        
        # Validate exception details
        assert exc_info.value.code == 403
        assert "Resource access denied - outside configured scope" in str(exc_info.value)
    
    def test_read_resource_notebook_not_found(self, resource_manager_no_scope, mock_api_client):
        """Test read_resource handles notebook not found correctly."""
        # Mock API client response with empty notebook list
        mock_api_client.list_notebooks.return_value = NotebookListResponse(
            notebooks=[]
        )
        
        # Call read_resource
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager_no_scope.read_resource("labarchives://notebook/nb_999999")
        
        # Validate exception details
        assert exc_info.value.code == 404
        assert "Notebook not found" in str(exc_info.value)
    
    def test_read_resource_page_not_found(self, resource_manager_no_scope, mock_api_client):
        """Test read_resource handles page not found correctly."""
        # Mock API client response with empty page list
        mock_api_client.list_pages.return_value = PageListResponse(
            pages=[]
        )
        
        # Call read_resource
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager_no_scope.read_resource("labarchives://notebook/nb_123456/page/page_999999")
        
        # Validate exception details
        assert exc_info.value.code == 404
        assert "Page not found" in str(exc_info.value)
    
    def test_read_resource_entry_not_found(self, resource_manager_no_scope, mock_api_client):
        """Test read_resource handles entry not found correctly."""
        # Mock API client response with empty entry list
        mock_api_client.get_entry_content.return_value = EntryListResponse(
            entries=[]
        )
        
        # Call read_resource
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager_no_scope.read_resource("labarchives://entry/entry_999999")
        
        # Validate exception details
        assert exc_info.value.code == 404
        assert "Entry not found" in str(exc_info.value)
    
    def test_read_resource_unsupported_resource_type(self, resource_manager_no_scope):
        """Test read_resource handles unsupported resource types correctly."""
        # Call read_resource with unsupported resource type
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager_no_scope.read_resource("labarchives://unsupported/resource_123")
        
        # Validate exception details
        assert exc_info.value.code == 400
        assert "Unsupported resource type" in str(exc_info.value)
    
    def test_read_resource_api_permission_error(self, resource_manager_no_scope, mock_api_client):
        """Test read_resource handles API permission errors correctly."""
        # Mock API client to raise permission error
        mock_api_client.get_entry_content.side_effect = APIPermissionError(
            message="Access denied to entry",
            code=403
        )
        
        # Call read_resource
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager_no_scope.read_resource("labarchives://entry/entry_345678")
        
        # Validate exception details
        assert exc_info.value.code == 403
        assert "Access denied to entry" in str(exc_info.value)
    
    def test_read_resource_api_authentication_error(self, resource_manager_no_scope, mock_api_client):
        """Test read_resource handles API authentication errors correctly."""
        # Mock API client to raise authentication error
        mock_api_client.get_entry_content.side_effect = APIAuthenticationError(
            message="Authentication failed",
            code=401
        )
        
        # Call read_resource
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager_no_scope.read_resource("labarchives://entry/entry_345678")
        
        # Validate exception details
        assert exc_info.value.code == 401
        assert "Authentication failed" in str(exc_info.value)


class TestResourceManagerScopeEnforcement:
    """Test scope limitation and access control enforcement."""
    
    @pytest.fixture
    def mock_api_client(self):
        """Create a mock LabArchivesAPIClient for testing."""
        return Mock(spec=LabArchivesAPIClient)
    
    def test_scope_limitation_enforced_notebook_scope(self, mock_api_client):
        """Test that ResourceManager enforces notebook scope limitations."""
        # Create ResourceManager with notebook scope
        resource_manager = ResourceManager(
            api_client=mock_api_client,
            scope_config={"notebook_id": "nb_123456"},
            jsonld_enabled=False
        )
        
        # Test in-scope access (should work)
        assert is_resource_in_scope(
            {"type": "notebook", "notebook_id": "nb_123456"},
            {"notebook_id": "nb_123456"}
        )
        
        # Test out-of-scope access (should fail)
        assert not is_resource_in_scope(
            {"type": "notebook", "notebook_id": "nb_999999"},
            {"notebook_id": "nb_123456"}
        )
    
    def test_scope_limitation_enforced_page_scope(self, mock_api_client):
        """Test that ResourceManager enforces page scope limitations."""
        # Create ResourceManager with notebook scope
        resource_manager = ResourceManager(
            api_client=mock_api_client,
            scope_config={"notebook_id": "nb_123456"},
            jsonld_enabled=False
        )
        
        # Test in-scope page access (should work)
        assert is_resource_in_scope(
            {"type": "page", "notebook_id": "nb_123456", "page_id": "page_789012"},
            {"notebook_id": "nb_123456"}
        )
        
        # Test out-of-scope page access (should fail)
        assert not is_resource_in_scope(
            {"type": "page", "notebook_id": "nb_999999", "page_id": "page_789012"},
            {"notebook_id": "nb_123456"}
        )
    
    def test_scope_limitation_enforced_entry_scope(self, mock_api_client):
        """Test that ResourceManager handles entry scope validation."""
        # Create ResourceManager with notebook scope
        resource_manager = ResourceManager(
            api_client=mock_api_client,
            scope_config={"notebook_id": "nb_123456"},
            jsonld_enabled=False
        )
        
        # Test entry scope validation (deferred to content retrieval)
        assert is_resource_in_scope(
            {"type": "entry", "entry_id": "entry_345678"},
            {"notebook_id": "nb_123456"}
        )
    
    def test_scope_limitation_enforced_no_scope(self, mock_api_client):
        """Test that ResourceManager allows all access when no scope is configured."""
        # Create ResourceManager with no scope
        resource_manager = ResourceManager(
            api_client=mock_api_client,
            scope_config={},
            jsonld_enabled=False
        )
        
        # Test that all resources are allowed
        assert is_resource_in_scope(
            {"type": "notebook", "notebook_id": "nb_123456"},
            {}
        )
        assert is_resource_in_scope(
            {"type": "page", "notebook_id": "nb_999999", "page_id": "page_789012"},
            {}
        )
        assert is_resource_in_scope(
            {"type": "entry", "entry_id": "entry_345678"},
            {}
        )
    
    def test_scope_violation_raises_exception(self, mock_api_client):
        """Test that scope violations raise appropriate exceptions."""
        # Create ResourceManager with notebook scope
        resource_manager = ResourceManager(
            api_client=mock_api_client,
            scope_config={"notebook_id": "nb_123456"},
            jsonld_enabled=False
        )
        
        # Test scope violation in read_resource
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager.read_resource("labarchives://notebook/nb_999999")
        
        # Validate exception details
        assert exc_info.value.code == 403
        assert "Resource access denied - outside configured scope" in str(exc_info.value)
        assert "nb_999999" in str(exc_info.value.context)


class TestResourceManagerErrorHandling:
    """Test comprehensive error handling and graceful degradation."""
    
    @pytest.fixture
    def mock_api_client(self):
        """Create a mock LabArchivesAPIClient for testing."""
        return Mock(spec=LabArchivesAPIClient)
    
    @pytest.fixture
    def resource_manager(self, mock_api_client):
        """Create ResourceManager for testing."""
        return ResourceManager(
            api_client=mock_api_client,
            scope_config={},
            jsonld_enabled=False
        )
    
    def test_api_error_handling_authentication_failure(self, resource_manager, mock_api_client):
        """Test that ResourceManager correctly handles authentication failures."""
        # Mock API client to raise authentication error
        mock_api_client.list_notebooks.side_effect = APIAuthenticationError(
            message="Invalid credentials",
            code=401,
            context={"operation": "list_notebooks"}
        )
        
        # Call list_resources and expect LabArchivesMCPException
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager.list_resources()
        
        # Validate exception details
        assert exc_info.value.code == 401
        assert "Authentication failed" in str(exc_info.value)
    
    def test_api_error_handling_permission_denied(self, resource_manager, mock_api_client):
        """Test that ResourceManager correctly handles permission denied errors."""
        # Mock API client to raise permission error
        mock_api_client.list_notebooks.side_effect = APIPermissionError(
            message="Access denied",
            code=403,
            context={"operation": "list_notebooks"}
        )
        
        # Call list_resources and expect LabArchivesMCPException
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager.list_resources()
        
        # Validate exception details
        assert exc_info.value.code == 500
        assert "Failed to list notebooks" in str(exc_info.value)
    
    def test_api_error_handling_server_error(self, resource_manager, mock_api_client):
        """Test that ResourceManager correctly handles server errors."""
        # Mock API client to raise server error
        mock_api_client.list_notebooks.side_effect = APIError(
            message="Internal server error",
            code=500,
            context={"operation": "list_notebooks"}
        )
        
        # Call list_resources and expect LabArchivesMCPException
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager.list_resources()
        
        # Validate exception details
        assert exc_info.value.code == 500
        assert "Failed to list notebooks" in str(exc_info.value)
    
    def test_api_error_handling_malformed_response(self, resource_manager, mock_api_client):
        """Test that ResourceManager correctly handles malformed API responses."""
        # Mock API client to raise unexpected error
        mock_api_client.list_notebooks.side_effect = ValueError("Malformed JSON response")
        
        # Call list_resources and expect LabArchivesMCPException
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager.list_resources()
        
        # Validate exception details
        assert exc_info.value.code == 500
        assert "Unexpected error during resource listing" in str(exc_info.value)
        assert "ValueError" in str(exc_info.value.context)
    
    def test_api_error_handling_timeout_error(self, resource_manager, mock_api_client):
        """Test that ResourceManager correctly handles timeout errors."""
        # Mock API client to raise timeout error
        mock_api_client.get_entry_content.side_effect = APIError(
            message="Request timeout",
            code=408,
            context={"operation": "get_entry_content"}
        )
        
        # Call read_resource and expect LabArchivesMCPException
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager.read_resource("labarchives://entry/entry_345678")
        
        # Validate exception details
        assert exc_info.value.code == 500
        assert "Failed to read entry" in str(exc_info.value)


class TestResourceManagerConfigurationValidation:
    """Test configuration validation and error handling."""
    
    @pytest.fixture
    def mock_api_client(self):
        """Create a mock LabArchivesAPIClient for testing."""
        return Mock(spec=LabArchivesAPIClient)
    
    def test_invalid_config_raises_none_api_client(self):
        """Test that ResourceManager initialization fails with None API client."""
        with pytest.raises(ValueError) as exc_info:
            ResourceManager(
                api_client=None,
                scope_config={},
                jsonld_enabled=False
            )
        
        assert "API client is required" in str(exc_info.value)
    
    def test_invalid_config_raises_none_scope_config(self, mock_api_client):
        """Test that ResourceManager initialization fails with None scope config."""
        with pytest.raises(ValueError) as exc_info:
            ResourceManager(
                api_client=mock_api_client,
                scope_config=None,
                jsonld_enabled=False
            )
        
        assert "Scope configuration is required" in str(exc_info.value)
    
    def test_invalid_config_raises_invalid_credentials(self, get_invalid_config):
        """Test that ResourceManager operations fail with invalid configuration."""
        # Note: This test focuses on the ResourceManager's handling of invalid config
        # The actual credential validation happens in the API client layer
        
        # Create mock API client that simulates authentication failure
        mock_api_client = Mock(spec=LabArchivesAPIClient)
        mock_api_client.list_notebooks.side_effect = APIAuthenticationError(
            message="Invalid credentials",
            code=401
        )
        
        # Create ResourceManager with valid structure but invalid credentials
        resource_manager = ResourceManager(
            api_client=mock_api_client,
            scope_config={},
            jsonld_enabled=False
        )
        
        # Test that operations fail with authentication error
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager.list_resources()
        
        assert exc_info.value.code == 401
        assert "Authentication failed" in str(exc_info.value)


class TestResourceUriParsing:
    """Test resource URI parsing and validation."""
    
    def test_parse_resource_uri_notebook(self):
        """Test parsing of notebook resource URIs."""
        uri = "labarchives://notebook/nb_123456"
        result = parse_resource_uri(uri)
        
        assert result["type"] == "notebook"
        assert result["notebook_id"] == "nb_123456"
    
    def test_parse_resource_uri_page(self):
        """Test parsing of page resource URIs."""
        uri = "labarchives://notebook/nb_123456/page/page_789012"
        result = parse_resource_uri(uri)
        
        assert result["type"] == "page"
        assert result["notebook_id"] == "nb_123456"
        assert result["page_id"] == "page_789012"
    
    def test_parse_resource_uri_entry(self):
        """Test parsing of entry resource URIs."""
        uri = "labarchives://entry/entry_345678"
        result = parse_resource_uri(uri)
        
        assert result["type"] == "entry"
        assert result["entry_id"] == "entry_345678"
    
    def test_parse_resource_uri_invalid_scheme(self):
        """Test parsing of URI with invalid scheme."""
        uri = "invalid://notebook/nb_123456"
        
        with pytest.raises(LabArchivesMCPException) as exc_info:
            parse_resource_uri(uri)
        
        assert exc_info.value.code == 400
        assert "Invalid resource URI scheme" in str(exc_info.value)
    
    def test_parse_resource_uri_empty_path(self):
        """Test parsing of URI with empty path."""
        uri = "labarchives://"
        
        with pytest.raises(LabArchivesMCPException) as exc_info:
            parse_resource_uri(uri)
        
        assert exc_info.value.code == 400
        assert "Empty resource path" in str(exc_info.value)
    
    def test_parse_resource_uri_invalid_notebook_format(self):
        """Test parsing of URI with invalid notebook format."""
        uri = "labarchives://notebook/"
        
        with pytest.raises(LabArchivesMCPException) as exc_info:
            parse_resource_uri(uri)
        
        assert exc_info.value.code == 400
        assert "Invalid notebook URI format" in str(exc_info.value)
    
    def test_parse_resource_uri_invalid_entry_format(self):
        """Test parsing of URI with invalid entry format."""
        uri = "labarchives://entry/"
        
        with pytest.raises(LabArchivesMCPException) as exc_info:
            parse_resource_uri(uri)
        
        assert exc_info.value.code == 400
        assert "Invalid entry URI format" in str(exc_info.value)
    
    def test_parse_resource_uri_unsupported_type(self):
        """Test parsing of URI with unsupported resource type."""
        uri = "labarchives://unsupported/resource_123"
        
        with pytest.raises(LabArchivesMCPException) as exc_info:
            parse_resource_uri(uri)
        
        assert exc_info.value.code == 400
        assert "Unsupported resource type" in str(exc_info.value)


class TestResourceManagerAuditLogging:
    """Test comprehensive audit logging for all operations."""
    
    @pytest.fixture
    def mock_api_client(self):
        """Create a mock LabArchivesAPIClient for testing."""
        return Mock(spec=LabArchivesAPIClient)
    
    @pytest.fixture
    def resource_manager(self, mock_api_client):
        """Create ResourceManager for testing."""
        return ResourceManager(
            api_client=mock_api_client,
            scope_config={},
            jsonld_enabled=False
        )
    
    @patch('src.cli.resource_manager.get_logger')
    def test_audit_logging_list_resources_success(self, mock_get_logger, resource_manager, mock_api_client):
        """Test that successful resource listing operations are logged."""
        # Mock logger
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        # Mock API client response
        mock_api_client.list_notebooks.return_value = NotebookListResponse(notebooks=[])
        
        # Call list_resources
        resource_manager.list_resources()
        
        # Verify logging calls
        mock_logger.info.assert_any_call("Starting resource listing operation", extra=unittest.mock.ANY)
        mock_logger.info.assert_any_call("Resource listing completed successfully", extra=unittest.mock.ANY)
    
    @patch('src.cli.resource_manager.get_logger')
    def test_audit_logging_read_resource_success(self, mock_get_logger, resource_manager, mock_api_client):
        """Test that successful resource reading operations are logged."""
        # Mock logger
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        # Mock API client response
        sample_entry = EntryContent(
            id="entry_345678",
            page_id="page_789012",
            entry_type="text",
            title="Test Entry",
            content="Test content",
            created_date=datetime.now(),
            last_modified=datetime.now(),
            author="test@example.com",
            version=1,
            metadata={}
        )
        mock_api_client.get_entry_content.return_value = EntryListResponse(entries=[sample_entry])
        
        # Call read_resource
        resource_manager.read_resource("labarchives://entry/entry_345678")
        
        # Verify logging calls
        mock_logger.info.assert_any_call("Starting resource read operation", extra=unittest.mock.ANY)
        mock_logger.info.assert_any_call("Successfully read entry content", extra=unittest.mock.ANY)
    
    @patch('src.cli.resource_manager.get_logger')
    def test_audit_logging_scope_violation(self, mock_get_logger, mock_api_client):
        """Test that scope violations are logged as security events."""
        # Mock logger
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        # Create ResourceManager with scope limitation
        resource_manager = ResourceManager(
            api_client=mock_api_client,
            scope_config={"notebook_id": "nb_123456"},
            jsonld_enabled=False
        )
        
        # Attempt to access out-of-scope resource
        with pytest.raises(LabArchivesMCPException):
            resource_manager.read_resource("labarchives://notebook/nb_999999")
        
        # Verify warning log for scope violation
        mock_logger.warning.assert_called_once()
        warning_call = mock_logger.warning.call_args
        assert "Resource access denied - outside configured scope" in warning_call[0][0]
    
    @patch('src.cli.resource_manager.get_logger')
    def test_audit_logging_api_error(self, mock_get_logger, resource_manager, mock_api_client):
        """Test that API errors are logged appropriately."""
        # Mock logger
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        # Mock API client to raise error
        mock_api_client.list_notebooks.side_effect = APIError(
            message="Server error",
            code=500
        )
        
        # Call list_resources and expect exception
        with pytest.raises(LabArchivesMCPException):
            resource_manager.list_resources()
        
        # Verify error logging
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args
        assert "API error listing notebooks" in error_call[0][0]