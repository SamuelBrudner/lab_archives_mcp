# setuptools>=65.0.0 - Core Python packaging library for building and distributing Python projects
import os

from setuptools import find_packages
from setuptools import setup


# Read the long description from README.md to provide detailed package description for PyPI
def read_long_description():
    """Read the long description from README.md file."""
    readme_path = os.path.join(os.path.dirname(__file__), "..", "..", "README.md")
    try:
        with open(readme_path, "r", encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return "LabArchives MCP Server for AI integration - A Model Context Protocol server that provides read-only access to LabArchives electronic lab notebook data for AI applications."


# Global variable for long description
long_description = read_long_description()


# Main setuptools function that configures the package metadata, dependencies, and entry points
def setup_package():
    """Configure and set up the LabArchives MCP Server CLI package."""

    # Runtime dependencies as specified in technical requirements
    install_requires = [
        "mcp>=1.0.0",  # Official MCP Python SDK for protocol implementation
        "fastmcp>=1.0.0",  # FastMCP server framework for MCP protocol handling
        "pydantic>=2.11.7",  # Data validation with JSON Schema support
        "pydantic-settings>=2.10.1",  # Settings management with CLI support
        "requests>=2.31.0",  # HTTP library for LabArchives API calls
        "urllib3>=2.0.0",  # HTTP client dependency for secure connections
    ]

    # Development dependencies for testing, formatting, and type checking
    extras_require = {
        "dev": [
            "pytest>=7.0.0",  # Testing framework for comprehensive test coverage
            "black>=23.0.0",  # Code formatting for consistent style
            "mypy>=1.0.0",  # Type checking for enhanced code quality
        ]
    }

    # PyPI classifiers for package categorization and compatibility
    classifiers = [
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Communications :: Chat",
        "Operating System :: OS Independent",
        "Environment :: Console",
        "Natural Language :: English",
    ]

    # Entry points for console script registration
    entry_points = {
        "console_scripts": [
            "labarchives-mcp=main:main",  # Register the CLI command for global access
        ],
    }

    # Main setup configuration
    setup(
        # Package identification and metadata
        name="labarchives-mcp",
        version="0.1.0",
        description="LabArchives MCP Server for AI integration",
        long_description=long_description,
        long_description_content_type="text/markdown",
        # Author and project information
        author="Lab Team",
        author_email="team@lab.org",
        url="https://github.com/org/labarchives-mcp-server",
        # Package discovery and structure
        packages=find_packages(where="."),
        package_dir={"": "."},
        # Entry points for CLI registration
        entry_points=entry_points,
        # Dependencies and requirements
        install_requires=install_requires,
        extras_require=extras_require,
        python_requires=">=3.11",
        # Package metadata and classification
        classifiers=classifiers,
        # Package data inclusion
        include_package_data=True,
        # Additional metadata
        keywords="mcp, labarchives, ai, model-context-protocol, electronic-lab-notebook, research",
        project_urls={
            "Documentation": "https://github.com/org/labarchives-mcp-server/blob/main/README.md",
            "Source": "https://github.com/org/labarchives-mcp-server",
            "Tracker": "https://github.com/org/labarchives-mcp-server/issues",
        },
        # License and legal information
        license="MIT",
        # Platform compatibility
        platforms=["any"],
        # Additional options for setuptools
        zip_safe=False,  # Ensure package is installed as directory for proper file access
    )


# Execute setup when script is run directly
if __name__ == "__main__":
    setup_package()
