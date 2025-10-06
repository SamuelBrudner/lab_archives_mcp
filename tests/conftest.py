"""Pytest configuration for test discovery, env, and fixtures.

This file ensures that:
- `src/` is importable
- Integration tests can read credentials from `conf/secrets.yml`
- DVC uses a local, writable site cache to avoid macOS permission issues
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure src directory is in path for imports
repo_root = Path(__file__).parent.parent
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


def _load_secrets_into_env() -> None:
    """Load secrets from conf/secrets.yml into environment if not set.

    Only sets variables that are currently unset to avoid overriding user-provided
    environment. This supports running integration tests locally without manual
    export of credentials.
    """
    secrets_path = repo_root / "conf" / "secrets.yml"
    if not secrets_path.exists():
        return

    try:
        import yaml  # type: ignore[import-untyped]
    except Exception:
        # If PyYAML is not available, silently skip (tests may still run)
        return

    try:
        data = yaml.safe_load(secrets_path.read_text()) or {}
    except Exception:
        return

    # Map YAML keys to environment variable names
    key_map = {
        "OPENAI_API_KEY": "OPENAI_API_KEY",
        "PINECONE_API_KEY": "PINECONE_API_KEY",
        "PINECONE_ENVIRONMENT": "PINECONE_ENVIRONMENT",
        # LabArchives (used by MCP integration tests/scripts)
        "LABARCHIVES_AKID": "LABARCHIVES_AKID",
        "LABARCHIVES_PASSWORD": "LABARCHIVES_PASSWORD",
        "LABARCHIVES_REGION": "LABARCHIVES_REGION",
        "LABARCHIVES_UID": "LABARCHIVES_UID",
    }

    for yaml_key, env_key in key_map.items():
        if os.environ.get(env_key):
            continue
        value = data.get(yaml_key)
        if value:
            os.environ[env_key] = str(value)


def _ensure_local_dvc_site_cache() -> None:
    """Ensure DVC uses a local, writable site cache directory.

    On some macOS setups, DVC defaults to `/Library/Caches/...` which may be
    unwritable in sandboxed environments. Point it to a repo-local directory.
    """
    cache_dir = os.environ.get("DVC_SITE_CACHE_DIR")
    if not cache_dir:
        cache_dir = str(repo_root / ".dvc_site_cache")
        os.environ["DVC_SITE_CACHE_DIR"] = cache_dir
    Path(cache_dir).mkdir(parents=True, exist_ok=True)


def pytest_sessionstart(session: object) -> None:
    _ensure_local_dvc_site_cache()
    _load_secrets_into_env()
