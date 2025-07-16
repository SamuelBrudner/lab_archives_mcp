"""
LabArchives MCP Server - Configuration Test Fixtures and Sample Data

This module provides reusable sample configuration objects and data structures for 
testing configuration parsing, validation, and CLI/environment variable integration 
in the LabArchives MCP Server test suite. Used to mock and supply valid, invalid, 
and edge-case configurations for unit and integration tests.

This module supports comprehensive testing of:
- F-005: Authentication and Security Management - Sample authentication configurations
  with valid API keys, tokens, usernames, and various security scenarios
- F-006: CLI Interface and Configuration - Configuration parsing, validation, and 
  error handling for CLI arguments and environment variables
- F-007: Scope Limitation and Access Control - Sample scope configurations for 
  testing notebook, folder, and access control boundary enforcement
- F-008: Comprehensive Audit Logging - Sample logging configurations for testing
  audit trails, error logging, and compliance scenarios

All fixtures are designed to be used with pytest's fixture system and provide
consistent, reusable test data for parameterized testing scenarios.
"""

import pytest  # pytest>=7.0.0 - Python testing framework for fixture decorators and parameterized tests

# Internal imports from configuration module - Core configuration classes and validation
from src.cli.config import (
    ServerConfiguration,
    AuthenticationConfig,
    ScopeConfig,
    OutputConfig,
    LoggingConfig
)

# Internal imports from constants module - Default values and configuration constants
from src.cli.constants import (
    DEFAULT_API_BASE_URL,
    DEFAULT_LOG_FILE,
    DEFAULT_LOG_LEVEL,
    MCP_SERVER_NAME,
    MCP_SERVER_VERSION
)

# =============================================================================
# Global Configuration Sample Data
# =============================================================================

# Valid configuration sample with all required fields populated with typical values
# This represents a standard, working configuration that passes all validation rules
VALID_CONFIG_SAMPLE = {
    "access_key_id": "AKID1234567890ABCDEF",
    "access_secret": "secure_password_or_token_123",
    "username": "researcher@university.edu",
    "api_base_url": DEFAULT_API_BASE_URL,
    "notebook_id": "notebook_12345",
    "notebook_name": None,
    "folder_path": None,
    "json_ld_enabled": False,
    "structured_output": True,
    "log_file": DEFAULT_LOG_FILE,
    "log_level": DEFAULT_LOG_LEVEL,
    "verbose": False,
    "quiet": False,
    "server_name": MCP_SERVER_NAME,
    "server_version": MCP_SERVER_VERSION
}

# Invalid configuration sample with missing required fields and invalid types
# This represents various validation failures for testing error handling
INVALID_CONFIG_SAMPLE = {
    "access_key_id": "",  # Invalid: empty string
    "access_secret": None,  # Invalid: None value for required field
    "username": "not-an-email",  # Invalid: not a valid email format
    "api_base_url": "http://insecure.com",  # Invalid: not HTTPS
    "notebook_id": "notebook_12345",
    "notebook_name": "Conflicting Notebook Name",  # Invalid: conflicts with notebook_id
    "folder_path": None,
    "json_ld_enabled": "true",  # Invalid: string instead of boolean
    "structured_output": False,  # Invalid: JSON-LD requires structured output
    "log_file": "/root/inaccessible.log",  # Invalid: likely permission issues
    "log_level": "INVALID_LEVEL",  # Invalid: not a valid log level
    "verbose": True,
    "quiet": True,  # Invalid: conflicts with verbose
    "server_name": "",  # Invalid: empty string
    "server_version": "invalid-version"  # Invalid: not semantic versioning
}

# Edge case configuration sample with extreme values and special characters
# This represents boundary conditions and unusual inputs for robustness testing
EDGE_CASE_CONFIG_SAMPLE = {
    "access_key_id": "A" * 256,  # Edge case: maximum length
    "access_secret": "x" * 1024,  # Edge case: maximum length
    "username": "very.long.email.address.with.many.parts@very.long.domain.name.institution.edu",
    "api_base_url": DEFAULT_API_BASE_URL,
    "notebook_id": "notebook_with_special-chars_123",
    "notebook_name": None,
    "folder_path": None,
    "json_ld_enabled": True,
    "structured_output": True,
    "log_file": "logs/with spaces and unicode 测试.log",
    "log_level": "DEBUG",
    "verbose": False,
    "quiet": False,
    "server_name": "labarchives-mcp-server-with-very-long-name-for-testing",
    "server_version": "999.999.999-beta.1+build.123"
}

# =============================================================================
# Direct Access Functions (for import by other test modules)
# =============================================================================

