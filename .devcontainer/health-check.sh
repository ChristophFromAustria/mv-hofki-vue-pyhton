#!/usr/bin/env bash
# Session health check — reports MCP server and plugin status at session start
MCP_STATUS=$(claude mcp list 2>&1 | grep -v '^Checking' | grep -v '^$' | grep -v '^claude\.ai' || true)
PLUGIN_STATUS=$(claude plugin list 2>&1 | grep -E '❯|Status:' | paste - - | sed 's/^[[:space:]]*//' || true)
REPORT=$(printf 'MCP Servers:\n%s\n\nPlugins:\n%s' "$MCP_STATUS" "$PLUGIN_STATUS")
jq -n --arg ctx "$REPORT" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$ctx}}'
