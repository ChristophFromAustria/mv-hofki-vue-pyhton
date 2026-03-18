#!/usr/bin/env bash
# Setup script for MCP keepalive proxy.
# Usage: ./setup-mcp-proxy.sh <mcp-name> <remote-url> [auth-header] [port]
#
# Example:
#   ./setup-mcp-proxy.sh mssql-mcp https://admin.mkw.at/mcp/mssql/mcp "Bearer token123"
#
# This script:
# 1. Copies the proxy script to the persistent .claude volume
# 2. Configures Claude Code to use the local proxy instead of the remote URL
# 3. Starts the proxy in the background

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MCP_NAME="${1:?Usage: $0 <mcp-name> <remote-url> [auth-header] [port]}"
REMOTE_URL="${2:?Usage: $0 <mcp-name> <remote-url> [auth-header] [port]}"
AUTH_HEADER="${3:-}"
PROXY_PORT="${4:-9847}"

PROXY_SCRIPT="$SCRIPT_DIR/mcp-keepalive-proxy.js"
PERSISTENT_SCRIPT="/home/vscode/.claude/mcp-keepalive-proxy.js"
LOG_FILE="/home/vscode/mcp-proxy.log"

echo "[setup] MCP keepalive proxy setup"
echo "[setup]   Name:   $MCP_NAME"
echo "[setup]   Remote: $REMOTE_URL"
echo "[setup]   Port:   $PROXY_PORT"

# Copy proxy to persistent volume so it survives container rebuilds
cp "$PROXY_SCRIPT" "$PERSISTENT_SCRIPT"
echo "[setup] Copied proxy script to $PERSISTENT_SCRIPT"

# Kill any existing proxy on the same port
if lsof -ti ":$PROXY_PORT" &>/dev/null; then
  echo "[setup] Killing existing proxy on port $PROXY_PORT"
  kill $(lsof -ti ":$PROXY_PORT") 2>/dev/null || true
  sleep 1
fi

# Start the proxy
MCP_REMOTE_URL="$REMOTE_URL" \
MCP_AUTH_HEADER="$AUTH_HEADER" \
MCP_PROXY_PORT="$PROXY_PORT" \
  node "$PERSISTENT_SCRIPT" &>"$LOG_FILE" &

echo "[setup] Proxy started (PID: $!), log: $LOG_FILE"

# Wait for proxy to be ready
sleep 2
if ! lsof -ti ":$PROXY_PORT" &>/dev/null; then
  echo "[setup] ERROR: Proxy failed to start. Check $LOG_FILE"
  cat "$LOG_FILE"
  exit 1
fi

# Configure Claude MCP to point at the proxy
claude mcp remove "$MCP_NAME" 2>/dev/null || true
claude mcp add --transport http "$MCP_NAME" "http://127.0.0.1:$PROXY_PORT"
echo "[setup] Claude MCP '$MCP_NAME' configured -> http://127.0.0.1:$PROXY_PORT"
echo "[setup] Done. Run /mcp in Claude to reconnect."
