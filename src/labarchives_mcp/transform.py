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

    REQUIRED_FIELDS: dict[str, list[str]] = {
        "nbid": ["id", "nbid"],  # user_info_via_id returns <id>, notebook list returns <nbid>
        "name": ["name"],
    }

    OPTIONAL_FIELDS: dict[str, str] = {
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

        # LabArchives responses may wrap notebooks under <response>, <users>,
        # or top-level <notebooks>
        if root.tag in ["response", "users"]:
            notebooks_parent = root.find("notebooks")
        else:
            notebooks_parent = root

        if notebooks_parent is None:
            return []

        # Extract user info for fallback owner data
        owner_email = NotebookTransformer._text_or_empty(root, "email")
        owner_name = NotebookTransformer._text_or_empty(root, "fullname")

        records: list[dict[str, Any]] = []
        for notebook_node in notebooks_parent.findall("notebook"):
            record: dict[str, Any] = {}

            # Required fields - try all possible XML tag names
            for field_name, possible_tags in NotebookTransformer.REQUIRED_FIELDS.items():
                value = ""
                for tag in possible_tags:
                    value = NotebookTransformer._text_or_empty(notebook_node, tag)
                    if value:
                        break

                if not value:
                    raise ValueError(f"Notebook record missing `{possible_tags[0]}` field")

                record[field_name] = value
            # Optional fields with fallbacks
            for tag, field_name in NotebookTransformer.OPTIONAL_FIELDS.items():
                value = NotebookTransformer._text_or_empty(notebook_node, tag)

                # Provide sensible defaults for missing owner/timestamp fields
                if not value:
                    if field_name == "owner_email":
                        # Fallback to root-level email, then <owner> tag
                        value = owner_email or record.get("owner", "")
                    elif field_name == "owner":
                        value = owner_email or NotebookTransformer._text_or_empty(
                            notebook_node, "owner-email"
                        )
                    elif field_name == "owner_name":
                        value = owner_name
                    elif field_name in {"created_at", "modified_at"}:
                        value = "1970-01-01T00:00:00Z"

                if tag in {"created-at", "modified-at"} and value != "1970-01-01T00:00:00Z":
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
        candidate = raw_value.strip()
        if candidate.endswith("Z"):
            candidate = f"{candidate[:-1]}+00:00"

        parsed: datetime
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            try:
                parsed = datetime.strptime(candidate, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    parsed = datetime.strptime(candidate, "%Y-%m-%dT%H:%M:%S")
                except ValueError as exc:
                    raise ValueError(f"Notebook record has invalid `{field}` value") from exc

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        else:
            parsed = parsed.astimezone(UTC)

        return parsed.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def translate_labarchives_fault(error: LabArchivesAPIError) -> dict[str, Any]:
    """Convert a LabArchives-specific error into an MCP error payload."""

    retryable = error.code in {4505, 4506}
    return {
        "code": f"labarchives:{error.code}",
        "message": error.message,
        "retryable": retryable,
        "domain": "labarchives",
    }
