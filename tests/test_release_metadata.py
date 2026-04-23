"""Release metadata consistency checks."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import yaml


def test_release_metadata_files_share_version_doi_and_year() -> None:
    """Keep the public release metadata in sync across key entry points."""

    repo_root = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text())
    citation = yaml.safe_load((repo_root / "CITATION.cff").read_text())
    codemeta = json.loads((repo_root / "codemeta.json").read_text())
    readme = (repo_root / "README.md").read_text()

    version = pyproject["project"]["version"]
    release_year = int(citation["date-released"].split("-", maxsplit=1)[0])
    doi = next(
        identifier["value"] for identifier in citation["identifiers"] if identifier["type"] == "doi"
    )
    doi_url = f"https://doi.org/{doi}"

    assert citation["version"] == version
    assert citation["preferred-citation"]["version"] == version
    assert citation["preferred-citation"]["year"] == release_year
    assert citation["preferred-citation"]["doi"] == doi

    assert codemeta["version"] == version
    assert codemeta["identifier"] == doi_url
    assert doi_url in codemeta["relatedLink"]

    assert f"[![DOI](https://zenodo.org/badge/DOI/{doi}.svg)]({doi_url})" in readme
    assert f"year = {{{release_year}}}" in readme
    assert f"doi = {{{doi}}}" in readme
    assert f"url = {{{doi_url}}}" in readme
    assert f"version = {{{version}}}" in readme
