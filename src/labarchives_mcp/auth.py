"""Authentication primitives for the LabArchives MCP PoL server."""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

import httpx
from omegaconf import OmegaConf
from pydantic import BaseModel, HttpUrl


class Credentials(BaseModel):
    """Validated LabArchives API credentials."""

    akid: str
    password: str
    region: HttpUrl
    uid: str | None = None
    auth_email: str | None = None
    auth_code: str | None = None

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
            uid=(
                str(normalized.get("LABARCHIVES_UID"))
                if normalized.get("LABARCHIVES_UID")
                else None
            ),
            auth_email=(
                str(normalized.get("LABARCHIVES_AUTH_EMAIL"))
                if normalized.get("LABARCHIVES_AUTH_EMAIL")
                else None
            ),
            auth_code=(
                str(normalized.get("LABARCHIVES_AUTH_CODE"))
                if normalized.get("LABARCHIVES_AUTH_CODE")
                else None
            ),
        )


class AuthenticationManager:
    """Coordinate authentication flows against the LabArchives API."""

    USER_ACCESS_METHOD = "users:user_access_info"

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
        """Forget cached uid, forcing the next call to re-authenticate."""
        self._uid = None

    @property
    def _api_base(self) -> str:
        return f"{str(self._credentials.region).rstrip('/')}/apiv1"

    async def _fetch_uid_via_user_access_info(self) -> str:
        params = self._build_auth_params(self.USER_ACCESS_METHOD)
        params.update(
            {
                "email": cast(str, self._credentials.auth_email),
                "password": cast(str, self._credentials.auth_code),
            }
        )

        url = f"{self._api_base}/users/user_access_info"
        response = await self._client.get(url, params=params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - exercised in tests
            raise RuntimeError("LabArchives user_access_info failed") from exc

        payload = self._parse_response_json(response)
        uid = payload.get("uid")
        if not uid:
            raise RuntimeError("LabArchives user_access_info failed: missing uid")

        return str(uid)

    def _build_auth_params(self, method: str) -> dict[str, str]:
        expires = str(int(time.time() * 1000) + 120_000)
        message = f"{self._credentials.akid}{method}{expires}".encode()
        digest = hmac.new(
            self._credentials.password.encode("utf-8"),
            message,
            hashlib.sha512,
        ).digest()
        signature = quote(base64.b64encode(digest).decode("ascii"), safe="")

        return {
            "akid": self._credentials.akid,
            "expires": expires,
            "sig": signature,
        }

    @staticmethod
    def _parse_response_json(response: httpx.Response) -> dict[str, Any]:
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("LabArchives returned malformed JSON payload")
        return payload
