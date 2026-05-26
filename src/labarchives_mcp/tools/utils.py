"""Shared helpers for LabArchives MCP tools."""

from __future__ import annotations

import html
import re
from collections.abc import Mapping, Sequence
from typing import TypeVar
from urllib.parse import unquote

from ..schemas.tool_responses import PaginationMetaResponse

_LABARCHIVES_SHARE_URL_RE = re.compile(
    r"(?:https?://)?(?:[A-Za-z0-9.-]+\.)?labarchives\.com/share/"
    r"([^/\"'\s<>?#]+)/([^/\"'\s<>?#]+)",
    re.IGNORECASE,
)

T = TypeVar("T")


def _extract_labarchives_page_links(
    entries: Sequence[Mapping[str, object]],
) -> list[tuple[str, str]]:
    """Return unique (notebook_id, page_id) links detected in LabArchives entry content."""
    links: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for entry in entries:
        content = entry.get("content") or ""
        if not isinstance(content, str):
            continue

        for notebook_id, page_id in _LABARCHIVES_SHARE_URL_RE.findall(html.unescape(content)):
            notebook_id = unquote(notebook_id).strip()
            page_id = unquote(page_id).split("&", maxsplit=1)[0].rstrip(".,;:)]}").strip()
            if not notebook_id or not page_id:
                continue

            key = (notebook_id, page_id)
            if key in seen:
                continue

            seen.add(key)
            links.append(key)

    return links


def _paginate_items(
    items: Sequence[T], limit: int | None = None, offset: int = 0
) -> tuple[list[T], PaginationMetaResponse]:
    """Slice items with limit/offset and emit truncation metadata."""
    total = len(items)
    start = max(offset, 0)
    if limit is None or limit <= 0:
        return list(items), {"total": total, "offset": start, "limit": limit, "truncated": False}

    end = start + limit
    truncated = total > end
    return list(items[start:end]), {
        "total": total,
        "offset": start,
        "limit": limit,
        "truncated": truncated,
    }
