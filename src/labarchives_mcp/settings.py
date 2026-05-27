"""Runtime configuration for the LabArchives MCP server."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, Field

from .auth import Credentials
from .auth_loader import (
    credentials_kwargs,
    load_normalized_secrets,
    require_secrets,
    resolve_secrets_location,
)

CONFIG_PATH_ENV = "LABARCHIVES_CONFIG_PATH"
UPLOAD_ENABLED_ENV = "LABARCHIVES_ENABLE_UPLOAD"
STATE_DIR_ENV = "LABARCHIVES_STATE_DIR"
VECTOR_CONFIG_ENV = "LABARCHIVES_VECTOR_CONFIG"
VECTOR_CONFIG_PATH_ENV = "LABARCHIVES_VECTOR_CONFIG_PATH"
DEFAULT_SECRETS_PATH = Path("conf/secrets.yml")


def default_state_dir() -> Path:
    """Return the default cross-repository state directory."""
    return Path.home() / ".labarchives_state"


def _setting_path(raw: str | Path) -> Path:
    return Path(raw).expanduser()


def _parse_bool(value: str | None, *, default: bool, name: str) -> bool:
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be one of true/false, 1/0, yes/no, or on/off.")


def _secrets_spec(
    environ: Mapping[str, str], credentials_path: str | Path | None
) -> tuple[str | Path, str]:
    if credentials_path is not None:
        return credentials_path, "path"
    if env_path := environ.get(CONFIG_PATH_ENV):
        return env_path, CONFIG_PATH_ENV
    return DEFAULT_SECRETS_PATH, "default"


class Settings(BaseModel):
    """Inspectable runtime settings loaded once at server startup."""

    credentials: Credentials = Field(description="LabArchives API credentials")
    secrets_path: Path = Field(description="Resolved path to the secrets file")
    state_dir: Path = Field(default_factory=default_state_dir, description="State storage path")
    upload_enabled: bool = Field(
        default=True,
        description="Whether LabArchives write/upload tools should be registered",
    )
    vector_config_name: str = Field(
        default="default",
        description="Hydra vector-search config name to load without the .yaml suffix",
    )
    vector_config_path: Path | None = Field(
        default=None,
        description="Optional directory containing vector-search Hydra configs",
    )
    secrets: dict[str, Any] = Field(
        default_factory=dict,
        repr=False,
        description="Normalized key/value secrets loaded from the configured secrets file",
    )

    @classmethod
    def from_env(
        cls,
        *,
        credentials_path: str | Path | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> Self:
        """Load settings from process environment and the configured secrets file."""
        env = os.environ if environ is None else environ
        secrets_spec, source = _secrets_spec(env, credentials_path)

        try:
            resolved_path = resolve_secrets_location(secrets_spec, source=source)
        except FileNotFoundError:
            # Preserve test and extension points that monkeypatch Credentials.from_file
            # while still failing loudly for the real loader.
            credentials = (
                Credentials.from_file()
                if source == "default"
                else Credentials.from_file(secrets_spec)
            )
            resolved_path = _setting_path(secrets_spec)
            secrets: dict[str, Any] = {}
        else:
            secrets = load_normalized_secrets(resolved_path)
            require_secrets(secrets)
            credentials = Credentials(**credentials_kwargs(secrets))

        state_dir_raw = env.get(STATE_DIR_ENV)
        state_dir = _setting_path(state_dir_raw) if state_dir_raw else default_state_dir()
        upload_enabled = _parse_bool(
            env.get(UPLOAD_ENABLED_ENV),
            default=True,
            name=UPLOAD_ENABLED_ENV,
        )
        vector_config_name = env.get(VECTOR_CONFIG_ENV, "default").strip() or "default"
        vector_config_path_raw = env.get(VECTOR_CONFIG_PATH_ENV)
        vector_config_path = (
            _setting_path(vector_config_path_raw) if vector_config_path_raw else None
        )

        return cls(
            credentials=credentials,
            secrets_path=resolved_path,
            state_dir=state_dir,
            upload_enabled=upload_enabled,
            vector_config_name=vector_config_name,
            vector_config_path=vector_config_path,
            secrets=secrets,
        )
