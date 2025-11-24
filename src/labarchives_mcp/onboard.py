"""Generate onboarding payloads for the LabArchives MCP server."""

from __future__ import annotations

import asyncio
import re
import time

from labarchives_mcp.auth import AuthenticationManager
from labarchives_mcp.eln_client import LabArchivesClient
from labarchives_mcp.schemas.onboard import (
    HowToUse,
    LabSummary,
    NotebookSummary,
    OnboardPayload,
    RecentActivityItem,
    StickyContext,
)


class OnboardService:
    """Aggregate notebook metadata to produce onboarding payloads."""

    def __init__(
        self,
        auth_manager: AuthenticationManager,
        notebook_client: LabArchivesClient,
        *,
        version: str,
        cache_ttl_seconds: int = 300,
        # Deprecated/Unused parameters kept for compatibility
        max_notebooks: int = 5,
        recent_activity_limit: int = 5,
    ) -> None:
        self._auth_manager = auth_manager
        self._notebook_client = notebook_client
        self._version = version
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cache: tuple[float, OnboardPayload] | None = None
        self._lock = asyncio.Lock()
        self._max_notebooks = max_notebooks
        self._recent_activity_limit = recent_activity_limit

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
            # No need to check size budget as it will be very small now

            self._cache = (now, payload)
            return payload

    async def _build_payload(self) -> OnboardPayload:
        uid = await self._auth_manager.ensure_uid()

        try:
            notebooks = await self._notebook_client.list_notebooks(uid)
        except Exception:
            notebooks = []

        notebook_summaries: list[NotebookSummary] = []
        activity_items: list[RecentActivityItem] = []

        for notebook in notebooks[: self._max_notebooks]:
            page_nodes = []
            try:
                page_nodes = await self._notebook_client.get_notebook_tree(uid, notebook.nbid, 0)
            except Exception:
                page_nodes = []

            n_pages = sum(1 for node in page_nodes if node.get("is_page"))
            notebook_summaries.append(
                NotebookSummary(
                    id=notebook.nbid,
                    title=notebook.name,
                    n_pages=n_pages,
                    last_updated=notebook.modified_at or notebook.created_at,
                )
            )

            # Build recent activity summaries up to limit
            for node in page_nodes:
                if not node.get("is_page"):
                    continue
                if len(activity_items) >= self._recent_activity_limit:
                    break
                page_id = node.get("tree_id")
                page_title = node.get("display_text", "Untitled")
                try:
                    entries = await self._notebook_client.get_page_entries(
                        uid, notebook.nbid, str(page_id), include_data=True
                    )
                except Exception:
                    entries = []

                if not entries:
                    continue
                entry = entries[0]
                content = entry.get("content") or ""
                summary = self._strip_html(content)
                updated_at = entry.get("updated_at") or entry.get("created_at") or ""

                activity_items.append(
                    RecentActivityItem(
                        notebook_id=str(notebook.nbid),
                        notebook_title=notebook.name,
                        page_id=str(page_id),
                        page_title=page_title,
                        summary=summary,
                        updated_at=updated_at,
                    )
                )

            if len(activity_items) >= self._recent_activity_limit:
                break

        # Sort activity by recency if timestamps exist
        activity_items.sort(key=lambda a: a.updated_at or "", reverse=True)

        how_to_use = HowToUse(
            when=[
                "User mentions experiments, protocols, results, or prior lab work.",
                "Prompts reference LabArchives notebooks, pages, figures, or sample IDs.",
                "Requests involve lab dates, experiment logs, or ELN provenance.",
                "User wants to start a long-running research task or manage a project context.",
            ],
            primary_tools={
                "search_labarchives": "Search ALL notebooks with natural language—no ID needed.",
                "create_project": "Start a new research context to organize your work.",
                "get_related_pages": (
                    "Find related pages via project graph or detected content links."
                ),
                "trace_provenance": "Discover the source and derivation history of an entry.",
                "suggest_next_steps": "Get lightweight guidance from the current project state.",
                "list_notebooks": "Enumerate notebooks available to the authenticated user.",
                "list_notebook_pages": "Browse notebook structure to locate pages.",
                "read_notebook_page": "Retrieve full structured content for a given page.",
            },
            decision_aid="Start with `search_labarchives`—it searches all notebooks.",
            context_persistence="Add the provided `sticky_context` block to each response turn.",
        )

        lab_summary = LabSummary(
            notebooks=notebook_summaries,
            recent_activity=activity_items,
        )

        sticky_context = StickyContext(
            last_notebook_id=None,
            last_page_id=None,
            workflow_hint="ALWAYS start with search_labarchives for content queries. "
            "Use create_project() to organize multi-session work.",
        )

        router_prompt = (
            "Use LabArchives MCP for anything involving experiments, protocols, results, "
            "ELN pages, or managing research contexts."
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

    @staticmethod
    def _strip_html(text: str) -> str:
        return re.sub(r"<[^>]+>", "", text)

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
        lines.append("### Notebooks")
        if lab_summary.notebooks:
            for nb in lab_summary.notebooks:
                lines.append(f"- {nb.title} (pages: {nb.n_pages}, updated: {nb.last_updated})")
        else:
            lines.append("- No notebooks available yet.")
        lines.append("")
        lines.append("### Recent Activity")
        if lab_summary.recent_activity:
            for act in lab_summary.recent_activity:
                lines.append(
                    f"- {act.notebook_title} / {act.page_title}: "
                    f"{act.summary} (updated {act.updated_at})"
                )
        else:
            lines.append("- No recent activity found.")
        lines.append("")
        lines.append("### Router Prompt")
        lines.append(router_prompt)
        return "\n".join(lines)
