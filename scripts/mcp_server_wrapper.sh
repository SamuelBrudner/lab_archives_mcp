#!/bin/bash
# Wrapper script for debugging MCP server startup in Windsurf

LOG_FILE="/tmp/labarchives_mcp_debug.log"

{
    echo "=== MCP Server Start: $(date) ==="
    echo "Working directory: $(pwd)"
    echo "Environment variables:"
    env | grep LABARCHIVES || echo "No LABARCHIVES_* vars set"
    echo "==="

    # Run the server
    exec conda run -p "/Users/samuelbrudner/Yale University Dropbox/Samuel Brudner/lab_archives_mcp/conda_envs/pol-dev" python -m labarchives_mcp 2>&1

} | tee -a "$LOG_FILE"
