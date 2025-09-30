#!/bin/bash
# Wrapper script for debugging MCP server startup in Windsurf

LOG_FILE="/tmp/labarchives_mcp_debug.log"
REPO_DIR="/Users/samuelbrudner/Yale University Dropbox/Samuel Brudner/lab_archives_mcp"

{
    echo "=== MCP Server Start: $(date) ==="
    echo "Working directory: $(pwd)"
    echo "Changing to: $REPO_DIR"
    cd "$REPO_DIR" || exit 1
    echo "New working directory: $(pwd)"
    echo "Environment variables:"
    env | grep LABARCHIVES || echo "No LABARCHIVES_* vars set"
    env | grep FASTMCP || echo "No FASTMCP_* vars set"
    echo "==="

    # Run the server
    # Redirect stderr to filter out banner, but keep real errors
    conda run -p "$REPO_DIR/conda_envs/pol-dev" python -m labarchives_mcp 2>&1 | grep -v "FastMCP\|Transport:\|Docs:\|Deploy:\|MCP SDK\|Server name:" || true

} | tee -a "$LOG_FILE"
