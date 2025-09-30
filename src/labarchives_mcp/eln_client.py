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

    async def get_notebook_tree(
        self, uid: str, nbid: str, parent_tree_id: int = 0
    ) -> list[dict[str, Any]]:
        """Get one level of the notebook tree structure."""
        logger.debug(f"get_notebook_tree: nbid={nbid}, parent_tree_id={parent_tree_id}")

        auth_params = self._auth_manager._build_auth_params("get_tree_level")
        params = {"uid": uid, "nbid": nbid, "parent_tree_id": str(parent_tree_id), **auth_params}

        url = "https://api.labarchives.com/api/tree_tools/get_tree_level"
        logger.debug(f"Making API request to {url}")

        response = await self._client.get(url, params=params)
        logger.debug(f"API response status: {response.status_code}")
        response.raise_for_status()

        from lxml import etree

        root = etree.fromstring(response.content)
        nodes = root.findall(".//level-node")
        logger.debug(f"Parsed {len(nodes)} nodes from XML response")

        return [
            {
                "tree_id": node.findtext("tree-id"),
                "display_text": node.findtext("display-text"),
                "is_page": node.findtext("is-page") == "true",
                "is_folder": node.findtext("is-page") != "true",
            }
            for node in nodes
        ]

    async def get_page_entries(
        self, uid: str, nbid: str, page_tree_id: int, include_data: bool = True
    ) -> list[dict[str, Any]]:
        """Get all entries for a specific page with their content."""
        logger.debug(
            f"get_page_entries: nbid={nbid}, page_tree_id={page_tree_id}, "
            f"include_data={include_data}"
        )

        auth_params = self._auth_manager._build_auth_params("get_entries_for_page")
        params = {
            "uid": uid,
            "nbid": nbid,
            "page_tree_id": str(page_tree_id),
            "entry_data": "true" if include_data else "false",
            **auth_params,
        }

        url = "https://api.labarchives.com/api/tree_tools/get_entries_for_page"
        logger.debug(f"Making API request to {url}")

        response = await self._client.get(url, params=params)
        logger.debug(f"API response status: {response.status_code}")
        response.raise_for_status()

        from lxml import etree

        root = etree.fromstring(response.content)
        entry_elements = root.findall(".//entry")
        logger.debug(f"Parsed {len(entry_elements)} entries from XML response")

        entries = []
        for entry in entry_elements:
            entry_dict = {
                "eid": entry.findtext("eid"),
                "part_type": entry.findtext("part-type"),
                "created_at": entry.findtext("created-at"),
                "updated_at": entry.findtext("updated-at"),
            }
            if include_data:
                entry_data = entry.find("entry-data")
                if entry_data is not None and entry_data.text:
                    entry_dict["content"] = entry_data.text
            entries.append(entry_dict)

        return entries
