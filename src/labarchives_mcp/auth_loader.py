"""Shared secrets-file loading helpers for LabArchives credentials."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from omegaconf import OmegaConf
from pydantic import HttpUrl


def repo_root() -> Path:
    """Return the project root used for resolving relative secrets files."""
    return Path(__file__).resolve().parents[2]


def candidate_paths(raw: Path) -> tuple[Path, ...]:
    """Return the ordered candidate paths for a secrets-file reference."""
    if raw.is_absolute():
        return (raw,)
    return (Path.cwd() / raw, repo_root() / raw)


def existing_unique_paths(candidates: tuple[Path, ...]) -> tuple[Path, ...]:
    """Return existing candidates with duplicates removed after resolution."""
    existing: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if not candidate.exists():
            continue
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        existing.append(resolved)
    return tuple(existing)


def missing_secrets_message(raw: Path, source: str, candidates: tuple[Path, ...]) -> str:
    """Build the fail-loud message for a missing secrets file."""
    checked = "\n".join(str(candidate) for candidate in candidates)
    return f"Secrets file not found for {source}: {raw}\nChecked:\n{checked}"


def multiple_secrets_message(raw: Path, source: str, existing: tuple[Path, ...]) -> str:
    """Build the fail-loud message for ambiguous secrets-file resolution."""
    joined = ", ".join(str(path) for path in existing)
    return f"Multiple secrets files found for {source}: {raw}. Candidates: {joined}"


def resolve_secrets_location(spec: Path | str, *, source: str) -> Path:
    """Resolve a secrets file path or raise when the location is missing/ambiguous."""
    raw = Path(spec).expanduser()
    candidates = candidate_paths(raw)
    existing = existing_unique_paths(candidates)
    if len(existing) == 1:
        return existing[0]
    if not existing:
        raise FileNotFoundError(missing_secrets_message(raw, source, candidates))
    raise RuntimeError(multiple_secrets_message(raw, source, existing))


def load_normalized_secrets(location: Path) -> dict[str, Any]:
    """Load a YAML secrets mapping with uppercase keys."""
    raw_config = OmegaConf.load(location)
    config = OmegaConf.to_container(raw_config, resolve=True)
    if not isinstance(config, dict):
        raise ValueError("Secrets file must contain a mapping of credential keys.")
    return {str(key).upper(): value for key, value in config.items()}


def require_secrets(normalized: dict[str, Any]) -> None:
    """Require the LabArchives credential keys used by the MCP server."""
    required_keys = ["LABARCHIVES_AKID", "LABARCHIVES_PASSWORD", "LABARCHIVES_REGION"]
    missing = [key for key in required_keys if not normalized.get(key)]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Missing LabArchives secrets: {joined}")


def optional_str(normalized: dict[str, Any], key: str) -> str | None:
    """Return a normalized optional string value from secrets."""
    value = normalized.get(key)
    return str(value) if value else None


def credentials_kwargs(normalized: dict[str, Any]) -> dict[str, Any]:
    """Build keyword arguments for ``Credentials`` from normalized secrets."""
    return {
        "akid": str(normalized["LABARCHIVES_AKID"]),
        "password": str(normalized["LABARCHIVES_PASSWORD"]),
        "region": cast(HttpUrl, str(normalized["LABARCHIVES_REGION"])),
        "uid": optional_str(normalized, "LABARCHIVES_UID"),
        "auth_email": optional_str(normalized, "LABARCHIVES_AUTH_EMAIL"),
        "auth_code": optional_str(normalized, "LABARCHIVES_AUTH_CODE"),
    }
