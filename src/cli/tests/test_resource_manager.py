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

# Import FolderPath for scope enforcement testing
from src.cli.data_models.scoping import FolderPath

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
            message="Authentication failed"
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
            message="Access denied to notebook"
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
            message="Access denied to entry"
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
            message="Authentication failed"
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
            message="Invalid credentials"
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


class TestResourceManagerFolderPathScopeEnforcement:
    """Test ResourceManager folder path scope enforcement using FolderPath comparisons."""
    
    @pytest.fixture
    def mock_api_client(self):
        """Create a mock LabArchivesAPIClient for testing."""
        return Mock(spec=LabArchivesAPIClient)
    
    @pytest.fixture
    def resource_manager_folder_scope(self, mock_api_client):
        """Create ResourceManager with folder path scope limitation."""
        return ResourceManager(
            api_client=mock_api_client,
            scope_config={"folder_path": "Projects/AI"},
            jsonld_enabled=False
        )
    
    @pytest.fixture
    def resource_manager_complex_folder_scope(self, mock_api_client):
        """Create ResourceManager with complex folder path scope limitation."""
        return ResourceManager(
            api_client=mock_api_client,
            scope_config={"folder_path": "Experiments/Protein Analysis"},
            jsonld_enabled=False
        )
    
    @pytest.fixture
    def resource_manager_root_scope(self, mock_api_client):
        """Create ResourceManager with root folder scope (no restriction)."""
        return ResourceManager(
            api_client=mock_api_client,
            scope_config={"folder_path": ""},
            jsonld_enabled=False
        )
    
    @pytest.fixture
    def sample_notebooks_with_folders(self):
        """Create sample notebooks with various folder structures."""
        return [
            NotebookMetadata(
                id="nb_ai_research",
                name="AI Research Notebook",
                description="Research notebook for AI experiments",
                owner="researcher@university.edu",
                created_date=datetime(2024, 1, 15, 10, 30, 0),
                last_modified=datetime(2024, 11, 20, 14, 22, 35),
                folder_count=5,
                page_count=24
            ),
            NotebookMetadata(
                id="nb_chemistry",
                name="Chemistry Lab Notebook",
                description="Documentation of chemistry experiments",
                owner="chemist@university.edu",
                created_date=datetime(2024, 2, 1, 9, 0, 0),
                last_modified=datetime(2024, 11, 21, 11, 15, 22),
                folder_count=3,
                page_count=18
            ),
            NotebookMetadata(
                id="nb_physics",
                name="Physics Experiments",
                description="Physics research and experiments",
                owner="physicist@university.edu",
                created_date=datetime(2024, 3, 1, 10, 0, 0),
                last_modified=datetime(2024, 11, 22, 12, 30, 15),
                folder_count=4,
                page_count=32
            )
        ]
    
    @pytest.fixture
    def sample_pages_with_folders(self):
        """Create sample pages with various folder paths for testing."""
        return [
            # Pages within "Projects/AI" scope
            PageMetadata(
                id="page_ai_001",
                notebook_id="nb_ai_research",
                title="AI Model Training Results",
                folder_path="Projects/AI/Models",
                created_date=datetime(2024, 1, 16, 9, 15, 0),
                last_modified=datetime(2024, 11, 20, 16, 45, 12),
                entry_count=8,
                author="researcher@university.edu"
            ),
            PageMetadata(
                id="page_ai_002",
                notebook_id="nb_ai_research",
                title="AI Data Analysis",
                folder_path="Projects/AI/Data",
                created_date=datetime(2024, 1, 18, 14, 30, 0),
                last_modified=datetime(2024, 11, 21, 10, 20, 45),
                entry_count=12,
                author="researcher@university.edu"
            ),
            # Pages outside "Projects/AI" scope
            PageMetadata(
                id="page_chem_001",
                notebook_id="nb_chemistry",
                title="Chemistry Experiment",
                folder_path="Experiments/Chemistry/Organic",
                created_date=datetime(2024, 2, 5, 11, 0, 0),
                last_modified=datetime(2024, 11, 21, 14, 30, 20),
                entry_count=6,
                author="chemist@university.edu"
            ),
            PageMetadata(
                id="page_physics_001",
                notebook_id="nb_physics",
                title="Physics Research",
                folder_path="Research/Physics/Quantum",
                created_date=datetime(2024, 3, 10, 13, 45, 0),
                last_modified=datetime(2024, 11, 22, 15, 20, 30),
                entry_count=10,
                author="physicist@university.edu"
            ),
            # Edge case: similar folder name that should NOT match
            PageMetadata(
                id="page_ai_similar",
                notebook_id="nb_ai_research",
                title="AI-Related but Different Path",
                folder_path="Projects/AI-Extended/Advanced",
                created_date=datetime(2024, 1, 20, 10, 0, 0),
                last_modified=datetime(2024, 11, 21, 16, 0, 0),
                entry_count=5,
                author="researcher@university.edu"
            )
        ]
    
    def test_notebook_contains_folder_method_with_folderpath(self, resource_manager_folder_scope, mock_api_client):
        """Test _notebook_contains_folder method uses FolderPath.is_parent_of() instead of string operations."""
        # Mock the _notebook_contains_folder method to ensure it's using FolderPath
        with patch.object(resource_manager_folder_scope, '_notebook_contains_folder') as mock_method:
            mock_method.return_value = True
            
            # Create sample pages with mixed folder paths
            pages = [
                PageMetadata(
                    id="page_in_scope",
                    notebook_id="nb_123",
                    title="In Scope Page",
                    folder_path="Projects/AI/Research",
                    created_date=datetime.now(),
                    last_modified=datetime.now(),
                    entry_count=1,
                    author="test@example.com"
                )
            ]
            
            # Test that method correctly uses FolderPath comparisons
            mock_api_client.list_pages.return_value = PageListResponse(pages=pages)
            
            result = resource_manager_folder_scope._notebook_contains_folder(
                notebook_id="nb_123",
                folder_scope=FolderPath.from_raw("Projects/AI")
            )
            
            # Verify the method was called with correct parameters
            mock_method.assert_called_once_with(
                notebook_id="nb_123",
                folder_scope=FolderPath.from_raw("Projects/AI")
            )
    
    def test_list_resources_with_folder_scope_filtering(self, resource_manager_folder_scope, 
                                                      mock_api_client, sample_notebooks_with_folders,
                                                      sample_pages_with_folders):
        """Test list_resources method uses FolderPath-based filtering in two-phase listing."""
        # Mock API client responses for two-phase listing
        mock_api_client.list_notebooks.return_value = NotebookListResponse(
            notebooks=sample_notebooks_with_folders
        )
        
        # Create mock responses for each notebook's pages
        def mock_list_pages(notebook_id):
            if notebook_id == "nb_ai_research":
                return PageListResponse(pages=[
                    page for page in sample_pages_with_folders 
                    if page.notebook_id == "nb_ai_research"
                ])
            elif notebook_id == "nb_chemistry":
                return PageListResponse(pages=[
                    page for page in sample_pages_with_folders 
                    if page.notebook_id == "nb_chemistry"
                ])
            elif notebook_id == "nb_physics":
                return PageListResponse(pages=[
                    page for page in sample_pages_with_folders 
                    if page.notebook_id == "nb_physics"
                ])
            else:
                return PageListResponse(pages=[])
        
        mock_api_client.list_pages.side_effect = mock_list_pages
        
        # Call list_resources with folder scope
        resources = resource_manager_folder_scope.list_resources()
        
        # Validate that only pages within "Projects/AI" scope are returned
        assert len(resources) == 2  # Only pages with folder_path under "Projects/AI"
        
        # Validate specific resources
        resource_uris = [resource.uri for resource in resources]
        assert "labarchives://notebook/nb_ai_research/page/page_ai_001" in resource_uris
        assert "labarchives://notebook/nb_ai_research/page/page_ai_002" in resource_uris
        
        # Validate that pages outside scope are NOT included
        assert "labarchives://notebook/nb_chemistry/page/page_chem_001" not in resource_uris
        assert "labarchives://notebook/nb_physics/page/page_physics_001" not in resource_uris
        assert "labarchives://notebook/nb_ai_research/page/page_ai_similar" not in resource_uris
        
        # Verify that notebooks without pages in scope are not included
        notebook_ids = [parse_resource_uri(uri)["notebook_id"] for uri in resource_uris]
        assert "nb_chemistry" not in notebook_ids
        assert "nb_physics" not in notebook_ids
    
    def test_list_resources_exact_folder_path_matching(self, resource_manager_folder_scope, 
                                                     mock_api_client):
        """Test that folder path matching is exact and prevents substring false positives."""
        # Create pages with similar but different folder paths
        pages_with_similar_paths = [
            PageMetadata(
                id="page_exact_match",
                notebook_id="nb_test",
                title="Exact Match Page",
                folder_path="Projects/AI/Research",  # Should match "Projects/AI"
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            ),
            PageMetadata(
                id="page_similar_but_different",
                notebook_id="nb_test",
                title="Similar Path Page",
                folder_path="Projects/AI-Extended/Research",  # Should NOT match "Projects/AI"
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            ),
            PageMetadata(
                id="page_substring_trap",
                notebook_id="nb_test",
                title="Substring Trap Page",
                folder_path="Projects/AI-Research/Advanced",  # Should NOT match "Projects/AI"
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            )
        ]
        
        # Mock API responses
        mock_api_client.list_notebooks.return_value = NotebookListResponse(
            notebooks=[NotebookMetadata(
                id="nb_test",
                name="Test Notebook",
                description="Test notebook",
                owner="test@example.com",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                folder_count=1,
                page_count=3
            )]
        )
        
        mock_api_client.list_pages.return_value = PageListResponse(pages=pages_with_similar_paths)
        
        # Call list_resources
        resources = resource_manager_folder_scope.list_resources()
        
        # Validate exact matching - only exact match should be included
        assert len(resources) == 1
        assert resources[0].uri == "labarchives://notebook/nb_test/page/page_exact_match"
        
        # Verify that similar paths are excluded
        resource_uris = [resource.uri for resource in resources]
        assert "labarchives://notebook/nb_test/page/page_similar_but_different" not in resource_uris
        assert "labarchives://notebook/nb_test/page/page_substring_trap" not in resource_uris
    
    def test_read_resource_page_folder_scope_enforcement(self, resource_manager_folder_scope, 
                                                       mock_api_client):
        """Test read_resource method enforces folder scope for page resources."""
        # Create pages with different folder paths
        in_scope_page = PageMetadata(
            id="page_in_scope",
            notebook_id="nb_123",
            title="In Scope Page",
            folder_path="Projects/AI/Research",
            created_date=datetime.now(),
            last_modified=datetime.now(),
            entry_count=1,
            author="test@example.com"
        )
        
        out_of_scope_page = PageMetadata(
            id="page_out_of_scope",
            notebook_id="nb_123",
            title="Out of Scope Page",
            folder_path="Research/Physics/Quantum",
            created_date=datetime.now(),
            last_modified=datetime.now(),
            entry_count=1,
            author="test@example.com"
        )
        
        # Test in-scope page access (should succeed)
        mock_api_client.list_pages.return_value = PageListResponse(pages=[in_scope_page])
        mock_api_client.list_entries.return_value = EntryListResponse(entries=[])
        
        resource_content = resource_manager_folder_scope.read_resource(
            "labarchives://notebook/nb_123/page/page_in_scope"
        )
        
        # Should succeed and return resource content
        assert isinstance(resource_content, MCPResourceContent)
        assert resource_content.content["id"] == "page_in_scope"
        assert resource_content.content["folder_path"] == "Projects/AI/Research"
        
        # Test out-of-scope page access (should fail with 403)
        mock_api_client.list_pages.return_value = PageListResponse(pages=[out_of_scope_page])
        
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager_folder_scope.read_resource(
                "labarchives://notebook/nb_123/page/page_out_of_scope"
            )
        
        # Should raise 403 ScopeViolation error
        assert exc_info.value.code == 403
        assert "ScopeViolation" in str(exc_info.value)
    
    def test_read_resource_entry_folder_scope_enforcement(self, resource_manager_folder_scope, 
                                                        mock_api_client):
        """Test read_resource method enforces folder scope for entry resources."""
        # Create entries with different folder paths (via their parent pages)
        in_scope_entry = EntryContent(
            id="entry_in_scope",
            page_id="page_in_scope",
            entry_type="text",
            title="In Scope Entry",
            content="This entry is within the allowed folder scope",
            created_date=datetime.now(),
            last_modified=datetime.now(),
            author="test@example.com",
            version=1,
            metadata={}
        )
        
        # Mock page metadata to determine folder scope
        in_scope_page = PageMetadata(
            id="page_in_scope",
            notebook_id="nb_123",
            title="In Scope Page",
            folder_path="Projects/AI/Research",
            created_date=datetime.now(),
            last_modified=datetime.now(),
            entry_count=1,
            author="test@example.com"
        )
        
        out_of_scope_page = PageMetadata(
            id="page_out_of_scope",
            notebook_id="nb_123",
            title="Out of Scope Page",
            folder_path="Research/Physics/Quantum",
            created_date=datetime.now(),
            last_modified=datetime.now(),
            entry_count=1,
            author="test@example.com"
        )
        
        # Test in-scope entry access (should succeed)
        mock_api_client.get_entry_content.return_value = EntryListResponse(entries=[in_scope_entry])
        mock_api_client.list_pages.return_value = PageListResponse(pages=[in_scope_page])
        # Mock list_notebooks for folder scope validation
        mock_api_client.list_notebooks.return_value = NotebookListResponse(
            notebooks=[NotebookMetadata(
                id="nb_123",
                name="Test Notebook",
                description="Test notebook",
                owner="test@example.com",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                folder_count=1,
                page_count=1
            )]
        )
        
        resource_content = resource_manager_folder_scope.read_resource(
            "labarchives://entry/entry_in_scope"
        )
        
        # Should succeed and return resource content
        assert isinstance(resource_content, MCPResourceContent)
        assert resource_content.content["id"] == "entry_in_scope"
        assert resource_content.content["page_id"] == "page_in_scope"
        
        # Test out-of-scope entry access (should fail with 403)
        out_of_scope_entry = EntryContent(
            id="entry_out_of_scope",
            page_id="page_out_of_scope",
            entry_type="text",
            title="Out of Scope Entry",
            content="This entry is outside the allowed folder scope",
            created_date=datetime.now(),
            last_modified=datetime.now(),
            author="test@example.com",
            version=1,
            metadata={}
        )
        
        mock_api_client.get_entry_content.return_value = EntryListResponse(entries=[out_of_scope_entry])
        mock_api_client.list_pages.return_value = PageListResponse(pages=[out_of_scope_page])
        # Mock list_notebooks for folder scope validation (same notebook)
        mock_api_client.list_notebooks.return_value = NotebookListResponse(
            notebooks=[NotebookMetadata(
                id="nb_123",
                name="Test Notebook",
                description="Test notebook",
                owner="test@example.com",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                folder_count=1,
                page_count=1
            )]
        )
        
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager_folder_scope.read_resource(
                "labarchives://entry/entry_out_of_scope"
            )
        
        # Should raise 403 ScopeViolation error
        assert exc_info.value.code == 403
        assert "ScopeViolation" in str(exc_info.value)
    
    def test_scope_violation_error_format(self, resource_manager_folder_scope, mock_api_client):
        """Test that scope violation errors return proper 403 ScopeViolation format."""
        # Create out-of-scope page
        out_of_scope_page = PageMetadata(
            id="page_out_of_scope",
            notebook_id="nb_123",
            title="Out of Scope Page",
            folder_path="Research/Physics/Quantum",
            created_date=datetime.now(),
            last_modified=datetime.now(),
            entry_count=1,
            author="test@example.com"
        )
        
        mock_api_client.list_pages.return_value = PageListResponse(pages=[out_of_scope_page])
        
        # Test scope violation error format
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager_folder_scope.read_resource(
                "labarchives://notebook/nb_123/page/page_out_of_scope"
            )
        
        # Validate error format matches specification
        assert exc_info.value.code == 403
        assert "ScopeViolation" in str(exc_info.value)
        
        # Validate error context includes relevant information
        context = exc_info.value.context
        assert "requested" in context
        assert "allowed" in context
        assert context["requested"] == "Research/Physics/Quantum"
        assert context["allowed"] == "Projects/AI"
    
    def test_root_folder_scope_allows_all_access(self, resource_manager_root_scope, 
                                                mock_api_client, sample_pages_with_folders):
        """Test that root folder scope allows access to all resources."""
        # Mock API responses with pages from various folders
        mock_api_client.list_pages.return_value = PageListResponse(pages=[sample_pages_with_folders[0]])
        mock_api_client.list_entries.return_value = EntryListResponse(entries=[])
        
        # Test access to any folder path should succeed
        for page in sample_pages_with_folders:
            mock_api_client.list_pages.return_value = PageListResponse(pages=[page])
            
            resource_content = resource_manager_root_scope.read_resource(
                f"labarchives://notebook/{page.notebook_id}/page/{page.id}"
            )
            
            # Should succeed for all folder paths
            assert isinstance(resource_content, MCPResourceContent)
            assert resource_content.content["id"] == page.id
            assert resource_content.content["folder_path"] == page.folder_path
    
    def test_complex_folder_scope_enforcement(self, resource_manager_complex_folder_scope, 
                                            mock_api_client):
        """Test folder scope enforcement with complex multi-level paths."""
        # Create pages with complex folder structures
        complex_pages = [
            PageMetadata(
                id="page_exact_match",
                notebook_id="nb_test",
                title="Exact Match",
                folder_path="Experiments/Protein Analysis/Results",  # Should match
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            ),
            PageMetadata(
                id="page_parent_match",
                notebook_id="nb_test",
                title="Parent Match",
                folder_path="Experiments/Protein Analysis/Methods/Advanced",  # Should match
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            ),
            PageMetadata(
                id="page_no_match",
                notebook_id="nb_test",
                title="No Match",
                folder_path="Experiments/Chemistry/Organic",  # Should NOT match
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            ),
            PageMetadata(
                id="page_substring_trap",
                notebook_id="nb_test",
                title="Substring Trap",
                folder_path="Experiments/Protein Analysis Advanced/Data",  # Should NOT match
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            )
        ]
        
        # Test in-scope access (should succeed)
        for page in complex_pages[:2]:  # First two pages are in scope
            mock_api_client.list_pages.return_value = PageListResponse(pages=[page])
            mock_api_client.list_entries.return_value = EntryListResponse(entries=[])
            
            resource_content = resource_manager_complex_folder_scope.read_resource(
                f"labarchives://notebook/{page.notebook_id}/page/{page.id}"
            )
            
            assert isinstance(resource_content, MCPResourceContent)
            assert resource_content.content["id"] == page.id
        
        # Test out-of-scope access (should fail with 403)
        for page in complex_pages[2:]:  # Last two pages are out of scope
            mock_api_client.list_pages.return_value = PageListResponse(pages=[page])
            
            with pytest.raises(LabArchivesMCPException) as exc_info:
                resource_manager_complex_folder_scope.read_resource(
                    f"labarchives://notebook/{page.notebook_id}/page/{page.id}"
                )
            
            assert exc_info.value.code == 403
            assert "ScopeViolation" in str(exc_info.value)
    
    def test_integration_folderpath_throughout_resource_operations(self, resource_manager_folder_scope, 
                                                                 mock_api_client):
        """Test that FolderPath comparisons are used throughout all resource operations."""
        # Create test data
        notebooks = [
            NotebookMetadata(
                id="nb_ai",
                name="AI Notebook",
                description="AI research",
                owner="test@example.com",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                folder_count=1,
                page_count=2
            )
        ]
        
        pages = [
            PageMetadata(
                id="page_in_scope",
                notebook_id="nb_ai",
                title="In Scope Page",
                folder_path="Projects/AI/Research",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            ),
            PageMetadata(
                id="page_out_of_scope",
                notebook_id="nb_ai",
                title="Out of Scope Page",
                folder_path="Research/Physics/Quantum",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            )
        ]
        
        entries = [
            EntryContent(
                id="entry_in_scope",
                page_id="page_in_scope",
                entry_type="text",
                title="In Scope Entry",
                content="Test content",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                author="test@example.com",
                version=1,
                metadata={}
            )
        ]
        
        # Mock API responses
        mock_api_client.list_notebooks.return_value = NotebookListResponse(notebooks=notebooks)
        mock_api_client.list_pages.return_value = PageListResponse(pages=pages)
        mock_api_client.list_entries.return_value = EntryListResponse(entries=entries)
        mock_api_client.get_entry_content.return_value = EntryListResponse(entries=entries)
        
        # Test list_resources uses FolderPath filtering
        resources = resource_manager_folder_scope.list_resources()
        
        # Should only return in-scope resources
        assert len(resources) == 1
        assert resources[0].uri == "labarchives://notebook/nb_ai/page/page_in_scope"
        
        # Test read_resource uses FolderPath validation for pages
        resource_content = resource_manager_folder_scope.read_resource(
            "labarchives://notebook/nb_ai/page/page_in_scope"
        )
        assert isinstance(resource_content, MCPResourceContent)
        assert resource_content.content["id"] == "page_in_scope"
        
        # Test read_resource blocks out-of-scope pages
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager_folder_scope.read_resource(
                "labarchives://notebook/nb_ai/page/page_out_of_scope"
            )
        assert exc_info.value.code == 403
        assert "ScopeViolation" in str(exc_info.value)
        
        # Test read_resource uses FolderPath validation for entries
        resource_content = resource_manager_folder_scope.read_resource(
            "labarchives://entry/entry_in_scope"
        )
        assert isinstance(resource_content, MCPResourceContent)
        assert resource_content.content["id"] == "entry_in_scope"
    
    def test_scope_violation_audit_logging(self, resource_manager_folder_scope, 
                                         mock_api_client):
        """Test that scope violations are properly logged for audit purposes."""
        # Mock logger on the resource manager instance
        mock_logger = Mock()
        resource_manager_folder_scope.logger = mock_logger
        
        # Create out-of-scope page
        out_of_scope_page = PageMetadata(
            id="page_out_of_scope",
            notebook_id="nb_123",
            title="Out of Scope Page",
            folder_path="Research/Physics/Quantum",
            created_date=datetime.now(),
            last_modified=datetime.now(),
            entry_count=1,
            author="test@example.com"
        )
        
        mock_api_client.list_pages.return_value = PageListResponse(pages=[out_of_scope_page])
        
        # Attempt to access out-of-scope resource
        with pytest.raises(LabArchivesMCPException):
            resource_manager_folder_scope.read_resource(
                "labarchives://notebook/nb_123/page/page_out_of_scope"
            )
        
        # Verify audit logging for scope violation
        mock_logger.warning.assert_called_once()
        warning_call = mock_logger.warning.call_args
        assert "Page access denied - outside folder scope" in warning_call[0][0]
        assert "Research/Physics/Quantum" in warning_call[0][0]


