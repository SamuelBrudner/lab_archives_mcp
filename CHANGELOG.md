# Changelog

All notable changes to the LabArchives MCP Server project.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## v0.5.1 (2026-05-27)

### Docs

- jors: correct `tools/` subpackage module count claim from twelve to thirteen (six tool-category modules plus seven shared-infrastructure modules) in cover letter, response, and changelog
- jors: fix stale test path `tests/spec/test_search_page_limit.py` → `tests/contract/test_search_page_limit.py` in metapaper §3
- jors: substitute v0.5.1 Zenodo version DOI across metapaper §4, cover letter, response R3.1, README citation policy, README BibTeX, CITATION.cff, and codemeta.json

### Note

This patch release exists so that the Zenodo archive reviewers download
matches the final submitted documents. The v0.5.0 archive
(DOI 10.5281/zenodo.20421239) was deposited before the final-review
doc fixes landed and is retained for traceability.

## v0.5.0 (2026-05-27)

### Feat

- refactor: decompose 823-line `StateManager` god object into `state/` subpackage with six focused services (`ProjectService`, `KnowledgeGraph`, `ProvenanceService`, `GraphValidationService`, `StateRepository`, `StateManager` facade)
- refactor: split ~1100-line `mcp_server.py` bootstrap into 155-line entry point and `tools/` subpackage with thirteen modules (six tool-category modules plus seven shared-infrastructure modules)
- refactor: introduce `VectorIndex` as a `typing.Protocol` enabling swappable backends without inheritance
- refactor: add `TypedDict` definitions for tool responses throughout the tool layer
- refactor: make `AuthenticationManager.build_auth_params()` part of the public API
- benchmark: add `scripts/benchmark_internal.py` reporting median and p95 in-process latencies

### Docs

- jors: restructure Section 1 into §1.1 Motivation and objectives (O1–O3) and §1.2 Related work (five new peer-reviewed citations)
- jors: add architecture diagram (`docs/figures/architecture.{mmd,svg,png}`) rendered in manuscript Figure 1
- jors: update §3 benchmark to median (p95) latencies; update §4 Availability to three-DOI citation policy with v0.5.0 as JORS resubmission archive
- jors: add engineering improvements preamble and update R1.8 and R3.1 in response document
- jors: rewrite cover letter with structured paragraphs covering Section 1 changes, engineering improvements, updated QC numbers, and three-DOI policy
- citation: update README BibTeX to `brudner2026labarchives` (year 2026, version 0.5.0); update `CITATION.cff` preferred-citation to year 2026 / version 0.5.0
- audit: fix 23 documentation consistency issues identified across README, metapaper, and configuration files

## v0.4.0 (2026-04-20)

### Feat

- provenance: record upload activities, artifacts, users, and software agents in the project graph
- linked-data: add PROV-O / JSON-LD export through the MCP server and CLI

### Docs

- add linked-data export design notes and README / quickstart usage examples
- add `codemeta.json` alongside the existing citation metadata

### Test

- add serializer, state, MCP, and CLI parity coverage for linked-data export

## v0.3.3 (2025-12-16)

### Fix

- auth: strengthen secrets file resolution to avoid startup failures across working directories

### Docs

- scripts: sanitize helper scripts by removing hard-coded user paths and avoiding logging secret values
- citation: note that the JORS archival citation remains the `v0.3.2` Zenodo
  snapshot at <https://doi.org/10.5281/zenodo.17772522>; `v0.3.3` is a
  post-archive maintenance release

### Chore

- release: bump package version to 0.3.3

## v0.2.4 (2025-10-15)

### Docs

- Consolidate agent configuration into a single canonical guide; link from README and Quickstart
- Unify vector backend license language to MIT and remove placeholder owner fields
- Fix code-fence closers and language tags across README and vector backend docs
- Replace missing/broken references (e.g., test_baseline.py → test_e2e_workflow.py, PHASE1_COMPLETE.md → README_VECTOR_BACKEND.md)
- Standardize example owner names and placeholder paths in example configs

## v0.2.3 (2025-10-07)

### Feat

- mcp: implement `sync_vector_index` execution for incremental and rebuild paths (requires `notebook_id` scope). Incremental indexes only changed entries since the last build; rebuild re-indexes all pages for the notebook.

### Test

- spec: add execution tests for incremental and rebuild sync flows (`tests/spec/test_mcp_sync_execution.py`)

### Docs

- clarify `sync_vector_index` usage in docs/QUICKSTART.md and README_VECTOR_BACKEND.md (execution requires `notebook_id`)

## v0.2.2 (2025-10-07)

### Fix

- embedding: replace OpenAI SDK usage with direct HTTP via httpx to avoid `openai` import/package conflicts and stabilize tests (respx-mocked)

