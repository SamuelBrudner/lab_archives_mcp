"""Serialize LabArchives project provenance graphs to JSON-LD."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final
from urllib.parse import quote

import networkx as nx

from labarchives_mcp.state import ProjectContext, StateManager

LABMCP_BASE: Final[str] = "https://samuelbrudner.github.io/lab_archives_mcp/ns#"
CONTEXT_URL: Final[str] = "https://samuelbrudner.github.io/lab_archives_mcp/ns/context.jsonld"

_TYPE_MAP: Final[dict[str, list[str]]] = {
    "project": ["prov:Collection", "schema:Dataset"],
    "notebook": ["prov:Collection", "schema:Collection"],
    "page": ["prov:Entity", "schema:CreativeWork"],
    "finding": ["prov:Entity", "schema:CreativeWork"],
    "artifact": ["prov:Entity", "schema:DigitalDocument"],
    "activity": ["prov:Activity"],
    "user": ["prov:Agent", "schema:Person"],
    "software_agent": ["prov:Agent", "prov:SoftwareAgent", "schema:SoftwareApplication"],
}

_ACTIVITY_FIELD_MAP: Final[dict[str, str]] = {
    "git_commit_sha": "labmcp:gitCommitSha",
    "git_branch": "labmcp:gitBranch",
    "git_repo_url": "labmcp:gitRepoUrl",
    "git_is_dirty": "labmcp:gitIsDirty",
    "python_version": "labmcp:pythonVersion",
    "dependencies": "labmcp:dependencies",
    "hostname": "labmcp:hostname",
    "os_name": "labmcp:operatingSystem",
    "server_version": "labmcp:serverVersion",
}


def build_context() -> dict[str, Any]:
    """Return the inline JSON-LD context."""
    return {
        "prov": "http://www.w3.org/ns/prov#",
        "schema": "http://schema.org/",
        "labmcp": LABMCP_BASE,
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "name": "schema:name",
        "description": "schema:description",
        "identifier": "schema:identifier",
        "url": "schema:url",
        "dateCreated": "schema:dateCreated",
        "dateModified": "schema:dateModified",
        "contentSize": "schema:contentSize",
        "encodingFormat": "schema:encodingFormat",
        "softwareVersion": "schema:softwareVersion",
        "isPartOf": {"@id": "schema:isPartOf", "@type": "@id"},
        "hadMember": {"@id": "prov:hadMember", "@type": "@id"},
        "wasGeneratedBy": {"@id": "prov:wasGeneratedBy", "@type": "@id"},
        "used": {"@id": "prov:used", "@type": "@id"},
        "wasDerivedFrom": {"@id": "prov:wasDerivedFrom", "@type": "@id"},
        "wasAttributedTo": {"@id": "prov:wasAttributedTo", "@type": "@id"},
        "wasAssociatedWith": {"@id": "prov:wasAssociatedWith", "@type": "@id"},
        "wasInformedBy": {"@id": "prov:wasInformedBy", "@type": "@id"},
        "startedAtTime": {"@id": "prov:startedAtTime", "@type": "xsd:dateTime"},
        "endedAtTime": {"@id": "prov:endedAtTime", "@type": "xsd:dateTime"},
    }


def _as_isoformat(value: Any) -> str | None:
    """Normalize timestamps from strings, datetimes, or epoch seconds."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return None


def _first_present(attrs: Mapping[str, Any], *keys: str) -> Any | None:
    for key in keys:
        if key in attrs and attrs[key] is not None:
            return attrs[key]
    return None


def _infer_node_type(node_id: str, attrs: Mapping[str, Any]) -> str:
    node_type = attrs.get("type")
    if isinstance(node_type, str):
        if node_type not in _TYPE_MAP:
            raise ValueError(f"Unsupported graph node type for {node_id!r}")
        return node_type
    prefix = node_id.split(":", 1)[0]
    if prefix in _TYPE_MAP:
        return prefix
    raise ValueError(f"Unsupported graph node type for {node_id!r}")


def _node_iri(node_id: str, node_type: str) -> str:
    if node_id.startswith(f"{node_type}:"):
        tail = node_id.split(":")[1:]
    else:
        tail = [node_id]
    encoded_tail = "/".join(quote(part, safe="") for part in tail)
    return f"labmcp:{node_type}/{encoded_tail}"


def _append_ref(document: dict[str, Any], key: str, value: str) -> None:
    current = document.get(key)
    if current is None:
        document[key] = value
        return
    if isinstance(current, list):
        if value not in current:
            current.append(value)
        return
    if current != value:
        document[key] = [current, value]


