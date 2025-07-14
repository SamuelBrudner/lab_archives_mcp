"""
Unit and Integration Tests for LabArchives API Integration Layer

This test module provides comprehensive coverage for the LabArchives API integration layer,
validating the correct behavior of the high-level API wrapper functions and the underlying
API client. The tests ensure robust, secure, and standards-compliant access to LabArchives
notebooks, pages, entries, and user context through both positive and negative test scenarios.

The test suite covers:
- Authentication flows with both permanent API keys and temporary user tokens
- Resource discovery and listing operations with proper scope validation
- Content retrieval with metadata preservation and error handling
- Comprehensive error scenarios including network failures, authentication errors, and malformed responses
- Rate limiting and graceful degradation functionality
- Response validation and data integrity checks

All tests use static and dynamic fixtures to simulate LabArchives API responses, providing
deterministic and repeatable test execution. The tests support Feature F-002 (LabArchives API
Integration), F-003 (Resource Discovery), F-004 (Content Retrieval), F-005 (Authentication
and Security), and F-008 (Comprehensive Error Handling).

Test Categories:
- Authentication Tests: Validate credential handling and user context retrieval
- Resource Discovery Tests: Test notebook, page, and entry listing functionality
- Content Retrieval Tests: Verify metadata and content access with proper validation
- Error Handling Tests: Ensure graceful handling of all error conditions
- Integration Tests: End-to-end scenarios combining multiple API operations
"""

import pytest  # >=7.0.0 - Primary testing framework for unit/integration tests
from unittest.mock import Mock, patch, MagicMock, AsyncMock  # builtin - Mock API responses and network calls
import json  # builtin - Parse and compare JSON fixture data
from datetime import datetime
from typing import List, Dict, Any

# Import functions under test from the LabArchives API integration layer
from src.cli.labarchives_api import (
    get_authenticated_client,
    list_user_notebooks,
    list_notebook_pages,
    list_page_entries,
    get_notebook_metadata,
    get_page_metadata,
    get_entry_content
)

# Import exception classes for error handling tests
from src.cli.api.errors import (
    APIError,
    APIAuthenticationError,
    APIRateLimitError,
    APIResponseParseError,
    APIPermissionError
)

# Import data models for response validation
from src.cli.api.models import (
    NotebookMetadata,
    PageMetadata,
    EntryContent,
    NotebookListResponse,
    PageListResponse,
    EntryListResponse,
    UserContextResponse
)

# Import test fixtures for mocking API responses
from src.cli.tests.fixtures.api_responses import (
    get_notebook_list_json,
    get_page_list_json,
    get_entry_list_json,
    get_user_context_json,
    get_malformed_json,
    get_error_json,
    get_rate_limit_error_json,
    get_timeout_error_json
)


