"""Minimal LabArchives ELN client for PoL purposes."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, Field


class NotebookRecord(BaseModel):
    """Normalized notebook metadata returned to MCP clients."""

    nbid: str
    name: str
    owner: str
    created_at: str = Field(alias="created_at")


class LabArchivesClient:
    """Wrap LabArchives ELN API calls needed for proof-of-life."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def list_notebooks(self, uid: str) -> list[NotebookRecord]:
        """Return notebooks for a user uid."""
        raise NotImplementedError("Implement notebook listing via LabArchives API.")

    @staticmethod
    def parse_xml(payload: str) -> list[dict[str, Any]]:
        """Placeholder XML parser stub for PoL scope."""
        raise NotImplementedError("Implement XML parsing for LabArchives responses.")
