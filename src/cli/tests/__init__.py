"""
Test suite initialization for the LabArchives MCP Server CLI.

This module marks the 'tests' directory as a Python package, enabling pytest and other 
test runners to discover and execute all test modules and fixtures within the test suite.

The test suite follows a structured approach with:
- Unit tests for individual components
- Integration tests for service interactions  
- End-to-end tests for complete workflows
- Shared fixtures and test data in conftest.py

Test discovery is handled automatically by pytest when this package is properly initialized.
"""

# This file intentionally left minimal to serve as a package marker.
# Shared test fixtures and configuration are managed in conftest.py
# according to pytest best practices.