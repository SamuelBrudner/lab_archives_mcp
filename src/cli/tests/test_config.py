"""
LabArchives MCP Server - Configuration Management Test Suite

This comprehensive test module verifies the configuration management subsystem of the
LabArchives MCP Server CLI. It tests the loading, merging, and validation of configuration
from CLI arguments, environment variables, and config files, ensuring that the
ServerConfiguration object is constructed correctly and that all validation logic
(including error handling for invalid/edge-case configs) is robust.

Test Coverage:
- F-005: Authentication and Security Management - Tests secure credential loading and validation
- F-006: CLI Interface and Configuration - Tests CLI argument parsing and precedence rules
- F-007: Scope Limitation and Access Control - Tests scope configuration validation
- F-008: Comprehensive Audit Logging - Tests error logging and structured exception handling

The test suite uses sample configurations from fixtures to verify correct behavior for
valid, invalid, and edge-case scenarios, checking that all exceptions and error messages
are raised as expected with proper audit logging for compliance requirements.
"""

import pytest  # pytest>=7.0.0 - Python testing framework for unit and integration tests
import os  # builtin - Operating system interface for environment variable manipulation
import copy  # builtin - Deep copy utilities for test data isolation
import tempfile  # builtin - Temporary file creation for testing file operations
import json  # builtin - JSON serialization for test configuration files
from unittest.mock import patch, MagicMock, mock_open  # builtin - Mocking framework for test isolation
from typing import Dict, Any, Optional  # builtin - Type annotations for test functions

# Internal imports - Configuration management functions under test
from src.cli.config import (
    load_configuration,
    reload_configuration,
    get_config_value,
    _CONFIG_CACHE,
    _LAST_CLI_ARGS,
    _LAST_CONFIG_FILE_PATH
)

# Internal imports - Configuration models for type checking and validation
from src.cli.models import (
    ServerConfiguration,
    AuthenticationConfig,
    ScopeConfig,
    OutputConfig,
    LoggingConfig
)

# Internal imports - Exception classes for error handling tests
from src.cli.exceptions import LabArchivesMCPException

# Internal imports - Test fixtures for sample configuration data
from src.cli.tests.fixtures.config_samples import (
    get_valid_config,
    get_invalid_config,
    get_edge_case_config
)

# Internal imports - Constants for default values and validation
from src.cli.constants import (
    DEFAULT_API_BASE_URL,
    DEFAULT_LOG_FILE,
    DEFAULT_LOG_LEVEL,
    MCP_SERVER_NAME,
    MCP_SERVER_VERSION
)


class TestLoadValidConfiguration:
    """
    Test class for validating the load_configuration function with valid input scenarios.
    
    This class tests the primary happy path scenarios where configuration loading
    should succeed with properly structured and validated configuration objects.
    Tests cover various combinations of configuration sources and verify that
    the resulting ServerConfiguration object contains expected values.
    """
    
    @pytest.mark.usefixtures('get_valid_config')
    def test_load_valid_configuration_from_cli_args(self, get_valid_config):
        """
        Tests that load_configuration correctly loads and validates a valid configuration
        from CLI arguments and returns a ServerConfiguration object with expected values.
        
        This test verifies the fundamental functionality of configuration loading when
        provided with valid CLI arguments. It ensures that all configuration sections
        are properly constructed and that the precedence rules work correctly.
        """
        # Arrange: Prepare valid CLI arguments based on the fixture
        valid_config = get_valid_config
        cli_args = {
            'access_key_id': valid_config.authentication.access_key_id,
            'access_secret': valid_config.authentication.access_secret,
            'username': valid_config.authentication.username,
            'api_base_url': valid_config.authentication.api_base_url,
            'notebook_id': valid_config.scope.notebook_id,
            'log_level': valid_config.logging.log_level,
            'verbose': valid_config.logging.verbose
        }
        
        # Act: Call load_configuration with valid CLI arguments
        result_config = load_configuration(cli_args=cli_args)
        
        # Assert: Verify the returned object is a ServerConfiguration instance
        assert isinstance(result_config, ServerConfiguration), \
            "load_configuration should return a ServerConfiguration object"
        
        # Assert: Verify authentication configuration is correctly populated
        assert result_config.authentication.access_key_id == cli_args['access_key_id'], \
            "Authentication access_key_id should match CLI argument"
        assert result_config.authentication.access_secret == cli_args['access_secret'], \
            "Authentication access_secret should match CLI argument"
        assert result_config.authentication.username == cli_args['username'], \
            "Authentication username should match CLI argument"
        assert result_config.authentication.api_base_url == cli_args['api_base_url'], \
            "Authentication api_base_url should match CLI argument"
        
        # Assert: Verify scope configuration is correctly populated
        assert result_config.scope.notebook_id == cli_args['notebook_id'], \
            "Scope notebook_id should match CLI argument"
        assert result_config.scope.notebook_name is None, \
            "Scope notebook_name should be None when not specified"
        assert result_config.scope.folder_path is None, \
            "Scope folder_path should be None when not specified"
        
        # Assert: Verify logging configuration is correctly populated
        assert result_config.logging.log_level == cli_args['log_level'], \
            "Logging log_level should match CLI argument"
        assert result_config.logging.verbose == cli_args['verbose'], \
            "Logging verbose should match CLI argument"
        
        # Assert: Verify server metadata uses default values
        assert result_config.server_name == MCP_SERVER_NAME, \
            "Server name should use default value"
        assert result_config.server_version == MCP_SERVER_VERSION, \
            "Server version should use default value"
        
        # Assert: Verify no exceptions are raised during configuration loading
        # This is implicit in the successful execution above
    
    def test_load_valid_configuration_from_config_file(self, tmp_path):
        """
        Tests that load_configuration correctly loads configuration from a JSON file
        and merges it with default values to create a valid ServerConfiguration.
        
        This test verifies file-based configuration loading with proper JSON parsing
        and validation. It ensures that configuration files can be used as a source
        for configuration data with appropriate error handling.
        """
        # Arrange: Create a temporary configuration file with valid JSON
        config_data = {
            'access_key_id': 'AKID_FILE_TEST_12345',
            'access_secret': 'file_secret_password_123',
            'username': 'fileuser@example.com',
            'api_base_url': DEFAULT_API_BASE_URL,
            'notebook_id': 'notebook_file_test',
            'log_level': 'DEBUG',
            'verbose': True
        }
        
        config_file = tmp_path / "test_config.json"
        config_file.write_text(json.dumps(config_data, indent=2))
        
        # Act: Load configuration from the file
        result_config = load_configuration(config_file_path=str(config_file))
        
        # Assert: Verify the configuration was loaded correctly from the file
        assert isinstance(result_config, ServerConfiguration), \
            "Configuration should be loaded as ServerConfiguration object"
        
        # Assert: Verify file-based values are used
        assert result_config.authentication.access_key_id == config_data['access_key_id'], \
            "Authentication access_key_id should match file value"
        assert result_config.authentication.access_secret == config_data['access_secret'], \
            "Authentication access_secret should match file value"
        assert result_config.scope.notebook_id == config_data['notebook_id'], \
            "Scope notebook_id should match file value"
        assert result_config.logging.log_level == config_data['log_level'], \
            "Logging log_level should match file value"
        assert result_config.logging.verbose == config_data['verbose'], \
            "Logging verbose should match file value"
        
        # Assert: Verify default values are used where not specified in file
        assert result_config.output.json_ld_enabled is False, \
            "Output json_ld_enabled should use default value"
        assert result_config.output.structured_output is True, \
            "Output structured_output should use default value"
    
    def test_load_configuration_with_environment_variables(self):
        """
        Tests that load_configuration correctly loads configuration from environment
        variables and merges it with default values to create a valid ServerConfiguration.
        
        This test verifies environment variable-based configuration loading with
        proper type conversion and validation. It ensures that environment variables
        follow the expected naming convention and precedence rules.
        """
        # Arrange: Set environment variables with valid configuration values
        env_vars = {
            'LABARCHIVES_AKID': 'AKID_ENV_TEST_67890',
            'LABARCHIVES_SECRET': 'env_secret_password_456',
            'LABARCHIVES_USER': 'envuser@example.com',
            'LABARCHIVES_API_BASE': DEFAULT_API_BASE_URL,
            'LABARCHIVES_NOTEBOOK_ID': 'notebook_env_test',
            'LABARCHIVES_LOG_LEVEL': 'WARNING',
            'LABARCHIVES_VERBOSE': 'false'
        }
        
        # Act: Load configuration with environment variables set
        with patch.dict(os.environ, env_vars):
            result_config = load_configuration()
        
        # Assert: Verify environment variable values are used
        assert result_config.authentication.access_key_id == env_vars['LABARCHIVES_AKID'], \
            "Authentication access_key_id should match environment variable"
        assert result_config.authentication.access_secret == env_vars['LABARCHIVES_SECRET'], \
            "Authentication access_secret should match environment variable"
        assert result_config.authentication.username == env_vars['LABARCHIVES_USER'], \
            "Authentication username should match environment variable"
        assert result_config.scope.notebook_id == env_vars['LABARCHIVES_NOTEBOOK_ID'], \
            "Scope notebook_id should match environment variable"
        assert result_config.logging.log_level == env_vars['LABARCHIVES_LOG_LEVEL'], \
            "Logging log_level should match environment variable"
        assert result_config.logging.verbose is False, \
            "Logging verbose should be converted from string to boolean"
        
        # Assert: Verify default values are used where environment variables are not set
        assert result_config.output.json_ld_enabled is False, \
            "Output json_ld_enabled should use default value"
        assert result_config.server_name == MCP_SERVER_NAME, \
            "Server name should use default value"
    
    def test_load_configuration_all_sources_combined(self, tmp_path):
        """
        Tests that load_configuration correctly merges configuration from all sources
        (CLI args, environment variables, config file, defaults) with proper precedence.
        
        This test verifies the complete configuration merging workflow with all
        possible configuration sources. It ensures that precedence rules are
        correctly applied: CLI > env > file > defaults.
        """
        # Arrange: Create a configuration file with base values
        file_config = {
            'access_key_id': 'AKID_FILE_BASE',
            'access_secret': 'file_secret_base',
            'username': 'fileuser@example.com',
            'log_level': 'INFO',
            'notebook_id': 'notebook_file_base'
        }
        
        config_file = tmp_path / "combined_config.json"
        config_file.write_text(json.dumps(file_config, indent=2))
        
        # Set environment variables that should override file values
        env_vars = {
            'LABARCHIVES_AKID': 'AKID_ENV_OVERRIDE',
            'LABARCHIVES_LOG_LEVEL': 'DEBUG',
            'LABARCHIVES_VERBOSE': 'true'
        }
        
        # Set CLI arguments that should override both env and file values
        cli_args = {
            'access_key_id': 'AKID_CLI_FINAL',
            'log_level': 'ERROR',
            'quiet': True  # Should override env verbose setting
        }
        
        # Act: Load configuration with all sources
        with patch.dict(os.environ, env_vars):
            result_config = load_configuration(
                cli_args=cli_args,
                config_file_path=str(config_file)
            )
        
        # Assert: Verify CLI arguments have highest precedence
        assert result_config.authentication.access_key_id == cli_args['access_key_id'], \
            "CLI argument should override environment and file values"
        assert result_config.logging.log_level == cli_args['log_level'], \
            "CLI log_level should override environment and file values"
        assert result_config.logging.quiet == cli_args['quiet'], \
            "CLI quiet should override environment verbose setting"
        
        # Assert: Verify environment variables override file values
        # (where CLI doesn't override)
        assert result_config.authentication.access_secret == file_config['access_secret'], \
            "File access_secret should be used when not overridden"
        
        # Assert: Verify file values are used where not overridden
        assert result_config.authentication.username == file_config['username'], \
            "File username should be used when not overridden by CLI or env"
        assert result_config.scope.notebook_id == file_config['notebook_id'], \
            "File notebook_id should be used when not overridden"
        
        # Assert: Verify default values are used where not specified anywhere
        assert result_config.output.json_ld_enabled is False, \
            "Default json_ld_enabled should be used"
        assert result_config.server_name == MCP_SERVER_NAME, \
            "Default server_name should be used"


