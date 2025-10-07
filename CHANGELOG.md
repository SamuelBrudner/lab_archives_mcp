# Changelog

All notable changes to the LabArchives MCP Server project.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

## [0.1.0] - 2025-09-30

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
- Comprehensive test suite (unit + integration)
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
✅ List 4 notebooks from samuel.brudner@yale.edu account
✅ Navigate "Mosquito Navigation" notebook structure
✅ Retrieve 6 top-level folders (Protocols, Sample Log, Experiment Data, Presentations, Manuscripts, References)
✅ Full MCP integration with Windsurf agent

**API Coverage**:
- `users:user_access_info` - UID resolution via temp token
- `users:user_info_via_id` - Fetch user notebooks
- `tree_tools:get_tree_level` - Navigate notebook tree
- `tree_tools:get_entries_for_page` - Read page entries

## Architecture

```
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

## v0.1.0 (2025-10-01)

### Feat

- add semantic search MCP tool
- add parent-child retrieval for full page content
- complete LabArchives semantic search pipeline
- add LabArchives indexer with TDD (24 tests passing)
- implement vector backend for semantic search with TDD (Phase 1)
- **mcp**: add upload_to_labarchives MCP tool with provenance metadata
- **upload**: implement insert_node, add_attachment, add_entry, and upload_to_labarchives methods
- **upload**: add mandatory ProvenanceMetadata for code/notebook reproducibility
- add folder navigation to list_notebook_pages with folder_id parameter
- add comprehensive logging to page reading tools for debugging
- add page-level reading tools (list_notebook_pages, read_notebook_page)
- add list_labarchives_notebooks tool for better MCP client discovery
- add agent connectivity with console script and configuration guide
- Complete LabArchives API integration with authentication and notebook listing
- add owner metadata and modified_at fields to notebook records
- add authlib and cyclopts dependencies to conda lock file
- implement LabArchives login handshake with HMAC authentication
- implement LabArchives notebook listing with XML parsing and tests
- add pre-commit hooks and switch to config-driven secrets

### Fix

- properly clean HTML in text entries
- use tree_id strings for page_tree_id parameter (consistent with folder navigation)
- use tree_id directly as parent_tree_id for folder navigation (no decoding needed)
- use first number from tree_id as parent_tree_id for folder navigation
- correct folder_id decoding to extract TreeNode ID properly
- correct XPath for notebook tree parsing (level-node vs node)
- wrapper script changes to repo directory before starting server
- move banner disable to import time to prevent stdio interference
- disable FastMCP CLI banner for stdio transport compatibility with Windsurf
- use LABARCHIVES_CONFIG_PATH env var instead of cwd for Windsurf compatibility
- use run_async() instead of non-existent serve() method in FastMCP
- add cwd parameter to Claude Desktop config to locate secrets.yml
- correct module path for MCP server execution (use -m labarchives_mcp)

### Refactor

- simplify XML parsing logic with pattern matching and cleaner conditionals
- Use Pydantic models as single source of truth for API schema
- extract XML parsing into NotebookTransformer class with error handling
- improve test formatting and remove unused notebook name field
- use pathlib.Path instead of pytest.TempPathFactory for test fixtures
