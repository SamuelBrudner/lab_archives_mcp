"""
LabArchives MCP Server - Data Models Package

This package contains all data models and value objects used throughout the
LabArchives MCP Server, including scoping models and other structured data
representations.
"""

# Import scoping models
from .scoping import FolderPath

__all__ = ['FolderPath']