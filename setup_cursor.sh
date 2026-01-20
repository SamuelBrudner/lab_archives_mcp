#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${LABARCHIVES_REPO_DIR:-$SCRIPT_DIR}"
ENV_PREFIX="${LABARCHIVES_CONDA_PREFIX:-$REPO_DIR/conda_envs/labarchives-mcp-pol}"
LOCKFILE="$REPO_DIR/conda-lock.yml"
ENV_YML="$REPO_DIR/environment.yml"
CONFIG_PATH="${CURSOR_MCP_CONFIG:-$HOME/.cursor/mcp.json}"

ensure_env() {
  if [ -x "$ENV_PREFIX/bin/python" ]; then
    return
  fi

  if ! command -v conda >/dev/null 2>&1; then
    echo "conda not found. Install conda to continue."
    exit 1
  fi

  mkdir -p "$(dirname "$ENV_PREFIX")"

  if command -v conda-lock >/dev/null 2>&1 && [ -f "$LOCKFILE" ]; then
    conda-lock install --prefix "$ENV_PREFIX" "$LOCKFILE"
    return
  fi

  if [ -f "$ENV_YML" ]; then
    conda env create -p "$ENV_PREFIX" -f "$ENV_YML"
    return
  fi

  echo "Neither $LOCKFILE nor $ENV_YML found; cannot create environment."
  exit 1
}

install_package() {
  "$ENV_PREFIX/bin/python" -m pip install -e "$REPO_DIR"
}

update_config() {
  mkdir -p "$(dirname "$CONFIG_PATH")"
  "$ENV_PREFIX/bin/python" - "$CONFIG_PATH" "$ENV_PREFIX" "$REPO_DIR" <<'PY'
import json
import os
import sys

config_path, env_prefix, repo_dir = sys.argv[1:4]
config = {"mcpServers": {}}

if os.path.exists(config_path):
    with open(config_path, "r", encoding="utf-8") as handle:
        try:
            config = json.load(handle)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in {config_path}: {exc}") from exc

if not isinstance(config, dict):
    config = {"mcpServers": {}}

servers = config.get("mcpServers")
if not isinstance(servers, dict):
    servers = {}
    config["mcpServers"] = servers

servers["labarchives"] = {
    "command": "conda",
    "args": [
        "run",
        "--no-capture-output",
        "-p",
        env_prefix,
        "python",
        "-m",
        "labarchives_mcp",
    ],
    "cwd": repo_dir,
    "env": {
        "LABARCHIVES_CONFIG_PATH": os.path.join(repo_dir, "conf", "secrets.yml"),
        "FASTMCP_SHOW_CLI_BANNER": "false",
    },
}

with open(config_path, "w", encoding="utf-8") as handle:
    json.dump(config, handle, indent=2)
    handle.write("\n")

print(f"Wrote {config_path}")
PY
}

ensure_env
install_package
update_config

if [ ! -f "$REPO_DIR/conf/secrets.yml" ]; then
  echo "WARNING: $REPO_DIR/conf/secrets.yml not found."
  echo "Create it from conf/secrets.example.yml or set LABARCHIVES_CONFIG_PATH."
fi

echo "Cursor setup complete. Restart Cursor to load the MCP config."
