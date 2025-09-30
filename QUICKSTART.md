# Quick Start — LabArchives MCP Server

## Run the Server

```bash
# Activate environment
conda activate ./conda_envs/pol-dev

# Start server (stdio mode)
python -m labarchives_mcp

# Or use console script
labarchives-mcp
```

## Agent Configuration

### Windsurf (Codeium)

**File**: `~/.codeium/windsurf/mcp_config.json`

```json
{
  "mcpServers": {
    "labarchives": {
      "command": "conda",
      "args": [
        "run",
        "-p",
        "/Users/samuelbrudner/Yale University Dropbox/Samuel Brudner/lab_archives_mcp/conda_envs/pol-dev",
        "python",
        "-m",
        "labarchives_mcp"
      ],
      "cwd": "/Users/samuelbrudner/Yale University Dropbox/Samuel Brudner/lab_archives_mcp"
    }
  }
}
```

**Important**: Update the path to match your system.

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
        "/Users/samuelbrudner/Yale University Dropbox/Samuel Brudner/lab_archives_mcp/conda_envs/pol-dev",
        "python",
        "-m",
        "labarchives_mcp"
      ],
      "cwd": "/Users/samuelbrudner/Yale University Dropbox/Samuel Brudner/lab_archives_mcp"
    }
  }
}
```

**Important**: Update the path to match your system.

## Verify Setup

```bash
# Test baseline functionality
python scripts/test_baseline.py

# Check credentials
cat conf/secrets.yml
```

## Available Resource

- **`labarchives:notebooks`** — List all notebooks for authenticated user

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
