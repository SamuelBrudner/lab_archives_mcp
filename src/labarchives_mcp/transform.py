"""Transform utilities for LabArchives XML responses and errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from lxml import etree


@dataclass(slots=True)
class LabArchivesAPIError(Exception):
    """Represent a LabArchives fault response for MCP translation."""

    code: int
    message: str


class NotebookTransformer:
    """Translate LabArchives notebook XML payloads into normalized JSON records."""

    @staticmethod
    def parse_notebook_list(payload: str) -> list[dict[str, Any]]:
        """Return notebook dictionaries from a LabArchives XML notebook listing."""

        try:
            root = etree.fromstring(payload.strip().encode())
        except etree.XMLSyntaxError as exc:  # pragma: no cover - defensive guard
            raise ValueError("Invalid LabArchives notebook XML payload") from exc

        # LabArchives responses may wrap notebooks under <response> or top-level <notebooks>
        notebooks_parent = root.find("notebooks") if root.tag == "response" else root
        if notebooks_parent is None:
            return []

        records: list[dict[str, Any]] = []
        for notebook_node in notebooks_parent.findall("notebook"):
            record = {
                "nbid": NotebookTransformer._text_or_empty(notebook_node, "nbid"),
                "name": NotebookTransformer._text_or_empty(notebook_node, "name"),
                "owner": NotebookTransformer._text_or_empty(notebook_node, "owner"),
                "created_at": NotebookTransformer._text_or_empty(notebook_node, "created-at"),
            }

            if not record["nbid"]:
                raise ValueError("Notebook record missing `nbid` field")

            records.append(record)

        return records

    @staticmethod
    def _text_or_empty(node: etree._Element, tag: str) -> str:
        element = node.find(tag)
        if element is None or element.text is None:
            return ""
        return cast(str, element.text).strip()


def translate_labarchives_fault(error: LabArchivesAPIError) -> dict[str, Any]:
    """Convert a LabArchives-specific error into an MCP error payload."""

    retryable = error.code in {4505, 4506}
    return {
        "code": f"labarchives:{error.code}",
        "message": error.message,
        "retryable": retryable,
        "domain": "labarchives",
    }
