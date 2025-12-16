"""Authentication primitives for the LabArchives MCP PoL server."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from pathlib import Path
from typing import Any, cast

import httpx
from lxml import etree
from omegaconf import OmegaConf
from pydantic import BaseModel, Field, HttpUrl


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _candidate_paths(raw: Path) -> tuple[Path, ...]:
    if raw.is_absolute():
        return (raw,)
    return (Path.cwd() / raw, _repo_root() / raw)


def _existing_unique_paths(candidates: tuple[Path, ...]) -> tuple[Path, ...]:
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


def _missing_secrets_message(raw: Path, source: str, candidates: tuple[Path, ...]) -> str:
    checked = "\n".join(str(candidate) for candidate in candidates)
    return f"Secrets file not found for {source}: {raw}\nChecked:\n{checked}"


def _multiple_secrets_message(raw: Path, source: str, existing: tuple[Path, ...]) -> str:
    joined = ", ".join(str(path) for path in existing)
    return f"Multiple secrets files found for {source}: {raw}. Candidates: {joined}"


def _resolve_secrets_location(spec: Path | str, *, source: str) -> Path:
    raw = Path(spec).expanduser()
    candidates = _candidate_paths(raw)
    existing = _existing_unique_paths(candidates)
    if len(existing) == 1:
        return existing[0]
    if not existing:
        raise FileNotFoundError(_missing_secrets_message(raw, source, candidates))
    raise RuntimeError(_multiple_secrets_message(raw, source, existing))


def _load_normalized_secrets(location: Path) -> dict[str, Any]:
    raw_config = OmegaConf.load(location)
    config = OmegaConf.to_container(raw_config, resolve=True)
    if not isinstance(config, dict):
        raise ValueError("Secrets file must contain a mapping of credential keys.")
    return {str(key).upper(): value for key, value in config.items()}


def _require_secrets(normalized: dict[str, Any]) -> None:
    required_keys = ["LABARCHIVES_AKID", "LABARCHIVES_PASSWORD", "LABARCHIVES_REGION"]
    missing = [key for key in required_keys if not normalized.get(key)]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Missing LabArchives secrets: {joined}")


def _optional_str(normalized: dict[str, Any], key: str) -> str | None:
    value = normalized.get(key)
    return str(value) if value else None


def _credentials_kwargs(normalized: dict[str, Any]) -> dict[str, Any]:
    return {
        "akid": str(normalized["LABARCHIVES_AKID"]),
        "password": str(normalized["LABARCHIVES_PASSWORD"]),
        "region": cast(HttpUrl, str(normalized["LABARCHIVES_REGION"])),
        "uid": _optional_str(normalized, "LABARCHIVES_UID"),
        "auth_email": _optional_str(normalized, "LABARCHIVES_AUTH_EMAIL"),
        "auth_code": _optional_str(normalized, "LABARCHIVES_AUTH_CODE"),
    }


class Credentials(BaseModel):
    """Validated LabArchives API credentials.

    This is the source of truth for required configuration.
    All credentials are read from conf/secrets.yml at runtime.
    """

    akid: str = Field(
        description="LabArchives Access Key ID (obtain from LabArchives support)",
        examples=["example_akid"],
    )
    password: str = Field(
        description="LabArchives Access Password (HMAC-SHA512 signing key)",
        examples=["super-secret-password"],
    )
    region: HttpUrl = Field(
        description="LabArchives API base URL",
        examples=["https://api.labarchives.com"],
    )
    uid: str | None = Field(
        default=None,
        description=(
            "User ID (obtain via scripts/resolve_uid.py). " "Permanent per-account identifier."
        ),
        examples=["233106187ler2,bix5417615158751911759198414"],
    )
    auth_email: str | None = Field(
        default=None,
        description="Email for temporary token authentication (alternative to uid)",
    )
    auth_code: str | None = Field(
        default=None,
        description=(
            "Temporary password token from LabArchives " "(alternative to uid, expires in 1 hour)"
        ),
    )

    @classmethod
    def from_file(cls, path: Path | str | None = None) -> Credentials:
        """Create credentials from a YAML secrets file located under ``conf/`` by default."""
        env_path = os.environ.get("LABARCHIVES_CONFIG_PATH")
        if env_path:
            location = _resolve_secrets_location(env_path, source="LABARCHIVES_CONFIG_PATH")
        elif path is not None:
            location = _resolve_secrets_location(path, source="path")
        else:
            location = _resolve_secrets_location("conf/secrets.yml", source="default")

        normalized = _load_normalized_secrets(location)
        _require_secrets(normalized)
        return cls(**_credentials_kwargs(normalized))


class AuthenticationManager:
    """Coordinate authentication flows against the LabArchives API."""

    USER_ACCESS_METHOD = "user_access_info"

    def __init__(self, client: httpx.AsyncClient, credentials: Credentials) -> None:
        self._client = client
        self._credentials = credentials
        self._uid: str | None = credentials.uid

    async def ensure_uid(self) -> str:
        """Return a cached uid or resolve it through the documented user access flow."""
        if self._uid:
            return self._uid

        if self._credentials.auth_email and self._credentials.auth_code:
            self._uid = await self._fetch_uid_via_user_access_info()
            return self._uid

        raise RuntimeError(
            "LabArchives credentials require either LABARCHIVES_UID or both "
            "LABARCHIVES_AUTH_EMAIL and LABARCHIVES_AUTH_CODE."
        )

    def clear_uid(self) -> None:
        self._uid = None

    async def _fetch_uid_via_user_access_info(self) -> str:
        params = self._build_auth_params(self.USER_ACCESS_METHOD)
        payload = {
            "login_or_email": cast(str, self._credentials.auth_email),
            "password": cast(str, self._credentials.auth_code),
        }

        root = str(self._credentials.region).rstrip("/")
        attempts: list[tuple[str, str, dict[str, str], dict[str, str] | None]] = [
            ("GET", f"{root}/api/users/user_access_info", params | payload, None),
        ]

        last_not_found: tuple[str, str, str] | None = None
        response: httpx.Response | None = None
        for method, url, query, form_data in attempts:
            request_kwargs: dict[str, Any] = {"params": query}
            if form_data is not None:
                request_kwargs["data"] = form_data

            response = await self._client.request(method, url, **request_kwargs)
            if response.status_code == httpx.codes.NOT_FOUND:
                last_not_found = (method, url, response.text)
                continue

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:  # pragma: no cover - exercised in tests
                raise RuntimeError(
                    "LabArchives user_access_info failed "
                    f"({method} {url} -> {response.status_code}): {response.text}"
                ) from exc

            break
        else:
            detail = (
                f"last attempt {last_not_found[0]} {last_not_found[1]} responded 404:"
                f" {last_not_found[2]}"
                if last_not_found
                else "no HTTP response recorded"
            )
            raise RuntimeError(
                "LabArchives user_access_info returned 404 for all endpoint variants. " f"{detail}"
            )

        body = self._parse_response_json(response)
        if uid := body.get("uid"):
            return str(uid)
        else:
            raise RuntimeError("LabArchives user_access_info failed: missing uid")

    def _build_auth_params(self, method: str) -> dict[str, str]:
        expires = str(int(time.time() * 1000) + 120_000)
        message = f"{self._credentials.akid}{method}{expires}".encode()
        digest = hmac.new(
            self._credentials.password.encode("utf-8"),
            message,
            hashlib.sha512,
        ).digest()
        signature = base64.b64encode(digest).decode("ascii")

        return {
            "akid": self._credentials.akid,
            "expires": expires,
            "sig": signature,
        }

    @staticmethod
    def _parse_response_json(response: httpx.Response) -> dict[str, Any]:
        """Parse XML response from user_access_info and extract user ID."""
        try:
            root = etree.fromstring(response.content)
            uid_elem = root.find(".//id")
            if uid_elem is not None and uid_elem.text:
                return {"uid": uid_elem.text}
            raise RuntimeError("LabArchives response missing <id> element")
        except etree.XMLSyntaxError as exc:
            raise RuntimeError(f"Invalid XML response: {response.text[:200]}") from exc
