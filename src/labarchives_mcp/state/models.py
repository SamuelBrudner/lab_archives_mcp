"""Pydantic models for persistent project state."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

from .constants import GRAPH_SCHEMA_VERSION


class Finding(BaseModel):
    """A key fact or data point extracted during an experiment."""

    content: str = Field(..., description="The fact or finding text")
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp of discovery")
    source_url: str | None = Field(None, description="URL or ID of the source page")


class VisitedPage(BaseModel):
    """Record of a page visit within an experiment context."""

    page_id: str = Field(..., description="Page tree ID")
    title: str = Field(..., description="Page title")
    notebook_id: str | None = Field(None, description="Notebook ID")
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp of visit")


class ProjectContext(BaseModel):
    """A scoped unit of work representing a research project."""

    id: str = Field(..., description="Unique identifier for the project")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="High-level goal or description")
    linked_notebook_ids: list[str] = Field(
        default_factory=list, description="List of relevant LabArchives Notebook IDs"
    )
    status: str = Field("active", description="active, paused, completed")
    created_at: float = Field(default_factory=time.time)
    visited_pages: list[VisitedPage] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    graph_data: dict[str, Any] = Field(
        default_factory=lambda: {
            "nodes": [],
            "links": [],
            "directed": True,
            "multigraph": False,
            "graph": {"schema_version": GRAPH_SCHEMA_VERSION},
        },
        description="Serialized NetworkX graph",
    )


class SessionState(BaseModel):
    """Global state container for the agent's memory."""

    active_context_id: str | None = Field(None, description="ID of the currently active project")
    contexts: dict[str, ProjectContext] = Field(default_factory=dict)
