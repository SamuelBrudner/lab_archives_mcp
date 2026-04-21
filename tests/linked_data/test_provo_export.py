"""Tests for PROV-O / JSON-LD export of project provenance graphs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import networkx as nx
import pytest

from labarchives_mcp.linked_data.provo_export import (
    CONTEXT_URL,
    MissingLinkedDataDependencyError,
    build_context,
    export_graph_jsonld,
    export_project_jsonld,
    write_graph_linked_data,
    write_graph_jsonld,
    write_project_jsonld,
)
from labarchives_mcp.models.upload import ProvenanceMetadata
from labarchives_mcp.state import StateManager


PROV_NS = "http://www.w3.org/ns/prov#"
SCHEMA_NS = "http://schema.org/"


class _FakeLinkedDataWriter:
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self.parse_data: str | None = None
        self.parse_format: str | None = None
        self.serialize_format: str | None = None

    def parse(self, *, data: str, format: str) -> _FakeLinkedDataWriter:
        self.parse_data = data
        self.parse_format = format
        return self

    def serialize(self, *, format: str) -> str:
        self.serialize_format = format
        return f"{self.kind}:{format}"


class _FakeRdflib:
    def __init__(self) -> None:
        self.instances: list[_FakeLinkedDataWriter] = []

    def Graph(self) -> _FakeLinkedDataWriter:
        writer = _FakeLinkedDataWriter("graph")
        self.instances.append(writer)
        return writer

    def Dataset(self) -> _FakeLinkedDataWriter:
        writer = _FakeLinkedDataWriter("dataset")
        self.instances.append(writer)
        return writer


@pytest.fixture
def empty_graph() -> nx.DiGraph:
    return nx.DiGraph()


@pytest.fixture
def legacy_graph() -> nx.DiGraph:
    graph = nx.DiGraph()
    graph.add_node("proj-1", type="project", label="Proj 1", description="Desc", created_at=1.0)
    graph.add_node("notebook:nb1", type="notebook", label="nb1", notebook_id="nb1")
    graph.add_node(
        "page:p1",
        type="page",
        label="Page 1",
        page_id="p1",
        notebook_id="nb1",
        first_seen=2.0,
        last_seen=3.0,
    )
    graph.add_node("finding:f1", type="finding", label="Observation", full_content="Observation body")
    graph.add_edge("proj-1", "notebook:nb1", relation="uses_notebook")
    graph.add_edge("notebook:nb1", "page:p1", relation="contains")
    graph.add_edge("proj-1", "page:p1", relation="visited")
    graph.add_edge("proj-1", "finding:f1", relation="discovered")
    graph.add_edge("page:p1", "finding:f1", relation="evidence_from")
    return graph


@pytest.fixture
def enriched_graph() -> nx.DiGraph:
    graph = nx.DiGraph()
    graph.add_node("proj-1", type="project", label="Proj 1", description="Desc", created_at=1.0)
    graph.add_node("notebook:nb1", type="notebook", label="nb1", notebook_id="nb1")
    graph.add_node(
        "page:page-123",
        type="page",
        label="Analysis Results",
        page_id="page-123",
        notebook_id="nb1",
        page_url="https://example.org/page-123",
        created_at="2026-04-20T14:02:11Z",
    )
    graph.add_node(
        "artifact:page-123:ATTACH_123",
        type="artifact",
        label="analysis.ipynb",
        filename="analysis.ipynb",
        entry_id="ATTACH_123",
        page_id="page-123",
        file_size_bytes=1234,
        encoding_format=".ipynb",
        created_at="2026-04-20T14:02:11Z",
    )
    graph.add_node(
        "activity:upload:page-123:ATTACH_123",
        type="activity",
        label="Upload analysis.ipynb",
        executed_at=datetime(2026, 4, 20, 14, 1, 58, tzinfo=UTC),
        completed_at=datetime(2026, 4, 20, 14, 2, 11, tzinfo=UTC),
        git_commit_sha="a" * 40,
        git_branch="main",
        git_repo_url="https://github.com/SamuelBrudner/lab_archives_mcp",
        git_is_dirty=False,
        code_version="0.4.0",
        python_version="3.11.8",
        dependencies={"networkx": "3.4"},
        os_name="Darwin",
        hostname="host.local",
        server_version="0.4.0",
    )
    graph.add_node("user:uid123", type="user", label="uid123", uid="uid123")
    graph.add_node(
        "software_agent:labarchives-mcp-pol",
        type="software_agent",
        label="LabArchives MCP Server",
        identifier="labarchives-mcp-pol",
        server_version="0.4.0",
    )
    graph.add_edge("proj-1", "notebook:nb1", relation="uses_notebook")
    graph.add_edge("notebook:nb1", "page:page-123", relation="contains")
    graph.add_edge("proj-1", "page:page-123", relation="tracked")
    graph.add_edge("proj-1", "artifact:page-123:ATTACH_123", relation="tracked")
    graph.add_edge("proj-1", "activity:upload:page-123:ATTACH_123", relation="tracked")
    graph.add_edge("page:page-123", "artifact:page-123:ATTACH_123", relation="contains_artifact")
    graph.add_edge(
        "page:page-123", "activity:upload:page-123:ATTACH_123", relation="was_generated_by"
    )
    graph.add_edge(
        "artifact:page-123:ATTACH_123",
        "activity:upload:page-123:ATTACH_123",
        relation="was_generated_by",
    )
    graph.add_edge("page:page-123", "user:uid123", relation="was_attributed_to")
    graph.add_edge("artifact:page-123:ATTACH_123", "user:uid123", relation="was_attributed_to")
    graph.add_edge(
        "activity:upload:page-123:ATTACH_123",
        "user:uid123",
        relation="was_associated_with",
    )
    graph.add_edge(
        "activity:upload:page-123:ATTACH_123",
        "software_agent:labarchives-mcp-pol",
        relation="was_associated_with",
    )
    return graph


def _node_by_suffix(document: dict[str, object], suffix: str) -> dict[str, object]:
    return next(node for node in document["@graph"] if str(node["@id"]).endswith(suffix))


def test_build_context_binds_expected_namespaces() -> None:
    context = build_context()
    assert context["prov"] == PROV_NS
    assert context["schema"] == SCHEMA_NS
    assert context["dateCreated"]["@type"] == "xsd:dateTime"
    assert context["dateModified"]["@type"] == "xsd:dateTime"
    assert context["hadMember"]["@id"] == "prov:hadMember"
    assert context["isPartOf"]["@id"] == "schema:isPartOf"


def test_empty_graph_produces_empty_graph_array(empty_graph: nx.DiGraph) -> None:
    document = export_graph_jsonld(empty_graph)
    assert document["@context"] == build_context()
    assert document["@graph"] == []


def test_hosted_context_url_is_available_when_requested(empty_graph: nx.DiGraph) -> None:
    document = export_graph_jsonld(empty_graph, inline_context=False)
    assert document["@context"] == CONTEXT_URL


def test_hosted_context_artifacts_match_inline_context() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    expected = build_context()

    for relative_path in ("ns/context.jsonld", "docs/ns/context.jsonld"):
        hosted_context = json.loads((repo_root / relative_path).read_text())
        assert hosted_context == {"@context": expected}


def test_legacy_graph_exports_membership_and_derivation(legacy_graph: nx.DiGraph) -> None:
    document = export_graph_jsonld(legacy_graph)
    project = _node_by_suffix(document, "project/proj-1")
    notebook = _node_by_suffix(document, "notebook/nb1")
    finding = _node_by_suffix(document, "finding/f1")

    assert "labmcp:notebook/nb1" in str(project["hadMember"])
    assert notebook["isPartOf"] == "labmcp:project/proj-1"
    assert finding["wasDerivedFrom"] == "labmcp:page/p1"


def test_was_derived_from_mints_stable_iris_across_mixed_entity_kinds() -> None:
    graph = nx.DiGraph()
    graph.add_node("proj-1", type="project", label="Proj 1")
    graph.add_node("notebook:nb1", type="notebook", label="Notebook 1", notebook_id="nb1")
    graph.add_node("page:p1", type="page", label="Page 1", page_id="p1")
    graph.add_node(
        "artifact:p1:ATTACH_123",
        type="artifact",
        label="analysis.ipynb",
        entry_id="ATTACH_123",
        page_id="p1",
    )
    graph.add_node("finding:f1", type="finding", label="Observation")

    for source_node_id in ("proj-1", "notebook:nb1", "page:p1", "artifact:p1:ATTACH_123"):
        graph.add_edge(source_node_id, "finding:f1", relation="evidence_from")

    document = export_graph_jsonld(graph)
    finding = _node_by_suffix(document, "finding/f1")

    assert set(finding["wasDerivedFrom"]) == {
        "labmcp:project/proj-1",
        "labmcp:notebook/nb1",
        "labmcp:page/p1",
        "labmcp:artifact/p1/ATTACH_123",
    }


def test_enriched_graph_exports_upload_provenance(enriched_graph: nx.DiGraph) -> None:
    document = export_graph_jsonld(enriched_graph)
    page = _node_by_suffix(document, "page/page-123")
    artifact = _node_by_suffix(document, "artifact/page-123/ATTACH_123")
    activity = _node_by_suffix(document, "activity/upload/page-123/ATTACH_123")

    assert page["wasGeneratedBy"] == "labmcp:activity/upload/page-123/ATTACH_123"
    assert "labmcp:page/page-123" in str(artifact["isPartOf"])
    assert activity["wasAssociatedWith"] == [
        "labmcp:user/uid123",
        "labmcp:software_agent/labarchives-mcp-pol",
    ]
    assert activity["labmcp:gitCommitSha"] == "a" * 40
    assert activity["labmcp:serverVersion"] == "0.4.0"


def test_datetimes_serialize_as_iso8601_z(enriched_graph: nx.DiGraph) -> None:
    document = export_graph_jsonld(enriched_graph)
    page = _node_by_suffix(document, "page/page-123")
    activity = _node_by_suffix(document, "activity/upload/page-123/ATTACH_123")
    assert page["dateCreated"] == "2026-04-20T14:02:11Z"
    assert activity["startedAtTime"] == "2026-04-20T14:01:58Z"
    assert activity["endedAtTime"] == "2026-04-20T14:02:11Z"


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("executed_at", datetime(2026, 4, 20, 14, 1, 58)),
        ("created_at", "2026-04-20T14:02:11"),
    ],
)
def test_naive_datetimes_raise_loudly(field_name: str, value: object) -> None:
    graph = nx.DiGraph()
    graph.add_node("activity:upload:test", type="activity", **{field_name: value})

    with pytest.raises(ValueError, match="Naive datetime"):
        export_graph_jsonld(graph)


def test_unknown_node_type_raises() -> None:
    graph = nx.DiGraph()
    graph.add_node("mystery", type="mystery")
    with pytest.raises(ValueError, match="Unsupported graph node type"):
        export_graph_jsonld(graph)


def test_write_graph_jsonld_creates_file(enriched_graph: nx.DiGraph, tmp_path: Path) -> None:
    output = tmp_path / "graph.jsonld"
    write_graph_jsonld(enriched_graph, output)
    written = json.loads(output.read_text())
    assert "@context" in written
    assert len(written["@graph"]) == 7


def test_write_graph_turtle_uses_rdflib_graph(
    enriched_graph: nx.DiGraph,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_rdflib = _FakeRdflib()
    monkeypatch.setattr("labarchives_mcp.linked_data.provo_export._load_rdflib", lambda: fake_rdflib)

    output = tmp_path / "graph.ttl"
    write_graph_linked_data(enriched_graph, output, output_format="turtle")

    writer = fake_rdflib.instances[0]
    assert writer.kind == "graph"
    assert writer.parse_format == "json-ld"
    assert json.loads(writer.parse_data or "{}")["@context"] == build_context()
    assert writer.serialize_format == "turtle"
    assert output.read_text() == "graph:turtle\n"


def test_write_graph_nquads_uses_rdflib_dataset(
    enriched_graph: nx.DiGraph,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_rdflib = _FakeRdflib()
    monkeypatch.setattr("labarchives_mcp.linked_data.provo_export._load_rdflib", lambda: fake_rdflib)

    output = tmp_path / "graph.nq"
    write_graph_linked_data(enriched_graph, output, output_format="n-quads")

    writer = fake_rdflib.instances[0]
    assert writer.kind == "dataset"
    assert writer.parse_format == "json-ld"
    assert writer.serialize_format == "nquads"
    assert output.read_text() == "dataset:nquads\n"


def test_alternate_formats_require_optional_rdflib(
    enriched_graph: nx.DiGraph,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _missing_rdflib() -> object:
        raise MissingLinkedDataDependencyError("install linked-data extra")

    monkeypatch.setattr("labarchives_mcp.linked_data.provo_export._load_rdflib", _missing_rdflib)

    with pytest.raises(MissingLinkedDataDependencyError, match="linked-data extra"):
        write_graph_linked_data(enriched_graph, tmp_path / "graph.ttl", output_format="turtle")


def test_state_wrapper_loads_project_from_state(tmp_path: Path) -> None:
    manager = StateManager(storage_dir=tmp_path)
    context = manager.create_project("Proj 1", "Desc")
    manager.log_visit("nb1", "p1", "Page 1")
    metadata = ProvenanceMetadata(
        git_commit_sha="b" * 40,
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
    manager.record_upload_provenance(
        uid="uid123",
        notebook_id="nb1",
        page_title="Analysis Results",
        file_path=tmp_path / "analysis.ipynb",
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

    document = export_project_jsonld(context.id, state_dir=tmp_path)
    assert any(node["@id"] == "labmcp:project/" + context.id for node in document["@graph"])
    assert any("activity/upload/page-123/ATTACH_123" in str(node["@id"]) for node in document["@graph"])


def test_write_project_jsonld_matches_in_memory_export(tmp_path: Path) -> None:
    manager = StateManager(storage_dir=tmp_path)
    context = manager.create_project("Proj 1", "Desc")
    manager.log_visit("nb1", "p1", "Page 1")

    output = tmp_path / "project.jsonld"
    write_project_jsonld(context.id, output, state_dir=tmp_path)

    written = json.loads(output.read_text())
    expected = export_project_jsonld(context.id, state_dir=tmp_path)
    assert written == expected


def test_exported_jsonld_loads_in_rdflib(enriched_graph: nx.DiGraph) -> None:
    rdflib = pytest.importorskip("rdflib")
    document = export_graph_jsonld(enriched_graph)
    graph = rdflib.Graph()
    graph.parse(data=json.dumps(document), format="json-ld")
    prov = rdflib.Namespace(PROV_NS)
    rdf_type = rdflib.RDF.type
    activities = list(graph.triples((None, rdf_type, prov.Activity)))
    assert len(activities) == 1