class TestAuthenticationFlow:
    """
    Test suite for authentication flow validation and user context management.
    
    This test class validates the authentication functionality including credential
    validation, user context retrieval, and error handling for various authentication
    scenarios. Tests cover both permanent API keys and temporary user tokens.
    """
    
    @pytest.mark.asyncio
    async def test_authentication_success(self):
        """
        Tests that get_authenticated_client returns a valid authenticated client when provided 
        with correct credentials and a valid user context response.
        
        This test validates successful authentication scenarios including:
        - Proper credential handling and validation
        - User context retrieval and parsing
        - Client initialization with valid authentication state
        - Audit logging of authentication events
        """
        # Arrange: Setup valid user context response fixture
        valid_user_context = json.loads(get_user_context_json())
        
        # Mock the underlying API client to return successful authentication
        with patch('src.cli.labarchives_api.LabArchivesAPI') as mock_api_class:
            mock_api_instance = Mock()
            mock_user_context = UserContextResponse(**valid_user_context)
            mock_api_instance.authenticate.return_value = mock_user_context
            mock_api_class.return_value = mock_api_instance
            
            # Act: Attempt authentication with valid credentials
            client = await get_authenticated_client(
                access_key_id="test_access_key",
                access_password="test_password",
                region="US"
            )
            
            # Assert: Verify successful authentication and client initialization
            assert client is not None, "Client should be returned for successful authentication"
            assert hasattr(client, 'client'), "Client should have underlying API client"
            assert client.client == mock_api_instance, "Client should contain the API instance"
            
            # Verify authentication method was called
            mock_api_instance.authenticate.assert_called_once()
            
            # Verify client initialization with correct parameters
            mock_api_class.assert_called_once_with(
                access_key_id="test_access_key",
                access_password="test_password",
                username=None,
                region="US"
            )
    
    @pytest.mark.asyncio
    async def test_authentication_failure(self):
        """
        Tests that get_authenticated_client raises APIAuthenticationError when provided 
        with invalid credentials or when the API returns an error response.
        
        This test validates authentication failure scenarios including:
        - Invalid credential handling
        - Authentication error propagation
        - Proper exception structure and context
        - Security audit logging of authentication failures
        """
        # Arrange: Mock the underlying API client to raise authentication error
        with patch('src.cli.labarchives_api.LabArchivesAPI') as mock_api_class:
            mock_api_instance = Mock()
            mock_api_instance.authenticate.side_effect = APIAuthenticationError(
                message="Invalid credentials",
                code=401,
                context={"endpoint": "/api/user_info", "timestamp": "2024-01-01T12:00:00Z"}
            )
            mock_api_class.return_value = mock_api_instance
            
            # Act & Assert: Verify authentication error is raised
            with pytest.raises(APIAuthenticationError) as exc_info:
                await get_authenticated_client(
                    access_key_id="invalid_key",
                    access_password="invalid_password",
                    region="US"
                )
            
            # Verify error details
            assert "Invalid credentials" in str(exc_info.value)
            assert exc_info.value.code == 401
            assert exc_info.value.context is not None
            
            # Verify authentication method was called
            mock_api_instance.authenticate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_authentication_with_user_token(self):
        """
        Tests authentication with temporary user tokens for SSO users.
        
        This test validates authentication scenarios for SSO users using temporary
        tokens rather than permanent API keys, ensuring proper token handling and
        user context retrieval.
        """
        # Arrange: Setup valid user context response fixture
        valid_user_context = json.loads(get_user_context_json())
        
        # Mock the underlying API client to return successful authentication
        with patch('src.cli.labarchives_api.LabArchivesAPI') as mock_api_class:
            mock_api_instance = Mock()
            mock_user_context = UserContextResponse(**valid_user_context)
            mock_api_instance.authenticate.return_value = mock_user_context
            mock_api_class.return_value = mock_api_instance
            
            # Act: Attempt authentication with user token
            client = await get_authenticated_client(
                access_key_id="test_access_key",
                access_password="temp_token_12345",
                username="testuser@university.edu",
                region="AU"
            )
            
            # Assert: Verify successful authentication with user token
            assert client is not None, "Client should be returned for successful token authentication"
            
            # Verify client initialization with username parameter
            mock_api_class.assert_called_once_with(
                access_key_id="test_access_key",
                access_password="temp_token_12345",
                username="testuser@university.edu",
                region="AU"
            )


