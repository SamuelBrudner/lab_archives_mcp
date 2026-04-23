"""CLI regression tests for provenance export."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cli.main import _run_cli
from labarchives_mcp import __main__ as package_main
from labarchives_mcp.linked_data import (
    MissingLinkedDataDependencyError,
    export_project_jsonld,
)
from labarchives_mcp.models.upload import ProvenanceMetadata
from labarchives_mcp.state import StateManager


class _FakeLinkedDataWriter:
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self.serialize_format: str | None = None

    def parse(self, *, data: str, format: str) -> _FakeLinkedDataWriter:
        return self

    def serialize(self, *, format: str) -> str:
        self.serialize_format = format
        return f"{self.kind}:{format}"


class _FakeRdflib:
    def Graph(self) -> _FakeLinkedDataWriter:  # noqa: N802 - mirrors rdflib API
        return _FakeLinkedDataWriter("graph")

    def Dataset(self) -> _FakeLinkedDataWriter:  # noqa: N802 - mirrors rdflib API
        return _FakeLinkedDataWriter("dataset")


def _seed_project(tmp_path: Path) -> tuple[StateManager, str]:
    manager = StateManager(storage_dir=tmp_path)
    context = manager.create_project("Proj 1", "Desc")
    manager.log_visit("nb1", "p1", "Page 1")
    metadata = ProvenanceMetadata(
        git_commit_sha="c" * 40,
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
    return manager, context.id


def test_export_provenance_cli_writes_jsonld(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, project_id = _seed_project(tmp_path)
    output = tmp_path / "graph.jsonld"

    exit_code = _run_cli(
        [
            "export-provenance",
            "--project",
            project_id,
            "--output",
            str(output),
            "--state-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    assert output.exists()
    assert capsys.readouterr().out.strip() == str(output)
    assert json.loads(output.read_text()) == export_project_jsonld(project_id, state_dir=tmp_path)


def test_export_provenance_cli_writes_turtle(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, project_id = _seed_project(tmp_path)
    output = tmp_path / "graph.ttl"
    monkeypatch.setattr(
        "labarchives_mcp.linked_data.provo_export._load_rdflib", lambda: _FakeRdflib()
    )

    exit_code = _run_cli(
        [
            "export-provenance",
            "--project",
            project_id,
            "--output",
            str(output),
            "--format",
            "turtle",
            "--state-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    assert output.read_text() == "graph:turtle\n"
    assert capsys.readouterr().out.strip() == str(output)


def test_export_provenance_cli_reports_missing_rdflib(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, project_id = _seed_project(tmp_path)
    output = tmp_path / "graph.nq"

    def _missing_rdflib() -> object:
        raise MissingLinkedDataDependencyError("install linked-data extra")

    monkeypatch.setattr(
        "labarchives_mcp.linked_data.provo_export._load_rdflib",
        _missing_rdflib,
    )

    with pytest.raises(SystemExit) as exc_info:
        _run_cli(
            [
                "export-provenance",
                "--project",
                project_id,
                "--output",
                str(output),
                "--format",
                "n-quads",
                "--state-dir",
                str(tmp_path),
            ]
        )

    assert exc_info.value.code == 1
    assert "install linked-data extra" in capsys.readouterr().err


def test_python_module_entrypoint_routes_to_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, project_id = _seed_project(tmp_path)
    output = tmp_path / "module-graph.jsonld"
    monkeypatch.setattr(
        "sys.argv",
        [
            "python",
            "export-provenance",
            "--project",
            project_id,
            "--output",
            str(output),
            "--state-dir",
            str(tmp_path),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        package_main.main()

    assert exc_info.value.code == 0
    assert json.loads(output.read_text()) == export_project_jsonld(project_id, state_dir=tmp_path)
