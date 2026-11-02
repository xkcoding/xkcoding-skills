#!/usr/bin/env bash
# dispatch plugin environment diagnostic script
# Outputs a JSON report of the tools and environment a dispatch depends on.
#
# Usage: doctor.sh [--executor codex|pi]   (default codex)
# The same file ships in dispatch/codex and dispatch/pi; only the executor's own checks differ.
#
# Read-only: never installs, logs in, or initializes anything.
# Tools are detected by RUNNING their version command, never by `command -v`:
# a shim can resolve on PATH while the real tool does not run.
# Uses bash builtins only, so it still reports correctly on a minimal PATH.

set -uo pipefail

# Versions the driver documentation was verified against (see verified-facts.md)
VERIFIED_OPENSPEC="1.13.1"
VERIFIED_HERDR="0.9.0"
VERIFIED_CODEX="0.155.0"
VERIFIED_PI="1.4.0"
VERIFIED_PI_GOAL="0.6.1"
SANDBOX_RUNTIME="0.0.26"   # pinned in lane-guard/package.json
NODE_MIN_MAJOR=24          # pi-codex-goal's engines field

executor="codex"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --executor) executor="${2:-}"; shift 2 ;;
    *) printf '{"error":"unknown argument: %s"}\n' "$1"; exit 2 ;;
  esac
done
if [[ "$executor" != "codex" && "$executor" != "pi" ]]; then
  printf '{"error":"--executor must be codex or pi"}\n'
  exit 2
fi
script_dir="${BASH_SOURCE[0]%/*}"

# --- Helpers ---

json_str() {
  # Escape special JSON characters
  local val="${1:-}"
  val="${val//\\/\\\\}"
  val="${val//\"/\\\"}"
  val="${val//$'\n'/ }"
  val="${val//$'\r'/}"
  val="${val//$'\t'/ }"
  printf '"%s"' "$val"
}

first_line() {
  local val="${1:-}"
  printf '%s' "${val%%$'\n'*}"
}

# Run "<tool> <args…>" and emit {"ok":bool,"version":str,"error":str}
probe_tool() {
  local out rc
  out=$("$@" 2>&1)
  rc=$?
  if [[ $rc -eq 0 ]]; then
    printf '{"ok":true,"version":%s,"error":""}' "$(json_str "$(first_line "$out")")"
  else
    printf '{"ok":false,"version":"","error":%s}' "$(json_str "exit $rc: $(first_line "$out")")"
  fi
}

# Run a command for its exit status only
quiet() {
  "$@" >/dev/null 2>&1
}

bool() {
  if "$@"; then printf 'true'; else printf 'false'; fi
}

