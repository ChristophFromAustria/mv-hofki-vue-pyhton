#!/usr/bin/env bash
# Runs once after the container is created (not on every start).
set -euo pipefail

# Mark workspace as safe for git (bind-mount from Windows host)
git config --global --add safe.directory /workspaces/mv_hofki

# Fix git SSL backend — VS Code may forward host's 'schannel' config which doesn't exist on Linux
if git config --global --get-regexp 'http\..*\.sslbackend' 2>/dev/null | grep -q schannel; then
  git config --global --get-regexp 'http\..*\.sslbackend' | grep schannel | while read -r key _; do
    git config --global --unset "$key" 2>/dev/null || true
  done
fi
git config --global http.sslBackend openssl 2>/dev/null || true

# Install Python dev dependencies
pip install -e '.[dev]'

# Install frontend dependencies
cd src/frontend && npm install && cd ../..

# Install E2E test dependencies
cd e2e && npm install && cd ..

# Install pre-commit hooks
pre-commit install

# Install ttyd (web terminal)
if ! command -v ttyd &>/dev/null; then
  sudo curl -sL https://github.com/tsl0922/ttyd/releases/latest/download/ttyd.x86_64 -o /usr/local/bin/ttyd
  sudo chmod +x /usr/local/bin/ttyd
fi
# Source aliases in bashrc (use absolute path since $containerWorkspaceFolder is not a shell variable)
WORKSPACE="$(pwd)"

# Install Claude Code addons globally
sudo npm install -g ccstatusline @modelcontextprotocol/server-sequential-thinking
mkdir -p /home/vscode/.config/ccstatusline
cp "${WORKSPACE}/.devcontainer/ccstatusline-settings.json" /home/vscode/.config/ccstatusline/settings.json

# Register ccstatusline in Claude Code settings (merge into existing settings.json)
CLAUDE_SETTINGS="/home/vscode/.claude/settings.json"
if [ -f "$CLAUDE_SETTINGS" ]; then
  # Add statusLine key if not already present
  if ! grep -q '"statusLine"' "$CLAUDE_SETTINGS"; then
    tmp=$(mktemp)
    jq '. + {"statusLine": {"type": "command", "command": "ccstatusline"}}' "$CLAUDE_SETTINGS" > "$tmp" && mv "$tmp" "$CLAUDE_SETTINGS"
  fi
else
  mkdir -p /home/vscode/.claude
  echo '{"statusLine": {"type": "command", "command": "ccstatusline"}}' > "$CLAUDE_SETTINGS"
fi


if ! grep -q 'aliases.sh' ~/.bashrc 2>/dev/null; then
  echo "[ -f ${WORKSPACE}/.devcontainer/aliases.sh ] && source ${WORKSPACE}/.devcontainer/aliases.sh" >> ~/.bashrc
fi

# Superpowers plugin is enabled via .claude/settings.json (extraKnownMarketplaces + enabledPlugins).
# # No CLI install needed — Claude Code picks it up from project settings on session start.


