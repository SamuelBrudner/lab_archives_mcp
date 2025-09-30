# Changelog

All notable changes to the LabArchives MCP Server project.

## [Unreleased]

### Added - Page Reading Functionality (2025-09-30)

**New MCP Tools**:
- `list_notebook_pages(notebook_id)` - List pages and folders in a notebook
- `read_notebook_page(notebook_id, page_id)` - Read entries from a specific page

**Implementation**:
- Added `get_notebook_tree()` method to `LabArchivesClient` for navigating notebook structure
- Added `get_page_entries()` method to fetch entries with content from pages
- Comprehensive logging throughout the stack for debugging
- 5 unit tests covering tree navigation and entry reading
- Documentation with schemas and example workflows

**Bug Fixes**:
- Fixed XML parsing: LabArchives uses `<level-node>` not `<node>` elements
- Fixed module entry point: use `python -m labarchives_mcp` not `python -m labarchives_mcp.mcp_server`
- Added FastMCP banner suppression via `FASTMCP_SHOW_CLI_BANNER=false`
- Added `--no-capture-output` flag for conda to fix stdio issues

**Configuration**:
- Updated Windsurf config to use `LABARCHIVES_CONFIG_PATH` env var
- Verified working in Windsurf with real notebooks

### Initial Release (2025-09-30)

**Core Functionality**:
- HMAC-SHA512 authentication with LabArchives API
- `list_labarchives_notebooks()` tool - lists all user notebooks
- Resource: `labarchives://notebooks` - MCP resource for notebook metadata
- Fail-fast error handling with structured fault translation
- Async/await throughout with `httpx.AsyncClient`

**Development Setup**:
- Conda environment with locked dependencies
- Pre-commit hooks: Ruff, Black, isort, mypy, interrogate
- TDD with pytest + pytest-asyncio
- Loguru for structured logging

**Documentation**:
- Complete README with setup instructions
- API documentation from LabArchives
- Quickstart guide
- Windsurf and Claude Desktop configuration examples

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

## Next Steps

**High-Impact Features**:
1. Folder navigation (pass `folder_id` to `list_notebook_pages`)
2. Entry content search (requires vector store for semantic queries)
3. Attachment downloads (`entries:entry_attachment`)
4. Recent modifications (`search_tools:modified_since`)

**Infrastructure**:
- Log file rotation and retention policy
- Better error messages for common failures
- Caching for notebook tree (reduce API calls)
- Rate limiting / backoff for API compliance
