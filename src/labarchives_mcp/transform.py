"""Transform utilities for LabArchives XML responses and errors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from lxml import etree


@dataclass(slots=True)
class LabArchivesAPIError(Exception):
    """Represent a LabArchives fault response for MCP translation."""

    code: int
    message: str


class NotebookTransformer:
    """Translate LabArchives notebook XML payloads into normalized JSON records."""

    REQUIRED_FIELDS: dict[str, str] = {
        "nbid": "nbid",
        "name": "name",
        "owner": "owner",
        "owner-email": "owner_email",
        "owner-name": "owner_name",
        "created-at": "created_at",
        "modified-at": "modified_at",
    }

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
            record: dict[str, Any] = {}

            for tag, field_name in NotebookTransformer.REQUIRED_FIELDS.items():
                value = NotebookTransformer._text_or_empty(notebook_node, tag)
                if not value:
                    raise ValueError(f"Notebook record missing `{tag}` field")

                if tag in {"created-at", "modified-at"}:
                    value = NotebookTransformer._normalize_timestamp(value, tag)

                record[field_name] = value

            records.append(record)

        return records

    @staticmethod
    def _text_or_empty(node: etree._Element, tag: str) -> str:
        element = node.find(tag)
        if element is None or element.text is None:
            return ""
        return cast(str, element.text).strip()

    @staticmethod
    def _normalize_timestamp(raw_value: str, field: str) -> str:
        try:
            parsed = datetime.strptime(raw_value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                parsed = datetime.strptime(raw_value, "%Y-%m-%dT%H:%M:%S")
            except ValueError as exc:
                raise ValueError(f"Notebook record has invalid `{field}` value") from exc

        parsed = parsed.replace(tzinfo=UTC)
        return parsed.isoformat().replace("+00:00", "Z")


def translate_labarchives_fault(error: LabArchivesAPIError) -> dict[str, Any]:
    """Convert a LabArchives-specific error into an MCP error payload."""

    retryable = error.code in {4505, 4506}
    return {
        "code": f"labarchives:{error.code}",
        "message": error.message,
        "retryable": retryable,
        "domain": "labarchives",
    }
