#!/bin/bash
# Verify Claude Desktop configuration for LabArchives MCP

set -e

REPO_DIR="/Users/samuelbrudner/Yale University Dropbox/Samuel Brudner/lab_archives_mcp"
CONFIG_FILE="$HOME/Library/Application Support/Claude/claude_desktop_config.json"

echo "🔍 Claude Desktop MCP Configuration Checker"
echo "============================================="
echo

# Check 1: Config file exists
echo "✓ Check 1: Claude Desktop config file"
if [ -f "$CONFIG_FILE" ]; then
    echo "  → Found: $CONFIG_FILE"
else
    echo "  ✗ NOT FOUND: $CONFIG_FILE"
    echo "  → Create it with the MCP server configuration"
    exit 1
fi
echo

# Check 2: Config contains labarchives
echo "✓ Check 2: LabArchives MCP server configured"
if grep -q "labarchives" "$CONFIG_FILE"; then
    echo "  → LabArchives server found in config"
else
    echo "  ✗ LabArchives server NOT configured"
    echo "  → Add the MCP server configuration to $CONFIG_FILE"
    exit 1
fi
echo

# Check 3: Config has cwd parameter
echo "✓ Check 3: Working directory (cwd) configured"
if grep -q '"cwd"' "$CONFIG_FILE"; then
    echo "  → cwd parameter found"
    CWD_PATH=$(grep -A 1 '"cwd"' "$CONFIG_FILE" | tail -1 | sed 's/.*"\(.*\)".*/\1/')
    echo "  → Configured path: $CWD_PATH"

    if [ "$CWD_PATH" = "$REPO_DIR" ]; then
        echo "  → ✓ Path matches repository location"
    else
        echo "  → ⚠ Path mismatch!"
        echo "    Expected: $REPO_DIR"
        echo "    Found: $CWD_PATH"
    fi
else
    echo "  ✗ cwd parameter NOT found in config"
    echo "  → Add 'cwd' parameter to the labarchives server config"
    exit 1
fi
echo

# Check 4: Secrets file exists
echo "✓ Check 4: Secrets file exists"
SECRETS_FILE="$REPO_DIR/conf/secrets.yml"
if [ -f "$SECRETS_FILE" ]; then
    echo "  → Found: $SECRETS_FILE"
else
    echo "  ✗ NOT FOUND: $SECRETS_FILE"
    echo "  → Create it from conf/secrets.example.yml"
    exit 1
fi
echo

# Check 5: Test server can start
echo "✓ Check 5: Test server starts"
cd "$REPO_DIR"
timeout 2 conda run -p ./conda_envs/pol-dev python -m labarchives_mcp 2>&1 >/dev/null &
SERVER_PID=$!
sleep 1

if ps -p $SERVER_PID > /dev/null 2>&1; then
    echo "  → Server started successfully (PID: $SERVER_PID)"
    kill $SERVER_PID 2>/dev/null || true
else
    echo "  ✗ Server failed to start"
    echo "  → Run manually to see error: conda run -p ./conda_envs/pol-dev python -m labarchives_mcp"
    exit 1
fi
echo

echo "✅ All checks passed!"
echo
echo "Your configuration looks correct. Make sure to:"
echo "1. Restart Claude Desktop completely (Cmd+Q, then reopen)"
echo "2. Check Claude Desktop logs if issues persist:"
echo "   ~/Library/Logs/Claude/mcp*.log"
echo

# Show the correct config
echo "Expected configuration in $CONFIG_FILE:"
cat << 'EOF'
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
EOF
