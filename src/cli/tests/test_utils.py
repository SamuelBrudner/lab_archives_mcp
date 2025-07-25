"""
Unit tests for utility functions in src/cli/utils.py.

This module provides comprehensive unit tests for the utility functions used throughout
the LabArchives MCP Server CLI, ensuring correct behavior of helper methods including
string manipulation, environment variable handling, and data transformation utilities.

The tests provide regression coverage for edge cases and error handling in utility logic,
supporting the overall testing strategy by providing isolated, deterministic tests for
reusable code. All tests are designed to be fast, deterministic, and isolated to enable
reliable continuous integration and development workflows.

The test suite covers:
- Environment variable sanitization and validation
- Deep merging of nested dictionary structures  
- ISO 8601 datetime parsing with various formats
- Dictionary flattening with compound key generation
- Error handling and edge cases for all utility functions

Each test function follows the AAA pattern (Arrange, Act, Assert) and includes
comprehensive test data to verify both success and failure scenarios.
"""

import pytest  # version 7.0.0+ - Testing framework for writing and running unit tests
from datetime import datetime, timezone, timedelta
from src.cli.utils import (
    sanitize_env_var,
    deep_merge_dicts, 
    parse_iso_datetime,
    flatten_dict
)


class TestSanitizeEnvVar:
    """Test class for sanitize_env_var function."""
    
    @pytest.mark.parametrize("input_var,expected", [
        ("  DATABASE_URL  ", "DATABASE_URL"),
        ("api_key", "API_KEY"),
        ("  lowercase_with_spaces  ", "LOWERCASE_WITH_SPACES"),
        ("MixedCase", "MIXEDCASE"),
        ("already_UPPER", "ALREADY_UPPER"),
        ("with-dashes", "WITH_DASHES"),
        ("with.dots", "WITH_DOTS"),
        ("with123numbers", "WITH123NUMBERS"),
        ("", ""),
        ("   ", ""),
        ("special!@#chars", "SPECIAL_CHARS"),
        ("multiple   spaces", "MULTIPLE_SPACES"),
        ("trailing_underscore_", "TRAILING_UNDERSCORE_"),
        ("_leading_underscore", "_LEADING_UNDERSCORE"),
        ("double__underscores", "DOUBLE__UNDERSCORES"),
    ])
    def test_sanitize_env_var_valid(self, input_var, expected):
        """Test that sanitize_env_var correctly strips whitespace and uppercases environment variable names."""
        # Act
        result = sanitize_env_var(input_var)
        
        # Assert
        assert result == expected, f"Expected '{expected}', got '{result}'"
        assert result.isupper() or result == "", "Result should be uppercase or empty"
        assert result.strip() == result, "Result should not have leading/trailing whitespace"
    
    def test_sanitize_env_var_removes_invalid_characters(self):
        """Test that sanitize_env_var removes invalid characters from environment variable names."""
        # Arrange
        test_cases = [
            ("var!@#$%^&*()", "VAR_"),
            ("var with spaces", "VAR_WITH_SPACES"),
            ("var-with-dashes", "VAR_WITH_DASHES"),
            ("var.with.dots", "VAR_WITH_DOTS"),
            ("var+plus+signs", "VAR_PLUS_SIGNS"),
            ("var=equals=signs", "VAR_EQUALS_SIGNS"),
            ("var[brackets]", "VAR_BRACKETS_"),
            ("var{braces}", "VAR_BRACES_"),
            ("var|pipes|", "VAR_PIPES_"),
            ("var\\backslash", "VAR_BACKSLASH"),
            ("var/forward/slash", "VAR_FORWARD_SLASH"),
            ("var:colon", "VAR_COLON"),
            ("var;semicolon", "VAR_SEMICOLON"),
            ("var\"quotes\"", "VAR_QUOTES_"),
            ("var'apostrophe'", "VAR_APOSTROPHE_"),
            ("var<greater>", "VAR_GREATER_"),
            ("var?question", "VAR_QUESTION"),
            ("var,comma", "VAR_COMMA"),
        ]
        
        for input_var, expected in test_cases:
            # Act
            result = sanitize_env_var(input_var)
            
            # Assert
            assert result == expected, f"For input '{input_var}', expected '{expected}', got '{result}'"
            # Check that result contains only valid characters (letters, numbers, underscores)
            assert all(c.isalnum() or c == '_' for c in result), f"Result '{result}' contains invalid characters"
    
    def test_sanitize_env_var_edge_cases(self):
        """Test edge cases for sanitize_env_var function."""
        # Test None input
        with pytest.raises(TypeError):
            sanitize_env_var(None)
        
        # Test non-string input
        with pytest.raises(TypeError):
            sanitize_env_var(123)
        
        # Test empty string
        result = sanitize_env_var("")
        assert result == ""
        
        # Test whitespace only
        result = sanitize_env_var("   ")
        assert result == ""
        
        # Test very long variable name
        long_var = "a" * 1000
        result = sanitize_env_var(long_var)
        assert result == "A" * 1000
        
        # Test unicode characters
        result = sanitize_env_var("café")
        assert result == "CAF_"
    
    def test_sanitize_env_var_preserves_underscores(self):
        """Test that sanitize_env_var preserves underscores in valid positions."""
        # Arrange
        test_cases = [
            ("valid_var_name", "VALID_VAR_NAME"),
            ("_private_var", "_PRIVATE_VAR"),
            ("var_with_trailing_", "VAR_WITH_TRAILING_"),
            ("multiple__underscores", "MULTIPLE__UNDERSCORES"),
            ("___many_underscores___", "___MANY_UNDERSCORES___"),
        ]
        
        for input_var, expected in test_cases:
            # Act
            result = sanitize_env_var(input_var)
            
            # Assert
            assert result == expected, f"For input '{input_var}', expected '{expected}', got '{result}'"