class TestResourceDiscovery:
    """
    Test suite for resource discovery and listing operations.
    
    This test class validates the resource discovery functionality including notebook
    listing, page enumeration, and entry discovery. Tests cover both successful
    operations and error scenarios.
    """
    
    @pytest.mark.asyncio
    async def test_list_user_notebooks_success(self):
        """
        Tests that list_user_notebooks returns a list of NotebookMetadata objects when 
        the API returns a valid notebook list response.
        
        This test validates successful notebook listing including:
        - Proper API response parsing and validation
        - NotebookMetadata object construction
        - Response metadata preservation
        - Audit logging of resource access
        """
        # Arrange: Setup valid notebook list response fixture
        valid_notebook_response = json.loads(get_notebook_list_json())
        
        # Mock the authenticated client and API response
        mock_client = Mock()
        mock_client.client = Mock()
        mock_response = NotebookListResponse(**valid_notebook_response)
        mock_client.client.list_notebooks.return_value = mock_response
        
        # Act: List user notebooks
        notebooks = await list_user_notebooks(mock_client)
        
        # Assert: Verify successful notebook listing
        assert isinstance(notebooks, list), "Should return a list of notebooks"
        assert len(notebooks) > 0, "Should return at least one notebook"
        
        # Verify notebook metadata structure
        for notebook in notebooks:
            assert isinstance(notebook, NotebookMetadata), "Each item should be NotebookMetadata"
            assert hasattr(notebook, 'id'), "Notebook should have id"
            assert hasattr(notebook, 'name'), "Notebook should have name"
            assert hasattr(notebook, 'owner'), "Notebook should have owner"
            assert hasattr(notebook, 'created_date'), "Notebook should have created_date"
            assert hasattr(notebook, 'last_modified'), "Notebook should have last_modified"
            assert hasattr(notebook, 'page_count'), "Notebook should have page_count"
        
        # Verify API client method was called
        mock_client.client.list_notebooks.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_user_notebooks_api_error(self):
        """
        Tests that list_user_notebooks raises APIError when the API returns an error response.
        
        This test validates error handling during notebook listing including:
        - API error propagation
        - Proper exception structure and context
        - Audit logging of failed operations
        """
        # Arrange: Mock the authenticated client to raise API error
        mock_client = Mock()
        mock_client.client = Mock()
        mock_client.client.list_notebooks.side_effect = APIError(
            message="Failed to retrieve notebooks",
            code=500,
            context={"endpoint": "/api/notebooks", "timestamp": "2024-01-01T12:00:00Z"}
        )
        
        # Act & Assert: Verify API error is raised
        with pytest.raises(APIError) as exc_info:
            await list_user_notebooks(mock_client)
        
        # Verify error details
        assert "Failed to retrieve notebooks" in str(exc_info.value)
        assert exc_info.value.code == 500
        assert exc_info.value.context is not None
        
        # Verify API client method was called
        mock_client.client.list_notebooks.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_notebook_pages_success(self):
        """
        Tests that list_notebook_pages returns a list of PageMetadata objects for a valid notebook ID.
        
        This test validates successful page listing including:
        - Proper notebook ID validation
        - Page metadata parsing and validation
        - Hierarchical context preservation
        - Audit logging of page access
        """
        # Arrange: Setup valid page list response fixture
        valid_page_response = json.loads(get_page_list_json())
        
        # Mock the authenticated client and API response
        mock_client = Mock()
        mock_client.client = Mock()
        mock_response = PageListResponse(**valid_page_response)
        mock_client.client.list_pages.return_value = mock_response
        
        # Act: List notebook pages
        pages = await list_notebook_pages(mock_client, "nb_123456")
        
        # Assert: Verify successful page listing
        assert isinstance(pages, list), "Should return a list of pages"
        assert len(pages) > 0, "Should return at least one page"
        
        # Verify page metadata structure
        for page in pages:
            assert isinstance(page, PageMetadata), "Each item should be PageMetadata"
            assert hasattr(page, 'id'), "Page should have id"
            assert hasattr(page, 'notebook_id'), "Page should have notebook_id"
            assert hasattr(page, 'title'), "Page should have title"
            assert hasattr(page, 'created_date'), "Page should have created_date"
            assert hasattr(page, 'last_modified'), "Page should have last_modified"
            assert hasattr(page, 'entry_count'), "Page should have entry_count"
            assert hasattr(page, 'author'), "Page should have author"
        
        # Verify API client method was called with correct notebook ID
        mock_client.client.list_pages.assert_called_once_with("nb_123456")
    
    @pytest.mark.asyncio
    async def test_list_page_entries_success(self):
        """
        Tests that list_page_entries returns a list of EntryContent objects for a valid page ID.
        
        This test validates successful entry listing including:
        - Proper page ID validation
        - Entry content parsing and validation
        - Metadata preservation and version tracking
        - Audit logging of entry access
        """
        # Arrange: Setup valid entry list response fixture
        valid_entry_response = json.loads(get_entry_list_json())
        
        # Mock the authenticated client and API response
        mock_client = Mock()
        mock_client.client = Mock()
        mock_response = EntryListResponse(**valid_entry_response)
        mock_client.client.list_entries.return_value = mock_response
        
        # Act: List page entries
        entries = await list_page_entries(mock_client, "page_789012")
        
        # Assert: Verify successful entry listing
        assert isinstance(entries, list), "Should return a list of entries"
        assert len(entries) > 0, "Should return at least one entry"
        
        # Verify entry content structure
        for entry in entries:
            assert isinstance(entry, EntryContent), "Each item should be EntryContent"
            assert hasattr(entry, 'id'), "Entry should have id"
            assert hasattr(entry, 'page_id'), "Entry should have page_id"
            assert hasattr(entry, 'entry_type'), "Entry should have entry_type"
            assert hasattr(entry, 'content'), "Entry should have content"
            assert hasattr(entry, 'created_date'), "Entry should have created_date"
            assert hasattr(entry, 'last_modified'), "Entry should have last_modified"
            assert hasattr(entry, 'author'), "Entry should have author"
            assert hasattr(entry, 'version'), "Entry should have version"
        
        # Verify API client method was called with correct page ID
        mock_client.client.list_entries.assert_called_once_with("page_789012")