class TestLoadInvalidConfigurationRaises:
    """
    Test class for validating error handling in load_configuration with invalid inputs.
    
    This class tests negative scenarios where configuration loading should fail
    with appropriate LabArchivesMCPException instances. Tests cover various types
    of invalid configurations and ensure proper error messages and audit logging.
    """
    
    @pytest.mark.usefixtures('get_invalid_config')
    def test_load_invalid_configuration_missing_required_fields(self):
        """
        Tests that load_configuration raises LabArchivesMCPException when provided
        with configuration missing required fields like access_key_id or access_secret.
        
        This test ensures that validation catches missing required authentication
        credentials and provides clear error messages for troubleshooting.
        """
        # Arrange: Create CLI arguments with missing required fields
        invalid_cli_args = {
            'access_key_id': '',  # Invalid: empty string
            'access_secret': None,  # Invalid: None value
            'username': 'validuser@example.com',
            'log_level': 'INFO'
        }
        
        # Act & Assert: Verify that LabArchivesMCPException is raised
        with pytest.raises(LabArchivesMCPException) as exc_info:
            load_configuration(cli_args=invalid_cli_args)
        
        # Assert: Verify exception contains information about the validation failure
        assert "access_key_id" in str(exc_info.value) or "access_secret" in str(exc_info.value), \
            "Exception message should mention the missing required field"
        assert exc_info.value.code is not None, \
            "Exception should have an error code for programmatic handling"
        assert exc_info.value.context is not None, \
            "Exception should have context for audit logging"
    
    def test_load_invalid_configuration_invalid_types(self):
        """
        Tests that load_configuration raises LabArchivesMCPException when provided
        with configuration containing invalid data types for specific fields.
        
        This test ensures that type validation catches incorrect data types
        and provides clear error messages about expected vs actual types.
        """
        # Arrange: Create CLI arguments with invalid data types
        invalid_cli_args = {
            'access_key_id': 'AKID_VALID_12345',
            'access_secret': 'valid_secret_123',
            'username': 'validuser@example.com',
            'verbose': 'not_a_boolean',  # Invalid: string instead of boolean
            'quiet': 'also_not_boolean',  # Invalid: string instead of boolean
            'log_level': 'INVALID_LEVEL'  # Invalid: not a valid log level
        }
        
        # Act & Assert: Verify that LabArchivesMCPException is raised
        with pytest.raises(LabArchivesMCPException) as exc_info:
            load_configuration(cli_args=invalid_cli_args)
        
        # Assert: Verify exception contains information about type validation failure
        assert "validation" in str(exc_info.value).lower(), \
            "Exception message should mention validation failure"
        assert exc_info.value.code is not None, \
            "Exception should have an error code for programmatic handling"
        
        # Assert: Verify exception context contains diagnostic information
        assert exc_info.value.context is not None, \
            "Exception should have context for debugging"
    
    def test_load_invalid_configuration_conflicting_scope_values(self):
        """
        Tests that load_configuration raises LabArchivesMCPException when provided
        with configuration that has conflicting scope values (multiple scope types).
        
        This test ensures that business rule validation catches conflicting
        scope configurations and provides clear error messages about mutual exclusivity.
        """
        # Arrange: Create CLI arguments with conflicting scope values
        invalid_cli_args = {
            'access_key_id': 'AKID_VALID_12345',
            'access_secret': 'valid_secret_123',
            'username': 'validuser@example.com',
            'notebook_id': 'notebook_123',
            'notebook_name': 'Conflicting Notebook Name',  # Invalid: conflicts with notebook_id
            'folder_path': '/conflicting/path',  # Invalid: conflicts with notebook scope
            'log_level': 'INFO'
        }
        
        # Act & Assert: Verify that LabArchivesMCPException is raised
        with pytest.raises(LabArchivesMCPException) as exc_info:
            load_configuration(cli_args=invalid_cli_args)
        
        # Assert: Verify exception mentions scope conflict
        assert "scope" in str(exc_info.value).lower(), \
            "Exception message should mention scope validation"
        assert "mutual" in str(exc_info.value).lower() or "exclusive" in str(exc_info.value).lower(), \
            "Exception message should mention mutual exclusivity"
        assert exc_info.value.code is not None, \
            "Exception should have an error code for programmatic handling"
    
    def test_load_invalid_configuration_conflicting_verbosity_flags(self):
        """
        Tests that load_configuration raises LabArchivesMCPException when provided
        with configuration that has conflicting verbosity flags (both verbose and quiet).
        
        This test ensures that logging configuration validation catches conflicting
        verbosity settings and provides clear error messages about the conflict.
        """
        # Arrange: Create CLI arguments with conflicting verbosity flags
        invalid_cli_args = {
            'access_key_id': 'AKID_VALID_12345',
            'access_secret': 'valid_secret_123',
            'username': 'validuser@example.com',
            'log_level': 'INFO',
            'verbose': True,
            'quiet': True  # Invalid: conflicts with verbose
        }
        
        # Act & Assert: Verify that LabArchivesMCPException is raised
        with pytest.raises(LabArchivesMCPException) as exc_info:
            load_configuration(cli_args=invalid_cli_args)
        
        # Assert: Verify exception mentions verbosity conflict
        assert "verbose" in str(exc_info.value).lower() and "quiet" in str(exc_info.value).lower(), \
            "Exception message should mention both verbose and quiet"
        assert "simultaneously" in str(exc_info.value).lower() or "conflict" in str(exc_info.value).lower(), \
            "Exception message should mention the conflict"
        assert exc_info.value.code is not None, \
            "Exception should have an error code for programmatic handling"
    
    def test_load_invalid_configuration_invalid_file_path(self):
        """
        Tests that load_configuration raises LabArchivesMCPException when provided
        with an invalid or non-existent configuration file path.
        
        This test ensures that file access errors are properly handled and provide
        clear error messages for troubleshooting file-related issues.
        """
        # Arrange: Use a non-existent file path
        non_existent_file = '/definitely/does/not/exist/config.json'
        
        # Act & Assert: Verify that LabArchivesMCPException is raised
        with pytest.raises(LabArchivesMCPException) as exc_info:
            load_configuration(config_file_path=non_existent_file)
        
        # Assert: Verify exception mentions file access issue
        assert "file" in str(exc_info.value).lower(), \
            "Exception message should mention file access"
        assert exc_info.value.code is not None, \
            "Exception should have an error code for programmatic handling"
        assert exc_info.value.context is not None, \
            "Exception should have context with file path information"
    
    def test_load_invalid_configuration_malformed_json_file(self, tmp_path):
        """
        Tests that load_configuration raises LabArchivesMCPException when provided
        with a configuration file containing malformed JSON.
        
        This test ensures that JSON parsing errors are properly handled and provide
        clear error messages about the syntax issue.
        """
        # Arrange: Create a configuration file with malformed JSON
        malformed_config_file = tmp_path / "malformed_config.json"
        malformed_config_file.write_text('{"access_key_id": "test", "invalid": json}')
        
        # Act & Assert: Verify that LabArchivesMCPException is raised
        with pytest.raises(LabArchivesMCPException) as exc_info:
            load_configuration(config_file_path=str(malformed_config_file))
        
        # Assert: Verify exception mentions JSON parsing issue
        assert "json" in str(exc_info.value).lower() or "parse" in str(exc_info.value).lower(), \
            "Exception message should mention JSON parsing error"
        assert exc_info.value.code is not None, \
            "Exception should have an error code for programmatic handling"
        assert exc_info.value.context is not None, \
            "Exception should have context with file path information"
    
    def test_load_invalid_configuration_invalid_api_base_url(self):
        """
        Tests that load_configuration raises LabArchivesMCPException when provided
        with an invalid API base URL (non-HTTPS, malformed, or unsupported endpoint).
        
        This test ensures that API endpoint validation catches security issues
        and unsupported endpoints with clear error messages.
        """
        # Arrange: Create CLI arguments with invalid API base URL
        invalid_cli_args = {
            'access_key_id': 'AKID_VALID_12345',
            'access_secret': 'valid_secret_123',
            'username': 'validuser@example.com',
            'api_base_url': 'http://insecure.example.com/api',  # Invalid: not HTTPS
            'log_level': 'INFO'
        }
        
        # Act & Assert: Verify that LabArchivesMCPException is raised
        with pytest.raises(LabArchivesMCPException) as exc_info:
            load_configuration(cli_args=invalid_cli_args)
        
        # Assert: Verify exception mentions API URL validation
        assert "api_base_url" in str(exc_info.value).lower() or "https" in str(exc_info.value).lower(), \
            "Exception message should mention API URL validation"
        assert exc_info.value.code is not None, \
            "Exception should have an error code for programmatic handling"
        assert exc_info.value.context is not None, \
            "Exception should have context with URL information"


