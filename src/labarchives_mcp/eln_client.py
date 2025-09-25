"""Minimal LabArchives ELN client for PoL purposes."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import httpx
from lxml import etree
from pydantic import BaseModel, Field, ValidationError


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
        response = await self._client.get(
            "https://api.labarchives.com/apiv1/notebooks/list",
            params={"uid": uid},
        )
        response.raise_for_status()

        payload = response.text
        raw_records = self.parse_xml(payload)

        notebooks: list[NotebookRecord] = []
        for raw in raw_records:
            try:
                notebooks.append(NotebookRecord.model_validate(raw))
            except ValidationError as exc:
                raise ValueError("Invalid notebook record received from LabArchives") from exc

        return notebooks

    @staticmethod
    def parse_xml(payload: str) -> list[dict[str, Any]]:
        """Placeholder XML parser stub for PoL scope."""
        root = etree.fromstring(payload.encode())
        notebook_nodes: Iterable[etree._Element] = root.findall("notebook")

        records: list[dict[str, Any]] = []
        for node in notebook_nodes:
            record = {
                "nbid": (node.findtext("nbid") or "").strip(),
                "name": (node.findtext("name") or "").strip(),
                "owner": (node.findtext("owner") or "").strip(),
                "created_at": (node.findtext("created-at") or "").strip(),
            }

            if not record["nbid"]:
                raise ValueError("Notebook record missing `nbid` field")

            records.append(record)

        return records