class TestDeepMergeDicts:
    """Test class for deep_merge_dicts function."""
    
    def test_deep_merge_dicts_merges_nested(self):
        """Test that deep_merge_dicts correctly merges nested dictionaries."""
        # Arrange
        dict1 = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "credentials": {
                    "username": "admin"
                }
            },
            "logging": {
                "level": "INFO",
                "file": "/var/log/app.log"
            },
            "unique_to_dict1": "value1"
        }
        
        dict2 = {
            "database": {
                "port": 3306,  # This should override dict1's port
                "name": "production",  # This should be added
                "credentials": {
                    "password": "secret"  # This should be added to nested dict
                }
            },
            "api": {
                "endpoint": "https://api.example.com",
                "timeout": 30
            },
            "unique_to_dict2": "value2"
        }
        
        # Act
        result = deep_merge_dicts(dict1, dict2)
        
        # Assert
        expected = {
            "database": {
                "host": "localhost",
                "port": 3306,  # Overridden from dict2
                "name": "production",  # Added from dict2
                "credentials": {
                    "username": "admin",  # From dict1
                    "password": "secret"  # From dict2
                }
            },
            "logging": {
                "level": "INFO",
                "file": "/var/log/app.log"
            },
            "api": {
                "endpoint": "https://api.example.com",
                "timeout": 30
            },
            "unique_to_dict1": "value1",
            "unique_to_dict2": "value2"
        }
        
        assert result == expected, f"Expected {expected}, got {result}"
    
    def test_deep_merge_dicts_handles_overlapping_keys(self):
        """Test that deep_merge_dicts handles overlapping keys correctly."""
        # Arrange
        dict1 = {
            "config": {
                "debug": True,
                "features": {
                    "auth": True,
                    "cache": False
                }
            },
            "version": "1.0.0"
        }
        
        dict2 = {
            "config": {
                "debug": False,  # Override
                "timeout": 60,   # Add new
                "features": {
                    "cache": True,   # Override nested
                    "monitoring": True  # Add new nested
                }
            },
            "environment": "production"  # Add new top-level
        }
        
        # Act
        result = deep_merge_dicts(dict1, dict2)
        
        # Assert
        expected = {
            "config": {
                "debug": False,
                "timeout": 60,
                "features": {
                    "auth": True,
                    "cache": True,
                    "monitoring": True
                }
            },
            "version": "1.0.0",
            "environment": "production"
        }
        
        assert result == expected
    
    def test_deep_merge_dicts_preserves_original_dicts(self):
        """Test that deep_merge_dicts does not modify the original dictionaries."""
        # Arrange
        dict1 = {"a": {"b": 1}}
        dict2 = {"a": {"c": 2}}
        dict1_copy = dict1.copy()
        dict2_copy = dict2.copy()
        
        # Act
        result = deep_merge_dicts(dict1, dict2)
        
        # Assert
        assert dict1 == dict1_copy, "Original dict1 should not be modified"
        assert dict2 == dict2_copy, "Original dict2 should not be modified"
        assert result == {"a": {"b": 1, "c": 2}}, "Result should contain merged values"
    
    def test_deep_merge_dicts_handles_empty_dicts(self):
        """Test that deep_merge_dicts handles empty dictionaries correctly."""
        # Test empty dict1
        result = deep_merge_dicts({}, {"a": 1})
        assert result == {"a": 1}
        
        # Test empty dict2
        result = deep_merge_dicts({"a": 1}, {})
        assert result == {"a": 1}
        
        # Test both empty
        result = deep_merge_dicts({}, {})
        assert result == {}
    
    def test_deep_merge_dicts_handles_non_dict_values(self):
        """Test that deep_merge_dicts handles non-dict values correctly."""
        # Arrange
        dict1 = {
            "string": "value1",
            "number": 42,
            "boolean": True,
            "list": [1, 2, 3],
            "none": None
        }
        
        dict2 = {
            "string": "value2",  # Override
            "number": 100,       # Override
            "boolean": False,    # Override
            "list": [4, 5, 6],  # Override
            "none": "not_none"   # Override
        }
        
        # Act
        result = deep_merge_dicts(dict1, dict2)
        
        # Assert
        expected = {
            "string": "value2",
            "number": 100,
            "boolean": False,
            "list": [4, 5, 6],
            "none": "not_none"
        }
        
        assert result == expected
    
    def test_deep_merge_dicts_handles_type_conflicts(self):
        """Test that deep_merge_dicts handles type conflicts correctly."""
        # Arrange - dict1 has dict, dict2 has non-dict value
        dict1 = {"config": {"debug": True}}
        dict2 = {"config": "production"}
        
        # Act
        result = deep_merge_dicts(dict1, dict2)
        
        # Assert - dict2 value should override dict1 value
        assert result == {"config": "production"}
        
        # Test reverse scenario
        dict1 = {"config": "development"}
        dict2 = {"config": {"debug": False}}
        
        result = deep_merge_dicts(dict1, dict2)
        assert result == {"config": {"debug": False}}
    
    def test_deep_merge_dicts_deeply_nested(self):
        """Test that deep_merge_dicts works with deeply nested structures."""
        # Arrange
        dict1 = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "value": "deep1"
                        }
                    }
                }
            }
        }
        
        dict2 = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "another_value": "deep2"
                        }
                    }
                }
            }
        }
        
        # Act
        result = deep_merge_dicts(dict1, dict2)
        
        # Assert
        expected = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "value": "deep1",
                            "another_value": "deep2"
                        }
                    }
                }
            }
        }
        
        assert result == expected