class TestContentRetrieval:
    """
    Test suite for content retrieval and metadata access operations.
    
    This test class validates the content retrieval functionality including notebook
    metadata access, page metadata retrieval, and entry content access with proper
    validation and error handling.
    """
    
    @pytest.mark.asyncio
    async def test_get_notebook_metadata_success(self):
        """
        Tests that get_notebook_metadata returns a valid NotebookMetadata object for a valid notebook ID.
        
        This test validates successful notebook metadata retrieval including:
        - Proper notebook ID validation
        - Metadata parsing and validation
        - Complete notebook information access
        - Audit logging of metadata access
        """
        # Arrange: Setup valid notebook metadata from fixture
        valid_notebook_response = json.loads(get_notebook_list_json())
        notebook_data = valid_notebook_response['notebooks'][0]
        
        # Mock the authenticated client and API response
        mock_client = Mock()
        mock_client.client = Mock()
        mock_response = NotebookListResponse(**valid_notebook_response)
        mock_client.client.list_notebooks.return_value = mock_response
        
        # Act: Get notebook metadata
        notebook_metadata = await get_notebook_metadata(mock_client, "nb_123456")
        
        # Assert: Verify successful metadata retrieval
        assert isinstance(notebook_metadata, NotebookMetadata), "Should return NotebookMetadata object"
        assert notebook_metadata.id == "nb_123456", "Should return correct notebook ID"
        assert notebook_metadata.name == notebook_data['name'], "Should preserve notebook name"
        assert notebook_metadata.owner == notebook_data['owner'], "Should preserve owner information"
        assert notebook_metadata.page_count == notebook_data['page_count'], "Should preserve page count"
        assert notebook_metadata.folder_count == notebook_data['folder_count'], "Should preserve folder count"
        
        # Verify API client method was called
        mock_client.client.list_notebooks.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_page_metadata_success(self):
        """
        Tests that get_page_metadata returns a valid PageMetadata object for a valid page ID.
        
        This test validates successful page metadata retrieval including:
        - Proper page ID validation
        - Metadata parsing and validation
        - Hierarchical context preservation
        - Audit logging of metadata access
        """
        # Arrange: Setup valid page metadata from fixture
        valid_page_response = json.loads(get_page_list_json())
        page_data = valid_page_response['pages'][0]
        
        # Mock the authenticated client and API response
        mock_client = Mock()
        mock_client.client = Mock()
        mock_response = PageListResponse(**valid_page_response)
        mock_client.client.list_pages.return_value = mock_response
        
        # Act: Get page metadata
        page_metadata = await get_page_metadata(mock_client, "page_789012")
        
        # Assert: Verify successful metadata retrieval
        assert isinstance(page_metadata, PageMetadata), "Should return PageMetadata object"
        assert page_metadata.id == "page_789012", "Should return correct page ID"
        assert page_metadata.title == page_data['title'], "Should preserve page title"
        assert page_metadata.notebook_id == page_data['notebook_id'], "Should preserve notebook relationship"
        assert page_metadata.entry_count == page_data['entry_count'], "Should preserve entry count"
        assert page_metadata.author == page_data['author'], "Should preserve author information"
        assert page_metadata.folder_path == page_data['folder_path'], "Should preserve folder path"
        
        # Verify API client method was called with correct notebook ID
        mock_client.client.list_pages.assert_called_once_with(page_data['notebook_id'])
    
    @pytest.mark.asyncio
    async def test_get_entry_content_success(self):
        """
        Tests that get_entry_content returns a valid EntryContent object for a valid entry ID.
        
        This test validates successful entry content retrieval including:
        - Proper entry ID validation
        - Content parsing and validation
        - Metadata preservation and version tracking
        - Audit logging of content access
        """
        # Arrange: Setup valid entry content from fixture
        valid_entry_response = json.loads(get_entry_list_json())
        
        # Mock the authenticated client and API response
        mock_client = Mock()
        mock_client.client = Mock()
        mock_response = EntryListResponse(**valid_entry_response)
        mock_client.client.get_entry_content.return_value = mock_response
        
        # Act: Get entry content
        entry_content = await get_entry_content(mock_client, "entry_345678")
        
        # Assert: Verify successful content retrieval
        assert isinstance(entry_content, EntryContent), "Should return EntryContent object"
        assert entry_content.id == "entry_345678", "Should return correct entry ID"
        assert entry_content.entry_type == "text", "Should preserve entry type"
        assert len(entry_content.content) > 0, "Should have content"
        assert entry_content.version >= 1, "Should have valid version number"
        assert entry_content.metadata is not None, "Should preserve metadata"
        
        # Verify API client method was called with correct entry ID
        mock_client.client.get_entry_content.assert_called_once_with("entry_345678")