def _create_valid_config_instance() -> ServerConfiguration:
    """
    Internal helper function to create a valid ServerConfiguration instance.
    
    This function contains the actual logic for creating a valid configuration
    and is used by both the direct function and the pytest fixture.
    
    Returns:
        ServerConfiguration: A valid configuration object.
    """
    # Instantiate AuthenticationConfig with valid credentials and API endpoint
    auth_config = AuthenticationConfig(
        access_key_id="AKID1234567890ABCDEF",
        access_secret="secure_password_or_token_123",
        username="researcher@university.edu",
        api_base_url=DEFAULT_API_BASE_URL
    )
    
    # Instantiate ScopeConfig with a valid notebook ID for scope limitation
    scope_config = ScopeConfig(
        notebook_id="notebook_12345",
        notebook_name=None,
        folder_path=None
    )
    
    # Instantiate OutputConfig with standard formatting options
    output_config = OutputConfig(
        json_ld_enabled=False,
        structured_output=True
    )
    
    # Instantiate LoggingConfig with default logging settings
    logging_config = LoggingConfig(
        log_file=DEFAULT_LOG_FILE,
        log_level=DEFAULT_LOG_LEVEL,
        verbose=False,
        quiet=False
    )
    
    # Combine all configurations into a complete ServerConfiguration
    return ServerConfiguration(
        authentication=auth_config,
        scope=scope_config,
        output=output_config,
        logging=logging_config,
        server_name=MCP_SERVER_NAME,
        server_version=MCP_SERVER_VERSION
    )


def create_valid_config() -> ServerConfiguration:
    """
    Returns a valid ServerConfiguration object for direct use in tests.
    
    This function creates a complete, valid configuration that passes all validation
    rules and can be used for testing normal operation scenarios. Unlike the pytest
    fixture variant, this function can be imported directly by other test modules.
    
    Returns:
        ServerConfiguration: A valid configuration object ready for use in test cases.
                            Contains valid authentication, scope, output, and logging
                            configurations with all required fields populated.
    
    Example:
        from src.cli.tests.fixtures.config_samples import create_valid_config
        
        def test_folder_path_validation():
            config = create_valid_config()
            assert config.authentication.access_key_id == "AKID1234567890ABCDEF"
            assert config.scope.notebook_id == "notebook_12345"
    """
    return _create_valid_config_instance()





# =============================================================================
# Pytest Fixture Functions
# =============================================================================

@pytest.fixture
def valid_config() -> ServerConfiguration:
    """
    Returns a valid ServerConfiguration object for use in tests, with all required 
    fields populated with typical values.
    
    This fixture creates a complete, valid configuration that passes all validation
    rules and can be used for testing normal operation scenarios. All configuration
    sections are properly instantiated with realistic values.
    
    Returns:
        ServerConfiguration: A valid configuration object ready for use in test cases.
                           Contains valid authentication, scope, output, and logging
                           configurations with all required fields populated.
    
    Example:
        def test_server_initialization(valid_config):
            config = valid_config
            assert config.authentication.access_key_id == "AKID1234567890ABCDEF"
            assert config.scope.notebook_id == "notebook_12345"
            assert config.output.structured_output is True
            assert config.logging.log_level == "INFO"
    """
    # Use the helper function to avoid code duplication
    return _create_valid_config_instance()


