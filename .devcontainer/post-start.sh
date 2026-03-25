#!/usr/bin/env bash
# Runs on every container start.
set -euo pipefail

WORKSPACE="$(pwd)"

# Enable mouse scrolling in tmux sessions
tmux set -g mouse on 2>/dev/null || true

# Start backend server in tmux
tmux new-session -d -s server \
  "cd $WORKSPACE && PYTHONPATH=src/backend uvicorn mv_hofki.api.app:app --host 0.0.0.0 --port 8000 --reload"

# Start frontend watcher in tmux
tmux new-session -d -s frontend \
  "cd $WORKSPACE/src/frontend && VITE_BASE_PATH=${VITE_BASE_PATH:-/} npx vite build --watch"

# Start web terminal (ttyd) in tmux
if command -v ttyd &>/dev/null; then
  tmux new-session -d -s terminal \
    "ttyd --port 7681 --writable --index $WORKSPACE/.devcontainer/ttyd-index.html -t fontSize=16 -t disableResizeOverlay=true bash"
fi

claude plugin marketplace add obra/superpowers-marketplace
claude plugin install -s local superpowers@superpowers-marketplace

# Register MCP servers in Claude Code (ignore errors if already registered)
claude mcp add sequential-thinking -- mcp-server-sequential-thinking || true
claude mcp add context7 -- npx -y @upstash/context7-mcp || true

