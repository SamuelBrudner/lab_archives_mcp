# Agent Configuration Guide

This guide explains how to expose the LabArchives MCP server to AI agents.

## Overview

The LabArchives MCP server uses **stdio transport** for communication. This means:

- Agents launch the server as a subprocess
- Communication happens via stdin/stdout
- No network ports or HTTP endpoints needed

---

## Configuration for Claude Desktop

Claude Desktop is the primary client for MCP servers. Add this configuration to your Claude Desktop settings.

### Location

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**Linux**: `~/.config/Claude/claude_desktop_config.json`

### Configuration

```json
{
  "mcpServers": {
    "labarchives": {
      "command": "conda",
      "args": [
        "run",
        "-p",
        "/absolute/path/to/lab_archives_mcp/conda_envs/labarchives-mcp-pol",
        "python",
        "-m",
        "labarchives_mcp"
      ],
      "cwd": "/absolute/path/to/lab_archives_mcp"
    }
  }
}
```

**Important**:

- Replace `/absolute/path/to/lab_archives_mcp` with your actual repository path.
- The `cwd` parameter ensures the server finds `conf/secrets.yml` in the working directory.

### Alternative: Using Python Directly

If you don't want to use conda in the configuration:

```json
{
  "mcpServers": {
    "labarchives": {
      "command": "/absolute/path/to/lab_archives_mcp/conda_envs/labarchives-mcp-pol/bin/python",
      "args": ["-m", "labarchives_mcp"],
      "cwd": "/absolute/path/to/lab_archives_mcp"
    }
  }
}
```

The server will look for `conf/secrets.yml` in the current working directory.

---

## Configuration for Other MCP Clients

### Recommended Session Bootstrap

- Generate onboarding data via the CLI:
  ```bash
  labarchives-mcp --print-onboard json  # or markdown
  ```
- Persist the returned `sticky_context` in your agent memory and include it with every response that references LabArchives content.
- Use `decide_labarchives_usage(prompt)` before expensive operations to confirm that a user request truly needs LabArchives context.

### Generic MCP Client

Any MCP client supporting stdio transport can connect. The server expects:

- **Command**: Python interpreter from the conda environment
- **Args**: `["-m", "labarchives_mcp"]`
- **Working Directory**: Repository root (for `conf/secrets.yml` access)
- **Environment**: Optional `LABARCHIVES_CONFIG_PATH` to override secrets location

### Example: Python MCP SDK

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="python",
    args=["-m", "labarchives_mcp"],
    cwd="/absolute/path/to/lab_archives_mcp",
    env={"PATH": "/absolute/path/to/conda_envs/labarchives-mcp-pol/bin"}
)

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()

        # List available resources
        resources = await session.list_resources()

        # Read notebooks resource
        notebooks = await session.read_resource("labarchives:notebooks")
        print(notebooks)
```

---

## Available Resources

The server exposes one resource:

### `labarchives:notebooks`

Returns a list of LabArchives notebooks for the authenticated user.

**Response Schema**:

```json
{
  "resource": "labarchives:notebooks",
  "list": [
    {
      "nbid": "MTU2MTI4NS43fDEyMDA5ODkvMTIwMDk4OS9Ob3RlYm9vay81MzgyNzU0MDh8Mzk2MzI2My42OTk5OTk5OTk3",
      "name": "Fly Behavior Study",
      "owner": "owner@example.com",
      "owner_email": "owner@example.com",
      "owner_name": "Example Owner",
      "created_at": "2025-01-01T12:00:00Z",
      "modified_at": "2025-01-02T08:30:00Z"
    }
  ]
}
```

**Error Response**:

```json
{
  "resource": "labarchives:notebooks",
  "error": {
    "code": 4520,
    "message": "Invalid signature",
    "details": "The supplied signature parameter was invalid"
  }
}
```

---

## Verification

### Test Server Manually

Run the server directly to verify it starts:

```bash
cd /path/to/lab_archives_mcp
conda activate ./conda_envs/labarchives-mcp-pol
python -m labarchives_mcp
```

The server will start and wait for MCP protocol messages on stdin. Press `Ctrl+C` to stop.

### Test with MCP Inspector

Use the official MCP Inspector tool:

```bash
npx @modelcontextprotocol/inspector python -m labarchives_mcp
```

This opens a web UI where you can:

- View available resources
- Send requests
- Inspect responses

---

## Troubleshooting

### Server Won't Start

**Error**: `FileNotFoundError: Secrets file not found: conf/secrets.yml`

**Solution**: Ensure you're running from the repository root or set `LABARCHIVES_CONFIG_PATH`:

```bash
export LABARCHIVES_CONFIG_PATH=/absolute/path/to/conf/secrets.yml
```

### Agent Can't Connect

**Symptom**: Claude Desktop shows "MCP server failed to start"

**Checks**:

1. Verify conda environment path is correct
2. Test command manually in terminal
3. Check Claude Desktop logs:
   - macOS: `~/Library/Logs/Claude/mcp*.log`
   - Windows: `%APPDATA%\Claude\logs\mcp*.log`

### Authentication Errors

**Error**: `error: {"code": 4520, "message": "Invalid signature"}`

**Solution**: Verify credentials in `conf/secrets.yml`:

- `LABARCHIVES_AKID` matches your API key
- `LABARCHIVES_PASSWORD` is correct
- `LABARCHIVES_UID` is valid (or use temp token method)

---

## Security Notes

1. **Secrets**: The `conf/secrets.yml` file contains sensitive credentials. Never commit it to version control.

2. **Agent Access**: When an agent connects to this server, it can:
   - Read all notebooks for the authenticated user
   - Upload files to notebooks (if enabled)
   - The agent inherits your LabArchives permissions

3. **Fail-Fast**: The server will refuse to start if credentials are missing or invalid. No silent fallbacks.

4. **Write Capabilities**: The server includes an experimental `upload_to_labarchives` tool that allows AI assistants to upload files with Git provenance metadata. To disable this for production deployments, set the environment variable:

   ```bash
   export LABARCHIVES_ENABLE_UPLOAD=false
   ```

   Add this to your agent configuration:

   ```json
   {
     "mcpServers": {
       "labarchives": {
         "command": "conda",
         "args": ["run", "-p", "/path/to/conda_envs/labarchives-mcp-pol", "python", "-m", "labarchives_mcp"],
         "cwd": "/path/to/lab_archives_mcp",
         "env": {
           "LABARCHIVES_ENABLE_UPLOAD": "false"
         }
       }
     }
   }
   ```

---

## Next Steps

- **Test connection**: Use MCP Inspector to verify the server works
- **Configure agent**: Add server to Claude Desktop config
- **Monitor logs**: Check `logs/` directory for detailed server activity
- **Extend**: See `docs/api_docs.txt` for adding more resources