class TestParseIsoDatetime:
    """Test class for parse_iso_datetime function."""
    
    def test_parse_iso_datetime_valid_and_invalid(self):
        """Test parse_iso_datetime with valid and invalid ISO 8601 strings."""
        # Test valid ISO 8601 strings
        valid_test_cases = [
            ("2024-01-15T10:30:45Z", datetime(2024, 1, 15, 10, 30, 45, tzinfo=timezone.utc)),
            ("2024-01-15T10:30:45+00:00", datetime(2024, 1, 15, 10, 30, 45, tzinfo=timezone.utc)),
            ("2024-01-15T10:30:45.123456Z", datetime(2024, 1, 15, 10, 30, 45, 123456, tzinfo=timezone.utc)),
            ("2024-01-15T10:30:45.123Z", datetime(2024, 1, 15, 10, 30, 45, 123000, tzinfo=timezone.utc)),
            ("2024-01-15T10:30:45", datetime(2024, 1, 15, 10, 30, 45)),
            ("2024-01-15T10:30:45.123", datetime(2024, 1, 15, 10, 30, 45, 123000)),
            ("2024-12-31T23:59:59Z", datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc)),
            ("2024-02-29T12:00:00Z", datetime(2024, 2, 29, 12, 0, 0, tzinfo=timezone.utc)),  # Leap year
        ]
        
        for iso_string, expected_datetime in valid_test_cases:
            # Act
            result = parse_iso_datetime(iso_string)
            
            # Assert
            assert result == expected_datetime, f"For input '{iso_string}', expected {expected_datetime}, got {result}"
            assert isinstance(result, datetime), f"Result should be datetime object, got {type(result)}"
        
        # Test invalid ISO 8601 strings
        invalid_test_cases = [
            "2024-01-15",  # Date only
            "10:30:45",    # Time only
            "2024/01/15T10:30:45Z",  # Wrong date separator
            "2024-01-15 10:30:45",   # Space instead of T
            "2024-13-15T10:30:45Z",  # Invalid month
            "2024-01-32T10:30:45Z",  # Invalid day
            "2024-01-15T25:30:45Z",  # Invalid hour
            "2024-01-15T10:60:45Z",  # Invalid minute
            "2024-01-15T10:30:60Z",  # Invalid second
            "2024-01-15T10:30:45X",  # Invalid timezone
            "not-a-date",            # Completely invalid
            "",                      # Empty string
            "2024-01-15T10:30:45.1234567Z",  # Too many microseconds
            "2024-02-30T12:00:00Z",  # Invalid date (Feb 30)
            "2023-02-29T12:00:00Z",  # Invalid date (Feb 29 in non-leap year)
        ]
        
        for invalid_string in invalid_test_cases:
            # Act & Assert
            with pytest.raises(ValueError, match=r".*"):
                parse_iso_datetime(invalid_string)
    
    def test_parse_iso_datetime_timezone_handling(self):
        """Test that parse_iso_datetime correctly handles various timezone formats."""
        # Test different timezone formats
        timezone_test_cases = [
            ("2024-01-15T10:30:45Z", timezone.utc),
            ("2024-01-15T10:30:45+00:00", timezone.utc),
            ("2024-01-15T10:30:45-00:00", timezone.utc),
            ("2024-01-15T10:30:45+05:30", timezone(timedelta(hours=5, minutes=30))),
            ("2024-01-15T10:30:45-08:00", timezone(timedelta(hours=-8))),
            ("2024-01-15T10:30:45+12:00", timezone(timedelta(hours=12))),
            ("2024-01-15T10:30:45-12:00", timezone(timedelta(hours=-12))),
        ]
        
        for iso_string, expected_tz in timezone_test_cases:
            # Act
            result = parse_iso_datetime(iso_string)
            
            # Assert
            assert result.tzinfo == expected_tz, f"For input '{iso_string}', expected timezone {expected_tz}, got {result.tzinfo}"
    
    def test_parse_iso_datetime_microsecond_precision(self):
        """Test that parse_iso_datetime handles microsecond precision correctly."""
        # Test cases with different microsecond precision
        microsecond_test_cases = [
            ("2024-01-15T10:30:45.1Z", 100000),
            ("2024-01-15T10:30:45.12Z", 120000),
            ("2024-01-15T10:30:45.123Z", 123000),
            ("2024-01-15T10:30:45.1234Z", 123400),
            ("2024-01-15T10:30:45.12345Z", 123450),
            ("2024-01-15T10:30:45.123456Z", 123456),
        ]
        
        for iso_string, expected_microseconds in microsecond_test_cases:
            # Act
            result = parse_iso_datetime(iso_string)
            
            # Assert
            assert result.microsecond == expected_microseconds, f"For input '{iso_string}', expected {expected_microseconds} microseconds, got {result.microsecond}"
    
    def test_parse_iso_datetime_edge_cases(self):
        """Test edge cases for parse_iso_datetime function."""
        # Test None input
        with pytest.raises(TypeError):
            parse_iso_datetime(None)
        
        # Test non-string input
        with pytest.raises(TypeError):
            parse_iso_datetime(123)
        
        # Test minimum and maximum valid dates
        min_date = parse_iso_datetime("0001-01-01T00:00:00Z")
        assert min_date.year == 1
        
        max_date = parse_iso_datetime("9999-12-31T23:59:59Z")
        assert max_date.year == 9999
        
        # Test leap year handling
        leap_year_date = parse_iso_datetime("2024-02-29T12:00:00Z")
        assert leap_year_date.day == 29
        
        # Test non-leap year (should fail)
        with pytest.raises(ValueError):
            parse_iso_datetime("2023-02-29T12:00:00Z")