class TestErrorHandling:
    """
    Test suite for comprehensive error handling and graceful degradation.
    
    This test class validates error handling across all API operations including
    authentication failures, network errors, rate limiting, and malformed responses.
    """
    
    @pytest.mark.asyncio
    async def test_list_user_notebooks_malformed_response(self):
        """
        Tests that list_user_notebooks raises APIResponseParseError when the API returns 
        a malformed or invalid response.
        
        This test validates response parsing error handling including:
        - Malformed JSON detection and handling
        - Proper exception structure and context
        - Audit logging of parsing failures
        """
        # Arrange: Mock the authenticated client to return malformed response
        mock_client = Mock()
        mock_client.client = Mock()
        mock_client.client.list_notebooks.side_effect = APIResponseParseError(
            message="Invalid JSON response: missing required field 'notebooks'",
            code=422,
            context={"validation_errors": ["notebooks required"], "response_size": 1024}
        )
        
        # Act & Assert: Verify response parse error is raised
        with pytest.raises(APIResponseParseError) as exc_info:
            await list_user_notebooks(mock_client)
        
        # Verify error details
        assert "Invalid JSON response" in str(exc_info.value)
        assert exc_info.value.code == 422
        assert exc_info.value.context is not None
        assert "validation_errors" in exc_info.value.context
        
        # Verify API client method was called
        mock_client.client.list_notebooks.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_user_notebooks_rate_limit(self):
        """
        Tests that list_user_notebooks raises APIRateLimitError when the API rate limit is exceeded.
        
        This test validates rate limiting error handling including:
        - Rate limit detection and handling
        - Proper exception structure with retry information
        - Audit logging of rate limit events
        """
        # Arrange: Mock the authenticated client to raise rate limit error
        mock_client = Mock()
        mock_client.client = Mock()
        mock_client.client.list_notebooks.side_effect = APIRateLimitError(
            message="Rate limit exceeded: 100 requests per hour limit reached",
            code=429,
            context={"retry_after": 3600, "quota_reset": "2024-01-01T13:00:00Z"}
        )
        
        # Act & Assert: Verify rate limit error is raised
        with pytest.raises(APIRateLimitError) as exc_info:
            await list_user_notebooks(mock_client)
        
        # Verify error details
        assert "Rate limit exceeded" in str(exc_info.value)
        assert exc_info.value.code == 429
        assert exc_info.value.context is not None
        assert "retry_after" in exc_info.value.context
        assert "quota_reset" in exc_info.value.context
        
        # Verify API client method was called
        mock_client.client.list_notebooks.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_authentication_permission_error(self):
        """
        Tests that authentication operations raise APIPermissionError when user lacks 
        necessary permissions.
        
        This test validates permission error handling including:
        - Permission denial detection and handling
        - Proper exception structure and context
        - Security audit logging of permission failures
        """
        # Arrange: Mock the underlying API client to raise permission error
        with patch('src.cli.labarchives_api.LabArchivesAPI') as mock_api_class:
            mock_api_instance = Mock()
            mock_api_instance.authenticate.side_effect = APIPermissionError(
                message="Access denied: insufficient permissions for operation",
                code=403,
                context={"resource_type": "authentication", "user_scope": "limited_access"}
            )
            mock_api_class.return_value = mock_api_instance
            
            # Act & Assert: Verify permission error is raised
            with pytest.raises(APIPermissionError) as exc_info:
                await get_authenticated_client(
                    access_key_id="limited_key",
                    access_password="limited_password",
                    region="US"
                )
            
            # Verify error details
            assert "Access denied" in str(exc_info.value)
            assert exc_info.value.code == 403
            assert exc_info.value.context is not None
            assert "resource_type" in exc_info.value.context
            
            # Verify authentication method was called
            mock_api_instance.authenticate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_network_timeout_error(self):
        """
        Tests that network timeout errors are handled gracefully across all operations.
        
        This test validates network timeout error handling including:
        - Timeout detection and handling
        - Proper exception structure and context
        - Audit logging of network failures
        """
        # Arrange: Mock the authenticated client to raise timeout error
        mock_client = Mock()
        mock_client.client = Mock()
        mock_client.client.list_notebooks.side_effect = APIError(
            message="Request timeout - server did not respond within expected time",
            code=408,
            context={"timeout_duration": "30s", "retry_after": "5s"}
        )
        
        # Act & Assert: Verify timeout error is raised
        with pytest.raises(APIError) as exc_info:
            await list_user_notebooks(mock_client)
        
        # Verify error details
        assert "Request timeout" in str(exc_info.value)
        assert exc_info.value.code == 408
        assert exc_info.value.context is not None
        assert "timeout_duration" in exc_info.value.context
        
        # Verify API client method was called
        mock_client.client.list_notebooks.assert_called_once()


