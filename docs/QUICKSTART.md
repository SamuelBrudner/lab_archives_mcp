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

### Windsurf (Codeium) - ✅ Verified Working

**File**: `~/.codeium/windsurf/mcp_config.json`

```json
{
  "mcpServers": {
    "labarchives": {
      "command": "conda",
      "args": [
        "run",
        "--no-capture-output",
        "-p",
        "/Users/samuelbrudner/Yale University Dropbox/Samuel Brudner/lab_archives_mcp/conda_envs/labarchives-mcp-pol",
        "python",
        "-m",
        "labarchives_mcp"
      ],
      "env": {
        "LABARCHIVES_CONFIG_PATH": "/Users/samuelbrudner/Yale University Dropbox/Samuel Brudner/lab_archives_mcp/conf/secrets.yml",
        "FASTMCP_SHOW_CLI_BANNER": "false",
        "LABARCHIVES_ENABLE_UPLOAD": "true"
      }
    }
  }
}
```

**Setup Steps**:

1. Update both paths to match your repository location
2. Save the file
3. **Completely restart Windsurf** (Cmd+Q → Reopen)
4. Test: Ask "List my LabArchives notebooks"

### Claude Desktop

**File**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "labarchives": {
      "command": "conda",
      "args": [
        "run",
        "-p",
        "/Users/samuelbrudner/Yale University Dropbox/Samuel Brudner/lab_archives_mcp/conda_envs/labarchives-mcp-pol",
        "python",
        "-m",
        "labarchives_mcp"
      ],
      "cwd": "/Users/samuelbrudner/Yale University Dropbox/Samuel Brudner/lab_archives_mcp",
      "env": {
        "LABARCHIVES_CONFIG_PATH": "/Users/samuelbrudner/Yale University Dropbox/Samuel Brudner/lab_archives_mcp/conf/secrets.yml",
        "LABARCHIVES_ENABLE_UPLOAD": "true"
      }
    }
  }
}
```

**Important**: Update the paths to match your system.

## Verify Setup

```bash
# Test baseline functionality
python scripts/test_baseline.py

# Check credentials
cat conf/secrets.yml
```

## Available Tools

- **`list_labarchives_notebooks()`** — List all your notebooks
- **`list_notebook_pages(notebook_id, folder_id?)`** — Navigate notebook pages and folders
- **`read_notebook_page(notebook_id, page_id)`** — Read page content with entries
- **`search_labarchives(query, limit=5)`** — Semantic search across indexed notebooks
- **`upload_to_labarchives(...)`** — Upload files with Git provenance (see README for details)

**Resource**: `labarchives://notebooks` (same as list_labarchives_notebooks tool)

## Indexing & Sync

- Searches use the existing index; nothing is indexed implicitly during a search.
- To index or refresh, call the MCP tool from your agent:

  ```
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
- Run `python scripts/test_baseline.py` to diagnose

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