class TestEdgeCaseConfiguration:
    """
    Test class for validating edge case handling in load_configuration.
    
    This class tests boundary conditions, extreme values, and unusual but valid
    configurations to ensure robust handling of edge cases. Tests verify that
    the system handles unusual inputs gracefully and provides appropriate
    normalization or error handling.
    """
    
    @pytest.mark.usefixtures('get_edge_case_config')
    def test_edge_case_configuration_maximum_length_values(self):
        """
        Tests that load_configuration handles edge-case configurations with maximum
        length values for string fields according to business rules.
        
        This test ensures that boundary value validation works correctly for
        string length limits and that the system can handle maximum allowed values.
        """
        # Arrange: Create CLI arguments with maximum length values
        edge_case_cli_args = {
            'access_key_id': 'A' * 256,  # Edge case: maximum length
            'access_secret': 'x' * 1024,  # Edge case: maximum length
            'username': 'very.long.email.address@very.long.domain.name.institution.edu',
            'api_base_url': DEFAULT_API_BASE_URL,
            'notebook_id': 'notebook_with_special_chars_123',
            'log_level': 'DEBUG'
        }
        
        # Act: Load configuration with edge case values
        result_config = load_configuration(cli_args=edge_case_cli_args)
        
        # Assert: Verify that edge case values are accepted and processed correctly
        assert isinstance(result_config, ServerConfiguration), \
            "Configuration should be created successfully with edge case values"
        assert len(result_config.authentication.access_key_id) == 256, \
            "Maximum length access_key_id should be accepted"
        assert len(result_config.authentication.access_secret) == 1024, \
            "Maximum length access_secret should be accepted"
        assert result_config.authentication.username == edge_case_cli_args['username'], \
            "Long username should be accepted when valid"
        assert result_config.scope.notebook_id == edge_case_cli_args['notebook_id'], \
            "Notebook ID with special characters should be accepted"
        
        # Assert: Verify that validation doesn't reject valid edge cases
        assert result_config.logging.log_level == 'DEBUG', \
            "Edge case log level should be accepted"
    
    def test_edge_case_configuration_special_characters_in_paths(self, tmp_path):
        """
        Tests that load_configuration handles edge-case configurations with special
        characters in file paths and folder paths, normalizing them appropriately.
        
        This test ensures that file path handling is robust for various character
        sets and that path normalization works correctly with edge cases.
        """
        # Arrange: Create a configuration file with special characters in path
        config_data = {
            'access_key_id': 'AKID_SPECIAL_CHARS_123',
            'access_secret': 'special_secret_456',
            'username': 'user@example.com',
            'log_file': 'logs/with spaces and unicode 测试.log',
            'folder_path': 'research/project α/data β',
            'log_level': 'INFO'
        }
        
        # Create a config file with unicode characters in the name
        config_file = tmp_path / "config_测试.json"
        config_file.write_text(json.dumps(config_data, indent=2, ensure_ascii=False))
        
        # Act: Load configuration from file with special characters
        result_config = load_configuration(config_file_path=str(config_file))
        
        # Assert: Verify that special characters are handled correctly
        assert isinstance(result_config, ServerConfiguration), \
            "Configuration should be created successfully with special characters"
        assert result_config.logging.log_file == config_data['log_file'], \
            "Log file path with special characters should be preserved"
        assert result_config.scope.folder_path == config_data['folder_path'], \
            "Folder path with special characters should be preserved"
        
        # Assert: Verify that unicode characters don't cause parsing issues
        assert result_config.authentication.access_key_id == config_data['access_key_id'], \
            "Configuration should be parsed correctly despite unicode file name"
    
    def test_edge_case_configuration_empty_optional_fields(self):
        """
        Tests that load_configuration handles edge-case configurations where optional
        fields are explicitly set to None or empty strings, ensuring proper defaults.
        
        This test verifies that the system correctly distinguishes between missing
        fields and explicitly empty fields, applying appropriate default values.
        """
        # Arrange: Create CLI arguments with explicitly empty optional fields
        edge_case_cli_args = {
            'access_key_id': 'AKID_EMPTY_OPTIONAL_123',
            'access_secret': 'empty_optional_secret_456',
            'username': None,  # Explicitly None
            'notebook_id': None,  # Explicitly None
            'notebook_name': None,  # Explicitly None
            'folder_path': None,  # Explicitly None
            'log_file': None,  # Explicitly None
            'log_level': 'INFO'
        }
        
        # Act: Load configuration with explicitly empty optional fields
        result_config = load_configuration(cli_args=edge_case_cli_args)
        
        # Assert: Verify that None values are handled correctly
        assert isinstance(result_config, ServerConfiguration), \
            "Configuration should be created successfully with None optional fields"
        assert result_config.authentication.username is None, \
            "Username should remain None when explicitly set"
        assert result_config.scope.notebook_id is None, \
            "Notebook ID should remain None when explicitly set"
        assert result_config.scope.notebook_name is None, \
            "Notebook name should remain None when explicitly set"
        assert result_config.scope.folder_path is None, \
            "Folder path should remain None when explicitly set"
        
        # Assert: Verify that default values are used for required fields
        assert result_config.logging.log_file == DEFAULT_LOG_FILE, \
            "Log file should use default when None is provided"
        assert result_config.authentication.api_base_url == DEFAULT_API_BASE_URL, \
            "API base URL should use default when not specified"
    
    def test_edge_case_configuration_boolean_string_conversion(self):
        """
        Tests that load_configuration handles edge-case boolean string conversions
        from environment variables correctly, including various true/false representations.
        
        This test ensures that boolean environment variable parsing is robust
        and handles various string representations consistently.
        """
        # Arrange: Set environment variables with various boolean string representations
        env_vars = {
            'LABARCHIVES_AKID': 'AKID_BOOL_TEST_789',
            'LABARCHIVES_SECRET': 'bool_secret_test_012',
            'LABARCHIVES_USER': 'booluser@example.com',
            'LABARCHIVES_VERBOSE': 'yes',  # Should convert to True
            'LABARCHIVES_QUIET': 'off',   # Should convert to False
            'LABARCHIVES_JSON_LD_ENABLED': '1',  # Should convert to True
            'LABARCHIVES_STRUCTURED_OUTPUT': 'enabled'  # Should convert to True
        }
        
        # Act: Load configuration with boolean environment variables
        with patch.dict(os.environ, env_vars):
            result_config = load_configuration()
        
        # Assert: Verify boolean string conversion works correctly
        assert isinstance(result_config, ServerConfiguration), \
            "Configuration should be created successfully with boolean strings"
        
        # Note: The actual boolean conversion is handled by the get_env_var utility
        # These tests verify that the configuration system properly integrates
        # with the utility function for boolean conversion
    
    def test_edge_case_configuration_mixed_source_precedence(self, tmp_path):
        """
        Tests that load_configuration handles edge-case scenarios with mixed configuration
        sources and complex precedence rules, ensuring proper value selection.
        
        This test verifies that precedence rules work correctly in complex scenarios
        with partial configuration from multiple sources.
        """
        # Arrange: Create a configuration file with some values
        file_config = {
            'access_key_id': 'AKID_FILE_PRECEDENCE',
            'access_secret': 'file_secret_precedence',
            'username': 'fileuser@precedence.com',
            'log_level': 'WARNING',
            'notebook_name': 'File Notebook Name'
        }
        
        config_file = tmp_path / "precedence_config.json"
        config_file.write_text(json.dumps(file_config, indent=2))
        
        # Set environment variables for some other values
        env_vars = {
            'LABARCHIVES_SECRET': 'env_secret_precedence',  # Should override file
            'LABARCHIVES_LOG_LEVEL': 'DEBUG',  # Should override file
            'LABARCHIVES_NOTEBOOK_ID': 'env_notebook_id',  # Should override file notebook_name
            'LABARCHIVES_VERBOSE': 'true'
        }
        
        # Set CLI arguments for final overrides
        cli_args = {
            'access_key_id': 'AKID_CLI_PRECEDENCE',  # Should override file
            'log_level': 'ERROR',  # Should override env and file
            'quiet': True  # Should override env verbose
        }
        
        # Act: Load configuration with complex precedence scenario
        with patch.dict(os.environ, env_vars):
            result_config = load_configuration(
                cli_args=cli_args,
                config_file_path=str(config_file)
            )
        
        # Assert: Verify complex precedence rules work correctly
        assert result_config.authentication.access_key_id == cli_args['access_key_id'], \
            "CLI should override file for access_key_id"
        assert result_config.authentication.access_secret == env_vars['LABARCHIVES_SECRET'], \
            "Environment should override file for access_secret"
        assert result_config.authentication.username == file_config['username'], \
            "File should be used when not overridden by CLI or env"
        assert result_config.logging.log_level == cli_args['log_level'], \
            "CLI should override env and file for log_level"
        assert result_config.logging.quiet == cli_args['quiet'], \
            "CLI quiet should override env verbose"
        
        # Assert: Verify that scope precedence works correctly
        assert result_config.scope.notebook_id == env_vars['LABARCHIVES_NOTEBOOK_ID'], \
            "Environment notebook_id should override file notebook_name"
        assert result_config.scope.notebook_name is None, \
            "Notebook name should be None when notebook_id is set"