def _base_document(node_id: str, node_type: str, attrs: Mapping[str, Any]) -> dict[str, Any]:
    document: dict[str, Any] = {
        "@id": _node_iri(node_id, node_type),
        "@type": _TYPE_MAP[node_type],
    }
    name = _first_present(attrs, "name", "label", "title", "filename")
    if name is not None:
        document["name"] = name
    description = _first_present(attrs, "description", "full_content")
    if description is not None:
        document["description"] = description
    identifier = _first_present(attrs, "identifier", "uid", "notebook_id", "page_id", "entry_id")
    if identifier is None:
        identifier = node_id
    document["identifier"] = identifier
    url = _first_present(attrs, "url", "page_url")
    if url is not None:
        document["url"] = url

    created = _as_isoformat(
        _first_present(attrs, "created_at", "timestamp", "first_seen", "executed_at")
    )
    modified = _as_isoformat(_first_present(attrs, "modified_at", "last_seen", "completed_at"))
    if created is not None:
        document["dateCreated"] = created
    if modified is not None:
        document["dateModified"] = modified

    if node_type == "artifact":
        if (content_size := attrs.get("file_size_bytes")) is not None:
            document["contentSize"] = str(content_size)
        if (encoding_format := attrs.get("encoding_format")) is not None:
            document["encodingFormat"] = encoding_format

    if node_type == "activity":
        if (started := _as_isoformat(_first_present(attrs, "executed_at", "created_at"))) is not None:
            document["startedAtTime"] = started
        if (ended := _as_isoformat(_first_present(attrs, "completed_at", "last_seen"))) is not None:
            document["endedAtTime"] = ended
        if (software_version := _first_present(attrs, "code_version", "server_version")) is not None:
            document["softwareVersion"] = software_version
        for attr_name, jsonld_key in _ACTIVITY_FIELD_MAP.items():
            value = attrs.get(attr_name)
            if value is None:
                continue
            if attr_name == "dependencies":
                document[jsonld_key] = json.dumps(value, sort_keys=True)
            else:
                document[jsonld_key] = value

    if node_type == "software_agent":
        if (software_version := attrs.get("server_version")) is not None:
            document["softwareVersion"] = software_version

    return document


def export_graph_jsonld(graph: nx.Graph, *, inline_context: bool = True) -> dict[str, Any]:
    """Serialize a NetworkX graph into a JSON-LD document."""
    documents: dict[str, dict[str, Any]] = {}

    for node_id, attrs in graph.nodes(data=True):
        node_type = _infer_node_type(str(node_id), attrs)
        documents[str(node_id)] = _base_document(str(node_id), node_type, attrs)

    for source, target, attrs in graph.edges(data=True):
        source_key = str(source)
        target_key = str(target)
        relation = attrs.get("relation")
        if relation is None:
            continue
        source_doc = documents[source_key]
        target_doc = documents[target_key]
        source_iri = source_doc["@id"]
        target_iri = target_doc["@id"]

        if relation in {"uses_notebook", "contains", "visited", "tracked", "discovered"}:
            _append_ref(source_doc, "hadMember", target_iri)
            _append_ref(target_doc, "isPartOf", source_iri)
        elif relation == "contains_artifact":
            _append_ref(target_doc, "isPartOf", source_iri)
        elif relation == "evidence_from":
            _append_ref(target_doc, "wasDerivedFrom", source_iri)
        elif relation == "was_generated_by":
            _append_ref(source_doc, "wasGeneratedBy", target_iri)
        elif relation == "used":
            _append_ref(source_doc, "used", target_iri)
        elif relation == "was_attributed_to":
            _append_ref(source_doc, "wasAttributedTo", target_iri)
        elif relation == "was_associated_with":
            _append_ref(source_doc, "wasAssociatedWith", target_iri)
        elif relation == "was_informed_by":
            _append_ref(source_doc, "wasInformedBy", target_iri)
        else:
            _append_ref(source_doc, "labmcp:relatedTo", target_iri)

    context: str | dict[str, Any] = build_context() if inline_context else CONTEXT_URL
    return {"@context": context, "@graph": list(documents.values())}


def write_graph_jsonld(
    graph: nx.Graph,
    output_path: Path | str,
    *,
    inline_context: bool = True,
    indent: int = 2,
) -> Path:
    """Serialize a graph and write the JSON-LD document to disk."""
    path = Path(output_path)
    document = export_graph_jsonld(graph, inline_context=inline_context)
    path.write_text(json.dumps(document, indent=indent) + "\n", encoding="utf-8")
    return path


def _graph_for_context(context: ProjectContext) -> nx.DiGraph:
    graph = nx.node_link_graph(context.graph_data, edges="links")
    if not graph.has_node(context.id):
        graph.add_node(context.id, type="project")
    project_node = graph.nodes[context.id]
    project_node.setdefault("type", "project")
    project_node.setdefault("label", context.name)
    project_node.setdefault("description", context.description)
    project_node.setdefault("created_at", context.created_at)
    return graph


def export_project_context(context: ProjectContext, *, inline_context: bool = True) -> dict[str, Any]:
    """Serialize one project context into JSON-LD."""
    return export_graph_jsonld(_graph_for_context(context), inline_context=inline_context)


def export_project_jsonld(
    project_id: str,
    *,
    state_dir: Path | str | None = None,
    inline_context: bool = True,
) -> dict[str, Any]:
    """Load one project from state storage and serialize it to JSON-LD."""
    manager = StateManager(storage_dir=state_dir)
    context = manager._state.contexts.get(project_id)
    if context is None:
        raise ValueError(f"Unknown project_id: {project_id}")
    return export_project_context(context, inline_context=inline_context)


def write_project_jsonld(
    project_id: str,
    output_path: Path | str,
    *,
    state_dir: Path | str | None = None,
    inline_context: bool = True,
    indent: int = 2,
) -> Path:
    """Write one serialized project context to disk."""
    document = export_project_jsonld(project_id, state_dir=state_dir, inline_context=inline_context)
    path = Path(output_path)
    path.write_text(json.dumps(document, indent=indent) + "\n", encoding="utf-8")
    return path
