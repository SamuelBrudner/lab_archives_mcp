# Changelog

All notable changes to the LabArchives MCP Server project.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

## [Unreleased]

### Planned Features
- Attachment download support
- Advanced search filters (date range, author, tags)
- Batch operations for multiple notebooks
- Write operations (create/update entries)
- Caching for notebook tree to reduce API calls
- Rate limiting with automatic backoff

---

## Version History

[0.1.0]: https://github.com/SamuelBrudner/lab_archives_mcp/releases/tag/v0.1.0