# Like probe_tool, but also fails when the major version is below $1
probe_min_major() {
  local min="$1"; shift
  local res ver major
  res=$(probe_tool "$@")
  if [[ "$res" == '{"ok":true'* ]]; then
    ver=${res#*\"version\":\"}; ver=${ver%%\"*}
    major=${ver#v}; major=${major%%.*}
    if [[ "$major" =~ ^[0-9]+$ ]] && (( major < min )); then
      res=$(printf '{"ok":false,"version":%s,"error":%s}' "$(json_str "$ver")" \
        "$(json_str "$ver is older than the required major version $min")")
    fi
  fi
  printf '%s' "$res"
}

# The sandbox dependency of the pi lane-guard, installed into this skill directory by setup
probe_sandbox_runtime() {
  local pkg="$script_dir/lane-guard/node_modules/@anthropic-ai/sandbox-runtime/package.json"
  local line ver=""
  if [[ ! -f "$pkg" ]]; then
    printf '{"ok":false,"version":"","error":%s}' "$(json_str "not installed in $script_dir/lane-guard")"
    return
  fi
  while IFS= read -r line; do
    if [[ "$line" =~ \"version\":[[:space:]]*\"([^\"]+)\" ]]; then ver="${BASH_REMATCH[1]}"; break; fi
  done < "$pkg"
  if [[ "$ver" == "$SANDBOX_RUNTIME" ]]; then
    printf '{"ok":true,"version":%s,"error":""}' "$(json_str "$ver")"
  else
    printf '{"ok":false,"version":%s,"error":%s}' "$(json_str "$ver")" "$(json_str "expected $SANDBOX_RUNTIME")"
  fi
}

# --- Tools (required: openspec herdr git jq python3 + the executor's own; optional: gh, glab) ---
# gh / glab only matter for opening the review request; pushing a verified lane needs neither.

t_openspec=$(probe_tool openspec --version)
t_herdr=$(probe_tool herdr --version)
t_git=$(probe_tool git --version)
t_jq=$(probe_tool jq --version)
t_python3=$(probe_tool python3 --version)
t_gh=$(probe_tool gh --version)
t_glab=$(probe_tool glab --version)

gh_authenticated=$(bool quiet gh auth status)

# --- The executor (status only; never log in, never print a credential) ---

if [[ "$executor" == "codex" ]]; then
  t_codex=$(probe_tool codex --version)
  codex_logged_in=$(bool quiet codex login status)
else
  t_pi=$(probe_tool pi --version)
  t_node=$(probe_min_major "$NODE_MIN_MAJOR" node --version)
  t_rg=$(probe_tool rg --version)
  t_sandbox=$(probe_sandbox_runtime)
  linux="false"
  if [[ "${OSTYPE:-}" == linux* ]]; then
    linux="true"
    t_bwrap=$(probe_tool bwrap --version)
    t_socat=$(probe_tool socat -V)
  fi
  # pi's default model, and whether pi holds a usable credential for it (no refresh, no output of the key)
  pi_settings="${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}/settings.json"
  pi_provider=""; pi_model=""
  if [[ -f "$pi_settings" ]] && quiet jq --version; then
    pi_provider=$(jq -r '.defaultProvider // empty' "$pi_settings" 2>/dev/null)
    pi_model=$(jq -r '.defaultModel // empty' "$pi_settings" 2>/dev/null)
  fi
  pi_model_ready="false"
  if [[ -n "$pi_model" ]]; then
    if [[ -n "$pi_provider" ]]; then
      pi_model_ready=$(bool quiet pi auth check --provider "$pi_provider" --model "$pi_model" --json --no-refresh)
    else
      pi_model_ready=$(bool quiet pi auth check --model "$pi_model" --json --no-refresh)
    fi
  fi
fi

# --- herdr pane ---

in_herdr_pane="false"
if [[ "${HERDR_ENV:-}" == "1" && -n "${HERDR_PANE_ID:-}" ]] && quiet herdr agent list; then
  in_herdr_pane="true"
fi

# --- Repository ---

is_git_repo="false"
is_main_checkout="false"
repo_root=""
current_branch=""
has_origin="false"
has_openspec_dir="false"
codex_skill_tracked="false"
pi_skill_tracked="false"

if repo_root=$(git rev-parse --show-toplevel 2>/dev/null) && [[ -n "$repo_root" ]]; then
  is_git_repo="true"
  git_dir=$(cd "$repo_root" && cd "$(git rev-parse --git-dir 2>/dev/null)" 2>/dev/null && pwd -P)
  common_dir=$(cd "$repo_root" && cd "$(git rev-parse --git-common-dir 2>/dev/null)" 2>/dev/null && pwd -P)
  if [[ -n "$git_dir" && "$git_dir" == "$common_dir" ]]; then
    is_main_checkout="true"
  fi
  current_branch=$(git -C "$repo_root" branch --show-current 2>/dev/null || true)
  has_origin=$(bool quiet git -C "$repo_root" remote get-url origin)
  if [[ -d "$repo_root/openspec" ]]; then
    has_openspec_dir="true"
  fi
  codex_skill_tracked=$(bool quiet git -C "$repo_root" ls-files --error-unmatch .agents/skills/openspec-apply-change/SKILL.md)
  # pi discovers both its own .pi/skills and the shared .agents/skills
  if [[ "$codex_skill_tracked" == "true" ]] || \
     quiet git -C "$repo_root" ls-files --error-unmatch .pi/skills/openspec-apply-change/SKILL.md; then
    pi_skill_tracked="true"
  fi
else
  repo_root=""
fi

# --- Report ---

j_pane=$(json_str "${HERDR_PANE_ID:-}")
j_root=$(json_str "$repo_root")
j_branch=$(json_str "$current_branch")
j_v_openspec=$(json_str "$VERIFIED_OPENSPEC")
j_v_herdr=$(json_str "$VERIFIED_HERDR")
j_v_codex=$(json_str "$VERIFIED_CODEX")

# printf (a builtin) rather than cat: the report must still print on a minimal PATH
if [[ "$executor" == "codex" ]]; then
printf '%s\n' "{
  \"executor\": \"codex\",
  \"tools\": {
    \"openspec\": $t_openspec,
    \"herdr\": $t_herdr,
    \"codex\": $t_codex,
    \"git\": $t_git,
    \"jq\": $t_jq,
    \"python3\": $t_python3,
    \"gh\": $t_gh,
    \"glab\": $t_glab
  },
  \"required_tools\": [\"openspec\", \"herdr\", \"codex\", \"git\", \"jq\", \"python3\"],
  \"optional_tools\": [\"gh\", \"glab\"],
  \"logins\": {
    \"codex_logged_in\": $codex_logged_in,
    \"gh_authenticated\": $gh_authenticated
  },
  \"env\": {
    \"in_herdr_pane\": $in_herdr_pane,
    \"herdr_pane_id\": $j_pane
  },
  \"repo\": {
    \"is_git_repo\": $is_git_repo,
    \"is_main_checkout\": $is_main_checkout,
    \"root\": $j_root,
    \"current_branch\": $j_branch,
    \"has_origin\": $has_origin,
    \"has_openspec_dir\": $has_openspec_dir,
    \"codex_apply_skill_tracked\": $codex_skill_tracked
  },
  \"verified_against\": {
    \"openspec\": $j_v_openspec,
    \"herdr\": $j_v_herdr,
    \"codex\": $j_v_codex
  }
}"
exit 0
fi

