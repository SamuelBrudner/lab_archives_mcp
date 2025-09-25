"""Authentication primitives for the LabArchives MCP PoL server."""

from __future__ import annotations

import os
from typing import Mapping

import httpx
from pydantic import BaseModel, HttpUrl


class Credentials(BaseModel):
    """Validated LabArchives API credentials."""

    akid: str
    password: str
    region: HttpUrl

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Credentials":
        """Create credentials from environment variables, failing fast if missing."""
        source = env or os.environ
        keys = ["LABARCHIVES_AKID", "LABARCHIVES_PASSWORD", "LABARCHIVES_REGION"]
        values = {key: source.get(key) for key in keys}
        missing = [key for key, value in values.items() if not value]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Missing LabArchives environment variables: {joined}")
        return cls(akid=values[keys[0]], password=values[keys[1]], region=values[keys[2]])


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
        raise NotImplementedError("Implement LabArchives login handshake.")

    def clear_uid(self) -> None:
        """Forget cached uid, forcing the next call to re-authenticate."""
        self._uid = None
