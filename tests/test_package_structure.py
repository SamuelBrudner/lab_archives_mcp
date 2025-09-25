"""Sanity tests for the LabArchives MCP PoL package skeleton."""

from __future__ import annotations

from pathlib import Path

import pytest

from labarchives_mcp import run_server
from labarchives_mcp.auth import Credentials


def test_credentials_from_file_missing_file(tmp_path: Path) -> None:
    """Missing secrets file should raise a FileNotFoundError."""
    missing_path = tmp_path / "conf" / "secrets.yml"
    with pytest.raises(FileNotFoundError):
        Credentials.from_file(missing_path)


def test_credentials_from_file_missing_values(tmp_path: Path) -> None:
    """Secrets file without required keys should fail fast."""
    conf_dir = tmp_path / "conf"
    conf_dir.mkdir(parents=True, exist_ok=True)
    secrets_file = conf_dir / "secrets.yml"
    secrets_file.write_text("LABARCHIVES_AKID: example-akid\n")

    with pytest.raises(ValueError, match="Missing LabArchives secrets"):
        Credentials.from_file(secrets_file)


def test_credentials_from_file_success(tmp_path: Path) -> None:
    """Valid secrets file loads into a `Credentials` instance."""
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
    """`run_server` is a PoL stub and must raise until implemented."""
    with pytest.raises(NotImplementedError):
        await run_server()
