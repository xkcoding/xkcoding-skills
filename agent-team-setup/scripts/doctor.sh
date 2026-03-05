#!/usr/bin/env bash
# Agent Teams environment diagnostic script
# Outputs a JSON report of all dependencies and configurations

set -euo pipefail

# --- Helpers ---

json_bool() {
  if [[ "$1" == "true" ]]; then echo "true"; else echo "false"; fi
}

json_str() {
  # Escape special JSON characters
  local val="${1:-}"
  val="${val//\\/\\\\}"
  val="${val//\"/\\\"}"
  echo "\"$val\""
}

# --- Claude Code ---

claude_code_installed="false"
claude_code_version=""
if command -v claude &>/dev/null; then
  claude_code_installed="true"
  claude_code_version=$(claude --version 2>/dev/null || echo "unknown")
fi

# --- Settings JSON ---

settings_json_path="$HOME/.claude/settings.json"
settings_json_exists="false"
agent_teams_enabled="false"
current_teammate_mode=""

if [[ -f "$settings_json_path" ]]; then
  settings_json_exists="true"

  # Check CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS in settings.json
  if command -v python3 &>/dev/null; then
    agent_teams_flag=$(python3 -c "
import json, sys
try:
    with open('$settings_json_path') as f:
        data = json.load(f)
    val = data.get('env', {}).get('CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS', '')
    print(val)
except:
    print('')
" 2>/dev/null || echo "")

    if [[ "$agent_teams_flag" == "1" ]]; then
      agent_teams_enabled="true"
    fi

    current_teammate_mode=$(python3 -c "
import json
try:
    with open('$settings_json_path') as f:
        data = json.load(f)
    print(data.get('teammateMode', ''))
except:
    print('')
" 2>/dev/null || echo "")
  fi
fi

# Also check environment variable
if [[ "${CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS:-}" == "1" ]]; then
  agent_teams_enabled="true"
fi

# --- tmux ---

tmux_installed="false"
tmux_version=""
if command -v tmux &>/dev/null; then
  tmux_installed="true"
  tmux_version=$(tmux -V 2>/dev/null | head -1 || echo "unknown")
fi

# --- iTerm2 ---

iterm2_running="false"
it2_cli_installed="false"

if [[ "${TERM_PROGRAM:-}" == "iTerm.app" ]]; then
  iterm2_running="true"
fi

if command -v it2 &>/dev/null; then
  it2_cli_installed="true"
fi

# --- Terminal & OS ---

terminal="${TERM_PROGRAM:-unknown}"
os=$(uname -s 2>/dev/null || echo "unknown")
shell=$(basename "${SHELL:-unknown}")

# --- Inside tmux? ---

inside_tmux="false"
if [[ -n "${TMUX:-}" ]]; then
  inside_tmux="true"
fi

# --- Homebrew ---

brew_installed="false"
if command -v brew &>/dev/null; then
  brew_installed="true"
fi

# --- Output JSON ---

cat <<EOF
{
  "claude_code_installed": $(json_bool "$claude_code_installed"),
  "claude_code_version": $(json_str "$claude_code_version"),
  "agent_teams_enabled": $(json_bool "$agent_teams_enabled"),
  "settings_json_path": $(json_str "$settings_json_path"),
  "settings_json_exists": $(json_bool "$settings_json_exists"),
  "current_teammate_mode": $(json_str "$current_teammate_mode"),
  "tmux_installed": $(json_bool "$tmux_installed"),
  "tmux_version": $(json_str "$tmux_version"),
  "iterm2_running": $(json_bool "$iterm2_running"),
  "it2_cli_installed": $(json_bool "$it2_cli_installed"),
  "inside_tmux": $(json_bool "$inside_tmux"),
  "brew_installed": $(json_bool "$brew_installed"),
  "terminal": $(json_str "$terminal"),
  "os": $(json_str "$os"),
  "shell": $(json_str "$shell")
}
EOF
