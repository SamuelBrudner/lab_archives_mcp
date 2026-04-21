"""Tests for the LabArchives MCP state management module."""

import json
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import networkx as nx
import pytest

from labarchives_mcp.models.upload import ProvenanceMetadata
from labarchives_mcp.state import GRAPH_SCHEMA_VERSION, ProjectContext, StateManager


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


def test_log_page_content_links_adds_direct_edges(state_manager: StateManager) -> None:
    """Detected content links should persist as Page -> Page graph edges."""
    context = state_manager.create_project("Proj 1", "Desc 1")
    state_manager.log_visit("nb1", "p1", "Page 1")

    recorded = state_manager.log_page_content_links(
        "nb1",
        "p1",
        [("nb1", "p2"), ("nb1", "p2"), ("nb1", "p1")],
    )

    graph = nx.node_link_graph(context.graph_data, edges="links")

    assert recorded == 1
    assert graph.has_node("page:p2")
    assert graph.nodes["page:p2"]["type"] == "page"
    assert graph.nodes["page:p2"]["notebook_id"] == "nb1"
    assert graph.has_edge("page:p1", "page:p2")
    assert graph.edges["page:p1", "page:p2"]["relation"] == "content_link"
    assert [visit.page_id for visit in context.visited_pages] == ["p1"]


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

    graph = nx.node_link_graph(context.graph_data, edges="links")
    page_node_id = "page:p1"
    finding_nodes = [n for n, d in graph.nodes(data=True) if d.get("type") == "finding"]

    assert graph.has_node(page_node_id)
    assert finding_nodes
    assert graph.has_edge(page_node_id, finding_nodes[0])


def test_graph_migration_adds_version_and_timestamps(temp_state_dir: Path) -> None:
    """Old graph data is upgraded with schema_version and timing metadata."""
    old_state = {
        "active_context_id": "proj-1",
        "contexts": {
            "proj-1": {
                "id": "proj-1",
                "name": "Proj 1",
                "description": "Desc",
                "linked_notebook_ids": [],
                "status": "active",
                "created_at": 0,
                "visited_pages": [],
                "findings": [],
                "graph_data": {
                    "nodes": [
                        {
                            "id": "proj-1",
                            "type": "project",
                            # missing first_seen/last_seen to be backfilled
                        }
                    ],
                    "links": [
                        {
                            "source": "proj-1",
                            "target": "page:p1",
                            "relation": "visited",
                            # missing created_at/last_seen
                        }
                    ],
                    "directed": True,
                    "multigraph": False,
                    "graph": {},
                },
            }
        },
    }

    state_file = temp_state_dir / "session_state.json"
    state_file.write_text(json.dumps(old_state))

    migrated_manager = StateManager(storage_dir=temp_state_dir)
    context = migrated_manager.get_active_context()
    assert context is not None

    meta = context.graph_data.get("graph", {})
    assert meta.get("schema_version") == GRAPH_SCHEMA_VERSION

    for node in context.graph_data.get("nodes", []):
        assert "first_seen" in node
        assert "last_seen" in node

    for edge in context.graph_data.get("links", []):
        assert "created_at" in edge
        assert "last_seen" in edge


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


def test_visited_pages_capped(state_manager: StateManager) -> None:
    """Ensure visited_pages history is capped at MAX_VISITS."""
    context = state_manager.create_project("Proj", "Desc")
    for i in range(1100):
        state_manager.log_visit("nb", f"p{i}", f"Page {i}")

    assert len(context.visited_pages) == state_manager.MAX_VISITS
    # Should retain the most recent MAX_VISITS
    assert context.visited_pages[0].page_id == "p100"
    assert context.visited_pages[-1].page_id == "p1099"


def test_record_upload_provenance_adds_activity_subgraph(state_manager: StateManager) -> None:
    """Uploads should add activity, artifact, user, and software-agent nodes."""
    context = state_manager.create_project("Proj", "Desc")
    metadata = ProvenanceMetadata(
        git_commit_sha="d" * 40,
        git_branch="main",
        git_repo_url="https://github.com/SamuelBrudner/lab_archives_mcp",
        git_is_dirty=False,
        code_version="0.4.0",
        executed_at=datetime(2026, 4, 20, 14, 1, 58, tzinfo=UTC),
        python_version="3.11.8",
        dependencies={"networkx": "3.4"},
        os_name="Darwin",
        hostname="host.local",
    )

    state_manager.record_upload_provenance(
        uid="uid123",
        notebook_id="nb1",
        page_title="Analysis Results",
        file_path=state_manager.storage_dir / "analysis.ipynb",
        page_tree_id="page-123",
        entry_id="ATTACH_123",
        page_url="https://example.org/page-123",
        created_at="2026-04-20T14:02:11Z",
        file_size_bytes=1234,
        filename="analysis.ipynb",
        metadata=metadata,
        server_version="0.4.0",
        as_page_text=False,
    )

    graph = nx.node_link_graph(context.graph_data, edges="links")
    assert graph.nodes["page:page-123"]["type"] == "page"
    assert graph.nodes["artifact:page-123:ATTACH_123"]["type"] == "artifact"
    assert graph.nodes["activity:upload:page-123:ATTACH_123"]["type"] == "activity"
    assert graph.nodes["user:uid123"]["type"] == "user"
    assert graph.nodes["software_agent:labarchives-mcp-pol"]["type"] == "software_agent"
    assert graph.edges["artifact:page-123:ATTACH_123", "activity:upload:page-123:ATTACH_123"][
        "relation"
    ] == "was_generated_by"


def test_record_upload_provenance_without_active_context_is_noop(
    state_manager: StateManager,
) -> None:
    """Uploads should not create project state when no active project exists."""
    metadata = ProvenanceMetadata(
        git_commit_sha="e" * 40,
        git_branch="main",
        git_repo_url="https://github.com/SamuelBrudner/lab_archives_mcp",
        git_is_dirty=False,
        code_version="0.4.0",
        executed_at=datetime(2026, 4, 20, 14, 1, 58, tzinfo=UTC),
        python_version="3.11.8",
        dependencies={"networkx": "3.4"},
        os_name="Darwin",
        hostname="host.local",
    )

    state_manager.record_upload_provenance(
        uid="uid123",
        notebook_id="nb1",
        page_title="Analysis Results",
        file_path=state_manager.storage_dir / "analysis.ipynb",
        page_tree_id="page-123",
        entry_id="ATTACH_123",
        page_url="https://example.org/page-123",
        created_at="2026-04-20T14:02:11Z",
        file_size_bytes=1234,
        filename="analysis.ipynb",
        metadata=metadata,
        server_version="0.4.0",
        as_page_text=False,
    )

    assert state_manager._state.contexts == {}
