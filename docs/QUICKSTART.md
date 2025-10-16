# Quick Start — LabArchives MCP Server

## Run the Server

```bash
# Activate environment
conda activate ./conda_envs/labarchives-mcp-pol

# Start server (stdio mode)
python -m labarchives_mcp

# Or use console script
labarchives-mcp
```

## Agent Configuration

See `docs/agent_configuration.md` for configuration examples for Claude Desktop, Windsurf, and generic MCP clients (including environment configuration and restart tips).

## Verify Setup

```bash
# Test vector backend end-to-end
python scripts/test_e2e_workflow.py

# Check credentials
cat conf/secrets.yml
```

## Available Tools

- **`onboard()`** — Return structured lab overview, usage guidance, and sticky context
- **`decide_labarchives_usage(prompt)`** — Heuristic check for LabArchives relevance
- **`list_labarchives_notebooks()`** — List all notebooks for the authenticated user
- **`list_notebook_pages(notebook_id, folder_id?)`** — Navigate notebook hierarchy
- **`read_notebook_page(notebook_id, page_id)`** — Fetch full page entries with metadata
- **`peek_page(notebook_id, page_id)`** — Lightweight summary of a page
- **`summarize_page(notebook_id, page_id)`** — Generate condensed bullet/timeline summary
- **`semantic_search(query, limit=5, filters=None)`** — Filterable vector search across notebooks
- **`sync_vector_index(...)`** — Plan or run embedding/index updates
- **`upload_to_labarchives(...)`** — Upload files with provenance metadata

**Resource**: `labarchives://notebooks` (same as list_labarchives_notebooks tool)

> **Workflow tip:** Run `bd onboard` once per repo checkout, then call `onboard()` and persist the `sticky_context` block in your agent session before executing other tools.

## Indexing & Sync

- Searches use the existing index; nothing is indexed implicitly during a search.
- To index or refresh, call the MCP tool from your agent:

  ```json
  sync_vector_index {"force": false, "dry_run": true, "max_age_hours": 24}
  ```

  - `dry_run=true` returns the plan (`skip` | `incremental` | `rebuild`) without changes
  - When `max_age_hours` is set and the last build is older, `incremental` processing is chosen
  - `force=true` performs a rebuild regardless of the prior record
  - To actually index, provide a notebook scope: `notebook_id="<nbid>"`
    - Incremental: indexes only changed entries on that notebook's pages
    - Rebuild: re-indexes all entries on that notebook's pages

- Configuration lives at `conf/vector_search/default.yaml` and the persisted build record path is
  `incremental_updates.last_indexed_file`. See `README_VECTOR_BACKEND.md` for details.

## Troubleshooting

### Server won't start

- Check `conf/secrets.yml` exists with valid credentials
- Ensure conda environment is activated
- Run `python scripts/test_e2e_workflow.py` to diagnose

### Claude Desktop can't connect

- Verify the config file path is correct
- Check Claude Desktop logs: `~/Library/Logs/Claude/mcp*.log`
- Test server manually: `python -m labarchives_mcp`

### Authentication errors

- Verify `LABARCHIVES_UID` in `conf/secrets.yml`
- Re-run `scripts/resolve_uid.py` if UID is stale

## Documentation

- **Full setup**: [README.md](README.md)
- **Agent configuration**: [docs/agent_configuration.md](docs/agent_configuration.md)
- **API docs**: [docs/api_docs.txt](docs/api_docs.txt)
