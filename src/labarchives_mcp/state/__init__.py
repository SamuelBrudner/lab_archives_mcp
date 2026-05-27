"""Persistent state management for LabArchives MCP agent context."""

import os

import networkx as nx

from .constants import GRAPH_SCHEMA_VERSION
from .exceptions import GraphUpdateError, StateLoadError, StatePersistenceError, StateSaveError
from .graph_helpers import (
    GRAPH_UPDATE_ERRORS,
    _graph_attrs,
    _touch_graph_node,
    _touch_notebook_node,
    _touch_page_node,
    _upsert_graph_edge,
)
from .knowledge_graph import KnowledgeGraph
from .manager import StateManager
from .models import Finding, ProjectContext, SessionState, VisitedPage
from .project import ProjectService
from .provenance import ProvenanceService
from .repository import StateRepository
from .validation import GraphValidationService

__all__ = [
    "GRAPH_SCHEMA_VERSION",
    "GRAPH_UPDATE_ERRORS",
    "Finding",
    "GraphUpdateError",
    "GraphValidationService",
    "KnowledgeGraph",
    "ProjectContext",
    "ProjectService",
    "ProvenanceService",
    "SessionState",
    "StateLoadError",
    "StateManager",
    "StatePersistenceError",
    "StateRepository",
    "StateSaveError",
    "VisitedPage",
    "_graph_attrs",
    "_touch_graph_node",
    "_touch_notebook_node",
    "_touch_page_node",
    "_upsert_graph_edge",
    "nx",
    "os",
]