linux_tools=""
linux_required=""
if [[ "$linux" == "true" ]]; then
  linux_tools=",
    \"bwrap\": $t_bwrap,
    \"socat\": $t_socat"
  linux_required=", \"bwrap\", \"socat\""
fi
printf '%s\n' "{
  \"executor\": \"pi\",
  \"tools\": {
    \"openspec\": $t_openspec,
    \"herdr\": $t_herdr,
    \"pi\": $t_pi,
    \"node\": $t_node,
    \"rg\": $t_rg,
    \"sandbox_runtime\": $t_sandbox,
    \"git\": $t_git,
    \"jq\": $t_jq,
    \"python3\": $t_python3,
    \"gh\": $t_gh,
    \"glab\": $t_glab$linux_tools
  },
  \"required_tools\": [\"openspec\", \"herdr\", \"pi\", \"node\", \"rg\", \"sandbox_runtime\", \"git\", \"jq\", \"python3\"$linux_required],
  \"optional_tools\": [\"gh\", \"glab\"],
  \"logins\": {
    \"pi_model\": $(json_str "${pi_provider:+$pi_provider/}$pi_model"),
    \"pi_model_ready\": $pi_model_ready,
    \"gh_authenticated\": $gh_authenticated
  },
  \"env\": {
    \"in_herdr_pane\": $in_herdr_pane,
    \"herdr_pane_id\": $j_pane,
    \"sandbox_platform\": $(json_str "${OSTYPE:-unknown}")
  },
  \"repo\": {
    \"is_git_repo\": $is_git_repo,
    \"is_main_checkout\": $is_main_checkout,
    \"root\": $j_root,
    \"current_branch\": $j_branch,
    \"has_origin\": $has_origin,
    \"has_openspec_dir\": $has_openspec_dir,
    \"pi_apply_skill_tracked\": $pi_skill_tracked
  },
  \"verified_against\": {
    \"openspec\": $j_v_openspec,
    \"herdr\": $j_v_herdr,
    \"pi\": $(json_str "$VERIFIED_PI"),
    \"pi_codex_goal\": $(json_str "$VERIFIED_PI_GOAL"),
    \"sandbox_runtime\": $(json_str "$SANDBOX_RUNTIME"),
    \"node_min_major\": $NODE_MIN_MAJOR
  }
}"
