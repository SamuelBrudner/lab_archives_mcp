"""Sanity tests for the LabArchives MCP PoL package skeleton."""

from __future__ import annotations

from pathlib import Path

import pytest

from labarchives_mcp import run_server
from labarchives_mcp.auth import Credentials


def test_credentials_from_file_missing_file(tmp_path: Path) -> None:
    """Given no secrets file, when `Credentials.from_file()` runs,
    then a `FileNotFoundError` is raised."""
    missing_path = tmp_path / "conf" / "secrets.yml"
    with pytest.raises(FileNotFoundError):
        Credentials.from_file(missing_path)


def test_credentials_from_file_missing_values(tmp_path: Path) -> None:
    """Given a secrets file missing required keys, when `Credentials.from_file()`
    executes, then it raises a validation error."""
    conf_dir = tmp_path / "conf"
    conf_dir.mkdir(parents=True, exist_ok=True)
    secrets_file = conf_dir / "secrets.yml"
    secrets_file.write_text("LABARCHIVES_AKID: example-akid\n")

    with pytest.raises(ValueError, match="Missing LabArchives secrets"):
        Credentials.from_file(secrets_file)


def test_credentials_from_file_success(tmp_path: Path) -> None:
    """Given a fully populated secrets file, when `Credentials.from_file()` runs,
    then it returns a validated instance."""
    conf_dir = tmp_path / "conf"
    conf_dir.mkdir(parents=True, exist_ok=True)
    secrets_file = conf_dir / "secrets.yml"
    secrets_file.write_text(
        """
LABARCHIVES_AKID: example-akid
LABARCHIVES_PASSWORD: example-pass
LABARCHIVES_REGION: https://api.labarchives.com
""".strip()
    )

    creds = Credentials.from_file(secrets_file)

    assert creds.akid == "example-akid"
    assert creds.password == "example-pass"
    assert str(creds.region) == "https://api.labarchives.com/"


@pytest.mark.asyncio()  # type: ignore[misc]
async def test_run_server_not_implemented() -> None:
    """Given the PoL state, when `run_server()` is awaited,
    then a `NotImplementedError` surfaces."""
    with pytest.raises(NotImplementedError):
        await run_server()
