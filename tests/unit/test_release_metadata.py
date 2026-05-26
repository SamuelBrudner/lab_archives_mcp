"""Release metadata consistency checks."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import yaml


def test_release_metadata_files_distinguish_source_tree_and_jors_archive() -> None:
    """Keep current release metadata separate from the reviewed JORS archive."""

    repo_root = Path(__file__).resolve().parents[2]
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text())
    citation = yaml.safe_load((repo_root / "CITATION.cff").read_text())
    codemeta = json.loads((repo_root / "codemeta.json").read_text())
    readme = (repo_root / "README.md").read_text()

    version = pyproject["project"]["version"]
    concept_doi = next(
        identifier["value"] for identifier in citation["identifiers"] if identifier["type"] == "doi"
    )
    concept_doi_url = f"https://doi.org/{concept_doi}"
    archived = citation["preferred-citation"]
    archived_doi_url = f"https://doi.org/{archived['doi']}"

    assert citation["version"] == version

    assert codemeta["version"] == version
    assert codemeta["identifier"] == concept_doi_url
    assert concept_doi_url in codemeta["relatedLink"]
    assert archived_doi_url in codemeta["relatedLink"]

    assert archived["version"] == "0.3.2"
    assert archived["year"] == 2025

    assert f"[![DOI](https://zenodo.org/badge/DOI/{concept_doi}.svg)]({concept_doi_url})" in readme
    assert f"Current source tree: `{version}`" in readme
    assert f"year = {{{archived['year']}}}" in readme
    assert f"doi = {{{archived['doi']}}}" in readme
    assert f"url = {{{archived_doi_url}}}" in readme
    assert f"version = {{{archived['version']}}}" in readme
