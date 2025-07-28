#!/usr/bin/env python3
"""
Entry point for the LabArchives MCP Server CLI when run as a module.

This allows the package to be executed with:
    python -m labarchives_mcp

Usage:
    python -m labarchives_mcp --help
    python -m labarchives_mcp start --username user --api-key key
"""

from main import main

if __name__ == "__main__":
    main()
