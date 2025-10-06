"""Expose the CLI package version."""

from __future__ import annotations

from importlib import metadata


def _resolve_version() -> str:
    """Return the installed package version or fall back to the project default."""

    try:
        return metadata.version("labarchives-mcp-pol")
    except metadata.PackageNotFoundError:
        # Fallback for development checkouts where the distribution is not installed.
        return "0.2.1"


__version__ = _resolve_version()