class TestResourceManagerFolderPathEdgeCases:
    """Test ResourceManager folder path scope enforcement edge cases."""
    
    @pytest.fixture
    def mock_api_client(self):
        """Create a mock LabArchivesAPIClient for testing."""
        return Mock(spec=LabArchivesAPIClient)
    
    def test_empty_folder_path_scope_allows_all(self, mock_api_client):
        """Test that empty folder path scope allows access to all resources."""
        resource_manager = ResourceManager(
            api_client=mock_api_client,
            scope_config={"folder_path": ""},
            jsonld_enabled=False
        )
        
        # Create pages with various folder paths
        pages = [
            PageMetadata(
                id="page_deep_path",
                notebook_id="nb_test",
                title="Deep Path Page",
                folder_path="Very/Deep/Folder/Structure/Here",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            ),
            PageMetadata(
                id="page_root_path",
                notebook_id="nb_test",
                title="Root Path Page",
                folder_path="",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            )
        ]
        
        # Test that all pages are accessible
        for page in pages:
            mock_api_client.list_pages.return_value = PageListResponse(pages=[page])
            mock_api_client.list_entries.return_value = EntryListResponse(entries=[])
            
            resource_content = resource_manager.read_resource(
                f"labarchives://notebook/{page.notebook_id}/page/{page.id}"
            )
            
            assert isinstance(resource_content, MCPResourceContent)
            assert resource_content.content["id"] == page.id
    
    def test_single_component_folder_scope(self, mock_api_client):
        """Test folder scope with single component paths."""
        resource_manager = ResourceManager(
            api_client=mock_api_client,
            scope_config={"folder_path": "Research"},
            jsonld_enabled=False
        )
        
        # Create pages with single and multi-component paths
        pages = [
            PageMetadata(
                id="page_in_scope",
                notebook_id="nb_test",
                title="In Scope Page",
                folder_path="Research/AI",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            ),
            PageMetadata(
                id="page_out_of_scope",
                notebook_id="nb_test",
                title="Out of Scope Page",
                folder_path="Projects/AI",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            ),
            PageMetadata(
                id="page_exact_match",
                notebook_id="nb_test",
                title="Exact Match Page",
                folder_path="Research",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            )
        ]
        
        # Test in-scope access
        mock_api_client.list_pages.return_value = PageListResponse(pages=[pages[0]])
        mock_api_client.list_entries.return_value = EntryListResponse(entries=[])
        
        resource_content = resource_manager.read_resource(
            f"labarchives://notebook/{pages[0].notebook_id}/page/{pages[0].id}"
        )
        assert isinstance(resource_content, MCPResourceContent)
        
        # Test out-of-scope access
        mock_api_client.list_pages.return_value = PageListResponse(pages=[pages[1]])
        
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager.read_resource(
                f"labarchives://notebook/{pages[1].notebook_id}/page/{pages[1].id}"
            )
        assert exc_info.value.code == 403
        assert "ScopeViolation" in str(exc_info.value)
        
        # Test exact match access (should NOT be allowed since it's not a parent)
        mock_api_client.list_pages.return_value = PageListResponse(pages=[pages[2]])
        
        with pytest.raises(LabArchivesMCPException) as exc_info:
            resource_manager.read_resource(
                f"labarchives://notebook/{pages[2].notebook_id}/page/{pages[2].id}"
            )
        assert exc_info.value.code == 403
        assert "ScopeViolation" in str(exc_info.value)
    
    def test_case_sensitive_folder_scope(self, mock_api_client):
        """Test that folder scope matching is case-sensitive."""
        resource_manager = ResourceManager(
            api_client=mock_api_client,
            scope_config={"folder_path": "Projects/AI"},
            jsonld_enabled=False
        )
        
        # Create pages with case variations
        pages = [
            PageMetadata(
                id="page_exact_case",
                notebook_id="nb_test",
                title="Exact Case Page",
                folder_path="Projects/AI/Research",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            ),
            PageMetadata(
                id="page_wrong_case",
                notebook_id="nb_test",
                title="Wrong Case Page",
                folder_path="projects/ai/research",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            ),
            PageMetadata(
                id="page_mixed_case",
                notebook_id="nb_test",
                title="Mixed Case Page",
                folder_path="Projects/ai/Research",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            )
        ]
        
        # Test exact case match (should succeed)
        mock_api_client.list_pages.return_value = PageListResponse(pages=[pages[0]])
        mock_api_client.list_entries.return_value = EntryListResponse(entries=[])
        
        resource_content = resource_manager.read_resource(
            f"labarchives://notebook/{pages[0].notebook_id}/page/{pages[0].id}"
        )
        assert isinstance(resource_content, MCPResourceContent)
        
        # Test wrong case matches (should fail)
        for page in pages[1:]:
            mock_api_client.list_pages.return_value = PageListResponse(pages=[page])
            
            with pytest.raises(LabArchivesMCPException) as exc_info:
                resource_manager.read_resource(
                    f"labarchives://notebook/{page.notebook_id}/page/{page.id}"
                )
            assert exc_info.value.code == 403
            assert "ScopeViolation" in str(exc_info.value)
    
    def test_trailing_slash_normalization(self, mock_api_client):
        """Test that folder scopes with trailing slashes are normalized correctly."""
        resource_manager = ResourceManager(
            api_client=mock_api_client,
            scope_config={"folder_path": "Projects/AI/"},  # Note trailing slash
            jsonld_enabled=False
        )
        
        # Create page within scope
        page = PageMetadata(
            id="page_in_scope",
            notebook_id="nb_test",
            title="In Scope Page",
            folder_path="Projects/AI/Research",
            created_date=datetime.now(),
            last_modified=datetime.now(),
            entry_count=1,
            author="test@example.com"
        )
        
        mock_api_client.list_pages.return_value = PageListResponse(pages=[page])
        mock_api_client.list_entries.return_value = EntryListResponse(entries=[])
        
        # Should work despite trailing slash in scope configuration
        resource_content = resource_manager.read_resource(
            f"labarchives://notebook/{page.notebook_id}/page/{page.id}"
        )
        assert isinstance(resource_content, MCPResourceContent)
        assert resource_content.content["id"] == page.id
    
    def test_notebook_filtering_with_no_matching_pages(self, mock_api_client):
        """Test that notebooks with no pages matching folder scope are excluded from listing."""
        resource_manager = ResourceManager(
            api_client=mock_api_client,
            scope_config={"folder_path": "Projects/AI"},
            jsonld_enabled=False
        )
        
        # Create notebooks
        notebooks = [
            NotebookMetadata(
                id="nb_ai",
                name="AI Notebook",
                description="AI research",
                owner="test@example.com",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                folder_count=1,
                page_count=2
            ),
            NotebookMetadata(
                id="nb_physics",
                name="Physics Notebook",
                description="Physics research",
                owner="test@example.com",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                folder_count=1,
                page_count=1
            )
        ]
        
        # Create pages with mixed folder paths
        ai_pages = [
            PageMetadata(
                id="page_ai_1",
                notebook_id="nb_ai",
                title="AI Page 1",
                folder_path="Projects/AI/Research",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            )
        ]
        
        physics_pages = [
            PageMetadata(
                id="page_physics_1",
                notebook_id="nb_physics",
                title="Physics Page 1",
                folder_path="Research/Physics/Quantum",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            )
        ]
        
        # Mock API responses
        mock_api_client.list_notebooks.return_value = NotebookListResponse(notebooks=notebooks)
        
        def mock_list_pages(notebook_id):
            if notebook_id == "nb_ai":
                return PageListResponse(pages=ai_pages)
            elif notebook_id == "nb_physics":
                return PageListResponse(pages=physics_pages)
            return PageListResponse(pages=[])
        
        mock_api_client.list_pages.side_effect = mock_list_pages
        
        # Call list_resources
        resources = resource_manager.list_resources()
        
        # Should only return pages from notebook with matching folder scope
        assert len(resources) == 1
        assert resources[0].uri == "labarchives://notebook/nb_ai/page/page_ai_1"
        
        # Verify that physics notebook is excluded
        resource_uris = [resource.uri for resource in resources]
        assert "labarchives://notebook/nb_physics/page/page_physics_1" not in resource_uris
    
    def test_multiple_notebooks_with_mixed_folder_compliance(self, mock_api_client):
        """Test that two-phase listing correctly handles multiple notebooks with mixed folder compliance."""
        resource_manager = ResourceManager(
            api_client=mock_api_client,
            scope_config={"folder_path": "Experiments"},
            jsonld_enabled=False
        )
        
        # Create multiple notebooks
        notebooks = [
            NotebookMetadata(
                id="nb_exp1",
                name="Experiment Notebook 1",
                description="First experiment notebook",
                owner="test@example.com",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                folder_count=2,
                page_count=3
            ),
            NotebookMetadata(
                id="nb_exp2",
                name="Experiment Notebook 2",
                description="Second experiment notebook",
                owner="test@example.com",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                folder_count=1,
                page_count=2
            ),
            NotebookMetadata(
                id="nb_other",
                name="Other Notebook",
                description="Non-experiment notebook",
                owner="test@example.com",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                folder_count=1,
                page_count=1
            )
        ]
        
        # Create pages for each notebook
        exp1_pages = [
            PageMetadata(
                id="page_exp1_1",
                notebook_id="nb_exp1",
                title="Experiment 1 Page 1",
                folder_path="Experiments/Chemistry/Organic",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            ),
            PageMetadata(
                id="page_exp1_2",
                notebook_id="nb_exp1",
                title="Experiment 1 Page 2",
                folder_path="Experiments/Physics/Quantum",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            ),
            PageMetadata(
                id="page_exp1_out",
                notebook_id="nb_exp1",
                title="Experiment 1 Out of Scope",
                folder_path="Research/Biology/Genetics",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            )
        ]
        
        exp2_pages = [
            PageMetadata(
                id="page_exp2_1",
                notebook_id="nb_exp2",
                title="Experiment 2 Page 1",
                folder_path="Experiments/Biology/Molecular",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            ),
            PageMetadata(
                id="page_exp2_2",
                notebook_id="nb_exp2",
                title="Experiment 2 Page 2",
                folder_path="Experiments/Chemistry/Inorganic",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            )
        ]
        
        other_pages = [
            PageMetadata(
                id="page_other_1",
                notebook_id="nb_other",
                title="Other Page 1",
                folder_path="Research/Physics/Theoretical",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            )
        ]
        
        # Mock API responses
        mock_api_client.list_notebooks.return_value = NotebookListResponse(notebooks=notebooks)
        
        def mock_list_pages(notebook_id):
            if notebook_id == "nb_exp1":
                return PageListResponse(pages=exp1_pages)
            elif notebook_id == "nb_exp2":
                return PageListResponse(pages=exp2_pages)
            elif notebook_id == "nb_other":
                return PageListResponse(pages=other_pages)
            return PageListResponse(pages=[])
        
        mock_api_client.list_pages.side_effect = mock_list_pages
        
        # Call list_resources
        resources = resource_manager.list_resources()
        
        # Should return only pages within "Experiments" folder scope
        assert len(resources) == 4  # 2 from exp1, 2 from exp2, 0 from other
        
        resource_uris = [resource.uri for resource in resources]
        
        # Verify in-scope pages are included
        assert "labarchives://notebook/nb_exp1/page/page_exp1_1" in resource_uris
        assert "labarchives://notebook/nb_exp1/page/page_exp1_2" in resource_uris
        assert "labarchives://notebook/nb_exp2/page/page_exp2_1" in resource_uris
        assert "labarchives://notebook/nb_exp2/page/page_exp2_2" in resource_uris
        
        # Verify out-of-scope pages are excluded
        assert "labarchives://notebook/nb_exp1/page/page_exp1_out" not in resource_uris
        assert "labarchives://notebook/nb_other/page/page_other_1" not in resource_uris