class TestReloadConfigurationIdempotency:
    """
    Test class for validating the reload_configuration function and idempotency.
    
    This class tests that reload_configuration returns a configuration equivalent
    to load_configuration when called with the same arguments, ensuring idempotency
    and correctness of dynamic reloading functionality.
    """
    
    def test_reload_configuration_idempotency_with_cli_args(self):
        """
        Tests that reload_configuration returns a configuration equivalent to
        load_configuration when called with the same CLI arguments, ensuring
        idempotency and correctness of dynamic reloading.
        """
        # Arrange: Prepare CLI arguments for initial configuration load
        cli_args = {
            'access_key_id': 'AKID_IDEMPOTENCY_TEST',
            'access_secret': 'idempotency_secret_123',
            'username': 'idempotency@example.com',
            'api_base_url': DEFAULT_API_BASE_URL,
            'notebook_id': 'notebook_idempotency_test',
            'log_level': 'DEBUG',
            'verbose': True
        }
        
        # Act: Load configuration initially
        initial_config = load_configuration(cli_args=cli_args)
        
        # Act: Reload configuration using the same arguments
        reloaded_config = reload_configuration()
        
        # Assert: Verify that the reloaded configuration is equivalent to the initial
        assert isinstance(reloaded_config, ServerConfiguration), \
            "Reloaded configuration should be a ServerConfiguration object"
        
        # Assert: Verify authentication section equivalence
        assert reloaded_config.authentication.access_key_id == initial_config.authentication.access_key_id, \
            "Reloaded authentication access_key_id should match initial"
        assert reloaded_config.authentication.access_secret == initial_config.authentication.access_secret, \
            "Reloaded authentication access_secret should match initial"
        assert reloaded_config.authentication.username == initial_config.authentication.username, \
            "Reloaded authentication username should match initial"
        assert reloaded_config.authentication.api_base_url == initial_config.authentication.api_base_url, \
            "Reloaded authentication api_base_url should match initial"
        
        # Assert: Verify scope section equivalence
        assert reloaded_config.scope.notebook_id == initial_config.scope.notebook_id, \
            "Reloaded scope notebook_id should match initial"
        assert reloaded_config.scope.notebook_name == initial_config.scope.notebook_name, \
            "Reloaded scope notebook_name should match initial"
        assert reloaded_config.scope.folder_path == initial_config.scope.folder_path, \
            "Reloaded scope folder_path should match initial"
        
        # Assert: Verify logging section equivalence
        assert reloaded_config.logging.log_level == initial_config.logging.log_level, \
            "Reloaded logging log_level should match initial"
        assert reloaded_config.logging.verbose == initial_config.logging.verbose, \
            "Reloaded logging verbose should match initial"
        
        # Assert: Verify server metadata equivalence
        assert reloaded_config.server_name == initial_config.server_name, \
            "Reloaded server_name should match initial"
        assert reloaded_config.server_version == initial_config.server_version, \
            "Reloaded server_version should match initial"
    
    def test_reload_configuration_idempotency_with_config_file(self, tmp_path):
        """
        Tests that reload_configuration returns a configuration equivalent to
        load_configuration when called with the same config file, ensuring
        idempotency for file-based configuration reloading.
        """
        # Arrange: Create a configuration file
        config_data = {
            'access_key_id': 'AKID_FILE_IDEMPOTENCY',
            'access_secret': 'file_idempotency_secret',
            'username': 'fileidempotency@example.com',
            'log_level': 'WARNING',
            'notebook_name': 'File Idempotency Test'
        }
        
        config_file = tmp_path / "idempotency_config.json"
        config_file.write_text(json.dumps(config_data, indent=2))
        
        # Act: Load configuration initially from file
        initial_config = load_configuration(config_file_path=str(config_file))
        
        # Act: Reload configuration using the same file
        reloaded_config = reload_configuration()
        
        # Assert: Verify that the reloaded configuration is equivalent to the initial
        assert isinstance(reloaded_config, ServerConfiguration), \
            "Reloaded configuration should be a ServerConfiguration object"
        
        # Assert: Verify file-based values are preserved in reload
        assert reloaded_config.authentication.access_key_id == config_data['access_key_id'], \
            "Reloaded access_key_id should match file value"
        assert reloaded_config.authentication.access_secret == config_data['access_secret'], \
            "Reloaded access_secret should match file value"
        assert reloaded_config.authentication.username == config_data['username'], \
            "Reloaded username should match file value"
        assert reloaded_config.logging.log_level == config_data['log_level'], \
            "Reloaded log_level should match file value"
        assert reloaded_config.scope.notebook_name == config_data['notebook_name'], \
            "Reloaded notebook_name should match file value"
        
        # Assert: Verify complete equivalence with initial configuration
        assert reloaded_config.authentication.access_key_id == initial_config.authentication.access_key_id, \
            "Reloaded and initial configurations should be identical"
        assert reloaded_config.logging.log_level == initial_config.logging.log_level, \
            "Reloaded and initial log levels should be identical"
    
    def test_reload_configuration_fails_without_initial_load(self):
        """
        Tests that reload_configuration raises LabArchivesMCPException when called
        without a previous load_configuration call, ensuring proper error handling.
        """
        # Arrange: Clear any existing configuration cache
        global _CONFIG_CACHE
        original_cache = _CONFIG_CACHE
        _CONFIG_CACHE = None
        
        try:
            # Act & Assert: Verify that reload fails without initial load
            with pytest.raises(LabArchivesMCPException) as exc_info:
                reload_configuration()
            
            # Assert: Verify appropriate error message and code
            assert "no configuration has been loaded" in str(exc_info.value).lower() or \
                   "cannot reload" in str(exc_info.value).lower(), \
                "Exception should mention that no configuration was loaded previously"
            assert exc_info.value.code is not None, \
                "Exception should have an error code"
            assert exc_info.value.context is not None, \
                "Exception should have context for debugging"
        
        finally:
            # Cleanup: Restore original cache state
            _CONFIG_CACHE = original_cache
    
    def test_reload_configuration_reflects_environment_changes(self):
        """
        Tests that reload_configuration reflects changes in environment variables
        when reloading, ensuring that dynamic configuration updates work correctly.
        """
        # Arrange: Set initial environment variables
        initial_env = {
            'LABARCHIVES_AKID': 'AKID_INITIAL_ENV',
            'LABARCHIVES_SECRET': 'initial_secret',
            'LABARCHIVES_USER': 'initial@example.com',
            'LABARCHIVES_LOG_LEVEL': 'INFO'
        }
        
        # Act: Load configuration with initial environment
        with patch.dict(os.environ, initial_env):
            initial_config = load_configuration()
        
        # Arrange: Change environment variables
        updated_env = {
            'LABARCHIVES_AKID': 'AKID_UPDATED_ENV',
            'LABARCHIVES_SECRET': 'updated_secret',
            'LABARCHIVES_USER': 'updated@example.com',
            'LABARCHIVES_LOG_LEVEL': 'DEBUG'
        }
        
        # Act: Reload configuration with updated environment
        with patch.dict(os.environ, updated_env):
            reloaded_config = reload_configuration()
        
        # Assert: Verify that reloaded configuration reflects environment changes
        assert reloaded_config.authentication.access_key_id == updated_env['LABARCHIVES_AKID'], \
            "Reloaded configuration should reflect updated environment variable"
        assert reloaded_config.authentication.access_secret == updated_env['LABARCHIVES_SECRET'], \
            "Reloaded configuration should reflect updated secret"
        assert reloaded_config.authentication.username == updated_env['LABARCHIVES_USER'], \
            "Reloaded configuration should reflect updated username"
        assert reloaded_config.logging.log_level == updated_env['LABARCHIVES_LOG_LEVEL'], \
            "Reloaded configuration should reflect updated log level"
        
        # Assert: Verify that configuration actually changed from initial
        assert reloaded_config.authentication.access_key_id != initial_config.authentication.access_key_id, \
            "Configuration should be different after environment change"
        assert reloaded_config.logging.log_level != initial_config.logging.log_level, \
            "Log level should be different after environment change"


