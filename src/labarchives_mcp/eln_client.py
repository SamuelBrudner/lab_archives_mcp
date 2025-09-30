"""Minimal LabArchives ELN client for PoL purposes."""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from .auth import AuthenticationManager
from .transform import NotebookTransformer


class NotebookRecord(BaseModel):
    """Normalized notebook metadata returned to MCP clients."""

    nbid: str
    name: str
    owner: str
    owner_email: str
    owner_name: str
    created_at: str = Field(alias="created_at")
    modified_at: str = Field(alias="modified_at")


class LabArchivesClient:
    """Wrap LabArchives ELN API calls needed for proof-of-life."""

    def __init__(self, client: httpx.AsyncClient, auth_manager: AuthenticationManager) -> None:
        self._client = client
        self._auth_manager = auth_manager

    async def list_notebooks(self, uid: str) -> list[NotebookRecord]:
        """Return notebooks for a user uid."""
        auth_params = self._auth_manager._build_auth_params("user_info_via_id")
        params = {"uid": uid, **auth_params}

        response = await self._client.get(
            "https://api.labarchives.com/api/users/user_info_via_id",
            params=params,
        )
        response.raise_for_status()

        payload = response.text
        raw_records = self.parse_xml(payload)
        logger.info(f"Retrieved {len(raw_records)} notebooks for user")

        notebooks: list[NotebookRecord] = []
        for raw in raw_records:
            try:
                notebooks.append(NotebookRecord.model_validate(raw))
            except ValidationError as exc:
                logger.error(f"Notebook validation failed: {exc}")
                raise ValueError("Invalid notebook record received from LabArchives") from exc

        return notebooks

    @staticmethod
    def parse_xml(payload: str) -> list[dict[str, Any]]:
        """Parse LabArchives notebook XML into dictionaries."""

        return NotebookTransformer.parse_notebook_list(payload)