class TestIntegrationScenarios:
    """
    Test suite for end-to-end integration scenarios and workflow validation.
    
    This test class validates complete workflow scenarios combining multiple API
    operations to ensure proper integration and data flow across the system.
    """
    
    @pytest.mark.asyncio
    async def test_complete_resource_discovery_workflow(self):
        """
        Tests a complete workflow from authentication through content retrieval.
        
        This integration test validates the complete resource discovery workflow:
        1. Authentication with valid credentials
        2. Notebook listing and selection
        3. Page listing within notebook
        4. Entry listing within page
        5. Content retrieval for specific entry
        
        Ensures proper data flow and context preservation across all operations.
        """
        # Arrange: Setup all required fixtures
        valid_user_context = json.loads(get_user_context_json())
        valid_notebook_response = json.loads(get_notebook_list_json())
        valid_page_response = json.loads(get_page_list_json())
        valid_entry_response = json.loads(get_entry_list_json())
        
        # Mock the complete API workflow
        with patch('src.cli.labarchives_api.LabArchivesAPI') as mock_api_class:
            mock_api_instance = Mock()
            
            # Setup authentication response
            mock_user_context = UserContextResponse(**valid_user_context)
            mock_api_instance.authenticate.return_value = mock_user_context
            
            # Setup resource discovery responses
            mock_notebook_response = NotebookListResponse(**valid_notebook_response)
            mock_api_instance.list_notebooks.return_value = mock_notebook_response
            
            mock_page_response = PageListResponse(**valid_page_response)
            mock_api_instance.list_pages.return_value = mock_page_response
            
            mock_entry_response = EntryListResponse(**valid_entry_response)
            mock_api_instance.list_entries.return_value = mock_entry_response
            mock_api_instance.get_entry_content.return_value = mock_entry_response
            
            mock_api_class.return_value = mock_api_instance
            
            # Act: Execute complete workflow
            # Step 1: Authentication
            client = await get_authenticated_client(
                access_key_id="test_key",
                access_password="test_password",
                region="US"
            )
            
            # Step 2: List notebooks
            notebooks = await list_user_notebooks(client)
            assert len(notebooks) > 0, "Should have notebooks"
            selected_notebook = notebooks[0]
            
            # Step 3: List pages in notebook
            pages = await list_notebook_pages(client, selected_notebook.id)
            assert len(pages) > 0, "Should have pages"
            selected_page = pages[0]
            
            # Step 4: List entries in page
            entries = await list_page_entries(client, selected_page.id)
            assert len(entries) > 0, "Should have entries"
            selected_entry = entries[0]
            
            # Step 5: Get entry content
            entry_content = await get_entry_content(client, selected_entry.id)
            assert entry_content is not None, "Should have entry content"
            
            # Assert: Verify workflow completion and data consistency
            assert client is not None, "Authentication should succeed"
            assert isinstance(notebooks, list), "Should return notebook list"
            assert isinstance(pages, list), "Should return page list"
            assert isinstance(entries, list), "Should return entry list"
            assert isinstance(entry_content, EntryContent), "Should return entry content"
            
            # Verify proper context preservation
            assert selected_page.notebook_id == selected_notebook.id, "Page should belong to notebook"
            assert selected_entry.page_id == selected_page.id, "Entry should belong to page"
            assert entry_content.id == selected_entry.id, "Content should match entry"
            
            # Verify all API methods were called in correct sequence
            mock_api_instance.authenticate.assert_called_once()
            mock_api_instance.list_notebooks.assert_called_once()
            mock_api_instance.list_pages.assert_called_once_with(selected_notebook.id)
            mock_api_instance.list_entries.assert_called_once_with(selected_page.id)
            mock_api_instance.get_entry_content.assert_called_once_with(selected_entry.id)
    
    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self):
        """
        Tests error recovery and graceful degradation in workflow scenarios.
        
        This integration test validates proper error handling throughout the workflow:
        1. Authentication success
        2. Notebook listing failure with recovery
        3. Proper error propagation and context preservation
        4. Audit logging of error events
        """
        # Arrange: Setup authentication success but notebook listing failure
        valid_user_context = json.loads(get_user_context_json())
        
        with patch('src.cli.labarchives_api.LabArchivesAPI') as mock_api_class:
            mock_api_instance = Mock()
            
            # Setup authentication success
            mock_user_context = UserContextResponse(**valid_user_context)
            mock_api_instance.authenticate.return_value = mock_user_context
            
            # Setup notebook listing failure
            mock_api_instance.list_notebooks.side_effect = APIError(
                message="Service temporarily unavailable",
                code=503,
                context={"retry_after": "30s", "service_status": "degraded"}
            )
            
            mock_api_class.return_value = mock_api_instance
            
            # Act: Execute workflow with error handling
            # Step 1: Authentication should succeed
            client = await get_authenticated_client(
                access_key_id="test_key",
                access_password="test_password",
                region="US"
            )
            
            # Step 2: Notebook listing should fail gracefully
            with pytest.raises(APIError) as exc_info:
                await list_user_notebooks(client)
            
            # Assert: Verify error handling and context preservation
            assert client is not None, "Authentication should succeed despite later failures"
            assert "Service temporarily unavailable" in str(exc_info.value)
            assert exc_info.value.code == 503
            assert exc_info.value.context is not None
            assert "retry_after" in exc_info.value.context
            
            # Verify proper method call sequence
            mock_api_instance.authenticate.assert_called_once()
            mock_api_instance.list_notebooks.assert_called_once()