class TestResourceManagerFolderPathComparisonValidation:
    """Test that FolderPath comparison methods are correctly integrated into ResourceManager."""
    
    @pytest.fixture
    def mock_api_client(self):
        """Create a mock LabArchivesAPIClient for testing."""
        return Mock(spec=LabArchivesAPIClient)
    
    def test_folderpath_from_raw_integration(self, mock_api_client):
        """Test that ResourceManager correctly uses FolderPath.from_raw() for scope parsing."""
        # Test with various folder path formats
        test_cases = [
            ("Projects/AI", "Projects/AI"),
            ("Projects/AI/", "Projects/AI"),
            ("/Projects/AI/", "Projects/AI"),
            ("Projects//AI", "Projects/AI"),
            ("", ""),
            ("/", "")
        ]
        
        for raw_path, expected_normalized in test_cases:
            resource_manager = ResourceManager(
                api_client=mock_api_client,
                scope_config={"folder_path": raw_path},
                jsonld_enabled=False
            )
            
            # Create a test page that should match
            page = PageMetadata(
                id="page_test",
                notebook_id="nb_test",
                title="Test Page",
                folder_path=f"{expected_normalized}/Research" if expected_normalized else "Research",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            )
            
            mock_api_client.list_pages.return_value = PageListResponse(pages=[page])
            mock_api_client.list_entries.return_value = EntryListResponse(entries=[])
            
            # Should work with normalized path matching
            if expected_normalized:  # Non-root scope
                resource_content = resource_manager.read_resource(
                    f"labarchives://notebook/{page.notebook_id}/page/{page.id}"
                )
                assert isinstance(resource_content, MCPResourceContent)
            else:  # Root scope - should allow all
                resource_content = resource_manager.read_resource(
                    f"labarchives://notebook/{page.notebook_id}/page/{page.id}"
                )
                assert isinstance(resource_content, MCPResourceContent)
    
    def test_folderpath_is_parent_of_integration(self, mock_api_client):
        """Test that ResourceManager correctly uses FolderPath.is_parent_of() for scope validation."""
        resource_manager = ResourceManager(
            api_client=mock_api_client,
            scope_config={"folder_path": "Projects/AI"},
            jsonld_enabled=False
        )
        
        # Test cases for parent-child relationships
        test_cases = [
            ("Projects/AI/Research", True),  # Valid child
            ("Projects/AI/Research/Advanced", True),  # Valid grandchild
            ("Projects/AI", False),  # Exact match (not parent)
            ("Projects", False),  # Parent of scope (not child)
            ("Projects/AI-Extended", False),  # Similar but different
            ("Projects/AI/Research/../Other", True),  # Should be normalized first
            ("Other/Projects/AI", False),  # Different hierarchy
            ("", False),  # Root path
        ]
        
        for folder_path, should_allow in test_cases:
            page = PageMetadata(
                id="page_test",
                notebook_id="nb_test",
                title="Test Page",
                folder_path=folder_path,
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            )
            
            mock_api_client.list_pages.return_value = PageListResponse(pages=[page])
            mock_api_client.list_entries.return_value = EntryListResponse(entries=[])
            
            if should_allow:
                resource_content = resource_manager.read_resource(
                    f"labarchives://notebook/{page.notebook_id}/page/{page.id}"
                )
                assert isinstance(resource_content, MCPResourceContent)
            else:
                with pytest.raises(LabArchivesMCPException) as exc_info:
                    resource_manager.read_resource(
                        f"labarchives://notebook/{page.notebook_id}/page/{page.id}"
                    )
                assert exc_info.value.code == 403
                assert "ScopeViolation" in str(exc_info.value)
    
    def test_folderpath_immutability_in_resource_manager(self, mock_api_client):
        """Test that FolderPath instances remain immutable throughout ResourceManager operations."""
        resource_manager = ResourceManager(
            api_client=mock_api_client,
            scope_config={"folder_path": "Projects/AI"},
            jsonld_enabled=False
        )
        
        # Create initial FolderPath instance
        original_scope = FolderPath.from_raw("Projects/AI")
        
        # Create test page
        page = PageMetadata(
            id="page_test",
            notebook_id="nb_test",
            title="Test Page",
            folder_path="Projects/AI/Research",
            created_date=datetime.now(),
            last_modified=datetime.now(),
            entry_count=1,
            author="test@example.com"
        )
        
        mock_api_client.list_pages.return_value = PageListResponse(pages=[page])
        mock_api_client.list_entries.return_value = EntryListResponse(entries=[])
        
        # Perform operations that should not modify the original FolderPath
        resource_content = resource_manager.read_resource(
            f"labarchives://notebook/{page.notebook_id}/page/{page.id}"
        )
        
        # Verify original FolderPath is unchanged
        assert str(original_scope) == "Projects/AI"
        assert original_scope.components == ("Projects", "AI")
        assert not original_scope.is_root
        assert original_scope.depth == 2
        
        # Verify operations succeeded
        assert isinstance(resource_content, MCPResourceContent)
        assert resource_content.content["id"] == "page_test"
    
    def test_folderpath_error_handling_in_resource_manager(self, mock_api_client):
        """Test that ResourceManager properly handles FolderPath validation errors."""
        # Test invalid folder path configurations
        invalid_paths = [
            "Projects/../AI",  # Path traversal
            "Projects/./AI",   # Current directory reference
        ]
        
        for invalid_path in invalid_paths:
            with pytest.raises(LabArchivesMCPException) as exc_info:
                ResourceManager(
                    api_client=mock_api_client,
                    scope_config={"folder_path": invalid_path},
                    jsonld_enabled=False
                )
            
            # Should raise validation error during initialization
            assert exc_info.value.code == 400
            assert "Invalid path component" in str(exc_info.value)
    
    def test_folderpath_thread_safety_in_resource_manager(self, mock_api_client):
        """Test that FolderPath instances are thread-safe within ResourceManager operations."""
        import threading
        import time
        
        resource_manager = ResourceManager(
            api_client=mock_api_client,
            scope_config={"folder_path": "Projects/AI"},
            jsonld_enabled=False
        )
        
        # Create test pages
        pages = [
            PageMetadata(
                id=f"page_{i}",
                notebook_id="nb_test",
                title=f"Test Page {i}",
                folder_path=f"Projects/AI/Research/Test{i}",
                created_date=datetime.now(),
                last_modified=datetime.now(),
                entry_count=1,
                author="test@example.com"
            )
            for i in range(10)
        ]
        
        results = []
        errors = []
        
        def test_thread(page):
            try:
                mock_api_client.list_pages.return_value = PageListResponse(pages=[page])
                mock_api_client.list_entries.return_value = EntryListResponse(entries=[])
                
                resource_content = resource_manager.read_resource(
                    f"labarchives://notebook/{page.notebook_id}/page/{page.id}"
                )
                results.append(resource_content.content["id"])
            except Exception as e:
                errors.append(str(e))
        
        # Create and start multiple threads
        threads = []
        for page in pages:
            thread = threading.Thread(target=test_thread, args=(page,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all operations succeeded
        assert len(errors) == 0
        assert len(results) == 10
        assert all(f"page_{i}" in results for i in range(10))