class TestFlattenDict:
    """Test class for flatten_dict function."""
    
    def test_flatten_dict_handles_nested(self):
        """Test flatten_dict flattens nested dictionaries into a single-level dict with compound keys."""
        # Arrange
        nested_dict = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "credentials": {
                    "username": "admin",
                    "password": "secret"
                }
            },
            "logging": {
                "level": "INFO",
                "file": "/var/log/app.log"
            },
            "top_level": "value"
        }
        
        # Act
        result = flatten_dict(nested_dict)
        
        # Assert
        expected = {
            "database.host": "localhost",
            "database.port": 5432,
            "database.credentials.username": "admin",
            "database.credentials.password": "secret",
            "logging.level": "INFO",
            "logging.file": "/var/log/app.log",
            "top_level": "value"
        }
        
        assert result == expected, f"Expected {expected}, got {result}"
        
        # Verify that the result is a flat dictionary
        for key in result.keys():
            assert not isinstance(result[key], dict), f"Value for key '{key}' should not be a dict"
    
    def test_flatten_dict_custom_separator(self):
        """Test flatten_dict with custom separator for compound keys."""
        # Arrange
        nested_dict = {
            "section": {
                "subsection": {
                    "key": "value"
                }
            }
        }
        
        # Test with different separators
        separators = ["_", "/", ":", "->", "__"]
        
        for separator in separators:
            # Act
            result = flatten_dict(nested_dict, separator=separator)
            
            # Assert
            expected_key = f"section{separator}subsection{separator}key"
            expected = {expected_key: "value"}
            assert result == expected, f"With separator '{separator}', expected {expected}, got {result}"
    
    def test_flatten_dict_deeply_nested(self):
        """Test flatten_dict with deeply nested structures."""
        # Arrange
        deeply_nested = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "level5": {
                                "deep_value": "found"
                            }
                        }
                    }
                }
            }
        }
        
        # Act
        result = flatten_dict(deeply_nested)
        
        # Assert
        expected = {
            "level1.level2.level3.level4.level5.deep_value": "found"
        }
        
        assert result == expected
    
    def test_flatten_dict_mixed_types(self):
        """Test flatten_dict with mixed data types."""
        # Arrange
        mixed_dict = {
            "string": "text",
            "number": 42,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3],
            "nested": {
                "inner_string": "inner_text",
                "inner_number": 100,
                "inner_list": ["a", "b", "c"]
            }
        }
        
        # Act
        result = flatten_dict(mixed_dict)
        
        # Assert
        expected = {
            "string": "text",
            "number": 42,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3],
            "nested.inner_string": "inner_text",
            "nested.inner_number": 100,
            "nested.inner_list": ["a", "b", "c"]
        }
        
        assert result == expected
    
    def test_flatten_dict_empty_dicts(self):
        """Test flatten_dict with empty dictionaries."""
        # Test completely empty dict
        result = flatten_dict({})
        assert result == {}
        
        # Test dict with empty nested dict
        nested_with_empty = {
            "empty_nested": {},
            "normal_key": "value"
        }
        result = flatten_dict(nested_with_empty)
        expected = {"normal_key": "value"}
        assert result == expected
    
    def test_flatten_dict_key_conflicts(self):
        """Test flatten_dict handles potential key conflicts."""
        # Arrange - dict with keys that could conflict after flattening
        conflict_dict = {
            "config": {
                "debug": True
            },
            "config.debug": False  # This could conflict with flattened key
        }
        
        # Act
        result = flatten_dict(conflict_dict)
        
        # Assert - later keys should override earlier ones or handle conflicts gracefully
        assert "config.debug" in result
        # The exact behavior depends on implementation, but it should be consistent
        
    def test_flatten_dict_preserves_key_order(self):
        """Test that flatten_dict preserves key order when possible."""
        # Arrange
        ordered_dict = {
            "first": "value1",
            "second": {
                "nested_first": "nested_value1",
                "nested_second": "nested_value2"
            },
            "third": "value3"
        }
        
        # Act
        result = flatten_dict(ordered_dict)
        
        # Assert
        result_keys = list(result.keys())
        expected_keys = ["first", "second.nested_first", "second.nested_second", "third"]
        assert result_keys == expected_keys, f"Expected key order {expected_keys}, got {result_keys}"
    
    def test_flatten_dict_special_characters_in_keys(self):
        """Test flatten_dict with special characters in keys."""
        # Arrange
        special_keys_dict = {
            "key-with-dashes": "value1",
            "key_with_underscores": "value2",
            "key.with.dots": "value3",
            "key with spaces": "value4",
            "nested": {
                "special-key": "nested_value"
            }
        }
        
        # Act
        result = flatten_dict(special_keys_dict)
        
        # Assert
        expected = {
            "key-with-dashes": "value1",
            "key_with_underscores": "value2",
            "key.with.dots": "value3",
            "key with spaces": "value4",
            "nested.special-key": "nested_value"
        }
        
        assert result == expected
    
    def test_flatten_dict_numeric_keys(self):
        """Test flatten_dict with numeric keys."""
        # Arrange
        numeric_keys_dict = {
            1: "one",
            2: {
                3: "three",
                4: "four"
            },
            "string_key": "string_value"
        }
        
        # Act
        result = flatten_dict(numeric_keys_dict)
        
        # Assert
        expected = {
            1: "one",
            "2.3": "three",
            "2.4": "four",
            "string_key": "string_value"
        }
        
        assert result == expected
    
    def test_flatten_dict_edge_cases(self):
        """Test edge cases for flatten_dict function."""
        # Test None input
        with pytest.raises(TypeError):
            flatten_dict(None)
        
        # Test non-dict input
        with pytest.raises(TypeError):
            flatten_dict("not a dict")
        
        # Test dict with None values
        dict_with_none = {
            "key1": None,
            "nested": {
                "key2": None
            }
        }
        result = flatten_dict(dict_with_none)
        expected = {
            "key1": None,
            "nested.key2": None
        }
        assert result == expected