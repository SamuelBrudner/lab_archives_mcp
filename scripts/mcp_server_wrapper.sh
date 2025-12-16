#!/bin/bash
# Wrapper script for debugging MCP server startup in Windsurf

LOG_FILE="/tmp/labarchives_mcp_debug.log"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${LABARCHIVES_REPO_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
CONDA_ENV_NAME="${LABARCHIVES_CONDA_ENV:-labarchives-mcp-pol}"

{
    echo "=== MCP Server Start: $(date) ==="
    echo "Working directory: $(pwd)"
    echo "Changing to: $REPO_DIR"
    cd "$REPO_DIR" || exit 1
    echo "New working directory: $(pwd)"
    echo "Environment variables (names only):"
    if env | grep -q '^LABARCHIVES_'; then
        env | grep '^LABARCHIVES_' | sed 's/=.*//'
    else
        echo "No LABARCHIVES_* vars set"
    fi
    if env | grep -q '^FASTMCP_'; then
        env | grep '^FASTMCP_' | sed 's/=.*//'
    else
        echo "No FASTMCP_* vars set"
    fi
    echo "==="

    # Run the server
    # Redirect stderr to filter out banner, but keep real errors
    conda run --no-capture-output -n "$CONDA_ENV_NAME" python -m labarchives_mcp 2>&1 | grep -v "FastMCP\|Transport:\|Docs:\|Deploy:\|MCP SDK\|Server name:" || true

} | tee -a "$LOG_FILE"
