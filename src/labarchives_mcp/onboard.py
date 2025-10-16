"""Generate onboarding payloads for the LabArchives MCP server."""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
from typing import Any

from loguru import logger

from labarchives_mcp.auth import AuthenticationManager
from labarchives_mcp.eln_client import LabArchivesClient, NotebookRecord
from labarchives_mcp.schemas.onboard import (
    MAX_ONBOARD_PAYLOAD_BYTES,
    HowToUse,
    LabSummary,
    NotebookSummary,
    OnboardPayload,
    RecentActivityItem,
    StickyContext,
)

_PAGE_SCAN_LIMIT = 200
_MAX_TREE_DEPTH = 3
_RECENT_CANDIDATE_FACTOR = 3


@dataclass(slots=True)
class PageDescriptor:
    """Metadata for candidate pages used in recent activity summaries."""

    notebook: NotebookRecord
    tree_id: str
    title: str


class OnboardService:
    """Aggregate notebook metadata to produce onboarding payloads."""

    def __init__(
        self,
        auth_manager: AuthenticationManager,
        notebook_client: LabArchivesClient,
        *,
        version: str,
        cache_ttl_seconds: int = 300,
        max_notebooks: int = 5,
        recent_activity_limit: int = 5,
    ) -> None:
        self._auth_manager = auth_manager
        self._notebook_client = notebook_client
        self._version = version
        self._cache_ttl_seconds = cache_ttl_seconds
        self._max_notebooks = max_notebooks
        self._recent_activity_limit = recent_activity_limit
        self._recent_candidate_limit = recent_activity_limit * _RECENT_CANDIDATE_FACTOR
        self._cache: tuple[float, OnboardPayload] | None = None
        self._lock = asyncio.Lock()

    async def get_payload(self) -> OnboardPayload:
        """Return a cached onboarding payload, refreshing when expired."""

        now = time.time()
        cached = self._cache
        if cached and now - cached[0] < self._cache_ttl_seconds:
            return cached[1]

        async with self._lock:
            cached = self._cache
            now = time.time()
            if cached and now - cached[0] < self._cache_ttl_seconds:
                return cached[1]

            payload = await self._build_payload()
            payload_bytes = payload.to_json_bytes()
            if len(payload_bytes) > MAX_ONBOARD_PAYLOAD_BYTES:
                raise ValueError(
                    "Onboarding payload exceeds size budget"
                    f" ({len(payload_bytes)} > {MAX_ONBOARD_PAYLOAD_BYTES} bytes)"
                )

            self._cache = (now, payload)
            return payload

    async def _build_payload(self) -> OnboardPayload:
        uid = await self._auth_manager.ensure_uid()
        notebooks = await self._notebook_client.list_notebooks(uid)
        if not notebooks:
            logger.warning("No LabArchives notebooks found for user during onboarding")

        sorted_notebooks = sorted(
            notebooks,
            key=lambda nb: self._parse_timestamp(nb.modified_at, fallback_epoch=True),
            reverse=True,
        )

        notebook_summaries, page_candidates = await self._collect_notebook_context(
            uid, sorted_notebooks[: self._max_notebooks]
        )

        recent_activity = await self._summarize_recent_activity(uid, page_candidates)

        how_to_use = HowToUse(
            when=[
                "User mentions experiments, protocols, results, or prior lab work.",
                "Prompts reference LabArchives notebooks, pages, figures, or sample IDs.",
                "Requests involve lab dates, experiment logs, or ELN provenance.",
            ],
            primary_tools={
                "semantic_search": "Find relevant ELN pages from free-text prompts.",
                "list_notebooks": "Enumerate notebooks available to the authenticated user.",
                "list_notebook_pages": "Browse notebook structure to locate pages.",
                "read_notebook_page": "Retrieve full structured content for a given page.",
                "peek_page": "Quickly preview summaries without full content load.",
                "summarize_page": "Generate concise bullet or timeline summaries for a page.",
            },
            decision_aid="Call `decide_labarchives_usage` before querying to confirm relevance.",
            context_persistence="Add the provided `sticky_context` block to each response turn.",
        )

        lab_summary = LabSummary(
            notebooks=notebook_summaries,
            recent_activity=recent_activity,
        )

        sticky_context = StickyContext(last_notebook_id=None, last_page_id=None)

        router_prompt = (
            "Use LabArchives MCP for anything involving experiments, protocols, results, "
            "or ELN pages."
        )
        banner = "LabArchives MCP • Access experimental notebooks and context."

        markdown = self._to_markdown(how_to_use, lab_summary, router_prompt)

        return OnboardPayload(
            server="lab_archives_mcp",
            version=self._version,
            purpose="Provide experimental context from LabArchives ELN.",
            banner=banner,
            how_to_use=how_to_use,
            lab_summary=lab_summary,
            sticky_context=sticky_context,
            router_prompt=router_prompt,
            markdown=markdown,
        )

    async def _collect_notebook_context(
        self, uid: str, notebooks: list[NotebookRecord]
    ) -> tuple[list[NotebookSummary], list[PageDescriptor]]:
        notebook_summaries: list[NotebookSummary] = []
        page_candidates: list[PageDescriptor] = []

        for notebook in notebooks:
            try:
                n_pages, candidates = await self._scan_notebook(uid, notebook)
            except Exception as exc:  # pragma: no cover - network/runtime failures
                logger.warning(
                    "Failed to scan notebook %s during onboarding: %s",
                    notebook.nbid,
                    exc,
                )
                n_pages = 0
                candidates = []

            notebook_summaries.append(
                NotebookSummary(
                    id=notebook.nbid,
                    title=notebook.name,
                    n_pages=n_pages,
                    last_updated=self._parse_timestamp(notebook.modified_at),
                )
            )

            page_candidates.extend(candidates)

        return notebook_summaries, page_candidates

    async def _scan_notebook(
        self, uid: str, notebook: NotebookRecord
    ) -> tuple[int, list[PageDescriptor]]:
        pages_found = 0
        candidates: list[PageDescriptor] = []
        queue: list[tuple[str | int, int]] = [(0, 0)]
        seen: set[str] = set()

        while queue and pages_found < _PAGE_SCAN_LIMIT:
            parent_id, depth = queue.pop()
            parent_key = str(parent_id)
            if parent_key in seen:
                continue
            seen.add(parent_key)

            try:
                nodes = await self._notebook_client.get_notebook_tree(uid, notebook.nbid, parent_id)
            except Exception as exc:  # pragma: no cover - network/runtime failures
                logger.debug(
                    "Tree fetch failed for notebook %s parent %s: %s",
                    notebook.nbid,
                    parent_id,
                    exc,
                )
                continue

            for node in nodes:
                tree_id_raw = node.get("tree_id") or ""
                tree_id = str(tree_id_raw)
                if not tree_id:
                    continue

                is_page = bool(node.get("is_page"))
                is_folder = bool(node.get("is_folder"))
                title = node.get("display_text") or "Untitled Page"

                if is_page:
                    pages_found += 1
                    if len(candidates) < self._recent_candidate_limit:
                        candidates.append(
                            PageDescriptor(notebook=notebook, tree_id=tree_id, title=title)
                        )
                elif is_folder and depth < _MAX_TREE_DEPTH:
                    queue.append((tree_id, depth + 1))

                if pages_found >= _PAGE_SCAN_LIMIT:
                    break

        return pages_found, candidates

    async def _summarize_recent_activity(
        self, uid: str, candidates: list[PageDescriptor]
    ) -> list[RecentActivityItem]:
        activity: list[RecentActivityItem] = []
        dedup: set[tuple[str, str]] = set()

        for descriptor in candidates:
            key = (descriptor.notebook.nbid, descriptor.tree_id)
            if key in dedup:
                continue
            dedup.add(key)

            try:
                entries = await self._notebook_client.get_page_entries(
                    uid, descriptor.notebook.nbid, descriptor.tree_id, include_data=True
                )
            except Exception as exc:  # pragma: no cover - network/runtime failures
                logger.debug(
                    "Failed to fetch entries for notebook %s page %s: %s",
                    descriptor.notebook.nbid,
                    descriptor.tree_id,
                    exc,
                )
                continue

            summary, updated_at = self._summarize_entries(entries)
            if summary is None:
                summary = "Page has no textual content yet."
            activity.append(
                RecentActivityItem(
                    notebook_id=descriptor.notebook.nbid,
                    notebook_title=descriptor.notebook.name,
                    page_id=descriptor.tree_id,
                    page_title=descriptor.title,
                    summary=summary,
                    updated_at=updated_at,
                )
            )

        activity.sort(
            key=lambda item: self._parse_timestamp(item.updated_at, fallback_epoch=True),
            reverse=True,
        )
        return activity[: self._recent_activity_limit]

    def _summarize_entries(self, entries: list[dict[str, Any]]) -> tuple[str | None, str]:
        latest_timestamp = "1970-01-01T00:00:00Z"
        best_summary: str | None = None

        for entry in entries:
            updated = entry.get("updated_at") or entry.get("created_at") or ""
            latest_timestamp = max(
                latest_timestamp,
                self._parse_timestamp(updated, fallback_epoch=True),
            )

            if best_summary is not None:
                continue

            content = entry.get("content")
            if not content:
                continue

            text = self._strip_html(content)
            if text:
                best_summary = self._truncate_sentence(text)

        return best_summary, latest_timestamp

    @staticmethod
    def _strip_html(content: str) -> str:
        cleaned = re.sub(r"<[^>]+>", " ", content)
        cleaned = unescape(cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    @staticmethod
    def _truncate_sentence(text: str, limit: int = 200) -> str:
        if len(text) <= limit:
            return text

        truncated = text[: limit - 1].rstrip()
        last_space = truncated.rfind(" ")
        if last_space > 0 and last_space > limit * 0.6:
            truncated = truncated[:last_space]
        return f"{truncated}…"

    @staticmethod
    def _parse_timestamp(value: str, *, fallback_epoch: bool = False) -> str:
        if not value:
            return (
                "1970-01-01T00:00:00Z"
                if fallback_epoch
                else datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            )

        candidate = value.strip()
        if "T" not in candidate and " " in candidate:
            candidate = candidate.replace(" ", "T", 1)
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"

        parsed: datetime
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    parsed = datetime.strptime(candidate, fmt)
                    break
                except ValueError:
                    continue
            else:
                if fallback_epoch:
                    return "1970-01-01T00:00:00Z"
                parsed = datetime.now(UTC)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        else:
            parsed = parsed.astimezone(UTC)

        return parsed.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _to_markdown(how_to_use: HowToUse, lab_summary: LabSummary, router_prompt: str) -> str:
        lines: list[str] = ["## LabArchives MCP Onboarding", ""]
        lines.append("### When to Use")
        for when_item in how_to_use.when:
            lines.append(f"- {when_item}")
        lines.append("")
        lines.append("### Primary Tools")
        for tool, desc in how_to_use.primary_tools.items():
            lines.append(f"- `{tool}` — {desc}")
        lines.append("")
        lines.append("### Workflow Aids")
        lines.append(f"- Decision aid: {how_to_use.decision_aid}")
        lines.append(f"- Context persistence: {how_to_use.context_persistence}")
        lines.append("")
        lines.append("### Notebooks")
        if lab_summary.notebooks:
            for notebook_summary in lab_summary.notebooks:
                notebook_heading = f"**{notebook_summary.title}** (`{notebook_summary.id}`)"
                lines.append(
                    f"- {notebook_heading}, pages: {notebook_summary.n_pages}, "
                    f"last updated: {notebook_summary.last_updated}"
                )
        else:
            lines.append("- No notebooks available")
        lines.append("")
        lines.append("### Recent Activity")
        if lab_summary.recent_activity:
            for activity_item in lab_summary.recent_activity:
                page_heading = (
                    f"**{activity_item.page_title}** "
                    f"(`{activity_item.page_id}` in `{activity_item.notebook_title}`)"
                )
                lines.append(
                    f"- {page_heading} — "
                    f"{activity_item.summary} (updated {activity_item.updated_at})"
                )
        else:
            lines.append("- No recent activity detected")
        lines.append("")
        lines.append("### Router Prompt")
        lines.append(router_prompt)
        return "\n".join(lines)
