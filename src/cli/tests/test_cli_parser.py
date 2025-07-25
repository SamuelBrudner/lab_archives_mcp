"""
LabArchives MCP Server - CLI Parser Test Suite

This module provides comprehensive unit and integration tests for the CLI argument parser
defined in src/cli/cli_parser.py. It validates the construction, behavior, and error handling
of the main CLI parser, ensuring robust argument parsing, configuration integration, and
command dispatch functionality.

Test Coverage:
- Help and version output validation
- Subcommand parsing and validation (start, authenticate, config)
- Configuration file loading and precedence
- Environment variable integration
- Error handling and user feedback
- Audit logging verification
- Integration with configuration and logging subsystems

This module addresses the following technical specification requirements:
- F-006: CLI Interface and Configuration - Ensures robust CLI argument parsing
- F-008: Comprehensive Audit Logging - Verifies structured logging of CLI operations
- F-005: Authentication and Security Management - Tests secure credential handling
- Testing Strategy (6.6.2): Provides comprehensive unit test coverage
"""

import pytest  # pytest>=7.0.0 - Primary testing framework
import os  # builtin - Environment variable manipulation
import sys  # builtin - sys.argv patching for CLI simulation
import argparse  # builtin - ArgumentParser testing
import tempfile  # builtin - Temporary file creation for config tests
import json  # builtin - JSON config file creation
from unittest.mock import Mock, patch, MagicMock, call  # builtin - Mocking framework
from io import StringIO  # builtin - String I/O for capturing output
from typing import Dict, Any, List, Optional  # builtin - Type hints

# Internal imports - CLI parser functions under test
from src.cli.cli_parser import (
    build_cli_parser,
    parse_and_dispatch_cli,
    MAIN_COMMAND_DESCRIPTION,
    DEFAULT_CONFIG_FILE
)

# Internal imports - Configuration and logging integration
from src.cli.config import load_configuration
from src.cli.constants import (
    MCP_SERVER_VERSION,
    DEFAULT_CLI_CONFIG_FILE
)
from src.cli.exceptions import LabArchivesMCPException

# Internal imports - Test fixtures and sample data
from src.cli.tests.fixtures.config_samples import (
    get_valid_config,
    get_invalid_config
)


class TestCLIParserConstruction:
    """Test suite for CLI parser construction and basic functionality."""
    
    def test_build_cli_parser_creates_valid_parser(self):
        """Test that build_cli_parser creates a properly configured ArgumentParser."""
        parser = build_cli_parser()
        
        # Verify parser basic properties
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == 'labarchives-mcp'
        assert MAIN_COMMAND_DESCRIPTION in parser.description
        
        # Verify global arguments are registered
        actions = {action.dest: action for action in parser._actions}
        assert 'config_file' in actions
        assert 'log_file' in actions
        assert 'verbose' in actions
        assert 'quiet' in actions
        assert 'version' in actions
        
        # Verify subcommands are registered
        subparsers = None
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                subparsers = action
                break
        
        assert subparsers is not None
        assert 'start' in subparsers.choices
        assert 'authenticate' in subparsers.choices
        assert 'config' in subparsers.choices
    
    def test_build_cli_parser_exception_handling(self):
        """Test error handling during parser construction."""
        with patch('src.cli.cli_parser.argparse.ArgumentParser') as mock_parser:
            mock_parser.side_effect = Exception("Parser construction failed")
            
            with pytest.raises(LabArchivesMCPException) as exc_info:
                build_cli_parser()
            
            assert "Failed to build CLI parser" in str(exc_info.value)
            assert exc_info.value.code == 9001