def get_invalid_config() -> ServerConfiguration:
    """
    Returns an invalid ServerConfiguration object for use in negative test cases, 
    such as missing required fields or invalid types.
    
    This fixture creates a configuration that violates validation rules and should
    fail validation checks. It's designed to test error handling, validation logic,
    and edge cases in configuration processing.
    
    Note: This fixture bypasses normal validation by directly instantiating objects
    with invalid values. In normal usage, these values would be caught by Pydantic
    validation, but for testing purposes we need to create invalid configurations.
    
    Returns:
        ServerConfiguration: An invalid configuration object expected to fail validation.
                           Contains invalid authentication, scope, output, and logging
                           configurations for testing error scenarios.
    
    Example:
        def test_validation_failure(get_invalid_config):
            config = get_invalid_config
            with pytest.raises(LabArchivesMCPException):
                validate_server_configuration(config)
    """
    # Instantiate AuthenticationConfig with invalid credentials
    # Using object.__setattr__ to bypass Pydantic validation for testing
    auth_config = AuthenticationConfig.__new__(AuthenticationConfig)
    object.__setattr__(auth_config, 'access_key_id', "")  # Invalid: empty string
    object.__setattr__(auth_config, 'access_secret', None)  # Invalid: None value
    object.__setattr__(auth_config, 'username', "not-an-email")  # Invalid: not email format
    object.__setattr__(auth_config, 'api_base_url', "http://insecure.com")  # Invalid: not HTTPS
    
    # Instantiate ScopeConfig with conflicting values
    scope_config = ScopeConfig.__new__(ScopeConfig)
    object.__setattr__(scope_config, 'notebook_id', "notebook_12345")
    object.__setattr__(scope_config, 'notebook_name', "Conflicting Notebook Name")  # Invalid: conflicts with notebook_id
    object.__setattr__(scope_config, 'folder_path', None)
    
    # Instantiate OutputConfig with invalid type and conflicting settings
    output_config = OutputConfig.__new__(OutputConfig)
    object.__setattr__(output_config, 'json_ld_enabled', True)
    object.__setattr__(output_config, 'structured_output', False)  # Invalid: JSON-LD requires structured output
    
    # Instantiate LoggingConfig with invalid values and conflicts
    logging_config = LoggingConfig.__new__(LoggingConfig)
    object.__setattr__(logging_config, 'log_file', "/root/inaccessible.log")  # Invalid: likely permission issues
    object.__setattr__(logging_config, 'log_level', "INVALID_LEVEL")  # Invalid: not a valid log level
    object.__setattr__(logging_config, 'verbose', True)
    object.__setattr__(logging_config, 'quiet', True)  # Invalid: conflicts with verbose
    
    # Combine all invalid configurations into a ServerConfiguration
    server_config = ServerConfiguration.__new__(ServerConfiguration)
    object.__setattr__(server_config, 'authentication', auth_config)
    object.__setattr__(server_config, 'scope', scope_config)
    object.__setattr__(server_config, 'output', output_config)
    object.__setattr__(server_config, 'logging', logging_config)
    object.__setattr__(server_config, 'server_name', "")  # Invalid: empty string
    object.__setattr__(server_config, 'server_version', "invalid-version")  # Invalid: not semantic versioning
    
    return server_config


def get_edge_case_config() -> ServerConfiguration:
    """
    Returns a ServerConfiguration object with edge-case values to test the limits 
    of configuration validation and parsing.
    
    This fixture creates a configuration with boundary values, extreme lengths,
    special characters, and other edge cases that test the robustness of the
    configuration system. All values are technically valid but represent unusual
    or extreme usage scenarios.
    
    Returns:
        ServerConfiguration: A configuration object with edge-case values for
                           testing boundary conditions and robustness scenarios.
    
    Example:
        def test_edge_case_handling(get_edge_case_config):
            config = get_edge_case_config
            assert len(config.authentication.access_key_id) == 256  # Maximum length
            assert config.logging.log_level == "DEBUG"  # Most verbose level
    """
    # Instantiate AuthenticationConfig with edge-case values
    auth_config = AuthenticationConfig(
        access_key_id="A" * 256,  # Edge case: maximum allowed length
        access_secret="x" * 1024,  # Edge case: maximum allowed length
        username="very.long.email.address.with.many.parts@very.long.domain.name.institution.edu",
        api_base_url=DEFAULT_API_BASE_URL
    )
    
    # Instantiate ScopeConfig with special characters in notebook ID
    scope_config = ScopeConfig(
        notebook_id="notebook_with_special-chars_123",
        notebook_name=None,
        folder_path=None
    )
    
    # Instantiate OutputConfig with all options enabled
    output_config = OutputConfig(
        json_ld_enabled=True,
        structured_output=True
    )
    
    # Instantiate LoggingConfig with unusual file path and debug level
    logging_config = LoggingConfig(
        log_file="logs/with spaces and unicode 测试.log",
        log_level="DEBUG",
        verbose=False,
        quiet=False
    )
    
    # Combine all edge-case configurations into a complete ServerConfiguration
    return ServerConfiguration(
        authentication=auth_config,
        scope=scope_config,
        output=output_config,
        logging=logging_config,
        server_name="labarchives-mcp-server-with-very-long-name-for-testing",
        server_version="999.999.999-beta.1+build.123"
    )


# =============================================================================
# Additional Pytest Fixtures for Backward Compatibility
# =============================================================================

@pytest.fixture
def invalid_config() -> ServerConfiguration:
    """
    Pytest fixture version of get_invalid_config() for backward compatibility.
    
    Returns:
        ServerConfiguration: An invalid configuration object for negative test cases.
    """
    return get_invalid_config()


@pytest.fixture
def edge_case_config() -> ServerConfiguration:
    """
    Pytest fixture version of get_edge_case_config() for backward compatibility.
    
    Returns:
        ServerConfiguration: A configuration object with edge-case values.
    """
    return get_edge_case_config()


@pytest.fixture
def get_valid_config() -> ServerConfiguration:
    """
    Pytest fixture version of create_valid_config() function for test compatibility.
    
    This fixture provides a valid configuration object for pytest test cases that
    require a fixture-based approach to configuration management.
    
    Returns:
        ServerConfiguration: A valid configuration object for test cases.
    """
    return _create_valid_config_instance()





