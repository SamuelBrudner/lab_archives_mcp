#!/usr/bin/env python3
"""
Console script entry point for LabArchives MCP Server.

This module provides a proper entry point for the console script that
handles import path setup and module loading correctly.
"""

import sys
import os
import subprocess


def main():
    """Main entry point for the console script."""
    # Get the directory where this script is located (should be the package root)
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Run the main module using python -m to ensure proper package context
    try:
        # Change to the package directory and run as module
        result = subprocess.run([sys.executable, '-m', 'main'] + sys.argv[1:], cwd=script_dir)
        return result.returncode
    except Exception as e:
        print(f"Error running labarchives-mcp: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