## v0.2.1 (2025-10-06)

### Feat

- promote BuildRecord into shared semantic models (`vector_backend.models.BuildRecord`)
- add unit tests for build-state (fingerprint, persistence, rebuild logic)

### Test

- load `conf/secrets.yml` automatically during tests and set `DVC_SITE_CACHE_DIR` for reliable DVC integration tests on macOS

### Docs

- reference BuildRecord location in README_VECTOR_BACKEND

## [0.1.0] - 2025-10-01

### Added

**Core MCP Tools**:

- `list_labarchives_notebooks()` - List all user notebooks with metadata
- `list_notebook_pages(notebook_id, folder_id)` - Navigate notebook structure
- `read_notebook_page(notebook_id, page_id)` - Read page entries and content
- `search_labarchives(query, limit)` - Semantic search across notebooks (vector backend)
- `upload_to_labarchives(...)` - Upload files with Git/Python provenance (experimental)

**Authentication & API Client**:

- HMAC-SHA512 request signing for LabArchives API
- OAuth-based UID resolution with temporary token support
- Async HTTP client with proper error handling
- XML→JSON transformation with Pydantic validation

**Vector Search Backend**:

- Semantic search using OpenAI embeddings
- Pinecone vector database integration
- Automatic indexing of notebook content
- CLI tools for index management

**Development Infrastructure**:

- Conda-lock environment with reproducible dependencies
- Pre-commit hooks: Ruff, Black, isort, mypy, interrogate, Commitizen
- Unit and integration test suite
- GitHub Actions CI workflow
- MIT License

**Documentation**:

- Complete installation and setup guide
- Configuration examples for Claude Desktop and Windsurf
- API schemas generated from Pydantic models
- Contributing guidelines
- JOSS paper for academic citation

### Fixed

- XML parsing for LabArchives tree structure (`<level-node>` elements)
- Module entry point for `python -m labarchives_mcp`
- Conda stdio capture issues with `--no-capture-output` flag
- FastMCP banner suppression in production environments

### Changed

- License changed from Proprietary to MIT
- Project description updated to emphasize AI integration use case

## Verified Capabilities

**Tested with Real Data**:
✅ List 4 notebooks from <samuel.brudner@yale.edu> account
✅ Navigate "Mosquito Navigation" notebook structure
✅ Retrieve 6 top-level folders (Protocols, Sample Log, Experiment Data, Presentations, Manuscripts, References)
✅ Full MCP integration with Windsurf agent

**API Coverage**:

- `users:user_access_info` - UID resolution via temp token
- `users:user_info_via_id` - Fetch user notebooks
- `tree_tools:get_tree_level` - Navigate notebook tree
- `tree_tools:get_entries_for_page` - Read page entries

## Architecture

```text
┌─────────────────────────────────────────────┐
│         Windsurf / Claude Desktop           │
│              (MCP Client)                   │
└──────────────────┬──────────────────────────┘
                   │ stdio (MCP protocol)
                   ↓
┌─────────────────────────────────────────────┐
│          labarchives_mcp.mcp_server         │
│  - list_labarchives_notebooks()             │
│  - list_notebook_pages(notebook_id)         │
│  - read_notebook_page(notebook_id, page_id) │
└──────────────────┬──────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────┐
│       labarchives_mcp.eln_client            │
│  - list_notebooks(uid)                      │
│  - get_notebook_tree(uid, nbid, parent_id)  │
│  - get_page_entries(uid, nbid, page_id)     │
└──────────────────┬──────────────────────────┘
                   │ HMAC-SHA512 auth
                   ↓
┌─────────────────────────────────────────────┐
│       LabArchives REST API                  │
│       https://api.labarchives.com           │
└─────────────────────────────────────────────┘
```

## Test Coverage

- **Unit tests**: 5 tests for page reading, all passing
- **Integration**: Verified with live LabArchives API
- **End-to-end**: Tested via Windsurf MCP client

[0.1.0]: https://github.com/SamuelBrudner/lab_archives_mcp/releases/tag/v0.1.0

## v0.2.0 (2025-10-04)

### Feat

- **upload**: page-text uploads with Markdown to HTML and canonical URLs
- add timeouts and health checks to Pinecone index operations
- add conditional DVC test skipping when dvc package not installed
- Add DVC integration and concurrent write safety to LocalPersistence

### Fix

- update test badge URL to force cache refresh
- resolve whitespace and test_exhausted_retries_raises issues
- resolve all remaining linting issues
- correct NotebookIndexer test to use ChunkingConfig
- resolve 12 test failures for cross-platform CI compatibility

### Refactor

- migrate API keys from env vars to conf/secrets.yml