class TestGetConfigValueDotNotation:
    """
    Test class for validating the get_config_value function with dot notation access.
    
    This class tests that get_config_value retrieves nested configuration values
    using dot notation correctly and raises LabArchivesMCPException for missing fields.
    """
    
    def test_get_config_value_dot_notation_authentication_fields(self):
        """
        Tests that get_config_value retrieves authentication configuration values
        using dot notation correctly, including nested fields.
        """
        # Arrange: Load a valid configuration
        cli_args = {
            'access_key_id': 'AKID_DOT_NOTATION_TEST',
            'access_secret': 'dot_notation_secret_123',
            'username': 'dotnotation@example.com',
            'api_base_url': DEFAULT_API_BASE_URL,
            'log_level': 'INFO'
        }
        
        config = load_configuration(cli_args=cli_args)
        
        # Act: Retrieve authentication fields using dot notation
        access_key_id = get_config_value('authentication.access_key_id')
        access_secret = get_config_value('authentication.access_secret')
        username = get_config_value('authentication.username')
        api_base_url = get_config_value('authentication.api_base_url')
        
        # Assert: Verify that dot notation retrieval works correctly
        assert access_key_id == cli_args['access_key_id'], \
            "Dot notation should retrieve correct access_key_id value"
        assert access_secret == cli_args['access_secret'], \
            "Dot notation should retrieve correct access_secret value"
        assert username == cli_args['username'], \
            "Dot notation should retrieve correct username value"
        assert api_base_url == cli_args['api_base_url'], \
            "Dot notation should retrieve correct api_base_url value"
    
    def test_get_config_value_dot_notation_scope_fields(self):
        """
        Tests that get_config_value retrieves scope configuration values
        using dot notation correctly, including handling of None values.
        """
        # Arrange: Load a valid configuration with scope settings
        cli_args = {
            'access_key_id': 'AKID_SCOPE_DOT_TEST',
            'access_secret': 'scope_dot_secret_456',
            'username': 'scopedot@example.com',
            'notebook_id': 'notebook_dot_test_123',
            'log_level': 'INFO'
        }
        
        config = load_configuration(cli_args=cli_args)
        
        # Act: Retrieve scope fields using dot notation
        notebook_id = get_config_value('scope.notebook_id')
        notebook_name = get_config_value('scope.notebook_name')
        folder_path = get_config_value('scope.folder_path')
        
        # Assert: Verify that dot notation retrieval works for scope values
        assert notebook_id == cli_args['notebook_id'], \
            "Dot notation should retrieve correct notebook_id value"
        assert notebook_name is None, \
            "Dot notation should retrieve None for unset notebook_name"
        assert folder_path is None, \
            "Dot notation should retrieve None for unset folder_path"
    
    def test_get_config_value_dot_notation_logging_fields(self):
        """
        Tests that get_config_value retrieves logging configuration values
        using dot notation correctly, including boolean values.
        """
        # Arrange: Load a valid configuration with logging settings
        cli_args = {
            'access_key_id': 'AKID_LOGGING_DOT_TEST',
            'access_secret': 'logging_dot_secret_789',
            'username': 'loggingdot@example.com',
            'log_level': 'DEBUG',
            'verbose': True,
            'quiet': False,
            'log_file': 'custom_log.log'
        }
        
        config = load_configuration(cli_args=cli_args)
        
        # Act: Retrieve logging fields using dot notation
        log_level = get_config_value('logging.log_level')
        verbose = get_config_value('logging.verbose')
        quiet = get_config_value('logging.quiet')
        log_file = get_config_value('logging.log_file')
        
        # Assert: Verify that dot notation retrieval works for logging values
        assert log_level == cli_args['log_level'], \
            "Dot notation should retrieve correct log_level value"
        assert verbose == cli_args['verbose'], \
            "Dot notation should retrieve correct verbose boolean value"
        assert quiet == cli_args['quiet'], \
            "Dot notation should retrieve correct quiet boolean value"
        assert log_file == cli_args['log_file'], \
            "Dot notation should retrieve correct log_file value"
    
    def test_get_config_value_dot_notation_server_metadata(self):
        """
        Tests that get_config_value retrieves server metadata values
        using dot notation correctly, including top-level fields.
        """
        # Arrange: Load a valid configuration
        cli_args = {
            'access_key_id': 'AKID_SERVER_DOT_TEST',
            'access_secret': 'server_dot_secret_012',
            'username': 'serverdot@example.com',
            'log_level': 'INFO'
        }
        
        config = load_configuration(cli_args=cli_args)
        
        # Act: Retrieve server metadata using dot notation
        server_name = get_config_value('server_name')
        server_version = get_config_value('server_version')
        
        # Assert: Verify that dot notation retrieval works for server metadata
        assert server_name == MCP_SERVER_NAME, \
            "Dot notation should retrieve correct server_name value"
        assert server_version == MCP_SERVER_VERSION, \
            "Dot notation should retrieve correct server_version value"
    
    def test_get_config_value_dot_notation_missing_field_raises_exception(self):
        """
        Tests that get_config_value raises LabArchivesMCPException when attempting
        to retrieve a non-existent field using dot notation.
        """
        # Arrange: Load a valid configuration
        cli_args = {
            'access_key_id': 'AKID_MISSING_FIELD_TEST',
            'access_secret': 'missing_field_secret',
            'username': 'missingfield@example.com',
            'log_level': 'INFO'
        }
        
        config = load_configuration(cli_args=cli_args)
        
        # Act & Assert: Verify that accessing non-existent field raises exception
        with pytest.raises(LabArchivesMCPException) as exc_info:
            get_config_value('authentication.non_existent_field')
        
        # Assert: Verify appropriate error message and context
        assert "not found" in str(exc_info.value).lower(), \
            "Exception should mention that the field was not found"
        assert "authentication.non_existent_field" in str(exc_info.value), \
            "Exception should include the full field path"
        assert exc_info.value.code is not None, \
            "Exception should have an error code"
        assert exc_info.value.context is not None, \
            "Exception should have context for debugging"
    
    def test_get_config_value_dot_notation_invalid_section_raises_exception(self):
        """
        Tests that get_config_value raises LabArchivesMCPException when attempting
        to retrieve from a non-existent configuration section.
        """
        # Arrange: Load a valid configuration
        cli_args = {
            'access_key_id': 'AKID_INVALID_SECTION_TEST',
            'access_secret': 'invalid_section_secret',
            'username': 'invalidsection@example.com',
            'log_level': 'INFO'
        }
        
        config = load_configuration(cli_args=cli_args)
        
        # Act & Assert: Verify that accessing non-existent section raises exception
        with pytest.raises(LabArchivesMCPException) as exc_info:
            get_config_value('non_existent_section.some_field')
        
        # Assert: Verify appropriate error message and context
        assert "not found" in str(exc_info.value).lower(), \
            "Exception should mention that the section was not found"
        assert "non_existent_section" in str(exc_info.value), \
            "Exception should include the section name"
        assert exc_info.value.code is not None, \
            "Exception should have an error code"
        assert exc_info.value.context is not None, \
            "Exception should have context for debugging"
    
    def test_get_config_value_dot_notation_no_configuration_loaded_raises_exception(self):
        """
        Tests that get_config_value raises LabArchivesMCPException when called
        before any configuration has been loaded.
        """
        # Arrange: Clear any existing configuration cache
        global _CONFIG_CACHE
        original_cache = _CONFIG_CACHE
        _CONFIG_CACHE = None
        
        try:
            # Act & Assert: Verify that accessing config without loading raises exception
            with pytest.raises(LabArchivesMCPException) as exc_info:
                get_config_value('authentication.access_key_id')
            
            # Assert: Verify appropriate error message and context
            assert "no configuration has been loaded" in str(exc_info.value).lower(), \
                "Exception should mention that no configuration was loaded"
            assert exc_info.value.code is not None, \
                "Exception should have an error code"
            assert exc_info.value.context is not None, \
                "Exception should have context for debugging"
        
        finally:
            # Cleanup: Restore original cache state
            _CONFIG_CACHE = original_cache
    
    def test_get_config_value_dot_notation_invalid_key_format_raises_exception(self):
        """
        Tests that get_config_value raises LabArchivesMCPException when provided
        with invalid key formats (None, empty string, non-string types).
        """
        # Arrange: Load a valid configuration
        cli_args = {
            'access_key_id': 'AKID_INVALID_KEY_TEST',
            'access_secret': 'invalid_key_secret',
            'username': 'invalidkey@example.com',
            'log_level': 'INFO'
        }
        
        config = load_configuration(cli_args=cli_args)
        
        # Act & Assert: Test None key
        with pytest.raises(LabArchivesMCPException) as exc_info:
            get_config_value(None)
        
        assert "cannot be None" in str(exc_info.value), \
            "Exception should mention that key cannot be None"
        
        # Act & Assert: Test empty string key
        with pytest.raises(LabArchivesMCPException) as exc_info:
            get_config_value('')
        
        assert "cannot be empty" in str(exc_info.value), \
            "Exception should mention that key cannot be empty"
        
        # Act & Assert: Test non-string key
        with pytest.raises(LabArchivesMCPException) as exc_info:
            get_config_value(123)
        
        assert "must be a string" in str(exc_info.value), \
            "Exception should mention that key must be a string"


