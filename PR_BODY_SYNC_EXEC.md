# Description

- Implement sync execution in MCP tool `sync_vector_index`:
  - incremental: select only changed entries since last build and index them
  - rebuild: index all entries for the given notebook
  - requires `notebook_id` to perform indexing; otherwise returns the plan only
- Add spec tests for execution flows and update docs

Motivation

- Complete the “build record + sync” story end-to-end: plan → execute
- Avoid re-embedding unchanged content; enable faster refresh cycles
- Provide clear, documented contract for MCP clients

Type of Change

- New feature (non-breaking)
- Test improvement
- Documentation update

Implementation

- `labarchives_mcp.mcp_server.sync_vector_index` now:
  - loads config + prior BuildRecord
  - plans action via `plan_sync`
  - when `notebook_id` is provided, fetches pages and entries
  - performs incremental selection (if applicable)
  - runs `NotebookIndexer.index_page` to embed and upsert
  - persists a new BuildRecord after execution

Testing

- New spec tests: `tests/spec/test_mcp_sync_execution.py`
  - incremental: only changed page indexed, asserts processed_pages and indexed_chunks
  - rebuild: all pages indexed, asserts BuildRecord save is called
- Existing planning + search specs still pass

Checklist

- [x] pre-commit hooks pass
- [x] unit + spec tests pass locally
- [x] docs updated (QUICKSTART, README_VECTOR_BACKEND)
- [x] CHANGELOG updated under [Unreleased]
- [x] Conventional Commits followed

Notes

- Pinecone/Qdrant clients are stubbed in tests; no external calls
- Future enhancement: add CLI wrapper for sync and/or store BuildRecord in index metadata
