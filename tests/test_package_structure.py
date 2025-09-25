"""Sanity tests for the LabArchives MCP PoL package skeleton."""

from __future__ import annotations

import pytest

from labarchives_mcp import run_server
from labarchives_mcp.auth import Credentials


def test_credentials_from_env_missing_values() -> None:
    """`Credentials.from_env` should fail fast when variables are missing."""
    with pytest.raises(ValueError, match="Missing LabArchives environment variables"):
        Credentials.from_env({})


@pytest.mark.asyncio
async def test_run_server_not_implemented() -> None:
    """`run_server` is a PoL stub and must raise until implemented."""
    with pytest.raises(NotImplementedError):
        await run_server()
