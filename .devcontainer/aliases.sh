# Shell aliases — sourced from .bashrc via postCreateCommand
# Edit this file freely; no container rebuild needed.

# General
alias ll='ls -alF'

# Claude Code
alias claude-unsafe='claude --allow-dangerously-skip-permissions'

# Backend server (uvicorn in tmux session "server")
alias server-logs='tmux capture-pane -t server -p -S -500'
alias server-attach='tmux attach -t server'
alias server-restart='tmux send-keys -t server C-c && sleep 1 && tmux send-keys -t server "PYTHONPATH=src/backend uvicorn mv_hofki.api.app:app --host 0.0.0.0 --port 8000 --reload" Enter'

# Frontend watcher (vite build --watch in tmux session "frontend")
alias frontend-logs='tmux capture-pane -t frontend -p -S -500'
alias frontend-attach='tmux attach -t frontend'
alias frontend-restart='tmux send-keys -t frontend C-c && sleep 1 && tmux send-keys -t frontend "cd src/frontend && VITE_BASE_PATH=\${VITE_BASE_PATH:-/} npx vite build --watch" Enter'

# MCP keepalive proxy (not active by default — use setup-mcp-proxy.sh to configure)
WORKSPACE="$(pwd)"
alias mcp-proxy-start='node "$WORKSPACE/.devcontainer/mcp-keepalive-proxy.js" &>/home/vscode/mcp-proxy.log & echo "MCP proxy started (PID: $!)"'
alias mcp-proxy-stop='pkill -f mcp-keepalive-proxy.js 2>/dev/null && echo "MCP proxy stopped" || echo "MCP proxy not running"'
alias mcp-proxy-status='pgrep -f mcp-keepalive-proxy.js &>/dev/null && echo "MCP proxy running (PID: $(pgrep -f mcp-keepalive-proxy.js))" || echo "MCP proxy not running"'
alias mcp-proxy-logs='cat /home/vscode/mcp-proxy.log 2>/dev/null || echo "No log file"'
