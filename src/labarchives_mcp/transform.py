"""Transform utilities for LabArchives XML responses and errors."""

from __future__ import annotations

import html as _html
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from loguru import logger
from lxml import etree

from .schemas.tool_responses import LabArchivesErrorResponse


@dataclass(slots=True)
class LabArchivesAPIError(Exception):
    """Represent a LabArchives fault response for MCP translation."""

    code: int
    message: str


def markdown_to_html(markdown_text: str, require_lib: bool = False) -> str:
    """Convert Markdown to HTML using `markdown` when available."""

    try:
        import markdown as _md
    except ModuleNotFoundError as exc:
        if require_lib:
            raise RuntimeError(
                "High-fidelity Markdown conversion requires the 'markdown' package. "
                "Install it (e.g., 'pip install markdown' or add to your environment)"
            ) from exc
        logger.warning(
            f"High-fidelity Markdown conversion not available ({exc}); using fallback converter."
        )
    else:
        return str(
            _md.markdown(
                markdown_text,
                extensions=[
                    "fenced_code",
                    "tables",
                    "sane_lists",
                    "toc",
                    "attr_list",
                    "codehilite",
                ],
                output_format=cast(Any, "html5"),
            )
        )

    text = markdown_text.replace("\r\n", "\n").replace("\r", "\n")

    # Handle fenced code blocks first to avoid interfering with other rules.
    code_blocks: list[str] = []

    def _codeblock_repl(match: re.Match[str]) -> str:
        lang = match.group(1) or ""
        code = match.group(2)
        escaped = _html.escape(code)
        code_blocks.append(f'<pre><code class="language-{lang}">{escaped}</code></pre>')
        return f"[[CODEBLOCK:{len(code_blocks)-1}]]"

    text = re.sub(r"```([\w+-]*)\n([\s\S]*?)\n```", _codeblock_repl, text)

    def _mk_heading_replacer(level: int) -> Callable[[re.Match[str]], str]:
        def _repl(match: re.Match[str]) -> str:
            content = match.group(1).strip()
            return f"<h{level}>{content}</h{level}>"

        return _repl

    for level in range(6, 0, -1):
        pattern = re.compile(rf"^{'#' * level} +(.+)$", re.MULTILINE)
        text = pattern.sub(_mk_heading_replacer(level), text)

    lines = text.split("\n")
    out_lines: list[str] = []
    in_list = False
    for line in lines:
        match = re.match(r"^[\-*] +(.*)$", line)
        if match:
            if not in_list:
                out_lines.append("<ul>")
                in_list = True
            out_lines.append(f"<li>{match.group(1).strip()}</li>")
        else:
            if in_list:
                out_lines.append("</ul>")
                in_list = False
            out_lines.append(line)
    if in_list:
        out_lines.append("</ul>")
    text = "\n".join(out_lines)

    text = re.sub(r"`([^`]+)`", lambda match: f"<code>{_html.escape(match.group(1))}</code>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)

    blocks = [block.strip() for block in text.split("\n\n")]
    wrapped_blocks: list[str] = []
    for block in blocks:
        if not block:
            continue
        if block.startswith("<h") or block.startswith("<ul>") or block.startswith("<pre>"):
            wrapped_blocks.append(block)
        else:
            wrapped_blocks.append(f"<p>{block}</p>")
    html = "\n\n".join(wrapped_blocks)

    def _restore_code(match: re.Match[str]) -> str:
        idx = int(match.group(1))
        return code_blocks[idx]

    return re.sub(r"\[\[CODEBLOCK:(\d+)\]\]", _restore_code, html)


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


def parse_notebook_xml(payload: str) -> list[dict[str, Any]]:
    """Parse LabArchives notebook XML into dictionaries."""

    return NotebookTransformer.parse_notebook_list(payload)


def translate_labarchives_fault(error: LabArchivesAPIError) -> LabArchivesErrorResponse:
    """Convert a LabArchives-specific error into an MCP error payload."""

    retryable = error.code in {4505, 4506}
    return {
        "code": f"labarchives:{error.code}",
        "message": error.message,
        "retryable": retryable,
        "domain": "labarchives",
    }
