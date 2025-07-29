"""
LabArchives MCP Server - A Model Context Protocol server for LabArchives integration.

This package provides a command-line interface and server implementation for
accessing LabArchives electronic lab notebook data through the MCP protocol.
"""

__version__ = "0.1.0"
__author__ = "LabArchives MCP Team"
__email__ = "team@labarchives.com"

# Import main function for console script entry point
from .main import main


__all__ = ["main", "__version__"]
