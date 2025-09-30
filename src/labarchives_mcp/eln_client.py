"""Minimal LabArchives ELN client for PoL purposes."""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from .auth import AuthenticationManager
from .transform import NotebookTransformer


class NotebookRecord(BaseModel):
    """Normalized notebook metadata returned to MCP clients.

    This is the source of truth for the notebook resource schema.
    Generate JSON Schema:
        python -c "from labarchives_mcp.eln_client import NotebookRecord;
                   print(NotebookRecord.schema_json(indent=4))"
    """

    nbid: str = Field(
        description="LabArchives notebook ID (base64-encoded)",
        examples=[
            "MTU2MTI4NS43fDEyMDA5ODkvMTIwMDk4OS9Ob3RlYm9vay81MzgyNzU0MDh8Mzk2MzI2My42OTk5OTk5OTk3"
        ],
    )
    name: str = Field(description="Notebook name", examples=["Fly Behavior Study"])
    owner: str = Field(
        description="Owner identifier (typically email)",
        examples=["samuel.brudner@yale.edu"],
    )
    owner_email: str = Field(
        description="Owner email address", examples=["samuel.brudner@yale.edu"]
    )
    owner_name: str = Field(description="Owner full name", examples=["Samuel Brudner"])
    created_at: str = Field(
        alias="created_at",
        description="Notebook creation timestamp (ISO 8601, UTC)",
        examples=["2025-01-01T12:00:00Z"],
    )
    modified_at: str = Field(
        alias="modified_at",
        description="Last modification timestamp (ISO 8601, UTC)",
        examples=["2025-01-02T08:30:00Z"],
    )


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
