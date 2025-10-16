"""Pydantic schemas for LabArchives MCP onboarding payloads."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

MAX_ONBOARD_PAYLOAD_BYTES = 4096


class HowToUse(BaseModel):
    """Describe when and how to call the LabArchives MCP server."""

    model_config = ConfigDict(extra="forbid")

    when: list[str] = Field(..., description="Scenarios that should trigger LabArchives MCP usage")
    primary_tools: dict[str, str] = Field(
        ..., description="Primary MCP tools with short usage guidance"
    )
    decision_aid: str = Field(
        ..., description="Helper command agents should invoke before deciding to query"
    )
    context_persistence: str = Field(
        ..., description="Instructions for maintaining LabArchives context across turns"
    )


class NotebookSummary(BaseModel):
    """Compact notebook metadata for onboarding."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Notebook identifier (nbid)")
    title: str = Field(..., description="Notebook title")
    n_pages: int = Field(..., ge=0, description="Number of pages in notebook")
    last_updated: str = Field(..., description="ISO timestamp of last notebook update")


class RecentActivityItem(BaseModel):
    """Summaries of recent notebook activity."""

    model_config = ConfigDict(extra="forbid")

    notebook_id: str = Field(..., description="Notebook identifier for the page")
    notebook_title: str = Field(..., description="Notebook title for human-friendly display")
    page_id: str = Field(..., description="Page tree identifier")
    page_title: str = Field(..., description="Page display text")
    summary: str = Field(..., description="Human-readable summary of recent activity")
    updated_at: str = Field(..., description="ISO timestamp of the most recent edit on the page")


class LabSummary(BaseModel):
    """Aggregate lab context for onboarding."""

    model_config = ConfigDict(extra="forbid")

    notebooks: list[NotebookSummary] = Field(default_factory=list)
    recent_activity: list[RecentActivityItem] = Field(default_factory=list)


class StickyContext(BaseModel):
    """Hints that agents should persist across turns."""

    model_config = ConfigDict(extra="forbid")

    last_notebook_id: str | None = Field(None, description="Most recently referenced notebook id")
    last_page_id: str | None = Field(None, description="Most recently referenced page id")


def _lab_summary_factory() -> LabSummary:
    return LabSummary()


def _sticky_context_factory() -> StickyContext:
    return StickyContext(last_notebook_id=None, last_page_id=None)


class OnboardPayload(BaseModel):
    """Top-level onboarding payload returned to MCP agents."""

    model_config = ConfigDict(extra="forbid")

    server: str = Field(..., description="Server identifier")
    version: str = Field(..., description="Server version")
    purpose: str = Field(..., description="Short description of LabArchives MCP purpose")
    banner: str = Field(..., description="Single-line banner for routers/UI surfaces")
    how_to_use: HowToUse = Field(...)
    lab_summary: LabSummary = Field(default_factory=_lab_summary_factory)
    sticky_context: StickyContext = Field(default_factory=_sticky_context_factory)
    router_prompt: str = Field(..., description="Prompt fragment instructing router usage")
    markdown: str = Field(..., description="Human-readable onboarding markdown block")

    def to_json_bytes(self) -> bytes:
        """Return a compact JSON representation for size validation."""
        payload_dict = self.model_dump(by_alias=True, exclude_none=True)
        return json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation for MCP responses."""

        return self.model_dump(by_alias=True, exclude_none=True)
