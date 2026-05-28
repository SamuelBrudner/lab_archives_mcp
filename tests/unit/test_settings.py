from __future__ import annotations

from pathlib import Path

import pytest

from labarchives_mcp.auth import Credentials
from labarchives_mcp.settings import (
    CONFIG_PATH_ENV,
    STATE_DIR_ENV,
    UPLOAD_ENABLED_ENV,
    VECTOR_CONFIG_ENV,
    VECTOR_CONFIG_PATH_ENV,
    Settings,
)


def _write_secrets(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("""
LABARCHIVES_AKID: example-akid
LABARCHIVES_PASSWORD: example-pass
LABARCHIVES_REGION: https://api.labarchives.com
PINECONE_API_KEY: pinecone-key
PINECONE_ENVIRONMENT: us-west1-gcp
""".strip())


def test_settings_from_env_centralizes_runtime_config(tmp_path: Path) -> None:
    secrets_path = tmp_path / "conf" / "secrets.yml"
    state_dir = tmp_path / "state"
    _write_secrets(secrets_path)

    settings = Settings.from_env(
        environ={
            CONFIG_PATH_ENV: str(secrets_path),
            UPLOAD_ENABLED_ENV: "false",
            STATE_DIR_ENV: str(state_dir),
            VECTOR_CONFIG_ENV: "ci",
            VECTOR_CONFIG_PATH_ENV: str(tmp_path / "vector-conf"),
        }
    )

    assert settings.secrets_path == secrets_path
    assert settings.state_dir == state_dir
    assert settings.upload_enabled is False
    assert settings.vector_config_name == "ci"
    assert settings.vector_config_path == tmp_path / "vector-conf"
    assert isinstance(settings.credentials, Credentials)
    assert settings.credentials.akid == "example-akid"
    assert str(settings.credentials.region) == "https://api.labarchives.com/"
    assert settings.secrets["PINECONE_API_KEY"] == "pinecone-key"


def test_settings_defaults_uploads_enabled(tmp_path: Path) -> None:
    secrets_path = tmp_path / "secrets.yml"
    _write_secrets(secrets_path)

    settings = Settings.from_env(credentials_path=secrets_path, environ={})

    assert settings.upload_enabled is True


def test_settings_rejects_invalid_upload_flag(tmp_path: Path) -> None:
    secrets_path = tmp_path / "secrets.yml"
    _write_secrets(secrets_path)

    with pytest.raises(ValueError, match=UPLOAD_ENABLED_ENV):
        Settings.from_env(
            credentials_path=secrets_path,
            environ={UPLOAD_ENABLED_ENV: "sometimes"},
        )
