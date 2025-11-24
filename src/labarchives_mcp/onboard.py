"""Generate onboarding payloads for the LabArchives MCP server."""

from __future__ import annotations

import asyncio
import time

from labarchives_mcp.auth import AuthenticationManager
from labarchives_mcp.eln_client import LabArchivesClient
from labarchives_mcp.schemas.onboard import HowToUse, LabSummary, OnboardPayload, StickyContext


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
        # We no longer scan notebooks or summarize activity.
        # The agent starts "clean" and relies on search.

        how_to_use = HowToUse(
            when=[
                "User mentions experiments, protocols, results, or prior lab work.",
                "Prompts reference LabArchives notebooks, pages, figures, or sample IDs.",
                "Requests involve lab dates, experiment logs, or ELN provenance.",
                "User wants to start a long-running research task or manage a project context.",
            ],
            primary_tools={
                "create_project": "Start a new research context (Bead) to scope your work.",
                "log_finding": "Record a key fact or observation to the active project.",
                "suggest_next_steps": "Get AI-driven recommendations based on your progress.",
                "search_labarchives": "Find relevant ELN pages from prompts. Try this first.",
                "list_notebooks": "Enumerate notebooks available to the authenticated user.",
                "list_notebook_pages": "Browse notebook structure to locate pages.",
                "read_notebook_page": "Retrieve full structured content for a given page.",
            },
            decision_aid="Call `decide_labarchives_usage` or start with `search_labarchives`.",
            context_persistence="Add the provided `sticky_context` block to each response turn.",
        )

        # Empty summary
        lab_summary = LabSummary(
            notebooks=[],
            recent_activity=[],
        )

        sticky_context = StickyContext(
            last_notebook_id=None,
            last_page_id=None,
            workflow_hint="Prioritize semantic search (search_labarchives) for new queries.",
        )

        router_prompt = (
            "Use LabArchives MCP for anything involving experiments, protocols, results, "
            "ELN pages, or managing research contexts."
        )
        banner = "LabArchives MCP • Access experimental notebooks and context."

        markdown = self._to_markdown(how_to_use, router_prompt)

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
    def _to_markdown(how_to_use: HowToUse, router_prompt: str) -> str:
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
        lines.append("### Notebooks & Activity")
        lines.append("Use `list_notebooks` to see available notebooks.")
        lines.append("Use `search_labarchives` to find relevant pages.")
        lines.append("")
        lines.append("### Router Prompt")
        lines.append(router_prompt)
        return "\n".join(lines)
