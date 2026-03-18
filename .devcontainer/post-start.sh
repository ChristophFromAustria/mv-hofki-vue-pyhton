#!/usr/bin/env bash
# Runs on every container start.
set -euo pipefail

WORKSPACE="$(pwd)"

# Start backend server in tmux
tmux new-session -d -s server \
  "cd $WORKSPACE && PYTHONPATH=src/backend uvicorn mv_hofki.api.app:app --host 0.0.0.0 --port 8000 --reload"

# Start frontend watcher in tmux
tmux new-session -d -s frontend \
  "cd $WORKSPACE/src/frontend && VITE_BASE_PATH=${VITE_BASE_PATH:-/} npx vite build --watch"
