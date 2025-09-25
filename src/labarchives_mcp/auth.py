"""Authentication primitives for the LabArchives MCP PoL server."""

from __future__ import annotations

import hashlib
import hmac
import time
from pathlib import Path
from typing import cast

import httpx
from omegaconf import OmegaConf
from pydantic import BaseModel, HttpUrl


class Credentials(BaseModel):
    """Validated LabArchives API credentials."""

    akid: str
    password: str
    region: HttpUrl

    @classmethod
    def from_file(cls, path: Path | str | None = None) -> Credentials:
        """Create credentials from a YAML secrets file located under ``conf/`` by default."""

        location = Path(path) if path is not None else Path("conf/secrets.yml")
        if not location.exists():
            raise FileNotFoundError(f"Secrets file not found: {location}")

        raw_config = OmegaConf.load(location)
        config = OmegaConf.to_container(raw_config, resolve=True)
        if not isinstance(config, dict):
            raise ValueError("Secrets file must contain a mapping of credential keys.")

        normalized = {str(key).upper(): value for key, value in config.items()}
        required_keys = ["LABARCHIVES_AKID", "LABARCHIVES_PASSWORD", "LABARCHIVES_REGION"]
        if missing := [key for key in required_keys if not normalized.get(key)]:
            joined = ", ".join(missing)
            raise ValueError(f"Missing LabArchives secrets: {joined}")

        return cls(
            akid=str(normalized["LABARCHIVES_AKID"]),
            password=str(normalized["LABARCHIVES_PASSWORD"]),
            region=cast(HttpUrl, str(normalized["LABARCHIVES_REGION"])),
        )


class AuthenticationManager:
    """Coordinate authentication flows against the LabArchives API."""

    def __init__(self, client: httpx.AsyncClient, credentials: Credentials) -> None:
        self._client = client
        self._credentials = credentials
        self._uid: str | None = None

    async def ensure_uid(self) -> str:
        """Return a cached uid or trigger the LabArchives login handshake."""
        if self._uid:
            return self._uid

        response = await self._client.post(
            self._login_url,
            params=self._build_auth_params(),
        )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - exercised in tests
            raise RuntimeError("LabArchives login failed") from exc

        payload = response.json()
        if payload.get("status") != "success" or not payload.get("uid"):
            raise RuntimeError("LabArchives login failed: unexpected response payload")

        self._uid = str(payload["uid"])
        return self._uid

    def clear_uid(self) -> None:
        """Forget cached uid, forcing the next call to re-authenticate."""
        self._uid = None

    @property
    def _login_url(self) -> str:
        region = str(self._credentials.region).rstrip("/")
        return f"{region}/api/v1/login"

    def _build_auth_params(self) -> dict[str, str]:
        expires = str(int(time.time()) + 300)
        message = f"{self._credentials.akid}{expires}".encode()
        signature = hmac.new(
            self._credentials.password.encode("utf-8"),
            message,
            hashlib.sha256,
        ).hexdigest()

        return {
            "akid": self._credentials.akid,
            "expires": expires,
            "sig": signature,
        }