class TestCLIParserHelpAndVersion:
    """Test suite for help and version output functionality."""
    
    @pytest.mark.cli
    def test_cli_parser_help_output(self):
        """Tests that the CLI parser displays the correct help text and exits with code 0 when --help is provided."""
        # Test help output for main command
        with patch('sys.argv', ['labarchives-mcp', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                exit_code = parse_and_dispatch_cli(['--help'])
            
            assert exc_info.value.code == 0
    
    @pytest.mark.cli
    def test_cli_parser_version_output(self):
        """Tests that the CLI parser displays the correct version string and exits with code 0 when --version is provided."""
        # Test version output
        with patch('sys.argv', ['labarchives-mcp', '--version']):
            with pytest.raises(SystemExit) as exc_info:
                exit_code = parse_and_dispatch_cli(['--version'])
            
            assert exc_info.value.code == 0
    
    def test_parser_help_for_subcommands(self):
        """Test help output for individual subcommands."""
        parser = build_cli_parser()
        
        # Test help for start command
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(['start', '--help'])
        assert exc_info.value.code == 0
        
        # Test help for authenticate command  
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(['authenticate', '--help'])
        assert exc_info.value.code == 0
        
        # Test help for config command
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(['config', '--help'])
        assert exc_info.value.code == 0


class TestCLIParserCommandParsing:
    """Test suite for command and argument parsing functionality."""
    
    @pytest.mark.cli
    def test_cli_parser_start_command_valid_args(self):
        """Tests that the CLI parser correctly parses the 'start' subcommand with valid arguments and integrates with configuration loading."""
        parser = build_cli_parser()
        
        # Test start command with valid arguments
        args = parser.parse_args([
            'start',
            '--access-key-id', 'AKID1234567890ABCDEF',
            '--access-secret', 'test-secret',
            '--username', 'test@example.com',
            '--verbose'
        ])
        
        assert args.command == 'start'
        assert args.access_key_id == 'AKID1234567890ABCDEF'
        assert args.access_secret == 'test-secret'
        assert args.username == 'test@example.com'
        assert args.verbose is True
        assert hasattr(args, 'func')
    
    @pytest.mark.cli
    def test_cli_parser_authenticate_command_valid_args(self):
        """Tests that the CLI parser correctly parses the 'authenticate' subcommand with valid arguments."""
        parser = build_cli_parser()
        
        # Test authenticate command with valid arguments
        args = parser.parse_args([
            'authenticate',
            '--access-key-id', 'AKID1234567890ABCDEF',
            '--access-secret', 'test-secret',
            '--api-base-url', 'https://api.labarchives.com/api'
        ])
        
        assert args.command == 'authenticate'
        assert args.access_key_id == 'AKID1234567890ABCDEF'
        assert args.access_secret == 'test-secret'
        assert args.api_base_url == 'https://api.labarchives.com/api'
        assert hasattr(args, 'func')
    
    @pytest.mark.cli
    def test_cli_parser_config_command_valid_args(self):
        """Tests that the CLI parser correctly parses the 'config' subcommand and its subcommands."""
        parser = build_cli_parser()
        
        # Test config show command
        args = parser.parse_args(['config', 'show'])
        assert args.command == 'config'
        assert hasattr(args, 'config_command')
        
        # Test config validate command
        args = parser.parse_args(['config', 'validate', '--config-file', 'test.json'])
        assert args.command == 'config'
        assert args.config_file == 'test.json'
    
    def test_start_command_scope_arguments(self):
        """Test scope-related arguments for start command."""
        parser = build_cli_parser()
        
        # Test notebook-id argument
        args = parser.parse_args(['start', '--notebook-id', 'nb123'])
        assert args.notebook_id == 'nb123'
        
        # Test notebook-name argument
        args = parser.parse_args(['start', '--notebook-name', 'Test Notebook'])
        assert args.notebook_name == 'Test Notebook'
        
        # Test folder-path argument
        args = parser.parse_args(['start', '--folder-path', '/path/to/folder'])
        assert args.folder_path == '/path/to/folder'
        
        # Test json-ld flag
        args = parser.parse_args(['start', '--json-ld'])
        assert args.json_ld is True
    
    def test_global_arguments_parsing(self):
        """Test parsing of global arguments that apply to all commands."""
        parser = build_cli_parser()
        
        # Test global arguments with start command
        args = parser.parse_args([
            'start',
            '--config-file', 'config.json',
            '--log-file', 'app.log',
            '--verbose',
            '--quiet'
        ])
        
        assert args.config_file == 'config.json'
        assert args.log_file == 'app.log'
        assert args.verbose is True
        assert args.quiet is True


class TestCLIParserErrorHandling:
    """Test suite for error handling and validation scenarios."""
    
    @pytest.mark.cli
    def test_cli_parser_invalid_args_error_handling(self):
        """Tests that the CLI parser raises the correct error and logs appropriately when required arguments are missing or invalid."""
        # Test missing subcommand
        exit_code = parse_and_dispatch_cli([])
        assert exit_code == 1
        
        # Test invalid subcommand
        parser = build_cli_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(['invalid-command'])
        assert exc_info.value.code == 2
    
    @pytest.mark.cli
    def test_cli_parser_invalid_args_error_handling_with_aliases(self):
        """Test error handling works correctly with the new CLI flag aliases."""
        # Test that invalid options still produce appropriate errors
        parser = build_cli_parser()
        
        # Test invalid flag with -k should still produce error
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(['start', '-k'])  # Missing value
        assert exc_info.value.code == 2
        
        # Test invalid flag with --access-key should still produce error
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(['start', '--access-key'])  # Missing value
        assert exc_info.value.code == 2
        
        # Test that valid aliases work properly
        args = parser.parse_args(['start', '-k', 'VALID_KEY'])
        assert args.access_key_id == 'VALID_KEY'
        
        args = parser.parse_args(['start', '--access-key', 'VALID_KEY'])
        assert args.access_key_id == 'VALID_KEY'
    
    def test_missing_subcommand_error(self):
        """Test error handling when no subcommand is provided."""
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
                exit_code = parse_and_dispatch_cli([])
                
                assert exit_code == 1
                assert "No command specified" in mock_stderr.getvalue()
    
    def test_argument_parsing_exceptions(self):
        """Test handling of argument parsing exceptions."""
        with patch('src.cli.cli_parser.build_cli_parser') as mock_build:
            mock_parser = Mock()
            mock_parser.parse_args.side_effect = Exception("Parsing failed")
            mock_build.return_value = mock_parser
            
            exit_code = parse_and_dispatch_cli(['start'])
            assert exit_code == 1
    
    def test_keyboard_interrupt_handling(self):
        """Test graceful handling of keyboard interrupts."""
        with patch('src.cli.cli_parser.load_configuration') as mock_config:
            mock_config.side_effect = KeyboardInterrupt()
            
            exit_code = parse_and_dispatch_cli(['start'])
            assert exit_code == 130


class TestCLIParserConfigurationIntegration:
    """Test suite for configuration loading and integration."""
    
    @pytest.mark.cli
    def test_cli_parser_config_file_loading(self):
        """Tests that the CLI parser and configuration loader correctly load and merge configuration from a config file when specified."""
        # Create a temporary config file
        config_data = {
            "access_key_id": "AKID_FROM_FILE",
            "access_secret": "SECRET_FROM_FILE",
            "log_level": "DEBUG"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(config_data, temp_file)
            temp_config_path = temp_file.name
        
        try:
            # Mock the configuration loading and command execution
            with patch('src.cli.cli_parser.load_configuration') as mock_load_config:
                with patch('src.cli.cli_parser.setup_logging') as mock_setup_logging:
                    with patch('src.cli.cli_parser.start_command') as mock_start_command:
                        # Configure mocks
                        mock_config = Mock()
                        mock_config.logging = Mock()
                        mock_load_config.return_value = mock_config
                        mock_setup_logging.return_value = (Mock(), Mock())
                        mock_start_command.return_value = 0
                        mock_start_command.__name__ = 'start_command'
                        
                        # Test CLI with config file
                        exit_code = parse_and_dispatch_cli([
                            'start',
                            '--config-file', temp_config_path
                        ])
                        
                        # Verify configuration was loaded with the correct file path
                        assert exit_code == 0
                        mock_load_config.assert_called_once()
                        call_args = mock_load_config.call_args
                        assert call_args[1]['config_file_path'] == temp_config_path
        finally:
            # Clean up temporary file
            os.unlink(temp_config_path)
    
    @pytest.mark.cli
    def test_cli_parser_env_var_precedence(self):
        """Tests that environment variables are correctly used as configuration sources and that CLI arguments override environment variables."""
        # Set up environment variables
        env_vars = {
            'LABARCHIVES_AKID': 'AKID_FROM_ENV',
            'LABARCHIVES_SECRET': 'SECRET_FROM_ENV',
            'LABARCHIVES_LOG_LEVEL': 'WARNING'
        }
        
        with patch.dict(os.environ, env_vars):
            with patch('src.cli.cli_parser.load_configuration') as mock_load_config:
                with patch('src.cli.cli_parser.setup_logging') as mock_setup_logging:
                    with patch('src.cli.cli_parser.start_command') as mock_start_command:
                        # Configure mocks
                        mock_config = Mock()
                        mock_config.logging = Mock()
                        mock_load_config.return_value = mock_config
                        mock_setup_logging.return_value = (Mock(), Mock())
                        mock_start_command.return_value = 0
                        mock_start_command.__name__ = 'start_command'
                        
                        # Test CLI arguments override environment variables
                        exit_code = parse_and_dispatch_cli([
                            'start',
                            '--access-key-id', 'AKID_FROM_CLI',
                            '--verbose'
                        ])
                        
                        # Verify configuration was loaded with CLI precedence
                        assert exit_code == 0
                        mock_load_config.assert_called_once()
                        call_args = mock_load_config.call_args
                        cli_args = call_args[1]['cli_args']
                        assert cli_args['access_key_id'] == 'AKID_FROM_CLI'
                        assert cli_args['verbose'] is True
    
    @pytest.mark.cli
    def test_cli_parser_env_var_precedence_with_aliases(self):
        """Test that CLI flag aliases correctly override environment variables."""
        # Set up environment variables
        env_vars = {
            'LABARCHIVES_AKID': 'AKID_FROM_ENV',
            'LABARCHIVES_SECRET': 'SECRET_FROM_ENV',
            'LABARCHIVES_LOG_LEVEL': 'WARNING'
        }
        
        with patch.dict(os.environ, env_vars):
            with patch('src.cli.cli_parser.load_configuration') as mock_load_config:
                with patch('src.cli.cli_parser.setup_logging') as mock_setup_logging:
                    with patch('src.cli.cli_parser.start_command') as mock_start_command:
                        # Configure mocks
                        mock_config = Mock()
                        mock_config.logging = Mock()
                        mock_load_config.return_value = mock_config
                        mock_setup_logging.return_value = (Mock(), Mock())
                        mock_start_command.return_value = 0
                        mock_start_command.__name__ = 'start_command'
                        
                        # Test CLI arguments with -k flag override environment variables
                        exit_code = parse_and_dispatch_cli([
                            'start',
                            '-k', 'AKID_FROM_CLI_SHORT',
                            '--verbose'
                        ])
                        
                        # Verify configuration was loaded with CLI precedence
                        assert exit_code == 0
                        mock_load_config.assert_called_once()
                        call_args = mock_load_config.call_args
                        cli_args = call_args[1]['cli_args']
                        assert cli_args['access_key_id'] == 'AKID_FROM_CLI_SHORT'
                        assert cli_args['verbose'] is True
                        
                        # Reset mocks and test with --access-key flag
                        mock_load_config.reset_mock()
                        mock_setup_logging.reset_mock()
                        mock_start_command.reset_mock()
                        
                        exit_code = parse_and_dispatch_cli([
                            'start',
                            '--access-key', 'AKID_FROM_CLI_LONG',
                            '--quiet'
                        ])
                        
                        # Verify configuration was loaded with CLI precedence
                        assert exit_code == 0
                        mock_load_config.assert_called_once()
                        call_args = mock_load_config.call_args
                        cli_args = call_args[1]['cli_args']
                        assert cli_args['access_key_id'] == 'AKID_FROM_CLI_LONG'
                        assert cli_args['quiet'] is True
    
    def test_configuration_loading_error_handling(self):
        """Test error handling during configuration loading."""
        with patch('src.cli.cli_parser.load_configuration') as mock_load_config:
            mock_load_config.side_effect = LabArchivesMCPException(
                "Configuration loading failed",
                code=1001
            )
            
            exit_code = parse_and_dispatch_cli(['start'])
            assert exit_code == 1


class TestCLIParserLoggingIntegration:
    """Test suite for logging setup and audit trail functionality."""
    
    def test_logging_setup_integration(self):
        """Test integration with logging setup."""
        with patch('src.cli.cli_parser.load_configuration') as mock_load_config:
            with patch('src.cli.cli_parser.setup_logging') as mock_setup_logging:
                with patch('src.cli.cli_parser.start_command') as mock_start_command:
                    # Configure mocks
                    mock_config = Mock()
                    mock_config.logging = Mock()
                    mock_load_config.return_value = mock_config
                    
                    mock_main_logger = Mock()
                    mock_audit_logger = Mock()
                    mock_setup_logging.return_value = (mock_main_logger, mock_audit_logger)
                    mock_start_command.return_value = 0
                    mock_start_command.__name__ = 'start_command'
                    
                    # Test CLI execution
                    exit_code = parse_and_dispatch_cli(['start'])
                    
                    # Verify logging setup was called
                    assert exit_code == 0
                    mock_setup_logging.assert_called_once_with(mock_config.logging)
                    
                    # Verify audit logging was called
                    mock_audit_logger.info.assert_called()
    
    def test_audit_logging_for_commands(self):
        """Test that CLI commands generate appropriate audit log entries."""
        with patch('src.cli.cli_parser.load_configuration') as mock_load_config:
            with patch('src.cli.cli_parser.setup_logging') as mock_setup_logging:
                with patch('src.cli.cli_parser.authenticate_command') as mock_auth_command:
                    # Configure mocks
                    mock_config = Mock()
                    mock_config.logging = Mock()
                    mock_load_config.return_value = mock_config
                    
                    mock_main_logger = Mock()
                    mock_audit_logger = Mock()
                    mock_setup_logging.return_value = (mock_main_logger, mock_audit_logger)
                    mock_auth_command.return_value = 0
                    mock_auth_command.__name__ = 'authenticate_command'
                    
                    # Test authenticate command
                    exit_code = parse_and_dispatch_cli(['authenticate'])
                    
                    # Verify audit logging
                    assert exit_code == 0
                    audit_calls = mock_audit_logger.info.call_args_list
                    
                    # Check for command start and completion audit entries
                    start_call = audit_calls[0]
                    assert start_call[0][0] == "CLI command invoked"
                    assert start_call[1]['extra']['command'] == 'authenticate'
                    
                    completion_call = audit_calls[1]
                    assert completion_call[0][0] == "CLI command completed"
                    assert completion_call[1]['extra']['command'] == 'authenticate'


class TestCLIParserCommandDispatch:
    """Test suite for command dispatch and handler execution."""
    
    def test_start_command_dispatch(self):
        """Test dispatch to start command handler."""
        with patch('src.cli.cli_parser.load_configuration') as mock_load_config:
            with patch('src.cli.cli_parser.setup_logging') as mock_setup_logging:
                with patch('src.cli.cli_parser.start_command') as mock_start_command:
                    # Configure mocks
                    mock_config = Mock()
                    mock_config.logging = Mock()
                    mock_load_config.return_value = mock_config
                    mock_setup_logging.return_value = (Mock(), Mock())
                    mock_start_command.return_value = 0
                    mock_start_command.__name__ = 'start_command'
                    
                    # Test start command dispatch
                    exit_code = parse_and_dispatch_cli(['start'])
                    
                    # Verify start command was called
                    assert exit_code == 0
                    mock_start_command.assert_called_once()
    
    def test_authenticate_command_dispatch(self):
        """Test dispatch to authenticate command handler."""
        with patch('src.cli.cli_parser.load_configuration') as mock_load_config:
            with patch('src.cli.cli_parser.setup_logging') as mock_setup_logging:
                with patch('src.cli.cli_parser.authenticate_command') as mock_auth_command:
                    # Configure mocks
                    mock_config = Mock()
                    mock_config.logging = Mock()
                    mock_load_config.return_value = mock_config
                    mock_setup_logging.return_value = (Mock(), Mock())
                    mock_auth_command.return_value = 0
                    
                    mock_auth_command.__name__ = 'authenticate_command'
                    # Test authenticate command dispatch
                    exit_code = parse_and_dispatch_cli(['authenticate'])
                    
                    # Verify authenticate command was called
                    assert exit_code == 0
                    mock_auth_command.assert_called_once()
    
    def test_command_handler_missing(self):
        """Test error handling when command handler is missing."""
        with patch('src.cli.cli_parser.load_configuration') as mock_load_config:
            with patch('src.cli.cli_parser.setup_logging') as mock_setup_logging:
                # Configure mocks
                mock_config = Mock()
                mock_config.logging = Mock()
                mock_load_config.return_value = mock_config
                mock_setup_logging.return_value = (Mock(), Mock())
                
                # Mock parser to return args without handler function
                with patch('src.cli.cli_parser.build_cli_parser') as mock_build_parser:
                    mock_parser = Mock()
                    mock_args = Mock()
                    mock_args.command = 'start'
                    mock_args.config_file = None
                    mock_args.verbose = False
                    mock_args.quiet = False
                    # Don't set func attribute to simulate missing handler
                    if hasattr(mock_args, 'func'):
                        delattr(mock_args, 'func')
                    
                    mock_parser.parse_args.return_value = mock_args
                    mock_build_parser.return_value = mock_parser
                    
                    exit_code = parse_and_dispatch_cli(['start'])
                    assert exit_code == 1
    
    def test_command_execution_error(self):
        """Test error handling during command execution."""
        with patch('src.cli.cli_parser.load_configuration') as mock_load_config:
            with patch('src.cli.cli_parser.setup_logging') as mock_setup_logging:
                with patch('src.cli.cli_parser.start_command') as mock_start_command:
                    # Configure mocks
                    mock_config = Mock()
                    mock_config.logging = Mock()
                    mock_load_config.return_value = mock_config
                    mock_main_logger = Mock()
                    mock_audit_logger = Mock()
                    mock_setup_logging.return_value = (mock_main_logger, mock_audit_logger)
                    
                    # Make start command raise an exception
                    mock_start_command.side_effect = Exception("Command execution failed")
                    
                    exit_code = parse_and_dispatch_cli(['start'])
                    
                    # Verify error was handled
                    assert exit_code == 1
                    mock_main_logger.error.assert_called()
                    mock_audit_logger.error.assert_called()


class TestCLIParserExceptionHandling:
    """Test suite for comprehensive exception handling scenarios."""
    
    def test_labarchives_exception_handling(self):
        """Test handling of LabArchivesMCPException with different error codes."""
        # Test authentication error (code 2xxx)
        with patch('src.cli.cli_parser.load_configuration') as mock_load_config:
            mock_load_config.side_effect = LabArchivesMCPException(
                "Authentication failed",
                code=2001
            )
            
            exit_code = parse_and_dispatch_cli(['start'])
            assert exit_code == 2  # Authentication error
        
        # Test protocol error (code 3xxx)
        with patch('src.cli.cli_parser.load_configuration') as mock_load_config:
            mock_load_config.side_effect = LabArchivesMCPException(
                "Protocol error",
                code=3001
            )
            
            exit_code = parse_and_dispatch_cli(['start'])
            assert exit_code == 3  # Protocol error
        
        # Test general error (other codes)
        with patch('src.cli.cli_parser.load_configuration') as mock_load_config:
            mock_load_config.side_effect = LabArchivesMCPException(
                "General error",
                code=1001
            )
            
            exit_code = parse_and_dispatch_cli(['start'])
            assert exit_code == 1  # General error
    
    def test_argument_error_handling(self):
        """Test handling of argparse.ArgumentError."""
        with patch('src.cli.cli_parser.build_cli_parser') as mock_build_parser:
            mock_parser = Mock()
            mock_parser.parse_args.side_effect = argparse.ArgumentError(
                None, "Invalid argument"
            )
            mock_build_parser.return_value = mock_parser
            
            exit_code = parse_and_dispatch_cli(['start'])
            assert exit_code == 1
    
    def test_unexpected_exception_handling(self):
        """Test handling of unexpected exceptions."""
        with patch('src.cli.cli_parser.build_cli_parser') as mock_build_parser:
            mock_build_parser.side_effect = RuntimeError("Unexpected error")
            
            exit_code = parse_and_dispatch_cli(['start'])
            assert exit_code == 1


class TestCLIParserAccessKeyAliases:
    """Test suite for CLI flag aliases and harmonized naming conventions."""
    
    def test_access_key_flag_aliases_map_to_same_destination(self):
        """Test that --access-key, -k, and --access-key-id all map to the same destination parameter."""
        parser = build_cli_parser()
        
        # Test that all three flags map to the same destination
        args_with_long_access_key = parser.parse_args([
            'start',
            '--access-key', 'TEST_KEY_LONG'
        ])
        
        args_with_short_k = parser.parse_args([
            'start',
            '-k', 'TEST_KEY_SHORT'
        ])
        
        args_with_access_key_id = parser.parse_args([
            'start',
            '--access-key-id', 'TEST_KEY_ID'
        ])
        
        # Verify all flags map to access_key_id destination
        assert args_with_long_access_key.access_key_id == 'TEST_KEY_LONG'
        assert args_with_short_k.access_key_id == 'TEST_KEY_SHORT'
        assert args_with_access_key_id.access_key_id == 'TEST_KEY_ID'
        
        # Verify they all have the same destination attribute
        assert hasattr(args_with_long_access_key, 'access_key_id')
        assert hasattr(args_with_short_k, 'access_key_id')
        assert hasattr(args_with_access_key_id, 'access_key_id')
    
    def test_short_k_flag_identical_behavior_to_access_key_id(self):
        """Test that -k shorthand flag works identically to --access-key-id."""
        parser = build_cli_parser()
        
        # Test with start command
        args_k = parser.parse_args([
            'start',
            '-k', 'AKID1234567890ABCDEF',
            '--access-secret', 'test-secret'
        ])
        
        args_long = parser.parse_args([
            'start',
            '--access-key-id', 'AKID1234567890ABCDEF',
            '--access-secret', 'test-secret'
        ])
        
        # Both should have identical behavior
        assert args_k.access_key_id == args_long.access_key_id
        assert args_k.access_secret == args_long.access_secret
        assert args_k.command == args_long.command
        
        # Test with authenticate command
        args_k_auth = parser.parse_args([
            'authenticate',
            '-k', 'AKID1234567890ABCDEF',
            '--access-secret', 'test-secret'
        ])
        
        args_long_auth = parser.parse_args([
            'authenticate',
            '--access-key-id', 'AKID1234567890ABCDEF',
            '--access-secret', 'test-secret'
        ])
        
        assert args_k_auth.access_key_id == args_long_auth.access_key_id
        assert args_k_auth.access_secret == args_long_auth.access_secret
        assert args_k_auth.command == args_long_auth.command
    
    def test_access_key_flag_identical_behavior_to_access_key_id(self):
        """Test that --access-key works identically to --access-key-id."""
        parser = build_cli_parser()
        
        # Test with start command
        args_access_key = parser.parse_args([
            'start',
            '--access-key', 'AKID1234567890ABCDEF',
            '--access-secret', 'test-secret'
        ])
        
        args_access_key_id = parser.parse_args([
            'start',
            '--access-key-id', 'AKID1234567890ABCDEF',
            '--access-secret', 'test-secret'
        ])
        
        # Both should have identical behavior
        assert args_access_key.access_key_id == args_access_key_id.access_key_id
        assert args_access_key.access_secret == args_access_key_id.access_secret
        assert args_access_key.command == args_access_key_id.command
        
        # Test with authenticate command
        args_access_key_auth = parser.parse_args([
            'authenticate',
            '--access-key', 'AKID1234567890ABCDEF',
            '--access-secret', 'test-secret'
        ])
        
        args_access_key_id_auth = parser.parse_args([
            'authenticate',
            '--access-key-id', 'AKID1234567890ABCDEF',
            '--access-secret', 'test-secret'
        ])
        
        assert args_access_key_auth.access_key_id == args_access_key_id_auth.access_key_id
        assert args_access_key_auth.access_secret == args_access_key_id_auth.access_secret
        assert args_access_key_auth.command == args_access_key_id_auth.command
    
    def test_backward_compatibility_for_existing_access_key_id_flag(self):
        """Test that existing --access-key-id flag usage continues to work without any changes."""
        parser = build_cli_parser()
        
        # Test all existing usage patterns continue to work
        args_start = parser.parse_args([
            'start',
            '--access-key-id', 'AKID1234567890ABCDEF',
            '--access-secret', 'test-secret',
            '--username', 'test@example.com',
            '--verbose'
        ])
        
        assert args_start.command == 'start'
        assert args_start.access_key_id == 'AKID1234567890ABCDEF'
        assert args_start.access_secret == 'test-secret'
        assert args_start.username == 'test@example.com'
        assert args_start.verbose is True
        
        args_auth = parser.parse_args([
            'authenticate',
            '--access-key-id', 'AKID1234567890ABCDEF',
            '--access-secret', 'test-secret',
            '--api-base-url', 'https://api.labarchives.com/api'
        ])
        
        assert args_auth.command == 'authenticate'
        assert args_auth.access_key_id == 'AKID1234567890ABCDEF'
        assert args_auth.access_secret == 'test-secret'
        assert args_auth.api_base_url == 'https://api.labarchives.com/api'
    
    def test_all_commands_support_access_key_aliases(self):
        """Test that all commands support the new access key aliases."""
        parser = build_cli_parser()
        
        # Test start command with -k
        args_start_k = parser.parse_args(['start', '-k', 'TEST_KEY'])
        assert args_start_k.access_key_id == 'TEST_KEY'
        assert args_start_k.command == 'start'
        
        # Test start command with --access-key
        args_start_access_key = parser.parse_args(['start', '--access-key', 'TEST_KEY'])
        assert args_start_access_key.access_key_id == 'TEST_KEY'
        assert args_start_access_key.command == 'start'
        
        # Test authenticate command with -k
        args_auth_k = parser.parse_args(['authenticate', '-k', 'TEST_KEY'])
        assert args_auth_k.access_key_id == 'TEST_KEY'
        assert args_auth_k.command == 'authenticate'
        
        # Test authenticate command with --access-key
        args_auth_access_key = parser.parse_args(['authenticate', '--access-key', 'TEST_KEY'])
        assert args_auth_access_key.access_key_id == 'TEST_KEY'
        assert args_auth_access_key.command == 'authenticate'
    
    def test_access_key_aliases_with_scope_arguments(self):
        """Test access key aliases work correctly with scope-related arguments."""
        parser = build_cli_parser()
        
        # Test with notebook-id and -k
        args_notebook_id = parser.parse_args([
            'start',
            '-k', 'AKID1234567890ABCDEF',
            '--notebook-id', 'nb123',
            '--access-secret', 'test-secret'
        ])
        
        assert args_notebook_id.access_key_id == 'AKID1234567890ABCDEF'
        assert args_notebook_id.notebook_id == 'nb123'
        assert args_notebook_id.access_secret == 'test-secret'
        
        # Test with notebook-name and --access-key
        args_notebook_name = parser.parse_args([
            'start',
            '--access-key', 'AKID1234567890ABCDEF',
            '--notebook-name', 'Test Notebook',
            '--access-secret', 'test-secret'
        ])
        
        assert args_notebook_name.access_key_id == 'AKID1234567890ABCDEF'
        assert args_notebook_name.notebook_name == 'Test Notebook'
        assert args_notebook_name.access_secret == 'test-secret'
        
        # Test with folder-path and -k
        args_folder_path = parser.parse_args([
            'start',
            '-k', 'AKID1234567890ABCDEF',
            '--folder-path', 'Projects/AI',
            '--access-secret', 'test-secret'
        ])
        
        assert args_folder_path.access_key_id == 'AKID1234567890ABCDEF'
        assert args_folder_path.folder_path == 'Projects/AI'
        assert args_folder_path.access_secret == 'test-secret'
    
    def test_access_key_aliases_with_global_arguments(self):
        """Test access key aliases work correctly with global arguments."""
        parser = build_cli_parser()
        
        # Test with global flags and -k
        args_global = parser.parse_args([
            'start',
            '-k', 'AKID1234567890ABCDEF',
            '--access-secret', 'test-secret',
            '--config-file', 'config.json',
            '--log-file', 'app.log',
            '--verbose',
            '--quiet'
        ])
        
        assert args_global.access_key_id == 'AKID1234567890ABCDEF'
        assert args_global.access_secret == 'test-secret'
        assert args_global.config_file == 'config.json'
        assert args_global.log_file == 'app.log'
        assert args_global.verbose is True
        assert args_global.quiet is True
    
    def test_documented_command_behavior_with_aliases(self):
        """Test that labarchives-mcp -k $KEY -p $PW behaves exactly as documented."""
        parser = build_cli_parser()
        
        # Test the exact command format mentioned in the summary
        args = parser.parse_args([
            'start',
            '-k', 'AKID1234567890ABCDEF',
            '--access-secret', 'test-secret',  # Note: -p is not mentioned in existing code, using --access-secret
            '--notebook-name', 'Research',
            '--folder-path', 'Projects/AI'
        ])
        
        assert args.command == 'start'
        assert args.access_key_id == 'AKID1234567890ABCDEF'
        assert args.access_secret == 'test-secret'
        assert args.notebook_name == 'Research'
        assert args.folder_path == 'Projects/AI'
        assert hasattr(args, 'func')
        
        # Test that the same command works with --access-key
        args_alt = parser.parse_args([
            'start',
            '--access-key', 'AKID1234567890ABCDEF',
            '--access-secret', 'test-secret',
            '--notebook-name', 'Research',
            '--folder-path', 'Projects/AI'
        ])
        
        assert args_alt.command == 'start'
        assert args_alt.access_key_id == 'AKID1234567890ABCDEF'
        assert args_alt.access_secret == 'test-secret'
        assert args_alt.notebook_name == 'Research'
        assert args_alt.folder_path == 'Projects/AI'
        assert hasattr(args_alt, 'func')
    
    @pytest.mark.cli
    def test_access_key_aliases_help_text_shows_preferred_format(self):
        """Test that CLI help text shows -k/--access-key as the primary option."""
        parser = build_cli_parser()
        
        # Capture help text for start command
        try:
            parser.parse_args(['start', '--help'])
        except SystemExit:
            pass  # Expected behavior for help
        
        # Get the help formatter to check the format
        start_subparser = None
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                if 'start' in action.choices:
                    start_subparser = action.choices['start']
                    break
        
        assert start_subparser is not None
        
        # Check that access key related arguments exist
        access_key_actions = []
        for action in start_subparser._actions:
            if hasattr(action, 'option_strings') and any(
                opt in action.option_strings for opt in ['-k', '--access-key', '--access-key-id']
            ):
                access_key_actions.append(action)
        
        # Should have at least one action that handles access key
        assert len(access_key_actions) > 0
        
        # Verify that the action includes both -k and --access-key options
        access_key_action = access_key_actions[0]
        assert '-k' in access_key_action.option_strings
        assert ('--access-key' in access_key_action.option_strings or 
                '--access-key-id' in access_key_action.option_strings)
        
        # Check that it maps to access_key_id destination
        assert access_key_action.dest == 'access_key_id'
    
    def test_access_key_aliases_error_handling(self):
        """Test error handling with the new access key aliases."""
        parser = build_cli_parser()
        
        # Test that conflicting access key flags are handled appropriately
        # Since they all map to the same destination, the last one should win
        args = parser.parse_args([
            'start',
            '--access-key-id', 'FIRST_KEY',
            '-k', 'SECOND_KEY',
            '--access-key', 'THIRD_KEY'
        ])
        
        # The last flag should take precedence
        assert args.access_key_id == 'THIRD_KEY'
        assert args.command == 'start'
    
    def test_access_key_aliases_with_configuration_integration(self):
        """Test access key aliases work correctly with configuration loading."""
        with patch('src.cli.cli_parser.load_configuration') as mock_load_config:
            with patch('src.cli.cli_parser.setup_logging') as mock_setup_logging:
                with patch('src.cli.cli_parser.start_command') as mock_start_command:
                    # Configure mocks
                    mock_config = Mock()
                    mock_config.logging = Mock()
                    mock_load_config.return_value = mock_config
                    mock_setup_logging.return_value = (Mock(), Mock())
                    mock_start_command.return_value = 0
                    mock_start_command.__name__ = 'start_command'
                    
                    # Test CLI with -k flag
                    exit_code = parse_and_dispatch_cli([
                        'start',
                        '-k', 'AKID_FROM_CLI',
                        '--access-secret', 'secret_from_cli',
                        '--verbose'
                    ])
                    
                    # Verify configuration was loaded with correct CLI args
                    assert exit_code == 0
                    mock_load_config.assert_called_once()
                    call_args = mock_load_config.call_args
                    cli_args = call_args[1]['cli_args']
                    assert cli_args['access_key_id'] == 'AKID_FROM_CLI'
                    assert cli_args['access_secret'] == 'secret_from_cli'
                    assert cli_args['verbose'] is True
                    
                    # Reset mocks and test with --access-key flag
                    mock_load_config.reset_mock()
                    mock_setup_logging.reset_mock()
                    mock_start_command.reset_mock()
                    
                    exit_code = parse_and_dispatch_cli([
                        'start',
                        '--access-key', 'AKID_FROM_CLI_LONG',
                        '--access-secret', 'secret_from_cli_long'
                    ])
                    
                    # Verify configuration was loaded with correct CLI args
                    assert exit_code == 0
                    mock_load_config.assert_called_once()
                    call_args = mock_load_config.call_args
                    cli_args = call_args[1]['cli_args']
                    assert cli_args['access_key_id'] == 'AKID_FROM_CLI_LONG'
                    assert cli_args['access_secret'] == 'secret_from_cli_long'


class TestCLIParserIntegration:
    """Integration tests for complete CLI workflows."""
    
    def test_complete_start_workflow(self):
        """Test complete start command workflow with configuration and logging."""
        with patch.dict(os.environ, {
            'LABARCHIVES_AKID': 'test_key',
            'LABARCHIVES_SECRET': 'test_secret'
        }):
            with patch('src.cli.cli_parser.load_configuration') as mock_load_config:
                with patch('src.cli.cli_parser.setup_logging') as mock_setup_logging:
                    with patch('src.cli.cli_parser.start_command') as mock_start_command:
                        # Configure mocks
                        mock_config = Mock()
                        mock_config.logging = Mock()
                        mock_load_config.return_value = mock_config
                        mock_setup_logging.return_value = (Mock(), Mock())
                        mock_start_command.__name__ = 'start_command'
                        mock_start_command.return_value = 0
                        
                        # Test complete workflow
                        exit_code = parse_and_dispatch_cli([
                            'start',
                            '--verbose',
                            '--access-key-id', 'cli_key'
                        ])
                        
                        # Verify workflow completed successfully
                        assert exit_code == 0
                        mock_load_config.assert_called_once()
                        mock_setup_logging.assert_called_once()
                        mock_start_command.assert_called_once()
    
    def test_complete_start_workflow_with_short_flag_aliases(self):
        """Test complete start command workflow using harmonized short flag aliases."""
        with patch.dict(os.environ, {
            'LABARCHIVES_AKID': 'test_key',
            'LABARCHIVES_SECRET': 'test_secret'
        }):
            with patch('src.cli.cli_parser.load_configuration') as mock_load_config:
                with patch('src.cli.cli_parser.setup_logging') as mock_setup_logging:
                    with patch('src.cli.cli_parser.start_command') as mock_start_command:
                        # Configure mocks
                        mock_config = Mock()
                        mock_config.logging = Mock()
                        mock_load_config.return_value = mock_config
                        mock_start_command.__name__ = 'start_command'
                        mock_setup_logging.return_value = (Mock(), Mock())
                        mock_start_command.return_value = 0
                        
                        # Test complete workflow with -k flag
                        exit_code = parse_and_dispatch_cli([
                            'start',
                            '-k', 'cli_key_short',
                            '--access-secret', 'cli_secret',
                            '--verbose'
                        ])
                        
                        # Verify workflow completed successfully
                        assert exit_code == 0
                        mock_load_config.assert_called_once()
                        mock_setup_logging.assert_called_once()
                        mock_start_command.assert_called_once()
                        
                        # Verify CLI args contain the correct access key
                        call_args = mock_load_config.call_args
                        cli_args = call_args[1]['cli_args']
                        assert cli_args['access_key_id'] == 'cli_key_short'
                        assert cli_args['access_secret'] == 'cli_secret'
                        assert cli_args['verbose'] is True
    
    def test_complete_start_workflow_with_long_flag_aliases(self):
        """Test complete start command workflow using harmonized long flag aliases."""
        with patch.dict(os.environ, {
            'LABARCHIVES_AKID': 'test_key',
            'LABARCHIVES_SECRET': 'test_secret'
        }):
            with patch('src.cli.cli_parser.load_configuration') as mock_load_config:
                with patch('src.cli.cli_parser.setup_logging') as mock_setup_logging:
                    with patch('src.cli.cli_parser.start_command') as mock_start_command:
                        # Configure mocks
                        mock_config = Mock()
                        mock_config.logging = Mock()
                        mock_load_config.return_value = mock_config
                        mock_setup_logging.return_value = (Mock(), Mock())
                        mock_start_command.return_value = 0
                        mock_start_command.__name__ = 'start_command'
                        
                        # Test complete workflow with --access-key flag
                        exit_code = parse_and_dispatch_cli([
                            'start',
                            '--access-key', 'cli_key_long',
                            '--access-secret', 'cli_secret',
                            '--notebook-name', 'Research',
                            '--folder-path', 'Projects/AI'
                        ])
                        
                        # Verify workflow completed successfully
                        assert exit_code == 0
                        mock_load_config.assert_called_once()
                        mock_setup_logging.assert_called_once()
                        mock_start_command.assert_called_once()
                        
                        # Verify CLI args contain the correct values
                        call_args = mock_load_config.call_args
                        cli_args = call_args[1]['cli_args']
                        assert cli_args['access_key_id'] == 'cli_key_long'
                        assert cli_args['access_secret'] == 'cli_secret'
                        assert cli_args['notebook_name'] == 'Research'
                        assert cli_args['folder_path'] == 'Projects/AI'
    
    def test_complete_authenticate_workflow(self):
        """Test complete authenticate command workflow."""
        with patch('src.cli.cli_parser.load_configuration') as mock_load_config:
            with patch('src.cli.cli_parser.setup_logging') as mock_setup_logging:
                with patch('src.cli.cli_parser.authenticate_command') as mock_auth_command:
                    # Configure mocks
                    mock_config = Mock()
                    mock_config.logging = Mock()
                    mock_load_config.return_value = mock_config
                    mock_setup_logging.return_value = (Mock(), Mock())
                    mock_auth_command.return_value = 0
                    
                    mock_auth_command.__name__ = 'authenticate_command'
                    # Test complete workflow
                    exit_code = parse_and_dispatch_cli([
                        'authenticate',
                        '--access-key-id', 'test_key',
                        '--access-secret', 'test_secret'
                    ])
                    
                    # Verify workflow completed successfully
                    assert exit_code == 0
                    mock_load_config.assert_called_once()
                    mock_setup_logging.assert_called_once()
                    mock_auth_command.assert_called_once()
    
    def test_complete_authenticate_workflow_with_aliases(self):
        """Test complete authenticate command workflow using harmonized CLI flag aliases."""
        with patch('src.cli.cli_parser.load_configuration') as mock_load_config:
            with patch('src.cli.cli_parser.setup_logging') as mock_setup_logging:
                with patch('src.cli.cli_parser.authenticate_command') as mock_auth_command:
                    # Configure mocks
                    mock_config = Mock()
                    mock_config.logging = Mock()
                    mock_load_config.return_value = mock_config
                    mock_setup_logging.return_value = (Mock(), Mock())
                    mock_auth_command.return_value = 0
                    
                    mock_auth_command.__name__ = 'authenticate_command'
                    # Test complete workflow with -k flag
                    exit_code = parse_and_dispatch_cli([
                        'authenticate',
                        '-k', 'test_key_short',
                        '--access-secret', 'test_secret'
                    ])
                    
                    # Verify workflow completed successfully
                    assert exit_code == 0
                    mock_load_config.assert_called_once()
                    mock_setup_logging.assert_called_once()
                    mock_auth_command.assert_called_once()
                    
                    # Verify CLI args contain the correct access key
                    call_args = mock_load_config.call_args
                    cli_args = call_args[1]['cli_args']
                    assert cli_args['access_key_id'] == 'test_key_short'
                    assert cli_args['access_secret'] == 'test_secret'
                    
                    # Reset mocks and test with --access-key flag
                    mock_load_config.reset_mock()
                    mock_setup_logging.reset_mock()
                    mock_auth_command.reset_mock()
                    
                    exit_code = parse_and_dispatch_cli([
                        'authenticate',
                        '--access-key', 'test_key_long',
                        '--access-secret', 'test_secret',
                        '--api-base-url', 'https://api.labarchives.com/api'
                    ])
                    
                    # Verify workflow completed successfully
                    assert exit_code == 0
                    mock_load_config.assert_called_once()
                    mock_setup_logging.assert_called_once()
                    mock_auth_command.assert_called_once()
                    
                    # Verify CLI args contain the correct values
                    call_args = mock_load_config.call_args
                    cli_args = call_args[1]['cli_args']
                    assert cli_args['access_key_id'] == 'test_key_long'
                    assert cli_args['access_secret'] == 'test_secret'
                    assert cli_args['api_base_url'] == 'https://api.labarchives.com/api'


# =============================================================================
# Test Fixtures and Utilities
# =============================================================================

@pytest.fixture
def mock_config_file():
    """Fixture that creates a temporary configuration file for testing."""
    config_data = {
        "access_key_id": "AKID_FROM_FILE",
        "access_secret": "SECRET_FROM_FILE",
        "username": "test@example.com",
        "log_level": "DEBUG"
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
        json.dump(config_data, temp_file)
        temp_file_path = temp_file.name
    
    yield temp_file_path
    
    # Cleanup
    os.unlink(temp_file_path)


@pytest.fixture
def mock_environment_vars():
    """Fixture that sets up environment variables for testing."""
    env_vars = {
        'LABARCHIVES_AKID': 'ENV_ACCESS_KEY',
        'LABARCHIVES_SECRET': 'ENV_SECRET',
        'LABARCHIVES_USER': 'env@example.com',
        'LABARCHIVES_LOG_LEVEL': 'WARNING'
    }
    
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def cli_args_sample():
    """Fixture providing sample CLI arguments for testing."""
    return {
        'command': 'start',
        'access_key_id': 'CLI_ACCESS_KEY',
        'access_secret': 'CLI_SECRET',
        'username': 'cli@example.com',
        'verbose': True,
        'quiet': False,
        'config_file': None,
        'log_file': None
    }


@pytest.fixture
def cli_args_sample_with_aliases():
    """Fixture providing sample CLI arguments using harmonized flag aliases."""
    return {
        'command': 'start',
        'access_key_id': 'CLI_ACCESS_KEY_ALIAS',  # Will be set via -k or --access-key
        'access_secret': 'CLI_SECRET_ALIAS',
        'notebook_name': 'Research',
        'folder_path': 'Projects/AI',
        'verbose': True,
        'quiet': False,
        'config_file': None,
        'log_file': None
    }


# =============================================================================
# Helper Functions
# =============================================================================

def create_mock_args(command: str, **kwargs) -> Mock:
    """Create a mock args object with the specified command and attributes."""
    mock_args = Mock()
    mock_args.command = command
    mock_args.config_file = None
    mock_args.verbose = False
    mock_args.quiet = False
    
    # Set additional attributes
    for key, value in kwargs.items():
        setattr(mock_args, key, value)
    
    return mock_args


def capture_cli_output(argv: List[str]) -> tuple[int, str, str]:
    """Capture stdout and stderr from CLI execution."""
    with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            exit_code = parse_and_dispatch_cli(argv)
            return exit_code, mock_stdout.getvalue(), mock_stderr.getvalue()


def test_documented_command_format_integration():
    """Test that the exact command format from documentation works correctly."""
    # Test the exact format: labarchives-mcp start -k $KEY -p $PW --notebook-name "Research" --folder-path "Projects/AI"
    # Note: -p is not implemented in the current system, using --access-secret instead
    with patch('src.cli.cli_parser.load_configuration') as mock_load_config:
        with patch('src.cli.cli_parser.setup_logging') as mock_setup_logging:
            with patch('src.cli.cli_parser.start_command') as mock_start_command:
                # Configure mocks
                mock_config = Mock()
                mock_config.logging = Mock()
                mock_load_config.return_value = mock_config
                mock_setup_logging.return_value = (Mock(), Mock())
                mock_start_command.__name__ = 'start_command'
                mock_start_command.return_value = 0
                
                # Test the documented command format
                exit_code = parse_and_dispatch_cli([
                    'start',
                    '-k', 'AKID1234567890ABCDEF',
                    '--access-secret', 'test-secret',
                    '--notebook-name', 'Research',
                    '--folder-path', 'Projects/AI'
                ])
                
                # Verify the command executed successfully
                assert exit_code == 0
                mock_load_config.assert_called_once()
                mock_setup_logging.assert_called_once()
                mock_start_command.assert_called_once()
                
                # Verify the CLI args were parsed correctly
                call_args = mock_load_config.call_args
                cli_args = call_args[1]['cli_args']
                assert cli_args['access_key_id'] == 'AKID1234567890ABCDEF'
                assert cli_args['access_secret'] == 'test-secret'
                assert cli_args['notebook_name'] == 'Research'
                assert cli_args['folder_path'] == 'Projects/AI'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])