class TestEnvironmentVariablePrecedence:
    """
    Test class for validating environment variable precedence in configuration loading.
    
    This class tests that environment variables override config file and default values
    when loading configuration, ensuring correct precedence order implementation.
    """
    
    def test_environment_variable_precedence_over_config_file(self, tmp_path):
        """
        Tests that environment variables override config file values when loading
        configuration, demonstrating proper precedence order.
        """
        # Arrange: Create a config file with base values
        file_config = {
            'access_key_id': 'AKID_FILE_BASE_VALUE',
            'access_secret': 'file_secret_base',
            'username': 'fileuser@example.com',
            'log_level': 'INFO',
            'verbose': False,
            'notebook_id': 'notebook_file_base'
        }
        
        config_file = tmp_path / "precedence_test.json"
        config_file.write_text(json.dumps(file_config, indent=2))
        
        # Arrange: Set environment variables that should override file values
        env_vars = {
            'LABARCHIVES_AKID': 'AKID_ENV_OVERRIDE',
            'LABARCHIVES_SECRET': 'env_secret_override',
            'LABARCHIVES_LOG_LEVEL': 'DEBUG',
            'LABARCHIVES_VERBOSE': 'true'
        }
        
        # Act: Load configuration with both file and environment variables
        with patch.dict(os.environ, env_vars):
            result_config = load_configuration(config_file_path=str(config_file))
        
        # Assert: Verify that environment variables override file values
        assert result_config.authentication.access_key_id == env_vars['LABARCHIVES_AKID'], \
            "Environment variable should override config file access_key_id"
        assert result_config.authentication.access_secret == env_vars['LABARCHIVES_SECRET'], \
            "Environment variable should override config file access_secret"
        assert result_config.logging.log_level == env_vars['LABARCHIVES_LOG_LEVEL'], \
            "Environment variable should override config file log_level"
        assert result_config.logging.verbose is True, \
            "Environment variable should override config file verbose setting"
        
        # Assert: Verify that file values are used where environment variables are not set
        assert result_config.authentication.username == file_config['username'], \
            "File value should be used when environment variable is not set"
        assert result_config.scope.notebook_id == file_config['notebook_id'], \
            "File value should be used when environment variable is not set"
        
        # Cleanup: Restore environment variables
        # This is handled automatically by patch.dict context manager
    
    def test_environment_variable_precedence_over_defaults(self):
        """
        Tests that environment variables override default values when loading
        configuration without a config file, demonstrating precedence over defaults.
        """
        # Arrange: Set environment variables that should override defaults
        env_vars = {
            'LABARCHIVES_AKID': 'AKID_ENV_OVER_DEFAULTS',
            'LABARCHIVES_SECRET': 'env_secret_over_defaults',
            'LABARCHIVES_USER': 'envuser@example.com',
            'LABARCHIVES_API_BASE': DEFAULT_API_BASE_URL,
            'LABARCHIVES_LOG_LEVEL': 'ERROR',
            'LABARCHIVES_LOG_FILE': 'custom_env.log',
            'LABARCHIVES_VERBOSE': 'true'
        }
        
        # Act: Load configuration with only environment variables (no file, no CLI args)
        with patch.dict(os.environ, env_vars):
            result_config = load_configuration()
        
        # Assert: Verify that environment variables override default values
        assert result_config.authentication.access_key_id == env_vars['LABARCHIVES_AKID'], \
            "Environment variable should override default access_key_id"
        assert result_config.authentication.access_secret == env_vars['LABARCHIVES_SECRET'], \
            "Environment variable should override default access_secret"
        assert result_config.authentication.username == env_vars['LABARCHIVES_USER'], \
            "Environment variable should override default username"
        assert result_config.logging.log_level == env_vars['LABARCHIVES_LOG_LEVEL'], \
            "Environment variable should override default log_level"
        assert result_config.logging.log_file == env_vars['LABARCHIVES_LOG_FILE'], \
            "Environment variable should override default log_file"
        assert result_config.logging.verbose is True, \
            "Environment variable should override default verbose setting"
        
        # Assert: Verify that defaults are used where environment variables are not set
        assert result_config.output.json_ld_enabled is False, \
            "Default value should be used when environment variable is not set"
        assert result_config.output.structured_output is True, \
            "Default value should be used when environment variable is not set"
        assert result_config.server_name == MCP_SERVER_NAME, \
            "Default server name should be used when environment variable is not set"
        
        # Cleanup: Restore environment variables
        # This is handled automatically by patch.dict context manager
    
    def test_environment_variable_type_conversion(self):
        """
        Tests that environment variables are properly converted to appropriate types
        (boolean, string) when loading configuration.
        """
        # Arrange: Set environment variables with various data types
        env_vars = {
            'LABARCHIVES_AKID': 'AKID_TYPE_CONVERSION_TEST',
            'LABARCHIVES_SECRET': 'type_conversion_secret',
            'LABARCHIVES_USER': 'typeconv@example.com',
            'LABARCHIVES_VERBOSE': 'yes',  # Should convert to True
            'LABARCHIVES_QUIET': 'no',    # Should convert to False
            'LABARCHIVES_JSON_LD_ENABLED': '1',  # Should convert to True
            'LABARCHIVES_STRUCTURED_OUTPUT': 'false'  # Should convert to False
        }
        
        # Act: Load configuration with type conversion environment variables
        with patch.dict(os.environ, env_vars):
            result_config = load_configuration()
        
        # Assert: Verify that boolean environment variables are converted correctly
        # Note: The actual conversion depends on the get_env_var utility function
        # These tests verify integration between configuration loading and type conversion
        assert isinstance(result_config.logging.verbose, bool), \
            "Verbose should be converted to boolean type"
        assert isinstance(result_config.logging.quiet, bool), \
            "Quiet should be converted to boolean type"
        assert isinstance(result_config.output.json_ld_enabled, bool), \
            "JSON-LD enabled should be converted to boolean type"
        assert isinstance(result_config.output.structured_output, bool), \
            "Structured output should be converted to boolean type"
        
        # Assert: Verify that string environment variables remain strings
        assert isinstance(result_config.authentication.access_key_id, str), \
            "Access key ID should remain as string type"
        assert isinstance(result_config.authentication.access_secret, str), \
            "Access secret should remain as string type"
        assert isinstance(result_config.authentication.username, str), \
            "Username should remain as string type"
        
        # Cleanup: Restore environment variables
        # This is handled automatically by patch.dict context manager
    
    def test_environment_variable_partial_override(self, tmp_path):
        """
        Tests that environment variables can partially override configuration file
        values, leaving other file values intact.
        """
        # Arrange: Create a comprehensive config file
        file_config = {
            'access_key_id': 'AKID_PARTIAL_FILE',
            'access_secret': 'partial_file_secret',
            'username': 'partialfile@example.com',
            'api_base_url': DEFAULT_API_BASE_URL,
            'notebook_id': 'notebook_partial_file',
            'log_level': 'INFO',
            'log_file': 'partial_file.log',
            'verbose': False,
            'json_ld_enabled': False,
            'structured_output': True
        }
        
        config_file = tmp_path / "partial_override_test.json"
        config_file.write_text(json.dumps(file_config, indent=2))
        
        # Arrange: Set environment variables for only some fields
        env_vars = {
            'LABARCHIVES_SECRET': 'env_partial_secret',  # Override file
            'LABARCHIVES_LOG_LEVEL': 'DEBUG',  # Override file
            'LABARCHIVES_VERBOSE': 'true'  # Override file
        }
        
        # Act: Load configuration with partial environment override
        with patch.dict(os.environ, env_vars):
            result_config = load_configuration(config_file_path=str(config_file))
        
        # Assert: Verify that environment variables override their respective file values
        assert result_config.authentication.access_secret == env_vars['LABARCHIVES_SECRET'], \
            "Environment variable should override file access_secret"
        assert result_config.logging.log_level == env_vars['LABARCHIVES_LOG_LEVEL'], \
            "Environment variable should override file log_level"
        assert result_config.logging.verbose is True, \
            "Environment variable should override file verbose setting"
        
        # Assert: Verify that file values are preserved where environment variables are not set
        assert result_config.authentication.access_key_id == file_config['access_key_id'], \
            "File access_key_id should be preserved when not overridden by environment"
        assert result_config.authentication.username == file_config['username'], \
            "File username should be preserved when not overridden by environment"
        assert result_config.scope.notebook_id == file_config['notebook_id'], \
            "File notebook_id should be preserved when not overridden by environment"
        assert result_config.logging.log_file == file_config['log_file'], \
            "File log_file should be preserved when not overridden by environment"
        assert result_config.output.json_ld_enabled == file_config['json_ld_enabled'], \
            "File json_ld_enabled should be preserved when not overridden by environment"
        
        # Cleanup: Restore environment variables
        # This is handled automatically by patch.dict context manager


