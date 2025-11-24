"""Tests for the LabArchives MCP state management module."""

import json
from collections.abc import Generator
from pathlib import Path

import networkx as nx
import pytest

from labarchives_mcp.state import ProjectContext, StateManager


@pytest.fixture  # type: ignore[misc]
def temp_state_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Provide a temporary directory for state files."""
    yield tmp_path


@pytest.fixture  # type: ignore[misc]
def state_manager(temp_state_dir: Path) -> StateManager:
    """Provide a StateManager instance using the temp directory."""
    return StateManager(storage_dir=temp_state_dir)


def test_initial_state(state_manager: StateManager) -> None:
    """Test that a fresh manager has empty state."""
    assert state_manager._state.active_context_id is None
    assert state_manager._state.contexts == {}
    assert state_manager.get_active_context() is None


def test_create_project(state_manager: StateManager) -> None:
    """Test creating a new project context."""
    context = state_manager.create_project("Test Project", "Testing description")

    assert isinstance(context, ProjectContext)
    assert context.name == "Test Project"
    assert context.description == "Testing description"
    assert context.status == "active"
    assert context.id.startswith("proj-")

    # Check it's active
    assert state_manager._state.active_context_id == context.id
    assert state_manager.get_active_context() == context

    # Check persistence
    state_file = state_manager.state_file
    assert state_file.exists()
    with open(state_file) as f:
        data = json.load(f)
        assert data["active_context_id"] == context.id
        assert context.id in data["contexts"]


def test_switch_project(state_manager: StateManager) -> None:
    """Test switching between projects."""
    proj1 = state_manager.create_project("Proj 1", "Desc 1")
    proj2 = state_manager.create_project("Proj 2", "Desc 2")

    assert state_manager.get_active_context() == proj2

    switched = state_manager.switch_project(proj1.id)
    assert switched == proj1
    assert state_manager.get_active_context() == proj1

    with pytest.raises(ValueError):
        state_manager.switch_project("non-existent-id")


def test_log_visit(state_manager: StateManager) -> None:
    """Test logging page visits."""
    # Should do nothing if no active context
    state_manager.log_visit("nb1", "p1", "Page 1")
    assert state_manager.get_active_context() is None

    # Create context
    context = state_manager.create_project("Proj 1", "Desc 1")
    state_manager.log_visit("nb1", "p1", "Page 1")

    assert len(context.visited_pages) == 1
    visit = context.visited_pages[0]
    assert visit.notebook_id == "nb1"
    assert visit.page_id == "p1"
    assert visit.title == "Page 1"

    # Check persistence
    state_manager2 = StateManager(storage_dir=state_manager.storage_dir)
    loaded_context = state_manager2.get_active_context()
    assert loaded_context is not None
    assert len(loaded_context.visited_pages) == 1
    assert loaded_context.visited_pages[0].page_id == "p1"

    # Graph should contain project and page nodes with a visited edge
    graph_nodes = {node["id"] for node in loaded_context.graph_data.get("nodes", [])}
    assert context.id in graph_nodes
    assert f"page:{visit.page_id}" in graph_nodes


def test_log_finding(state_manager: StateManager) -> None:
    """Test logging findings."""
    with pytest.raises(RuntimeError):
        state_manager.log_finding("Fact 1")

    context = state_manager.create_project("Proj 1", "Desc 1")
    state_manager.log_finding("Fact 1", "http://source.com")

    assert len(context.findings) == 1
    finding = context.findings[0]
    assert finding.content == "Fact 1"
    assert finding.source_url == "http://source.com"

    # Graph should contain project and finding nodes with a discovered edge
    graph_nodes = {node["id"] for node in context.graph_data.get("nodes", [])}
    assert context.id in graph_nodes
    finding_nodes = [node for node in graph_nodes if node.startswith("finding:")]
    assert finding_nodes


def test_log_finding_links_page(state_manager: StateManager) -> None:
    """Finding should be connected to a source page when provided."""
    context = state_manager.create_project("Proj 1", "Desc 1")
    state_manager.log_finding("Fact 1", page_id="p1")

    graph = nx.node_link_graph(context.graph_data)
    page_node_id = "page:p1"
    finding_nodes = [n for n, d in graph.nodes(data=True) if d.get("type") == "finding"]

    assert graph.has_node(page_node_id)
    assert finding_nodes
    assert graph.has_edge(page_node_id, finding_nodes[0])


def test_list_projects(state_manager: StateManager) -> None:
    """Test listing projects."""
    state_manager.create_project("Proj 1", "Desc 1")
    state_manager.create_project("Proj 2", "Desc 2")

    projects = state_manager.list_projects()
    assert len(projects) == 2

    # Proj 2 was created last, so it should be active
    proj2_summary = next(e for e in projects if e["name"] == "Proj 2")
    assert proj2_summary["active"] is True

    proj1_summary = next(e for e in projects if e["name"] == "Proj 1")
    assert proj1_summary["active"] is False