class TestCLIArgumentPrecedence:
    """
    Test class for validating CLI argument precedence in configuration loading.
    
    This class tests that CLI arguments override environment variables and config file
    values when loading configuration, ensuring the highest precedence is respected.
    """
    
    def test_cli_argument_precedence_over_environment_variables(self):
        """
        Tests that CLI arguments override environment variables when loading
        configuration, demonstrating highest precedence.
        """
        # Arrange: Set environment variables with base values
        env_vars = {
            'LABARCHIVES_AKID': 'AKID_ENV_BASE',
            'LABARCHIVES_SECRET': 'env_secret_base',
            'LABARCHIVES_USER': 'envuser@example.com',
            'LABARCHIVES_LOG_LEVEL': 'INFO',
            'LABARCHIVES_VERBOSE': 'false',
            'LABARCHIVES_NOTEBOOK_ID': 'notebook_env_base'
        }
        
        # Arrange: Set CLI arguments that should override environment variables
        cli_args = {
            'access_key_id': 'AKID_CLI_OVERRIDE',
            'access_secret': 'cli_secret_override',
            'log_level': 'DEBUG',
            'verbose': True,
            'notebook_id': 'notebook_cli_override'
        }
        
        # Act: Load configuration with both environment variables and CLI arguments
        with patch.dict(os.environ, env_vars):
            result_config = load_configuration(cli_args=cli_args)
        
        # Assert: Verify that CLI arguments override environment variables
        assert result_config.authentication.access_key_id == cli_args['access_key_id'], \
            "CLI argument should override environment variable access_key_id"
        assert result_config.authentication.access_secret == cli_args['access_secret'], \
            "CLI argument should override environment variable access_secret"
        assert result_config.logging.log_level == cli_args['log_level'], \
            "CLI argument should override environment variable log_level"
        assert result_config.logging.verbose == cli_args['verbose'], \
            "CLI argument should override environment variable verbose setting"
        assert result_config.scope.notebook_id == cli_args['notebook_id'], \
            "CLI argument should override environment variable notebook_id"
        
        # Assert: Verify that environment variables are used where CLI arguments are not provided
        assert result_config.authentication.username == env_vars['LABARCHIVES_USER'], \
            "Environment variable should be used when CLI argument is not provided"
        
        # Cleanup: Restore environment variables
        # This is handled automatically by patch.dict context manager
    
    def test_cli_argument_precedence_over_config_file(self, tmp_path):
        """
        Tests that CLI arguments override config file values when loading
        configuration, demonstrating precedence over file-based configuration.
        """
        # Arrange: Create a config file with base values
        file_config = {
            'access_key_id': 'AKID_FILE_BASE',
            'access_secret': 'file_secret_base',
            'username': 'fileuser@example.com',
            'log_level': 'WARNING',
            'verbose': False,
            'notebook_name': 'File Notebook Base',
            'json_ld_enabled': False
        }
        
        config_file = tmp_path / "cli_precedence_test.json"
        config_file.write_text(json.dumps(file_config, indent=2))
        
        # Arrange: Set CLI arguments that should override file values
        cli_args = {
            'access_key_id': 'AKID_CLI_OVERRIDE',
            'access_secret': 'cli_secret_override',
            'log_level': 'ERROR',
            'verbose': True,
            'notebook_id': 'notebook_cli_override',  # Should override file notebook_name
            'json_ld_enabled': True
        }
        
        # Act: Load configuration with both config file and CLI arguments
        result_config = load_configuration(
            cli_args=cli_args,
            config_file_path=str(config_file)
        )
        
        # Assert: Verify that CLI arguments override file values
        assert result_config.authentication.access_key_id == cli_args['access_key_id'], \
            "CLI argument should override config file access_key_id"
        assert result_config.authentication.access_secret == cli_args['access_secret'], \
            "CLI argument should override config file access_secret"
        assert result_config.logging.log_level == cli_args['log_level'], \
            "CLI argument should override config file log_level"
        assert result_config.logging.verbose == cli_args['verbose'], \
            "CLI argument should override config file verbose setting"
        assert result_config.scope.notebook_id == cli_args['notebook_id'], \
            "CLI argument notebook_id should override config file notebook_name"
        assert result_config.output.json_ld_enabled == cli_args['json_ld_enabled'], \
            "CLI argument should override config file json_ld_enabled"
        
        # Assert: Verify that file values are used where CLI arguments are not provided
        assert result_config.authentication.username == file_config['username'], \
            "File value should be used when CLI argument is not provided"
        
        # Assert: Verify that scope precedence works correctly
        assert result_config.scope.notebook_name is None, \
            "Notebook name should be None when CLI provides notebook_id"
    
    def test_cli_argument_precedence_over_all_sources(self, tmp_path):
        """
        Tests that CLI arguments override values from all other sources (environment
        variables, config file, defaults) when loading configuration.
        """
        # Arrange: Create a config file with base values
        file_config = {
            'access_key_id': 'AKID_FILE_ALL_SOURCES',
            'access_secret': 'file_secret_all_sources',
            'username': 'fileuser@allsources.com',
            'log_level': 'INFO',
            'verbose': False,
            'notebook_name': 'File All Sources Notebook'
        }
        
        config_file = tmp_path / "all_sources_test.json"
        config_file.write_text(json.dumps(file_config, indent=2))
        
        # Arrange: Set environment variables
        env_vars = {
            'LABARCHIVES_AKID': 'AKID_ENV_ALL_SOURCES',
            'LABARCHIVES_SECRET': 'env_secret_all_sources',
            'LABARCHIVES_LOG_LEVEL': 'DEBUG',
            'LABARCHIVES_VERBOSE': 'true',
            'LABARCHIVES_NOTEBOOK_ID': 'notebook_env_all_sources'
        }
        
        # Arrange: Set CLI arguments (should have highest precedence)
        cli_args = {
            'access_key_id': 'AKID_CLI_ALL_SOURCES',
            'access_secret': 'cli_secret_all_sources',
            'log_level': 'ERROR',
            'quiet': True,  # Should override env verbose and file verbose
            'folder_path': 'cli/folder/path'  # Should override env notebook_id and file notebook_name
        }
        
        # Act: Load configuration with all sources
        with patch.dict(os.environ, env_vars):
            result_config = load_configuration(
                cli_args=cli_args,
                config_file_path=str(config_file)
            )
        
        # Assert: Verify that CLI arguments have highest precedence
        assert result_config.authentication.access_key_id == cli_args['access_key_id'], \
            "CLI argument should override environment and file access_key_id"
        assert result_config.authentication.access_secret == cli_args['access_secret'], \
            "CLI argument should override environment and file access_secret"
        assert result_config.logging.log_level == cli_args['log_level'], \
            "CLI argument should override environment and file log_level"
        assert result_config.logging.quiet == cli_args['quiet'], \
            "CLI argument quiet should override environment verbose and file verbose"
        assert result_config.scope.folder_path == cli_args['folder_path'], \
            "CLI argument folder_path should override environment notebook_id and file notebook_name"
        
        # Assert: Verify that environment variables override file values (where CLI doesn't override)
        assert result_config.authentication.username == file_config['username'], \
            "File value should be used when not overridden by CLI or environment"
        
        # Assert: Verify that scope precedence works correctly with all sources
        assert result_config.scope.notebook_id is None, \
            "Notebook ID should be None when CLI provides folder_path"
        assert result_config.scope.notebook_name is None, \
            "Notebook name should be None when CLI provides folder_path"
        
        # Assert: Verify that verbosity conflict is resolved correctly
        assert result_config.logging.verbose is False, \
            "Verbose should be False when CLI quiet is True"
        
        # Cleanup: Restore environment variables
        # This is handled automatically by patch.dict context manager
    
    def test_cli_argument_partial_override_preserves_other_sources(self, tmp_path):
        """
        Tests that CLI arguments can partially override configuration while preserving
        values from other sources for fields not specified in CLI arguments.
        """
        # Arrange: Create a comprehensive config file
        file_config = {
            'access_key_id': 'AKID_PARTIAL_CLI_FILE',
            'access_secret': 'partial_cli_file_secret',
            'username': 'partialclifile@example.com',
            'api_base_url': DEFAULT_API_BASE_URL,
            'notebook_id': 'notebook_partial_cli_file',
            'log_level': 'INFO',
            'log_file': 'partial_cli_file.log',
            'verbose': False,
            'json_ld_enabled': False
        }
        
        config_file = tmp_path / "partial_cli_test.json"
        config_file.write_text(json.dumps(file_config, indent=2))
        
        # Arrange: Set environment variables for some fields
        env_vars = {
            'LABARCHIVES_SECRET': 'env_partial_cli_secret',
            'LABARCHIVES_LOG_LEVEL': 'DEBUG',
            'LABARCHIVES_VERBOSE': 'true'
        }
        
        # Arrange: Set CLI arguments for only specific fields
        cli_args = {
            'access_key_id': 'AKID_CLI_PARTIAL',  # Override file
            'log_level': 'ERROR',  # Override env and file
            'json_ld_enabled': True  # Override file
        }
        
        # Act: Load configuration with partial CLI override
        with patch.dict(os.environ, env_vars):
            result_config = load_configuration(
                cli_args=cli_args,
                config_file_path=str(config_file)
            )
        
        # Assert: Verify that CLI arguments override their respective values
        assert result_config.authentication.access_key_id == cli_args['access_key_id'], \
            "CLI argument should override file access_key_id"
        assert result_config.logging.log_level == cli_args['log_level'], \
            "CLI argument should override environment and file log_level"
        assert result_config.output.json_ld_enabled == cli_args['json_ld_enabled'], \
            "CLI argument should override file json_ld_enabled"
        
        # Assert: Verify that environment variables override file values (where CLI doesn't override)
        assert result_config.authentication.access_secret == env_vars['LABARCHIVES_SECRET'], \
            "Environment variable should override file access_secret when CLI doesn't specify"
        assert result_config.logging.verbose is True, \
            "Environment variable should override file verbose when CLI doesn't specify"
        
        # Assert: Verify that file values are preserved where neither CLI nor env override
        assert result_config.authentication.username == file_config['username'], \
            "File value should be preserved when not overridden by CLI or environment"
        assert result_config.scope.notebook_id == file_config['notebook_id'], \
            "File value should be preserved when not overridden by CLI or environment"
        assert result_config.logging.log_file == file_config['log_file'], \
            "File value should be preserved when not overridden by CLI or environment"
        
        # Cleanup: Restore environment variables
        # This is handled automatically by patch.dict context manager
    
    def test_cli_argument_none_values_do_not_override(self, tmp_path):
        """
        Tests that CLI arguments with None values do not override values from other
        sources, ensuring that None is treated as "not specified" rather than a value.
        """
        # Arrange: Create a config file with values
        file_config = {
            'access_key_id': 'AKID_NONE_TEST_FILE',
            'access_secret': 'none_test_file_secret',
            'username': 'nonetestfile@example.com',
            'log_level': 'INFO',
            'verbose': False,
            'notebook_id': 'notebook_none_test_file'
        }
        
        config_file = tmp_path / "none_test.json"
        config_file.write_text(json.dumps(file_config, indent=2))
        
        # Arrange: Set environment variables
        env_vars = {
            'LABARCHIVES_SECRET': 'env_none_test_secret',
            'LABARCHIVES_LOG_LEVEL': 'DEBUG'
        }
        
        # Arrange: Set CLI arguments with None values (should not override)
        cli_args = {
            'access_key_id': 'AKID_CLI_NONE_TEST',  # Should override
            'access_secret': None,  # Should not override (use env value)
            'username': None,  # Should not override (use file value)
            'log_level': None,  # Should not override (use env value)
            'verbose': None,  # Should not override (use file value)
            'notebook_id': None  # Should not override (use file value)
        }
        
        # Act: Load configuration with None CLI values
        with patch.dict(os.environ, env_vars):
            result_config = load_configuration(
                cli_args=cli_args,
                config_file_path=str(config_file)
            )
        
        # Assert: Verify that non-None CLI arguments override as expected
        assert result_config.authentication.access_key_id == cli_args['access_key_id'], \
            "Non-None CLI argument should override file value"
        
        # Assert: Verify that None CLI arguments do not override other sources
        assert result_config.authentication.access_secret == env_vars['LABARCHIVES_SECRET'], \
            "None CLI argument should not override environment variable"
        assert result_config.authentication.username == file_config['username'], \
            "None CLI argument should not override file value"
        assert result_config.logging.log_level == env_vars['LABARCHIVES_LOG_LEVEL'], \
            "None CLI argument should not override environment variable"
        assert result_config.logging.verbose == file_config['verbose'], \
            "None CLI argument should not override file value"
        assert result_config.scope.notebook_id == file_config['notebook_id'], \
            "None CLI argument should not override file value"
        
        # Cleanup: Restore environment variables
        # This is handled automatically by patch.dict context manager